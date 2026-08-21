from __future__ import annotations

import pytest

from seeingbench.datasets.labels import (
    label_coverage_status,
    label_resolution_status,
    label_summary,
    parse_pds_label_text,
)


def test_parse_pds_label_extracts_projection_bounds_resolution_and_image_fields() -> None:
    fields = parse_pds_label_text(
        """
        PDS_VERSION_ID = PDS3
        MAP_PROJECTION_TYPE = "EQUIRECTANGULAR"
        MINIMUM_LATITUDE = 0.0 <DEGREE>
        MAXIMUM_LATITUDE = 60.0 <DEGREE>
        WESTERNMOST_LONGITUDE = 270.0 <DEGREE>
        EASTERNMOST_LONGITUDE = 360.0 <DEGREE>
        MAP_SCALE = 99.75 <METERS/PIXEL>
        MAP_RESOLUTION = 304.0 <PIXELS/DEGREE>
        LINES = 18240
        LINE_SAMPLES = 27360
        SAMPLE_TYPE = LSB_INTEGER
        SAMPLE_BITS = 16
        END
        """
    )

    summary = label_summary(fields)

    assert summary["projection"] == "EQUIRECTANGULAR"
    assert summary["minimum_latitude"] == 0.0
    assert summary["maximum_latitude"] == 60.0
    assert summary["westernmost_longitude"] == 270.0
    assert summary["easternmost_longitude"] == 360.0
    assert summary["map_scale_m_per_px"] == 99.75
    assert summary["map_resolution_px_per_deg"] == 304.0
    assert summary["lines"] == 18240
    assert summary["line_samples"] == 27360
    assert summary["sample_type"] == "LSB_INTEGER"
    assert summary["sample_bits"] == 16


def test_parse_pds4_xml_label_extracts_projection_bounds_resolution_and_image_fields() -> None:
    fields = parse_pds_label_text(
        """<?xml version="1.0" encoding="UTF-8"?>
        <Product_Observational xmlns:cart="http://pds.nasa.gov/pds4/cart/v1">
          <cart:Bounding_Coordinates>
            <cart:west_bounding_coordinate unit="deg">270.0</cart:west_bounding_coordinate>
            <cart:east_bounding_coordinate unit="deg">360.0</cart:east_bounding_coordinate>
            <cart:north_bounding_coordinate unit="deg">60.0</cart:north_bounding_coordinate>
            <cart:south_bounding_coordinate unit="deg">0.0</cart:south_bounding_coordinate>
          </cart:Bounding_Coordinates>
          <cart:map_projection_name>Equirectangular</cart:map_projection_name>
          <cart:pixel_resolution_x unit="deg/pixel">0.003289473684210526</cart:pixel_resolution_x>
          <cart:pixel_scale_x unit="m/pixel">99.747863237334</cart:pixel_scale_x>
          <data_type>IEEE754LSBSingle</data_type>
          <img:sample_bit_mask xmlns:img="http://pds.nasa.gov/pds4/img/v1">
            2#11111111111111111111111111111111
          </img:sample_bit_mask>
          <Axis_Array><axis_name>Line</axis_name><elements>18240</elements></Axis_Array>
          <Axis_Array><axis_name>Sample</axis_name><elements>27360</elements></Axis_Array>
        </Product_Observational>
        """
    )

    summary = label_summary(fields)

    assert summary["projection"] == "Equirectangular"
    assert summary["minimum_latitude"] == 0.0
    assert summary["maximum_latitude"] == 60.0
    assert summary["westernmost_longitude"] == 270.0
    assert summary["easternmost_longitude"] == 360.0
    assert summary["map_scale_m_per_px"] == 99.747863237334
    assert summary["map_resolution_px_per_deg"] == pytest.approx(304.0)
    assert summary["lines"] == 18240
    assert summary["line_samples"] == 27360
    assert summary["sample_type"] == "IEEE754LSBSingle"
    assert summary["sample_bits"] == 32


def test_label_coverage_handles_negative_roi_longitude_against_east_longitudes() -> None:
    fields = parse_pds_label_text(
        """
        MINIMUM_LATITUDE = 0.0
        MAXIMUM_LATITUDE = 60.0
        WESTERNMOST_LONGITUDE = 270.0
        EASTERNMOST_LONGITUDE = 360.0
        """
    )

    assert label_coverage_status(fields, center_lat_deg=9.62, center_lon_deg=-20.08) == "ok"
    assert label_coverage_status(fields, center_lat_deg=-9.62, center_lon_deg=-20.08) == "outside"


def test_label_resolution_reports_coarser_than_target() -> None:
    fields = parse_pds_label_text("MAP_SCALE = 250.0 <METERS/PIXEL>")

    assert label_resolution_status(fields, target_resolution_m_per_px=100.0) == (
        "coarser_than_target"
    )
