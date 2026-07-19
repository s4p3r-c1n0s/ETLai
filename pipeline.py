"""Business pipeline definitions — each applies core atoms to specific domain data."""

from logic.atoms import groupby, mock_generate, vlookup
from runners.composite import vlookup_then_groupby
from runners.ops import (
    groupby_religion_pre_process_op,
    mock_generator_pre_process_op,
    vlookup_rollnumber_pre_process_op,
)
from runners.pipeline_factory import build_business_pipeline

vlookup_rollnumber = build_business_pipeline(
    pipeline_name="vlookup_rollnumber",
    atom_module=vlookup,
    atom_label="VLOOKUP by Roll Number",
    pre_process_op=vlookup_rollnumber_pre_process_op,
)

groupby_religion = build_business_pipeline(
    pipeline_name="groupby_religion",
    atom_module=groupby,
    atom_label="GroupBy Religion",
    pre_process_op=groupby_religion_pre_process_op,
)

mock_generator = build_business_pipeline(
    pipeline_name="mock_generator",
    atom_module=mock_generate,
    atom_label="Mock Data Generator",
    pre_process_op=mock_generator_pre_process_op,
)
