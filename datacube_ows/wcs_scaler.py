from datacube.utils import geometry
import numpy
import xarray
from affine import Affine

class WCSScalerException(Exception):
    pass

class WCSScalerUnknownDimension(WCSScalerException):
    pass

class WCSScalerOverspecifiedDimension(WCSScalerException):
    pass

class WCSScalarIllegalSize(WCSScalerException):
    pass


class SpatialParameter:
    def __init__(self, layer, crs, x=None, y=None):
        self.layer = layer
        self.crs_def = self.layer.global_cfg.published_CRSs[crs]
        self.x = x
        self.y = y

    def is_x_dim(self, dimension):
        if dimension == self.crs_def['horizontal_coord'].lower():
            return True
        elif dimension == self.crs_def['vertical_coord'].lower():
            return False
        elif dimension == self.layer.native_CRS_def['horizontal_coord'].lower():
            return True
        elif dimension == self.layer.native_CRS_def['vertical_coord'].lower():
            return False
        elif dimension in ("x", "i", "lon", "long", "lng", "longitude"):
            return True
        elif dimension in ("y", "j", "lat", "latitude"):
            return False
        else:
            raise WCSScalerUnknownDimension()

    def __getitem__(self, dim):
        if self.is_x_dim(dim):
            return self.x
        else:
            return self.y

    def __setitem__(self, dim, val):
        if self.is_x_dim(dim):
            self.x = val
        else:
            self.y = val

    def __getattr__(self, dim):
        return self[dim]

    def __setattr__(self, dim, val):
        if dim in ("x", "y", "layer", "crs_def"):
            super().__setattr__(dim, val)
        else:
            try:
                self[dim] = val
            except WCSScalerUnknownDimension:
                super().__setattr__(dim, val)

    def set(self, x, y):
        self.x = x
        self.y = y

class WCSScaler:
    def __init__(self, layer, crs=None):
        self.layer = layer
        self.cfg = self.layer.global_cfg
        if crs:
            self.crs = crs
        else:
            self.crs = self.layer.native_CRS
        self.min = SpatialParameter(self.layer, self.crs)
        self.max = SpatialParameter(self.layer, self.crs)
        self.size = SpatialParameter(self.layer, self.crs)
        self.subsetted = SpatialParameter(self.layer, self.crs, False, False)

    @property
    def crs(self):
        return self._crs

    @crs.setter
    def crs(self, crs):
        self.crs_def = self.layer.global_cfg.published_CRSs[crs]
        self._crs = crs

    def set_size(self, dim, size):
        if size <= 0:
            raise WCSScalarIllegalSize()
        if isinstance(size, float):
            size = int(size + 0.5)
        if self.size[dim] is None:
            self.size[dim] = size
        else:
            raise WCSScalerOverspecifiedDimension()

    def slice(self, dimension, value):
        self.min[dimension] = value
        self.max[dimension] = value

    def is_slice(self, dim):
        return self.subsetted[dim] and self.min[dim] == self.max[dim]

    def dim(self, dim):
        return self.size[dim], self.min[dim], self.max[dim]

    def trim(self, dimension, lower, higher):
        self.min[dimension] = lower
        self.max[dimension] = higher

    def to_crs(self, new_crs):
        grid = self.layer.grids[new_crs]
        if self.crs != new_crs:
            if not self.subsetted.x and not self.subsetted.y:
                # Neither axis subsetted
                self.min.x = self.layer.ranges["bboxes"][new_crs]["left"]
                self.max.x = self.layer.ranges["bboxes"][new_crs]["right"]
                self.min.y = self.layer.ranges["bboxes"][new_crs]["bottom"]
                self.max.y = self.layer.ranges["bboxes"][new_crs]["top"]
                self.crs = new_crs
            elif not self.subsetted.x or not self.subsetted.y:
                # One axis subsetted
                if self.subsetted_x:
                    self.min.y = self.layer.ranges["bboxes"][new_crs]["bottom"]
                    self.max.y = self.layer.ranges["bboxes"][new_crs]["top"]
                if self.subsetted_y:
                    self.min.x = self.layer.ranges["bboxes"][new_crs]["left"]
                    self.max.x = self.layer.ranges["bboxes"][new_crs]["right"]
            else:
                # Both axes subsetted
                pass

        if self.crs != new_crs:
            is_point = False
            # Prepare geometry for transformation
            old_crs_obj = geometry.CRS(self.crs)
            if self.is_slice("x") and self.is_slice("y"):
                geom = geometry.point(self.min.x, self.min.y, old_crs_obj)
                is_point = True
            elif self.is_slice("x") or self.is_slice("y"):
                geom = geometry.line(
                    (
                        (self.min.x, self.min.y),
                        (self.max.x, self.max.y)
                    ), old_crs_obj)
            else:
                geom = geometry.polygon(
                    (
                        (self.min.x, self.min.y),
                        (self.min.x, self.max.y),
                        (self.max.x, self.max.y),
                        (self.max.x, self.min.y),
                        (self.min.x, self.min.y),
                    ),
                    old_crs_obj
                )
            new_crs_obj = geometry.CRS(new_crs)
            grid = self.layer.grids[new_crs]
            if is_point:
                prj_pt = geom.to_crs(new_crs_obj)
                x, y = prj_pt.coords[0]
                self.min.set(x, y)
                self.max.set(x + grid["resolution"][0],
                             y + grid["resolution"][1])
                self.size.set(1, 1)
            else:
                bbox = geom.to_crs(new_crs_obj).boundingbox
                self.min.set(bbox.left, bbox.bottom)
                self.max.set(bbox.right, bbox.top)
                self.quantise_to_resolution(grid)
            self.crs = new_crs
        else:
            self.quantise_to_resolution(grid)

    def quantise_to_resolution(self, grid):
        for idx, dim in enumerate("xy"):
            if self.max[dim] - self.min[dim] < abs(grid["resolution"][idx] * 1.5):
                self.max[dim] = self.min[dim] + grid["resolution"][idx]
                self.size[dim] = 1

    def scale_axis(self, dimension, factor):
        dim_size, dim_min, dim_max = self.dim(dimension)
        if dim_size is not None:
            raise WCSScalerOverspecifiedDimension()
        grid = self.layer.grids[self.crs]
        if self.min.is_x_dim(dimension):
            res = grid["resolution"][0]
        else:
            res = grid["resolution"][1]
        scaled_size = abs(
            ((dim_max - dim_min) * factor / res)
        )
        self.set_size(dimension, scaled_size)

    def scale_size(self, dimension, size):
        self.set_size(dimension, size)

    def scale_extent(self, dimension, low, high):
        # TODO: What is this actually supposed to mean?
        self.set_size(dimension, high - low)

    def affine(self):
        if self.size.x is None:
            self.scale_axis("x", 1.0)
        if self.size.y is None:
            self.scale_axis("y", 1.0)

        x_scale = (self.max.x - self.min.x) / self.size.x
        # Y axis is reversed: image coordinate conventions
        y_scale = (self.min.y - self.max.y) / self.size.y
        trans_aff = Affine.translation(self.min.x, self.max.y)
        scale_aff = Affine.scale(x_scale, y_scale)
        return trans_aff * scale_aff

    def empty_dataset(self, bands, times):
        xvals = numpy.linspace(
            self.min.x,
            self.max.x,
            num = self.size.x
        )
        yvals = numpy.linspace(
            self.min.y,
            self.max.y,
            num = self.size.y
        )
        x_name = self.crs_def["horizontal_coord"],
        y_name = self.crs_def["vertical_coord"],
        if self.crs_def["vertical_coord_first"]:
            nparrays = {
                band: (
                        ("time", y_name, x_name),
                        numpy.full(
                            (len(times), self.size.y, self.size.x),
                            self.layer.nodata_dict[band]
                        )
                )
                for band in bands
            }
        else:
            nparrays = {
                band: (
                    ("time", x_name, y_name),
                    numpy.full(
                        (len(times), self.size.x, self.size.y),
                        self.layer.nodata_dict[band]
                    )
                )
                for band in bands
            }

        return xarray.Dataset(
                nparrays,
                coords={
                    "time": times,
                    x_name: xvals,
                    y_name: yvals,
                }
        ).astype("int16")