import pymodm.errors

from minilims.models.tag import Tag
from minilims.models.sample import Sample
from minilims.utils import expect

def validate_and_add(jsonbody):
    errors = {}
    missing = expect(jsonbody, ["value"])
    if missing:
        errors["missing_property"] = f"Missing properties: {missing}"
    if len(errors):
        return errors
    #Validation
    if "style" in jsonbody:
        Tag(
            value=jsonbody["value"],
            style=jsonbody["style"],
        ).save()
    else:
        Tag(
            value=jsonbody["value"],
        ).save()
    return errors

def validate_and_delete(tagvalue):
    errors = {}

    # Check there are no samples with the tag
    sample_count = Sample.objects.raw({"tags.value": tagvalue}).count()
    if sample_count != 0:
        errors["tag_is_assigned"] = ["Tag is assigned to samples. Unassign from all samples before deleting."]
    
    if len(errors):
        return errors
    
    Tag.objects.raw({"_id": tagvalue}).delete()

    return errors

def validate_and_assign_to_sample(tagvalue, jsonbody):
    errors = {}
    missing = expect(jsonbody, ["sample_barcodes"])
    if missing:
        errors["missing_property"] = f"Missing properties: {missing}"
    
    try:
        tag = Tag.objects.get({"_id": tagvalue})
    except pymodm.errors.DoesNotExist:
        errors["tag_not_found"] = [f"Tag {tagvalue} not found."]
    
    samples = list(Sample.objects.raw({"barcode": {"$in": jsonbody["sample_barcodes"]}}))
    if len(samples) == 0:
        errors["no_valid_samples"] = ["No valid samples found with the provided barcodes."]
    
    if len(errors):
        return errors

    for sample in samples:
        sample.assign_tag(tag)
    
    return errors

def validate_and_remove_from_sample(tagvalue, jsonbody):
    errors = {}
    missing = expect(jsonbody, ["sample_barcodes"])
    if missing:
        errors["missing_property"] = f"Missing properties: {missing}"
    
    try:
        tag = Tag.objects.get({"_id": tagvalue})
    except pymodm.errors.DoesNotExist:
        errors["tag_not_found"] = [f"Tag {tagvalue} not found."]
    
    samples = list(Sample.objects.raw({"barcode": {"$in": jsonbody["sample_barcodes"]}}))
    if len(samples) == 0:
        errors["no_valid_samples"] = ["No valid samples found with the provided barcodes."]
    
    if len(errors):
        return errors

    for sample in samples:
        sample.unassign_tag(tag)
    
    return errors
