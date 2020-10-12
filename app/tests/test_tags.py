from flask import url_for
import pymodm.errors
import json


from minilims.models.tag import Tag
from minilims.models.sample import Sample

from test_lims import Helper
import data_test as dt


def test_create_and_delete_tag(client, auth):
    helper = Helper(client)
    helper.reset_db()
    auth.login()

    tag_val = "testtag"

    tag = {
        "value": tag_val,
        "style": "#FF0000"
    }
    response = client.post(
        "/tags/",
        data=json.dumps(tag),
        content_type="application/json;charset=UTF-8",
        follow_redirects=True
    )
    print(response.json)
    assert response.json["status"] == "OK"

    tag_db = Tag.objects.get({
        "_id": tag_val
    })
    tag_db = tag_db.to_son().to_dict()
    del tag_db["_cls"]
    assert tag_db == {"_id": tag["value"], "style": tag["style"]}

    response = client.delete(
        f"/tags/{tag_val}",
        content_type="application/json;charset=UTF-8",
        follow_redirects=True
    )
    print(response.json)
    assert response.json["status"] == "OK"

    try:
        tag_db = Tag.objects.get(tag)
    except pymodm.errors.DoesNotExist:
        pass
    else:
        raise ValueError("Tag was not deleted")


def test_assign_unassign_tag(client, auth):
    helper = Helper(client)
    helper.reset_db()
    auth.login()

    helper.submit_samples(dt.samplesheets_success)

    tag_val = "testtag"

    tag = {
        "value": tag_val,
        "style": "#FF0000"
    }
    response = client.post(
        "/tags/",
        data=json.dumps(tag),
        content_type="application/json;charset=UTF-8",
        follow_redirects=True
    )

    print(response.json)
    assert response.json["status"] == "OK"

    barcode = dt.barcodes[0][0]

    response = client.post(
        f"/tags/{tag_val}/assign_to_samples",
        data=json.dumps({"sample_barcodes": [barcode]}),
        content_type="application/json;charset=UTF-8",
        follow_redirects=True
    )
    print(response.json)
    assert response.json["status"] == "OK"

    sample_db = Sample.objects.get({"barcode": barcode})

    tag_db = sample_db.tags[0].to_son().to_dict()

    del tag_db["_cls"]
    assert tag_db == {"_id": tag["value"], "style": tag["style"]}

    response = client.post(
        f"/tags/{tag_val}/remove_from_samples",
        data=json.dumps({"sample_barcodes": [barcode]}),
        content_type="application/json;charset=UTF-8",
        follow_redirects=True
    )
    print(response.json)
    assert response.json["status"] == "OK"

    sample_count = Sample.objects.raw({"barcode": barcode}).count()

    assert sample_count
