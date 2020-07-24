import os
from flask.globals import current_app
from pymongo.operations import IndexModel
from pymodm import MongoModel, fields, EmbeddedMongoModel
from minilims.utils.steploader import Steploader


class S_details(EmbeddedMongoModel):
    description = fields.CharField()


class S_value(EmbeddedMongoModel):
    name = fields.CharField(required=True)
    display_name = fields.CharField(required=True)
    scope = fields.CharField(required=True)  # sample/all
    type_ = fields.CharField(required=True)  # number/text/date/file
    showuser = fields.BooleanField(required=True)
    required = fields.BooleanField(required=False, default=True)


class S_input_output(EmbeddedMongoModel):
    name = fields.CharField(required=True)
    display_name = fields.CharField(required=True)
    stage = fields.CharField(required=True, choices=["stepstart", "stepend"])  # stepstart/stepend
    input_values = fields.EmbeddedDocumentListField(S_value)
    output_values = fields.EmbeddedDocumentListField(S_value)
    script = fields.CharField()


class Step(MongoModel):
    name = fields.CharField(required=True)
    display_name = fields.CharField(required=True)
    category = fields.CharField(required=True)
    version = fields.CharField(required=True)
    details = fields.EmbeddedDocumentField(S_details)
    requirements = fields.DictField()
    input_output = fields.EmbeddedDocumentListField(S_input_output)

    class Meta:
        indexes = [IndexModel([("name", 1)], unique=True)]

    def _sl(self):
        try:
            return getattr(self, '_steploader')
        except AttributeError:
            step_folder = os.path.join(current_app.instance_path, "steps")
            self._steploader = Steploader(step_folder)
            return self._steploader

    def run_script(self, script, params):
        module = self._sl().get_and_load(self.name)
        function = getattr(module, script.script)
        try:
            return function(**params)
        except Exception as e:
            raise e
            # return {
            #     "errors": str(e)
            # }

    def run_qc_script(self, script, step_instance):
        module = self._sl().get_and_load(self.name)
        function = getattr(module, script.script)
        return function(step_instance.samples, step_instance.qc_actions, step_instance)

    def required_params(self):
        """
        Get a dict with the required/expected params when a stepend is submitted.
        Generated from input_output
        """
        expected = {
            "samples": [],
            "all": []
        }
        for io in self.input_output:
            if io.stage == "stepend":
                for value in io.input_values:
                    if value.showuser and value.required:
                        expected[value.scope].append((value.name, value.type_))
        return expected

    def available_samples(self, distinct_batches_only=False):
        from minilims.models.workflow import Workflow
        previous_steps = set()  # Steps that lead directly to this one.
        for w in Workflow.objects.raw({"steps": self._id}):
            index = w.steps.index(self)
            if index == 0:
                previous_steps.add((w._id, "root"))
            else:
                previous_steps.add((w._id, w.steps[index - 1].category))
        from minilims.models.sample import Sample
        samples = list(Sample.objects.raw({"$or": [
            {"batches": {"$elemMatch": {"workflow": x[0],
                                        "step_cat": x[1],
                                        "archived": False}}} for x in previous_steps]}))
        if distinct_batches_only:
            batches = set()
            for sample in samples:
                for batch in sample.batches:
                    for x in previous_steps:
                        if batch.workflow._id == x[0] and batch.step_cat == x[1] and not batch.archived:
                            batches.add("{}: {}".format(batch.workflow.name, batch.batch_name))
            return list(batches)
        else:
            return samples

    def get_started(self):
        """
        Returns list of step instances of this step that are started.
        """
        from minilims.models.step_instance import Step_instance
        return Step_instance.objects.raw({"step": self._id, "status": "started"})

    def summary(self, get_workflows=False):
        info = {
            "name": self.name,
            "display_name": self.display_name,
            "category": self.category,
            "version": self.version,
        }

        if get_workflows:
            from minilims.models.workflow import Workflow
            workflows = Workflow.objects.raw({"steps": self._id}).project({"name": 1, "_id": 0})
            info["workflows"] = [workflow.name for workflow in workflows]

        return info

    def step_instances_summaries(self):
        from minilims.models.step_instance import Step_instance

        step_instance_summaries = []
        for s_i in Step_instance.objects.raw({"step": self._id}):
            step_instance_summaries.append(s_i.summary())

        return step_instance_summaries

    def available_batches(self):
        samples = self.available_samples()
