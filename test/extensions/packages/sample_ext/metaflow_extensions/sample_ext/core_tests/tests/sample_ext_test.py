from metaflow_test import MetaflowTest, ExpectationFailed, steps, tag


class SampleExtDecoratorTest(MetaflowTest):
    """
    Test that the sample_ext extension's decorator and config are properly loaded.
    Provided by the sample_ext extension package.
    """

    PRIORITY = 0
    SKIP_GRAPHS = [
        "simple_switch",
        "nested_switch",
        "branch_in_switch",
        "foreach_in_switch",
        "switch_in_branch",
        "switch_in_foreach",
        "recursive_switch",
        "recursive_switch_inside_foreach",
    ]

    @tag("sample_step_decorator")
    @steps(0, ["all"])
    def step_all(self):
        from metaflow.metaflow_config import METAFLOW_SAMPLE_EXT_VALUE
        from metaflow.plugins.sample_module import sample_value

        self.config_value = METAFLOW_SAMPLE_EXT_VALUE
        self.module_value = sample_value

    def check_results(self, flow, checker):
        for step in flow:
            checker.assert_artifact(step.name, "config_value", 99)
            checker.assert_artifact(step.name, "module_value", 99)
            checker.assert_artifact(
                step.name, "sample_ext_value", "sample_%s" % step.name
            )
