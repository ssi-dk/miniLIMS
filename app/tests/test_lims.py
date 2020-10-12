import pytest
from flask import g, session
from bson.objectid import ObjectId

import minilims.services.lims as s_lims
from minilims.models.step import Step
from minilims.models.tag import Tag
from minilims.models.sample import Sample
from minilims.models.workflow import Workflow
from minilims.models.step_instance import Step_instance
import minilims.utils.fileutils as fileutils
import json

import tests.data_test as dt

## Helper

class Helper:
    def __init__(self, client):
        self.client = client

    def reset_db(self):
        #reset 
        Step.objects.delete()
        Step_instance.objects.delete()
        Sample.objects.delete()
        Workflow.objects.delete()
        Tag.objects.delete()

    def submit_samples(self, samplesheet):
        response = self.client.post(
            '/samples/submit',
            data=json.dumps(samplesheet),
            content_type="application/json;charset=UTF-8",
            follow_redirects=True
        )
        print(response.json)
        assert response.json["status"] == "OK"
        return response

    def assign_samples(self, sample_barcodes, workflow_name, batch_name, step=None):
        assign_payload = {
            "sample_barcodes": sample_barcodes,
            "workflow": workflow_name,
            "batch_name": batch_name,
            "plate_type": "96plate"
        }
        if step is not None:
            assign_payload["step_name"] = step
        
        response = self.client.post(
            '/samples/assign-api',
            data=json.dumps(assign_payload),
            content_type="application/json;charset=UTF-8",
        )
        print(response.json)
        assert response.json["status"] == "OK"
        return response

    def unassign_samples(self, sample_barcodes, workflow_name, batch_name):
        response = self.client.put(
            '/samples/unassign',
            data=json.dumps({"sample_barcodes": sample_barcodes,
                            "workflow_batch": "{}: {}".format(workflow_name, dt.batch_name),
                            }),
            content_type="application/json;charset=UTF-8",
        )
        print(response.json)
        assert response.json["status"] == "OK"

    def start_step(self, step_name, data):
        response = self.client.post(
            '/steps/{}/start'.format(step_name),
            data=json.dumps(data),
            content_type="application/json;charset=UTF-8",
            follow_redirects=True
        )
        print(response.json)
        assert response.json["status"] == "OK"
        return response

    def end_step(self, step_i_id, data):
        response = self.client.post(
            '/stepinstance/{}/end'.format(step_i_id),
            data=data,
            content_type='multipart/form-data',
            follow_redirects=True
        )
        print(response.json)
        assert response.json["status"] == "OK"
        return response

    def workflow_finished(self, workflow_name, sample_barcodes):
        samples = Sample.objects.raw({"barcode": {"$in": sample_barcodes}})
        for sample in samples:
            assert "_workflow_finished" in sample.workflows[workflow_name]


## Tests


def test_create_and_save_step():
    helper = Helper(None)
    helper.reset_db()

    steps = [s[0] for s in dt.steps]

    retrieved = s_lims.import_steps(steps)
    for step in retrieved:
        assert Step.objects.get({"name":step.name}) is not None

def test_add_workflow():
    helper = Helper(None)
    helper.reset_db()

    steps = [s[0] for s in dt.steps]

    #needed
    s_lims.import_steps(steps)

    s_lims.import_workflow(dt.workflows[0])
    workflow_db = Workflow.objects.get({"name":dt.workflows[0]["name"]}).to_son().to_dict()
    assert workflow_db["name"] == dt.workflows[0]["name"]
    assert len(workflow_db["steps"]) == len(dt.workflows[0]["steps"])


@pytest.mark.parametrize(('sample_barcodes', 'step', 'workflow', 'step_end_data', 'expected_values'), (
    (dt.barcodes[0], dt.steps[0], dt.workflows[0], dt.attached['in1'], []),
    (dt.barcodes[0], dt.steps[1], dt.workflows[1], dt.attached['illu'], [("run_metadata", "result_all"),("samplesheet_csv", "result_all")]),
))
def test_step(client, auth, sample_barcodes, step, workflow, step_end_data, expected_values):
    helper = Helper(client)
    helper.reset_db()

    #needed
    s_lims.import_steps([step[0]])
    s_lims.import_workflow(workflow)

    workflow_name = workflow['name']
    batch_name = dt.batch_name

    auth.login()
    helper.submit_samples(dt.samplesheets_success)

    helper.assign_samples(sample_barcodes, workflow_name, batch_name)

    step_name = step[0]
    step_cat = step[1]

    step_data = {
        "sample_barcodes": sample_barcodes,
        "workflow_batch" : "{}: {}".format(workflow_name, batch_name)
    }
    
    helper.start_step(step_name, step_data)
    
    sample_o = Sample.objects.get({
        "barcode":sample_barcodes[0],
    })
    assert sample_o.workflows[workflow_name][step_cat][0].status == "started"
    # This query will raise DoesNotExist if missing.
    step = Step.objects.get({"name":step_name})
    step_i = Step_instance.objects.get({
        "step": step.pk,
        "status": "started",
        "result_samples.{}".format(sample_barcodes[0]): {"$exists": True}
    })

    helper.end_step(str(step_i.pk), step_end_data)

    finished_step_i = Step_instance.objects.get({
        "_id": step_i.pk,
        "status": "finished",
        "result_samples.{}".format(sample_barcodes[0]): {"$exists": True}
    })
    if step_name == "submit_to_bifrost":
        assert finished_step_i.result_all["samplesheet_csv"]
        assert finished_step_i.result_all["run_metadata"]

def test_except_missing_params(client, auth):
    helper = Helper(client)
    helper.reset_db()

    step = dt.steps[0][0]
    step_cat = dt.steps[0][1]
    workflow = dt.workflows[0]
    sample_barcodes = dt.barcodes[0]
    step_end_data = dt.attached['none']

    #needed
    s_lims.import_steps([step])
    s_lims.import_workflow(workflow)

    workflow_name = workflow['name']
    batch_name = dt.batch_name

    auth.login()
    helper.submit_samples(dt.samplesheets_success)
    helper.assign_samples(sample_barcodes, workflow_name, batch_name)

    step_name = step

    step_data = {
        "sample_barcodes": sample_barcodes,
        "workflow_batch" : "{}: {}".format(workflow_name, batch_name)
    }
    helper.start_step(step_name, step_data)

    sample_o = Sample.objects.get({
        "barcode": sample_barcodes[0],
    })
    assert sample_o.workflows[workflow_name][step_cat][0].status == "started"
    # This query will raise DoesNotExist if missing.
    step = Step.objects.get({"name":step_name})
    step_i = Step_instance.objects.get({
        "step": step.pk,
        "status": "started",
        "result_samples.{}".format(sample_barcodes[0]): {"$exists": True}
    })
    # for value, subdoc in expected_values:
    #     if not value in getattr(step_i, subdoc):
    #         raise ValueError("Missing expected value {} in {}".format(value, subdoc))
    response = client.post(
        '/stepinstance/{}/end'.format(str(step_i.pk)),
        data=step_end_data,
        content_type='multipart/form-data',
        follow_redirects=True
    )
    assert response.json["status"] == "Fail"
    assert response.json["errors"] == ["Missing or incorrect param in1"]

def test_two_steps(client, auth):
    helper = Helper(client)
    helper.reset_db()

    # Test variables
    steps = (dt.steps[0], dt.steps[2])
    step_names = [s[0] for s in steps]
    workflow = dt.workflows[2]
    sample_barcodes = dt.barcodes[0]

    #needed
    s_lims.import_steps(step_names)
    s_lims.import_workflow(workflow)

    workflow_name = workflow['name']
    batch_name = dt.batch_name

    auth.login()

    helper.submit_samples(dt.samplesheets_success)
    helper.assign_samples(sample_barcodes, workflow_name, batch_name)

    # Step 1 start
    end_step_1_data = dt.attached['in1']
    step_name = steps[0][0]
    step_cat = steps[0][1]

    step_data = {
        "sample_barcodes": sample_barcodes,
        "workflow_batch" : "{}: {}".format(workflow_name, batch_name)
        }

    helper.start_step(step_name, step_data)
    
    sample_o = Sample.objects.get({
        "barcode": sample_barcodes[0],
    })
    assert sample_o.workflows[workflow_name][step_cat][0].status == "started"
    # This query will raise DoesNotExist if missing.
    step = Step.objects.get({"name":step_name})
    step_i = Step_instance.objects.get({
        "step": step.pk,
        "status": "started",
        "result_samples.{}".format(sample_barcodes[0]): {"$exists": True}
    })
    # for value, subdoc in expected_values:
    #     if not value in getattr(step_i, subdoc):
    #         raise ValueError("Missing expected value {} in {}".format(value, subdoc))
    helper.end_step(str(step_i.pk), end_step_1_data)

    finished_step_i = Step_instance.objects.get({
        "_id": step_i.pk,
        "status": "finished",
        "result_samples.{}".format(sample_barcodes[0]): {"$exists": True}
    })

    # Now step 2
    step_name = steps[1][0]
    step_cat = steps[1][1]

    step_starts = {
        "sample_barcodes": sample_barcodes,
        "workflow_batch" : "{}: {}".format(workflow_name, batch_name)
    }
    helper.start_step(step_name, step_starts)

    sample_o = Sample.objects.get({
        "barcode": sample_barcodes[0],
    })
    assert sample_o.workflows[workflow_name][step_cat][0].status == "started"
    # This query will raise DoesNotExist if missing.
    step = Step.objects.get({"name":step_name})
    step_i = Step_instance.objects.get({
        "step": step.pk,
        "status": "started",
        "result_samples.{}".format(sample_barcodes[0]): {"$exists": True}
    })

    helper.end_step(str(step_i.pk), {})

    finished_step_i = Step_instance.objects.get({
        "_id": step_i.pk,
        "status": "finished",
        "result_samples.{}".format(sample_barcodes[0]): {"$exists": True}
    })


def test_start_step_and_cancel(client, auth):
    helper = Helper(client)
    helper.reset_db()

    # Test variables
    steps = (dt.steps[0], dt.steps[2])
    step_names = [s[0] for s in steps]
    workflow = dt.workflows[2]
    sample_barcodes = dt.barcodes[0]

    #needed
    s_lims.import_steps(step_names)
    s_lims.import_workflow(workflow)

    workflow_name = workflow['name']
    batch_name = dt.batch_name

    auth.login()

    helper.submit_samples(dt.samplesheets_success)
    helper.assign_samples(sample_barcodes, workflow_name, batch_name)

    # Step 1 start
    end_step_1_data = dt.attached['in1']
    step_name = steps[0][0]
    step_cat = steps[0][1]

    step_data = {
        "sample_barcodes": sample_barcodes,
        "workflow_batch" : "{}: {}".format(workflow_name, batch_name)
        }

    response = helper.start_step(step_name, step_data)

    step_instance_id = response.json["data"]["step_instance_id"]

    sample_o = Sample.objects.get({
        "barcode": sample_barcodes[0],
    })
    assert sample_o.workflows[workflow_name][step_cat][0].status == "started"


    # Cancel test
    response = client.post(
        '/stepinstance/{}/cancel'.format(step_instance_id),
        content_type="application/json;charset=UTF-8",
    )

    assert response.json["status"] == "Cancelled"

    step_i = Step_instance.objects.get({"_id": ObjectId(step_instance_id)})
    assert step_i.status == "cancelled"

    sample_o = Sample.objects.get({
        "barcode": sample_barcodes[0],
    })
    assert len(sample_o.workflows[workflow_name][step_cat]) == 0


def test_two_workflows_sequential(client, auth):
    helper = Helper(client)
    helper.reset_db()

    workflow_1 = dt.workflows[0]
    workflow_2 = dt.workflows[1]
    sample_barcodes = dt.barcodes[0]


    auth.login()
    #needed
    s_lims.import_steps([dt.steps[0][0], dt.steps[1][0]])
    s_lims.import_workflow(workflow_1)
    s_lims.import_workflow(workflow_2)

    helper.submit_samples(dt.samplesheets_success)

    # Workflow 1
    end_step_1_data = dt.attached['in1']
    workflow_name = workflow_1['name']
    batch_name = dt.batch_name

    helper.assign_samples(sample_barcodes, workflow_name, batch_name)

    step_name = dt.steps[0][0]
    step_cat = dt.steps[0][1]

    step_data = {
        "sample_barcodes": sample_barcodes,
        "workflow_batch" : "{}: {}".format(workflow_name, batch_name)
        }
    
    helper.start_step(step_name, step_data)
    
    sample_o = Sample.objects.get({
        "barcode": sample_barcodes[0],
    })
    assert sample_o.workflows[workflow_name][step_cat][0].status == "started"
    # This query will raise DoesNotExist if missing.
    step = Step.objects.get({"name":step_name})
    step_i = Step_instance.objects.get({
        "step": step.pk,
        "status": "started",
        "result_samples.{}".format(sample_barcodes[0]): {"$exists": True}
    })

    helper.end_step(str(step_i.pk), end_step_1_data)

    # Workflow 2
    workflow_name = workflow_2['name']

    helper.assign_samples(sample_barcodes, workflow_name, batch_name)

    step_name = dt.steps[1][0]
    step_cat = dt.steps[1][1]
    
    helper.start_step(step_name, step_data)
    
    sample_o = Sample.objects.get({
        "barcode": sample_barcodes[0],
    })
    assert sample_o.workflows[workflow_name][step_cat][0].status == "started"
    # This query will raise DoesNotExist if missing.
    step = Step.objects.get({"name":step_name})
    step_i = Step_instance.objects.get({
        "step": step.pk,
        "status": "started",
        "result_samples.{}".format(sample_barcodes[0]): {"$exists": True}
    })

    helper.end_step(str(step_i.pk), dt.attached['illu2'])

def test_two_workflows_parallel(client, auth):
    helper = Helper(client)
    helper.reset_db()

    workflow_1 = dt.workflows[0]
    workflow_2 = dt.workflows[1]
    sample_barcodes = dt.barcodes[0]


    auth.login()
    #needed
    s_lims.import_steps([dt.steps[0][0], dt.steps[1][0]])
    s_lims.import_workflow(workflow_1)
    s_lims.import_workflow(workflow_2)

    helper.submit_samples(dt.samplesheets_success)

    # Workflow 1 assign
    end_step_1_data = dt.attached['in1']
    workflow_name = workflow_1['name']
    batch_name = dt.batch_name

    helper.assign_samples(sample_barcodes, workflow_name, batch_name)

    # Workflow 2 assign
    helper.assign_samples(sample_barcodes, workflow_2['name'], batch_name)

    # Workflow 1 step
    step_name = dt.steps[0][0]
    step_cat = dt.steps[0][1]

    step_data = {
        "sample_barcodes": sample_barcodes,
        "workflow_batch" : "{}: {}".format(workflow_name, batch_name)
        }

    helper.start_step(step_name, step_data)
    
    sample_o = Sample.objects.get({"barcode": sample_barcodes[0]})
    assert sample_o.workflows[workflow_1['name']][step_cat][0].status == "started"
    # This query will raise DoesNotExist if missing.
    step = Step.objects.get({"name":step_name})
    step_i = Step_instance.objects.get({
        "step": step.pk,
        "status": "started",
        "result_samples.{}".format(sample_barcodes[0]): {"$exists": True}
    })

    helper.end_step(str(step_i.pk), end_step_1_data)

    # Workflow 2 step
    step_name = dt.steps[1][0]
    step_cat = dt.steps[1][1]
    
    helper.start_step(step_name, step_data)
    
    sample_o = Sample.objects.get({
        "barcode": sample_barcodes[0],
    })
    assert sample_o.workflows[workflow_2['name']][step_cat][0].status == "started"
    # This query will raise DoesNotExist if missing.
    step = Step.objects.get({"name":step_name})
    step_i = Step_instance.objects.get({
        "step": step.pk,
        "status": "started",
        "result_samples.{}".format(sample_barcodes[0]): {"$exists": True}
    })

    helper.end_step(str(step_i.pk), dt.attached['illu3'])

def test_download_file(client, auth):
    f = fileutils.Tempfile()
    auth.login()
    content = "asdasdasd"
    with open(f.filehandle.name, "w") as fio:
        fio.write(content)
    fid = f.save("testname")
    response = client.get(
        '/files/{}'.format(str(fid)),
    )
    assert response.data == content.encode("utf-8")

def test_delete_step(client, auth):
    helper = Helper(client)
    helper.reset_db()

    # Test variables
    steps = (dt.steps[0], dt.steps[2])
    step_names = [s[0] for s in steps]
    workflow = dt.workflows[2]
    sample_barcodes = dt.barcodes[0]
    batch_name = dt.batch_name

    #needed
    s_lims.import_steps(step_names)
    s_lims.import_workflow(workflow)

    workflow_name = workflow['name']
    batch_name = dt.batch_name

    auth.login()

    helper.submit_samples(dt.samplesheets_success)
    helper.assign_samples(sample_barcodes, workflow_name, batch_name)

    # Step 1 start
    end_step_1_data = dt.attached['in1']
    step_name = steps[0][0]
    step_cat = steps[0][1]

    step_data = {
        "sample_barcodes": sample_barcodes,
        "workflow_batch": "{}: {}".format(workflow_name, batch_name)
    }

    helper.start_step(step_name, step_data)
    
    sample_o = Sample.objects.get({
        "barcode": sample_barcodes[0],
    })
    assert sample_o.workflows[workflow_name][step_cat][0].status == "started"
    # This query will raise DoesNotExist if missing.
    step = Step.objects.get({"name":step_name})
    step_i = Step_instance.objects.get({
        "step": step.pk,
        "status": "started",
        "result_samples.{}".format(sample_barcodes[0]): {"$exists": True}
    })
    # for value, subdoc in expected_values:
    #     if not value in getattr(step_i, subdoc):
    #         raise ValueError("Missing expected value {} in {}".format(value, subdoc))
    helper.end_step(str(step_i.pk), end_step_1_data)

    finished_step_i = Step_instance.objects.get({
        "_id": step_i.pk,
        "status": "finished",
        "result_samples.{}".format(sample_barcodes[0]): {"$exists": True}
    })

    # Now step 2
    step_name = steps[1][0]
    step_cat = steps[1][1]

    helper.start_step(step_name, step_data)

    sample_o = Sample.objects.get({
        "barcode": sample_barcodes[0],
    })
    assert sample_o.workflows[workflow_name][step_cat][0].status == "started"
    # This query will raise DoesNotExist if missing.
    step = Step.objects.get({"name":step_name})
    step_i = Step_instance.objects.get({
        "step": step.pk,
        "status": "started",
        "result_samples.{}".format(sample_barcodes[0]): {"$exists": True}
    })

    helper.end_step(str(step_i.pk), {})

    finished_step_i = Step_instance.objects.get({
        "_id": step_i.pk,
        "status": "finished",
        "result_samples.{}".format(sample_barcodes[0]): {"$exists": True}
    })

    # So far the same as test_two_steps. Now delete the step
    response = client.post(
        '/stepinstance/{}/delete'.format(step_i.pk),
        content_type="application/json;charset=UTF-8",
    )
    print(response)
    print(response.data)
    assert response.json["status"] == "Deleted"
    # Test that step is deleted and that samples don't have it


    query_count = Step_instance.objects.raw({"_id": step_i.pk}).count()
    assert query_count == 0

    sample = Sample.objects.get({"barcode": sample_barcodes[0]})

    assert len(sample.workflows[workflow_name][step_i.step.name]) == 0