"""
Pytest unit tests for the sample_ext extension.
These are discovered by pytest (not the run_tests.py harness).
"""


def test_sample_decorator_registered():
    from metaflow.plugins import STEP_DECORATORS

    decorator_names = [d.name for d in STEP_DECORATORS]
    assert "sample_step_decorator" in decorator_names


def test_sample_config_value():
    from metaflow_extensions.sample_ext.config.mfextinit_sample_ext import (
        METAFLOW_SAMPLE_EXT_VALUE,
    )

    assert METAFLOW_SAMPLE_EXT_VALUE == 99


def test_sample_module_value():
    from metaflow_extensions.sample_ext.plugins.sample_module import sample_value

    assert sample_value == 99
