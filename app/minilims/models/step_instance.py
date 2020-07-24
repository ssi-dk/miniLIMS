import datetime
from pymongo.operations import IndexModel
from bson.objectid import ObjectId
from pymodm import MongoModel, fields, EmbeddedMongoModel, files
from flask import current_app, url_for


from minilims.models.user import User
from minilims.models.step import Step
from minilims.models.sample import Sample
from minilims.models.workflow import Workflow
import minilims.utils.fileutils as fileutils
import minilims.errors


class Step_instance(MongoModel):
    step = fields.ReferenceField(Step, required=True)
    start_date = fields.DateTimeField(required=True, default=datetime.datetime.now())
    finish_date = fields.DateTimeField()
    instrument = fields.CharField(required=True)
    status = fields.CharField(required=True,
                              default="started",
                              choices=("started", "finished", "cancelled"))
    user_started = fields.ReferenceField(User, required=True)
    user_ended = fields.ReferenceField(User)
    comment = fields.CharField()
    # result_input_ = fields.DictField()
    # outputFiles = fields.DictField()
    samples = fields.ListField(fields.ReferenceField(Sample), required=True)
    result_samples = fields.DictField(required=True)
    result_all = fields.DictField(blank=True)
    qc_actions = fields.DictField(blank=True)
    batch = fields.CharField()
    workflow = fields.ReferenceField(Workflow, required=True)

    @staticmethod
    def _clean_param(p):
        return p.replace(".", "_").replace("-", "_")

    @staticmethod
    def invalid_comb(t, s):
        raise ValueError("Invalid param combination: type {}. scope: {}".format(t, s))
    
    @staticmethod
    def invalid_param(s):
        raise ValueError("Invalid param: {}".format(s))

    def _get_result(self, fieldname, barcode=None):
        try:
            if barcode is None:
                return self.result_all[fieldname]
            else:
                return self.result_samples[barcode]
        except KeyError:
            raise minilims.errors.MissingValueError(
                "Value {} for barcode {} not found in results.".format(fieldname, barcode))

    def set_batch(self, batch_list):
        self.batch = batch_list
        self.save()

    def _get_param(self, param_name, scope):
        """
        Parses the param name and gets the value back
        Right now the format is step.field, but can be expanded to workflow.step.field
        """
        fields = param_name.split(".")
        sample_dict = {}
        if len(fields) == 1:
            # Same step
            workflow_name = None
            step_name = None
            field_name = param_name

            if scope == "all":
                for sample in self.samples:
                    sample_dict[sample.barcode] = self._get_result(param_name)
            else:  # "sample"
                for sample in self.samples:
                    sample_dict[sample.barcode] = self._get_result(field_name, sample.barcode)

        elif len(fields) == 2:
            # other step, any workflow
            workflow_name = None
            step_name = fields[0]
            field_name = fields[1]
            
            for sample in self.samples:
                potential_workflows = sample.find_workflow_for_step(step_name)
                if len(potential_workflows) > 1:
                    current_app.logging.warning(
                        ("Sample {} requests data for step {} but more than "
                         "one workflow is available ({}), using the first one").format(
                            sample.barcode, param_name, potential_workflows))
                workflow_name = potential_workflows[0]
                sample_dict[sample.barcode] = sample.find_result(workflow_name, step_name, scope, field_name, self)

        elif len(fields) == 3:
            # other step, other workflow
            workflow_name = fields[0]
            step_name = fields[1]
            field_name = fields[2]

            for sample in self.samples:
                sample_dict[sample.barcode] = sample.find_result(workflow_name, step_name, scope, field_name, self)

        else:
            raise ValueError("Invalid param name. Max 2 '.' allowed. Used to separate workflow.step_name.fieldname")

        return sample_dict

    def _get_params(self, script):
        """
        Get parameters according to the script instructions
        """
        params = {}
        ivs = script.input_values
        for iv in ivs:
            if iv.type_ == "sample_properties":
                if iv.scope == "sample":
                    if iv.name == "batch":
                        params[self._clean_param(iv.name)] = self._get_sample_batch_info()
                    else:
                        self.invalid_comb(iv.type_, iv.scope)
                else:
                    if iv.name == "samples":
                        params[self._clean_param(iv.name)] = self.samples
                    else:
                        self.invalid_comb(iv.type_, iv.scope)
            elif iv.type_ == "user_started":
                if iv.scope == "all":
                    params[self._clean_param(iv.name)] = self.user_started
                else:
                    self.invalid_comb(iv.type_, iv.scope)
            elif iv.type_ == "user_ended":
                if iv.scope == "all":
                    params[self._clean_param(iv.name)] = self.user_ended
                else:
                    self.invalid_comb(iv.type_, iv.scope)
            elif iv.type_ == "file":
                if iv.scope == "all":
                    if iv.name.count(".") != 0:
                        self.invalid_param("Invalid file field name '{}'. Character '.' is only allowed to specify 'step.field', but 'file' values with 'all' scope can only be from the same step.".format(iv.name))
                    else:
                        fileid = self._get_result(iv.name)
                        # params[iv.name] = fileutils.get_file(fileid)
                        params[self._clean_param(iv.name)] = fileid
                else:
                    self.invalid_comb(iv.type_, iv.scope)
            else:
                params[self._clean_param(iv.name)] = self._get_param(iv.name, iv.scope)
            # else:
            #     self.invalid_comb(iv.type_, iv.scope)
        # Much more work to do here.
        return params

    def save_files(self, files):
        for fieldname, fileobject in files.items():
            _id = fileutils.save_file(fieldname, fileobject)
            fieldname = fieldname.replace(".", "_")
            self.result_all[fieldname] = _id

    def delete_files(self, files):
        """
        Reverse save_files
        """
        for fieldname, fileobject in files.items():
            fieldname = fieldname.replace(".", "_")
            _id = self.result_all[fieldname]
            fileutils.delete_file(_id)
            self.result_all.pop(fieldname)

    def save_params(self, params):
        """
        Saves params in step_results.
        
        Expected format for params is a dict with the structure:

        params = {
            "files": {
                "fieldname": fileobject,
                "fieldname2": fileobject2,
            },
            "params": {
                "all": {
                    "fieldname": value1,
                    "fieldname2": value2,
                },
                "samples" : {
                    "barcode1" : {
                        "fieldname1": value1,
                        ...
                    },
                    ...
                }
            }
        }
        """
        if "files" in params:
            self.save_files(params["files"])
        if "params" in params:
            if "all" in params["params"]:
                for fieldname, fieldvalue in params["params"]["all"].items():
                    self.result_all[fieldname] = fieldvalue
            if "samples" in params["params"]:
                for barcode, sampleparams in params["params"]["samples"].items():
                    for fieldname, fieldvalue in params["params"]["samples"][barcode]:
                        self.result_samples[barcode][fieldname] = fieldvalue
        self.save()

    def remove_params(self, params):
        """
        Reverse save_params
        """
        if "files" in params:
            self.save_files(params["files"])
        if "params" in params:
            if "all" in params["params"]:
                for fieldname in params["params"]["all"].keys():
                    self.result_all.pop(fieldname, None)
            if "samples" in params["params"]:
                for barcode in params["params"]["samples"].keys():
                    for fieldname, fieldvalue in params["params"]["samples"][barcode]:
                        self.result_samples[barcode].pop(fieldname, None)
        self.save()

    def run_scripts(self, stage):
        """
        Run all scripts for this step in specified stage.
        """
        for script in self.step.input_output:
            if stage in ("stepstart", "stepend"):
                if script.stage == stage and script.script:
                    params = self._get_params(script)
                    results = self.step.run_script(script, params)
                    print(results)
                    # Right now the "output_values" property from
                    # input_output object is not used
                    # Save "all" results
                    for key, value in results.get("all", {}).items():
                        self.result_all[key] = value
                    # Save "samples" results
                    if "samples" in results:
                        for barcode, sample_result in results["samples"].items():
                            for key, value in sample_result.items():
                                self.result_samples[barcode][key] = value
                    if "qc_actions" in results:
                        self.qc_actions = results["qc_actions"]
            elif stage == "qc" and script.stage == stage:
                self.step.run_qc_script(script, self)
        self.save()

    def qc_actions_msg(self):
        if len(self.qc_actions) == 0:
            return []
        to_steps = {}
        for bc, step in self.qc_actions.items():
            if step in to_steps:
                to_steps[step].append(bc)
            else:
                to_steps[step] = [bc]
        messages = []
        for step, samples in to_steps.items():
            step_o = Step.objects.get({"name": step})
            messages.append("Samples {}: {}".format(", ".join(samples), "Unassigned from workflow. Recommended to send to: {}.".format(step_o.display_name)))
        return "QC issues: " + ".".join(messages)

    def _get_sample_batch_info(self):
        batch_info = {}
        for sample in self.samples:
            for batch in sample.batches:
                if batch.batch_name == self.batch:
                    batch_info[sample.barcode] = batch
        return batch_info

    def qc_reassign_data(self):
        data = {}
        #Only takes one suggested step per step instance
        reassign = list(set(self.qc_actions.values()))
        if len(reassign):

            data["suggested_step"] = reassign[0]
            data["samples"] = list(self.qc_actions.keys())
            data["workflow"] = {
                "name": self.workflow.name,
                "display_name": self.workflow.display_name,
                "plate_types": self.workflow.valid_plate_types
            }
            return data
        else:
            return {}

    def summary_values(self):
        summary = {}
        summary["values_samples"] = {}
        summary["fields_samples"] = []
        summary["values_all"] = []
        for s, v_dict in self.result_samples.items():
            s_dict = {}
            for k, v in v_dict.items():
                if isinstance(v, ObjectId):
                    v_type = "file"
                    v = url_for('lims.getfile', fileid=v)
                else:
                    v_type = "value"
                s_dict[k] = v
                if (k, v_type) not in summary["fields_samples"]:
                    summary["fields_samples"].append((k, v_type))
            summary["values_samples"][s] = s_dict

        for k, v in self.result_all.items():
            if isinstance(v, ObjectId):
                v_type = "file"
                v = url_for('lims.getfile', fileid=v)
            else:
                v_type = "value"
            summary["values_all"].append(
                {"name": k, "value": v, "type": v_type})
        return summary

    def summary(self, values=False):
        """
        Summary generated for finished_step view and step summary view (not done yet)
        """
        summary = {
            "display_name": self.step.display_name,
            "start_date": self.start_date,
            "finish_date": self.finish_date,
            "num_samples": len(self.samples),
            "id": self._id,
            "batch": self.batch,
            "samples": [s.barcode for s in self.samples]
        }
        if values:
            val = self.summary_values()
            summary["values_samples"] = val["values_samples"]
            summary["values_all"] = val["values_all"]
            summary["fields_samples"] = val["fields_samples"]


        return summary
