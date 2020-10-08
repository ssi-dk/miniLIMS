import os
import datetime
from bson.objectid import ObjectId
from flask import current_app, url_for
import minilims.models.workflow as m_workflow
import minilims.models.step as m_step
import minilims.models.step_instance as m_step_i
import minilims.models.sample as m_sample
import minilims.models.role as m_role
from minilims.utils import expect
import json
from minilims.utils.steploader import Steploader
import pymodm.errors
import pymongo.errors


## Workflow set up

def load_step_object(name, steploader):
    loaded_step = steploader.get_and_load(name)
    return m_step.Step(**loaded_step.step)

def import_steps(steps, steploader=None):
    if steploader is None:
        step_folder = os.path.join(current_app.instance_path, "steps")
        print(current_app.instance_path)
        steploader = Steploader(step_folder)
    step_o_list = [load_step_object(step, steploader)
                       for step in steps]
    try:
        saved = m_step.Step.objects.bulk_create(step_o_list, 
                                                retrieve=True)
        return saved
    except ValueError as e:
        raise e
    except Exception as e:
        print(e)

def import_all_steps():
    step_folder = os.path.join(current_app.instance_path, "steps")
    steploader = Steploader(step_folder)
    steps = steploader.find_steps()
    import_steps(steps, steploader)

def import_workflow(workflow_o):
    """
    Throws error if wrong.
    """
    workflow = workflow_o.copy() # Shallow copy, original untouched
    workflow["steps"] = m_workflow.Workflow.find_steps(workflow["steps"])
    workflow_o = m_workflow.Workflow(**workflow)
    workflow_o.denormalize_steps()
    workflow_o.save()

def init_workflows():
    import os.path
    import_all_steps()
    file_path = os.path.join(current_app.instance_path, "workflows.json")
    if os.path.exists(file_path):
        with open(file_path) as conf_io:
            jsont = json.loads(conf_io.read())
            for w in jsont:
                import_workflow(w)

def init_user_roles():
    """
    Imports user roles from instance path user_roles.json
    """
    import os.path

    file_path = os.path.join(current_app.instance_path, "user_roles.json")
    if os.path.exists(file_path):
        with open(file_path) as conf_io:
            jsont = json.loads(conf_io.read())
            for role, permissions in jsont.items():
                role_o = m_role.Role(name=role, permissions=permissions)
                try:
                    role_o.save()
                except pymongo.errors.DuplicateKeyError:
                    print(f"Role {role} already exists in db. Skipped.")

def init_config():
    init_workflows()
    #init_user_roles()

## Data for templates

def get_workflows_overview(user):
    """
    Returns workflow info for overview. Currently returns all but filtering
    should be added depending on user permissions.
    """
    data = {"workflows": []}
    # Get total and unassigned samples
    if (user.has_permission("samples_see_all")):
        data["samples_total"] = m_sample.Sample.objects.count()
        data["samples_unassigned"] = m_sample.Sample.get_unassigned(count=True)
        data["samples_archived"] = m_sample.Sample.get_archived(count=True)
        data["samples_running"] = m_sample.Sample.objects.raw({"batches.step_cat": {"$ne": "_workflow_finished"}, "batches.0": {"$exists": True} }).count()
    else:
        group = user.group
        group_path = "properties.sample_info.summary.group"
        data["samples_total"] = m_sample.Sample.objects.raw({"properties.sample_info.summary.group": group}).count()
        data["samples_unassigned"] = m_sample.Sample.get_unassigned(count=True, group=group)
        data["samples_archived"] = m_sample.Sample.get_archived(count=True, group=group)
        data["samples_running"] = m_sample.Sample.objects.raw({group_path: group, "batches.step_cat": {"$ne": "_workflow_finished"}, "batches.0": {"$exists": True} }).count()
    
    if user.has_permission("workflows_see_all"):
        # Get workflow info
        started_steps = m_step_i.Step_instance.objects.raw({"status": "started"})
        for wf in m_workflow.Workflow.objects:
            workflow = {
                "name": wf.name,
                "steps": []
            }
            for step in wf.steps:
                started_id = None
                for started in started_steps:
                    if started.step.name == step.name:
                        started_id = str(started._id)
                samples = len(step.available_samples())
                workflow["steps"].append({"name": step.name,
                                          "display_name": step.display_name,
                                          "samples": samples,
                                          "_id": str(step._id),
                                          "started": started_id})
            data["workflows"].append(workflow)
            print('w', workflow)
    return data

def get_batch_overview():

    return {"workflows": list(m_sample.Sample.get_batch_overview())}

def get_step_overview(step_name):
    step_o = m_step.Step.objects.get({"name":step_name})
    step_is = step_o.get_started()
    samples = step_o.available_samples()
    data = {
        "step": step_o.summary(),
        "step_batches": step_o.available_samples(distinct_batches_only=True),
        "available_samples": [s.summary("datatable") for s in samples],
        "started_steps": [{"id":step_i._id,
                           "samples": [s.barcode for s in step_i.samples]}
                           for step_i in step_is]
    }
    return data

# def get_step_samples(step_name, workflow_batch_name):
#     step_o = m_step.Step.objects.get({"name":step_name})


def get_step_started(step_instance_id):
    """
    Provide data for step started template.
    """
    try:
        step_instance = m_step_i.Step_instance.objects.get({"_id": ObjectId(step_instance_id)})
    except pymodm.errors.DoesNotExist:
        return None
    if step_instance.status != "started":
        return None
    step = step_instance.step
    data = {}
    
    data["provided_values"] = []
    data["expected_values"] = []
    data["samples"] = []
    data["step_instance_id"] = step_instance_id
    data["step"] = {"name": step.name, "display_name": step.display_name}
    for io in step_instance.step.input_output:
        # Find expected values
        if io.stage == "stepend":
            for iv in io.input_values:
                if iv.showuser:
                    value = {
                        "name": iv.name,
                        "display_name": iv.display_name,
                        "scope": iv.scope,
                        "type": iv.type_,
                        "required": iv.required
                    }
                    data["expected_values"].append(value)
        # Find provided values
        elif io.stage == "stepstart":
            for ov in io.output_values:
                if ov.showuser:
                    # Need to add: actual value
                    value = {
                        "name": ov.name,
                        "display_name": ov.display_name,
                        "scope": ov.scope,
                        "type": ov.type_
                    }
                    if ov.scope == "all":
                        value_ = step_instance._get_param(ov.name, ov.scope)
                        ## Check if all samples have the same value
                        values_dict = {} # Contains value as key, list of samples as value
                        for s, v in value_.items():
                            if v in values_dict:
                                values_dict[v].append(s)
                            else:
                                values_dict[v] = [s]
                        # TODO: Provide a list to the frontend if multiple keys
                        if len(values_dict.keys()) == 1:
                            value_ = list(values_dict.keys())[0]
                            if value["type"] == "file":
                                # Get value for first sample right now.
                                # fileid = list(value_.values())[0]
                                fileid = value_
                                value_ = url_for('lims.getfile', fileid=fileid)
                            value["value"] = value_
                        else:
                            i = 0
                            value["multivalue"] = []
                            for value_, samples in values_dict.items():
                                multivalue = {}
                                multivalue["samples"] = ", ".join(samples[:10])
                                if len(samples) > 10:
                                    multivalue["samples"] += "... ({} more)".format(str(len(samples) - 10)) 
                                if value["type"] == "file":
                                    # Get value for first sample right now.
                                    # fileid = list(value_.values())[0]
                                    fileid = value_
                                    value_ = url_for('lims.getfile', fileid=fileid)
                                multivalue["value"] = value_
                                multivalue["index"] = i
                                i += 1
                                value["multivalue"].append(multivalue)
                    data["provided_values"].append(value)    

    # Find step samples
    for sample in step_instance.samples:
        data["samples"].append(sample.summary())
    return data

## Step running

def validate_step_start(step_name, json_data):
    # It should also validate if all the samples are ready to start it.
    errors = {}

    missing = expect(json_data, ["sample_barcodes", "workflow_batch"])
    if len(missing):
        errors["missing_parameters"] = "Missing parameters {}".format(",".join(missing))
        return errors

    # Check missing step
    step = None
    try:
        step = m_step.Step.objects.get({"name":step_name})
    except pymodm.errors.DoesNotExist:
        errors["step_name"] = "Step doesn't exist"

    # Check missing samples
    samples = []
    if len(json_data.get("sample_barcodes",[])) == 0:
        errors["sample_barcodes"] = "No samples provided"
    else:
        missing_samples = []
        for s_b in json_data["sample_barcodes"]:
            sample = None
            try:
                sample_o = m_sample.Sample.objects.get({"barcode": s_b})
                samples.append(sample_o)
            except pymodm.errors.DoesNotExist:
                missing_samples.append(s_b)
        if len(missing_samples) > 0:
            e_b = "Missing samples: {}".format(",".join(missing_samples))
            errors["sample_barcodes"] = e_b


        # Check if there are samples that have started this step already
        # (and haven't finished)
        started_is = step.get_started()
        potential_samples = set(json_data["sample_barcodes"])
        for started_i in started_is:
            started_samples = set([s.barcode for s in started_i.samples])
            intersection = potential_samples.intersection(started_samples)
            if len(intersection) > 0:
                errors["already_running"] = "Samples {} are already running this step. Go to that currently running step or cancel it.".format(", ".join(intersection))

    # Check if step is correct.
    workflow_name, batch_name = json_data["workflow_batch"].split(": ")
    if step is not None:
        next_step = step.category
        invalid_step = []
        for sample in samples:
            if not sample.valid_next_step(next_step, batch_name):
                invalid_step.append(sample.barcode)
        if len(invalid_step) > 0:
            e_b = "Invalid next step for samples: {}".format(",".join(invalid_step))
            errors["invalid_step"] = e_b


    return errors

def start_step(step_name, sample_barcodes, workflow_name, batch_name, user):
    """
    Right now this will mean initialise the sample.workflow data,
    and creating the step_instance.
    in the future it will include generating input files.
    """
    step = m_step.Step.objects.get({"name": step_name})
    workflow = m_workflow.Workflow.objects.get({"name": workflow_name})
    instance = m_step_i.Step_instance(
        step=step,
        instrument="Test",
        user_started=user,
        samples=list(m_sample.Sample.objects.raw({"barcode":{ "$in": sample_barcodes}})),
        result_samples={s: {} for s in sample_barcodes},
        result_all={},
        batch=batch_name,
        workflow=workflow
    ).save()
    for s_b in sample_barcodes:
        sample = m_sample.Sample.objects.get({"barcode":s_b})
        batch_name = sample.init_step(instance)  # Returns batch name
    try:
        instance.run_scripts("stepstart")
    except Exception as e:
        step_instance_cancel_start(str(instance._id), "root")
        raise e
    return instance._id

def validate_step_instance_cancel_start(step_instance_id, user):
    """
    Check if step exists and can be cancelled
    """
    errors = {}
    step_instance = m_step_i.Step_instance.objects.get({"_id": ObjectId(step_instance_id)})
    
    if step_instance.status != "started":
        errors["step_instance_status"] = "Step_instance is not in the right status."
    
    return errors, {"step_name": step_instance.step.name}


def step_instance_cancel_start(step_instance_id, user):
    """
    Cancels running step instance start
    """

    step_instance = m_step_i.Step_instance.objects.get({"_id": ObjectId(step_instance_id)})
    step_category = step_instance.step.category

    # Delete results from samples
    for sample in step_instance.samples:
        # Iterate workflows to find the right step
        sample_done = False
        for workflow, steps in sample.workflows.items():
            # Iterate steps
            for step, step_list in steps.items():
                # Iterate step instances
                if step == step_category:
                    for i in range(len(step_list)):
                        if step_list[i].step_instance._id == step_instance._id:
                            # Delete step instance
                            sample.workflows[workflow][step].pop(i)
                            sample.save()
                            sample_done = True
                            break
                if sample_done:
                    break
            if sample_done:
                break
    
    step_instance.status = "cancelled"
    step_instance.save()



def validate_step_end(step_instance_id, params):
    """
    Checks if the end is correct:
    Required values are there and in the correct form
    """
    errors = []
    step_instance = m_step_i.Step_instance.objects.get({"_id":ObjectId(step_instance_id)})
    
    python_type = {
        'int': int,
        'str': str,
        'textarea': str
    }

    def e_missing(e, m, b=""):
        if b != "":
            b = " for barcode {}".format(b)
        e.append("Missing or incorrect param {}{}".format(m, b))
    
    required = step_instance.step.required_params()
    for req in required["all"]:
        if req[1] == "file":
            files_underscores = [f.replace(".", "_") for f in params["files"].keys()]
            if req[0] not in files_underscores:
                e_missing(errors, req[0])
        elif (not "all" in params["params"] or
              req[0] not in params["params"]["all"] or
              not isinstance(params["params"]["all"][req[0]], python_type[req[1]])):
            e_missing(errors, req[0])
    for req in required["samples"]:
        if "samples" not in params["params"]:
            e_missing(errors, req[0])
        else:
            for barcode, sampleparams in params["params"]["samples"].items():
                if (req[0] not in params["params"]["samples"][barcode] or
                    not isinstance(params["params"]["samples"][barcode][req[0]], python_type[req[1]])):
                    e_missing(errors, req[0], barcode)

    return errors

def end_step(step_instance_id, params, user):
    """
    Ends the step, runs the required scripts. Returns suggested next step.
    """
    step_instance = m_step_i.Step_instance.objects.get({"_id":ObjectId(step_instance_id)})
    step_instance.save_params(params)
    try:
        step_instance.run_scripts("stepend")
    except Exception as e:
        step_instance.remove_params(params)
        raise e
    step_instance.status = "finished"
    step_instance.user_ended = user
    step_instance.finish_date = datetime.datetime.now()
    step_instance.save()

    suggested_steps = {}

    for sample in step_instance.samples:
        s = sample.finish_step(step_instance, save=False)
        if s in suggested_steps:
            suggested_steps[s] += 1
        else:
            suggested_steps[s] = 1

    for s in step_instance.samples:
        s.save()
    
    step_instance.run_scripts("qc")

    qc_actions_msg = step_instance.qc_actions_msg()

    suggested_step = (None, 0)
    alternative_steps = set(suggested_steps.keys())
    for s, c in suggested_steps.items():
        if c > suggested_step[1]:
            suggested_step = (s, c)
    alternative_steps.remove(suggested_step[0])

    return {
        "suggested_step": suggested_step[0],
        'alternative_steps': list(alternative_steps),
        "qc_actions_msg": qc_actions_msg
    }

def get_step_finished(stepinstanceid, suggested_step, alternative_step_names, reassign_qc_fail):
    if suggested_step is not None and suggested_step != "_workflow_finished":
        step = m_step.Step.objects.get({"name": suggested_step})
        step_summary = step.summary()
    else:
        step_summary = None
    step_instance = m_step_i.Step_instance.objects.get({"_id": ObjectId(stepinstanceid)})
    alternative_steps = []
    if alternative_step_names is not None:
        alternative_steps = m_step.objects.raw({"name": {"$in": alternative_step_names}})
    reassign = {}
    if reassign_qc_fail is not None:
        reassign = step_instance.qc_reassign_data()
    
    return {
        "finished_step": step_instance.summary(values=True),
        'suggested_step': step_summary,
        'alternative_steps': [step.summary(values=True) for step in alternative_steps],
        'reassign': reassign
    }

def get_step_details(step_name):
    step = m_step.Step.objects.get({"name": step_name})

    return {
        'step': step.summary(get_workflows=True),
        'available': {"count": len(step.available_samples())},
        'step_instances': step.step_instances_summaries()
    }

def validate_delete_step_instance(stepinstanceid):
    # Check if it exists and is the last one for all samples (and if user has permission if relevant)
    errors = {}
    try:
        step_i = m_step_i.Step_instance.objects.get({"_id": ObjectId(stepinstanceid)})
    except pymodm.errors.DoesNotExist:
        errors["doesnotexist"] = "Step instance with id {} does not exist.".format(stepinstanceid)
        return errors

    # This will look all Samples in the step instance, will go through all workflows, steps
    # and attempts to look for samples with step instances with this step instance as a parent.
    samples_with_next_step = []
    samples = step_i.samples
    for sample in samples:
        found = False
        break_f = False
        for workflow, items in sample.workflows.items():
            if break_f:
                break
            for step, attempts in items.items():
                if break_f:
                    break
                if found:
                    for attempt in attempts:
                        if attempt.parent == found and step != "_workflow_finished":
                            samples_with_next_step.append(sample.barcode)
                            break
                if step == step_i.step.category:
                    for attempt_index in range(len(attempts)):
                        attempt = attempts[attempt_index]
                        if attempt.step_instance._id == step_i._id:
                            found = "{}.{}.{}".format(workflow, step, attempt_index)
                            break
    if samples_with_next_step:
        errors["samples_with_next_step"] = "Some samples ({}) have step instances that depend on this. Can't delete.".format(",".join(samples_with_next_step))
    
    return errors

def delete_step_instance(stepinstanceid):
    step_i = m_step_i.Step_instance.objects.get({"_id": ObjectId(stepinstanceid)})
    for sample in step_i.samples:
        break_f = False
        found = False
        prev_step = "root"
        for workflow, items in sample.workflows.items():
            if break_f:
                break
            for step, attempts in items.items():
                if break_f and step == "_workflow_finished":
                    for attempt_index in range(len(attempts)):
                        attempt = attempts[attempt_index]
                        if attempt.parent == found:
                            sample.workflows[workflow][step].pop(attempt_index)
                            sample.save()
                            break
                    break
                if step == step_i.step.category:
                    for attempt_index in range(len(attempts)):
                        attempt = attempts[attempt_index]
                        if attempt.step_instance._id == step_i._id:
                            sample.workflows[workflow][step].pop(attempt_index)
                            break_f = True
                            found = "{}.{}.{}".format(workflow, step, attempt_index)
                            sample.save()
                            break
                    if break_f:
                        break
                prev_step = step
            if found:
                for index in range(len(sample.batches)):
                    obj = sample.batches[index]
                    if obj.workflow.name == workflow:
                        obj.step_cat = prev_step
                        print("prev", prev_step)
                        sample.batches[index] = obj
                sample.save()
    
    m_step_i.Step_instance.objects.raw({"_id": ObjectId(stepinstanceid)}).delete()

