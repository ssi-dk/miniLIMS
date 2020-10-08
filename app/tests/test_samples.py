import datetime

import pytest
import minilims.services.lims as s_lims
from minilims.models.sample import Sample
from minilims.models.step import Step
from minilims.models.workflow import Workflow
import json

import data_test as dt
from test_lims import Helper

@pytest.mark.parametrize(('samplesheet', 'errors'), (
    (dt.samplesheets_fail[0], dt.errors[0]),
    (dt.samplesheets_fail[1], dt.errors[1]),
    (dt.samplesheets_fail[2], dt.errors[2]),
    (dt.samplesheets_fail[3], dt.errors[3]),
    (dt.samplesheets_success, dt.errors[4])
))
def test_validate_samplesheet(client, auth, samplesheet, errors):
    Sample.objects.delete()
    auth.login()
    response = client.post(
        '/samples/validate',
        data=json.dumps(samplesheet),
        content_type="application/json;charset=UTF-8"
    )
    assert errors == response.json

@pytest.mark.parametrize(('samplesheet', 'status','dbentries_test'), (
    (dt.samplesheets_fail[0], dt.status_fail, dt.dbentries_empty),
    (dt.samplesheets_fail[1], dt.status_fail, dt.dbentries_empty),
    (dt.samplesheets_fail[2], dt.status_fail, dt.dbentries_empty),
    (dt.samplesheets_fail[3], dt.status_fail, dt.dbentries_empty),
    (dt.samplesheets_success, dt.status_ok, dt.dbentries_success)
))
def test_submit_samplesheet(client, auth, samplesheet, status, dbentries_test):
    auth.login()
    Sample.objects.delete()
    response = client.post(
        '/samples/submit',
        data=json.dumps(samplesheet),
        content_type="application/json;charset=UTF-8",
        follow_redirects=True
    )
    assert response.json["status"] == status

    for sample in dbentries_test:
        sample_db = Sample.objects.get({"barcode": sample["barcode"]})
        sample_db_summary = sample_db.properties.sample_info.summary
        sample_summary = sample["properties"]["sample_info"]["summary"]
        # Check submitted_species and submitter
        assert (sample_summary["submitted_species"] == 
                sample_db_summary.submitted_species.name)
        assert (sample_summary["submitter"] == 
                sample_db_summary.submitter.email)
        # Delete _id, it isnt hardcoded
        sample_db_dict = sample_db.to_son().to_dict()
        del sample_db_dict["properties"]["sample_info"]["summary"]["submitted_species"]
        del sample["properties"]["sample_info"]["summary"]["submitted_species"]
        del sample_db_dict["properties"]["sample_info"]["summary"]["submitter"]
        del sample["properties"]["sample_info"]["summary"]["submitter"]
        del sample_db_dict["_id"]
        del sample_db_dict["submitted_on"]
        assert sample == sample_db_dict

@pytest.mark.parametrize(('samplesheet', 'status', 'assign_data'),(
    (dt.samplesheets_success, dt.status_ok, dt.assign_samples[0]),
))
def test_assign_samples(client, auth, samplesheet, status, assign_data):
    auth.login()
    Sample.objects.delete()
    Step.objects.delete()
    Workflow.objects.delete()

    steps = [s[0] for s in dt.steps]

    #import steps and workflow
    retrieved = s_lims.import_steps(steps)
    s_lims.import_workflow(dt.workflows[0])
    # import samples
    response = client.post(
        '/samples/submit',
        data=json.dumps(samplesheet),
        content_type="application/json;charset=UTF-8",
    )
    # Assign sample to workflow
    response = client.post(
        '/samples/assign-api',
        data=json.dumps(assign_data),
        content_type="application/json;charset=UTF-8",
    )
    assert response.json["status"] == status
    # Test if sample assigned
    for sample in samplesheet:
        sample_db = Sample.objects.get({"barcode":sample["barcode"]})
        assert sample_db.batches[0].workflow.name == dt.workflows[0]["name"]
        assert sample_db.batches[0].step_cat == "root"



def test_unassign_samples(client, auth):
    helper = Helper(client)
    helper.reset_db()

    #import steps and workflow
    steps = [s[0] for s in dt.steps]
    s_lims.import_steps(steps)
    s_lims.import_workflow(dt.workflows[0])

    sample_barcodes = dt.barcodes[0]
    samplesheet = dt.samplesheets_success
    status = dt.status_ok
    assign_data = dt.assign_samples[0]
    workflow_name = dt.workflows[0]['name']

    auth.login()
    helper.submit_samples(dt.samplesheets_success)

    helper.assign_samples(sample_barcodes, workflow_name, dt.batch_name)

    response = client.put(
        '/samples/unassign',
        data=json.dumps({"sample_barcodes": sample_barcodes,
                         "workflow_batch": "{}: {}".format(workflow_name, dt.batch_name),
                        }),
        content_type="application/json;charset=UTF-8",
    )
    print(response.json)
    assert response.json["status"] == status
    # Test if sample assigned
    for sample in samplesheet:
        sample_db = Sample.objects.get({"barcode": sample["barcode"]})
        assert sample_db.batches[0].workflow.name == dt.workflows[0]["name"]
        assert sample_db.batches[0].step_cat == "root"
        assert sample_db.batches[0].archived is True


@pytest.mark.parametrize(('json_body', 'expected_response', 'updater'),(
    ({"barcode": "123", "species": "1233", "group": "group12", "name": "testsample1@", "archived": "true", "submitted_on": None, "priority": "1", "batch": "Unassigned", "genome_size": 5000000},
    {'errors': {'wrong_barcode': ['Wrong barcode.'], 'wrong_species': ["Species doesn't match species in database."], 'validate_field_name': ['Invalid field value.']}},
    ("test@test.com", "test")),
    ({"barcode": "ABC", "species": "Salmonella enterica", "group": "FBI", "name": "testsample1", "archived": "true",  "submitted_on": None, "priority": "1", "batch": "Unassigned", "genome_size": 5000000},
    {"barcode": "ABC", "species": "Salmonella enterica", "group": "FBI", "name": "testsample1", "archived": "true", "submitted_on": None, "priority": "1", "batch": "Unassigned", "genome_size": 5000000},
    ("test@test.com", "test")),
    ({"barcode": "ABC", "species": "Salmonella enterica", "group": "FBI", "name": "testsample1", "archived": "true",  "submitted_on": None, "priority": "1", "batch": "Unassigned", "genome_size": 5000000},
    {'errors': {'authorization': ["Your user doesn't have permission to edit this sample. Please contact an admin to request changes."]}},
    ("supplying_lab@test.com", "supplying lab"))
))
def test_sample_update_from_web(client, auth, json_body, expected_response, updater):
    # setup
    helper = Helper(client)
    helper.reset_db()

    #

    auth.login()
    helper.submit_samples(dt.samplesheets_success)


    #Test

    auth.logout()
    auth.login(updater[0], updater[1])

    response = client.post(
        '/samples/data-source/update',
        data=json.dumps(json_body),
        content_type="application/json;charset=UTF-8",
    )
    print(response.json)
    assert response.json == expected_response



def test_assign_and_update(client, auth):
    # Test that user cannot edit sample after being assigned

    # Setup
    helper = Helper(client)
    helper.reset_db()

    s_lims.import_steps([dt.steps[0][0]])
    s_lims.import_workflow(dt.workflows[0])

    workflow_name = dt.workflows[0]['name']

    # upload samples

    auth.login("supplying_lab@test.com", "supplying lab")
    helper.submit_samples(dt.samplesheets_success)
    auth.logout()
    auth.login()
        
    helper.assign_samples(dt.barcodes[0], workflow_name, "batch1")

    auth.logout()
    auth.login("supplying_lab@test.com", "supplying lab")
    #Test

    json_body = {"barcode": "ABC", "species": "Salmonella enterica", "group": "FBI", "name": "testsample1", "archived": "true",  "submitted_on": None, "priority": "1", "batch": "Unassigned", "genome_size": 5000000}

    response = client.post(
        '/samples/data-source/update',
        data=json.dumps(json_body),
        content_type="application/json;charset=UTF-8",
    )
    assert response.json == {'errors': {'sample_assigned': ['This sample has already been assigned. Please contact an admin to request changes.']}}
