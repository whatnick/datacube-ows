from datacube_ows.startup_utils import initialise_ignorable_warnings
from datacube_ows.styles.base import StyleDefBase, StandaloneProductProxy
from datacube_ows.ogc_utils import create_geobox, xarray_image_as_png


initialise_ignorable_warnings()


def StandaloneStyle(cfg):
    """
    Construct a OWS style object that stands alone, independent of a complete OWS configuration environment.

    :param cfg: A valid OWS Style definition configuration dictionary.

        Refer to the documentation for the valid syntax:

        https://datacube-ows.readthedocs.io/en/latest/cfg_styling.html

    :return: A OWS Style Definition object, prepared to work in standalone mode.
    """
    style = StyleDefBase(StandaloneProductProxy(), cfg, stand_alone=True)
    style.make_ready(None)
    return style


def apply_ows_style(style, data, valid_data_mask=None):
    """
    Apply an OWS style to an ODC XArray to generate a styled image.

    :param style: An OWS Style object, as created by StandaloneStyle()
    :param data: An xarray Dataset, as generated by datacube.load_data()
            Note that the Dataset must contain all of the band names referenced by the standalone style
            configuration.  (The names of the data variables in the dataset must exactly match
            the band names in the configuration.  None of the band aliasing techniques normally
            supported by OWS can work in standalone mode.)
            For bands that are used as bitmaps (i.e. either for masking with pq_mask or colour coding
            in value_map), the data_variable must have a valid flag_definition attribute.
    :param valid_data_mask: (optional) An xarray DataArray mask, with dimensions and coordinates matching data.
    :return: An xarray Dataset, with the same dimensions and coordinates as data, and four data_vars of
            8 bit signed integer data named red, green, blue and alpha, representing an 24bit RGBA image.
    """
    return style.transform_data(
            data,
            style.to_mask(
                    data,
                    valid_data_mask
            )
    )


def apply_ows_style_cfg(cfg, data, valid_data_mask=None):
    """
    Apply an OWS style configuration to an ODC XArray to generate a styled image.

    :param cfg: A valid OWS Style definition configuration dictionary.

        Refer to the documentation for the valid syntax:

        https://datacube-ows.readthedocs.io/en/latest/cfg_styling.html
    :param data: An xarray Dataset, as generated by datacube.load_data()
            Note that the Dataset must contain all of the band names referenced by the standalone style
            configuration.  (The names of the data variables in the dataset must exactly match
            the band names in the configuration.  None of the band aliasing techniques normally
            supported by OWS can work in standalone mode.)
            For bands that are used as bitmaps (i.e. either for masking with pq_mask or colour coding
            in value_map), the data_variable must have a valid flag_definition attribute.
    :param valid_data_mask: (optional) An xarray DataArray mask, with dimensions and coordinates matching data.
    :return: An xarray Dataset, with the same dimensions and coordinates as data, and four data_vars of
            8 bit signed integer data named red, green, blue and alpha, representing an 24bit RGBA image.
    """
    return apply_ows_style(
        StandaloneStyle(cfg),
        data,
        valid_data_mask
    )


def generate_ows_legend_style(style, ndates=0):
    """

    :param style: An OWS Style object, as created by StandaloneStyle()
    :param ndates: (optional) Number of dates (for styles with multi-date handlers)
    :return: A PIL Image object.
    """
    return style.render_legend(ndates)


def generate_ows_legend_style_cfg(cfg, ndates=0):
    """

    :param cfg: A valid OWS Style definition configuration dictionary.

        Refer to the documentation for the valid syntax:

        https://datacube-ows.readthedocs.io/en/latest/cfg_styling.html
    :param ndates: (optional) Number of dates (for styles with multi-date handlers)
    :return: A PIL Image object.
    """
    return generate_ows_legend_style(StandaloneStyle(cfg), ndates)
