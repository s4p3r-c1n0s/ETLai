"""Dagster Definitions — registers all business pipelines, composites, and sensors."""

from dagster import Definitions

from pipeline import groupby_religion, mock_generator, vlookup_rollnumber
from runners.composite import vlookup_then_groupby
from sensors.hot_folder_sensor import build_hot_folder_sensor

vlookup_rollnumber_sensor = build_hot_folder_sensor("vlookup_rollnumber", "vlookup_rollnumber", min_files=2)
groupby_religion_sensor = build_hot_folder_sensor("groupby_religion", "groupby_religion", min_files=1)
mock_generator_sensor = build_hot_folder_sensor("mock_generator", "mock_generator", min_files=1)
vlookup_then_groupby_sensor = build_hot_folder_sensor("vlookup_then_groupby", "vlookup_then_groupby", min_files=2, load_files_op_name="vtg__load_files")

defs = Definitions(
    jobs=[vlookup_rollnumber, groupby_religion, mock_generator, vlookup_then_groupby],
    sensors=[
        vlookup_rollnumber_sensor,
        groupby_religion_sensor,
        mock_generator_sensor,
        vlookup_then_groupby_sensor,
    ],
)
