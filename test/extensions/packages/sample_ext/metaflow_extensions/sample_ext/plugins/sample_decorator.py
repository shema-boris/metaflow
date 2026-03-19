from metaflow.decorators import StepDecorator


class SampleStepDecorator(StepDecorator):
    name = "sample_step_decorator"

    def task_post_step(
        self, step_name, flow, graph, retry_count, max_user_code_retries
    ):
        flow.sample_ext_value = "sample_%s" % step_name
