"""Dagster Definitions entry point — registers all jobs for the instance."""

from dagster import Definitions

from pipeline import vlookup_pipeline

defs = Definitions(jobs=[vlookup_pipeline])
