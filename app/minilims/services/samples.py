import datetime
from minilims.models.counter import BarcodeProvider

from flask import url_for

import minilims.utils.samplesheet_validation as samplesheet_validation
import minilims.models.sample as m_sample
import minilims.models.workflow as m_workflow
from minilims.models.species import Species
import pymodm.errors
from minilims.utils import expect
import minilims.utils.fileutils as fileutils

# from minilims.models.user import User

def get_emails(e_str):
    """
    Split email string and clean spaces.
    """
    if e_str == "":
        return []
    emails = e_str.split(",")
    return [e.strip() for e in emails]

validate_samplesheet = samplesheet_validation.validate

def submit_samplesheet(samplesheet, user):
    """
    Submit samplesheet to the system.
    """
    priority_map = {
        "low" : 0,
        "high" : 4
    }
    samples = []
    for row in samplesheet:
        # Convert keys to lowercase
        lowercase_row = {}
        for key, value in row.items():
            lowercase_row[key.lower()] = value
        row = lowercase_row

        # This should pass as it's been validated
        species = Species.get_species(row["organism"])
        emails = get_emails(row.get("emails", ""))
        summary = m_sample.S_summary(
            name=str(row["sampleid"]),
            group=user.group,
            submitter=user,
            priority=priority_map[row.get("priority", "low").lower()],
            submitted_species=species,
            submitted_species_name=species.name,
            emails=emails
        )
        summary.clean_fields()
        s_info = m_sample.S_info(summary=summary)
        s_info.clean_fields()
        s_properties = m_sample.S_properties(sample_info=s_info)
        s_properties.clean_fields()
        sample = m_sample.Sample(barcode=row["barcode"],
                                 properties=s_properties,
                                 submitted_on=datetime.datetime.now())
        sample.clean_fields()
        samples.append(sample)

    #Done at the end to prevent crashing mid-save
    m_sample.Sample.objects.bulk_create(samples)

def validate_assign(jsonbody):
    """
    Expects dictionary with fields
    workflow, sample_barcodes, batch_name
    """
    errors = expect(jsonbody, ["plate_type", "workflow", "sample_barcodes", "batch_name"])
    if len(errors):
        return {"missing argument": errors}
    errors = {}

    try:
        workflow_name = jsonbody["workflow"]
        workflow = m_workflow.Workflow.objects.get({"name": workflow_name})
    except pymodm.errors.DoesNotExist:
        errors["workflow"] = "Workflow doesn't exist"
        return errors

    if "step_name" in jsonbody:
        workflow_step_names = [s["name"] for s in workflow.steps_denormalized]
        try:
            i = workflow_step_names.index(jsonbody["step_name"])
            if i == 0:
                prev_step = "root"
            else:
                prev_step = workflow.steps[i - 1].category
        except ValueError:
            errors["step_name"] = "Invalid step {} for workflow {}".format(jsonbody["step_name"], jsonbody["workflow"])


    if len(jsonbody["sample_barcodes"]) == 0:
        errors["sample_barcodes"] = "No samples provided"
    else:
        wrong_samples = []
        already_assigned = []
        errors_step = []
        for s_b in jsonbody["sample_barcodes"]:
            if s_b != "None":
                try:
                    sample = m_sample.Sample.objects.get({"barcode": s_b})
                except pymodm.errors.DoesNotExist:
                    wrong_samples.append(s_b)
                    continue
                for batch in sample.get_batches(workflow_name):
                    if not(jsonbody.get("reorganizing", False) or batch.archived):
                        already_assigned.append(s_b)
                if "step_name" in jsonbody:
                    if (prev_step != "root" and
                        not prev_step in sample.workflows[jsonbody["workflow"]]):
                        errors_step.append(s_b)
        if len(wrong_samples) > 0:
            e_b = "Missing samples: {}".format(",".join(wrong_samples))
            errors["sample_barcodes"] = e_b
        if len(already_assigned) > 0:
            errors["already_assigned"] = "Some samples were already assigned to workflow. ({})".format(",".join(already_assigned))
        if len(errors_step) > 0:
            errors["step"] = "Invalid step for some samples. ({})".format(",".join(errors_step))

    if not m_sample.Sample.validate_field("batch_name", jsonbody["batch_name"]):
        errors["batch_name"] = "Invalid batch name. Name should only have letters, dash (-) or underscore(_)"

    if len(jsonbody["sample_barcodes"]) > m_sample.Sample.plate_size(jsonbody["plate_type"]):
        errors["sample_barcodes_amount"] = "Too many samples for plate size."

    return errors


def validate_unassign(jsonbody):
    errors = {}
    warnings = {}
    workflow_name = None
    batch_name = None
    if "workflow_batch" not in jsonbody:
        errors["workflow_batch"] = "No workflow_batch provided"
    else:
        workflow_name, batch_name = jsonbody["workflow_batch"].split(": ")
        try:
            workflow_name = workflow_name
            m_workflow.Workflow.objects.get({"name": workflow_name})
        except pymodm.errors.DoesNotExist:
            errors["workflow"] = "Workflow doesn't exist"
    if len(jsonbody.get("sample_barcodes", [])) == 0:
        errors["sample_barcodes"] = "No samples provided"
    else:
        wrong_samples = []
        not_assigned = []
        for s_b in jsonbody["sample_barcodes"]:
            try:
                sample = m_sample.Sample.objects.get({"barcode": s_b})
            except pymodm.errors.DoesNotExist:
                wrong_samples.append(s_b)
                continue
            sample_batches = sample.get_batches(workflow_name, batch_name)
            for batch in sample_batches:
                if batch.archived is True:
                    not_assigned.append(s_b)
            if len(sample_batches) == 0:
                not_assigned.append(s_b)
        if len(wrong_samples) > 0:
            e_b = "Missing samples: {}".format(",".join(wrong_samples))
            errors["sample_barcodes"] = e_b
        if len(not_assigned) > 0:
            warnings["not_assigned"] = "Some samples aren't in the specified batch. ({})".format(
                ",".join(not_assigned))
    return errors, warnings

def assign_samples(jsonbody):
    batch_name = jsonbody["batch_name"]
    index = 0
    workflow = m_workflow.Workflow.objects.get({"name": jsonbody["workflow"]})
    plate_type = jsonbody["plate_type"]
    if jsonbody.get("reorganizing", False):
        for i, barcode in enumerate(jsonbody["sample_barcodes"]):
            if barcode != "None":
                sample = m_sample.Sample.objects.get({"barcode": barcode})
                sample.reorganize(workflow, batch_name, i)
    else:
        if "step_name" in jsonbody:
            step_name = jsonbody["step_name"]
            step_index = [s["name"] for s in workflow.steps_denormalized].index(step_name)
            if step_index == 0:
                prev_step_cat = "root"
            else:
                prev_step_cat = workflow.steps[step_index - 1].category
        else:
            prev_step_cat = "root"
        plate_view = m_sample.Sample.get_plate_view(workflow, batch_name, plate_type, barcode_only=True)
        for i, barcode in enumerate(jsonbody["sample_barcodes"]):
            if barcode != "None":
                sample = m_sample.Sample.objects.get({"barcode": barcode})
                plate_position = plate_view["free_spots"][i]
                sample.assign_workflow(workflow, batch_name, plate_position, plate_type, prev_step_cat)

def unassign_samples(jsonbody):
    # batch_name = jsonbody["batch_name"]
    # index = 0
    workflow_name, batch_name = jsonbody["workflow_batch"].split(": ")
    workflow = m_workflow.Workflow.objects.get({"name": workflow_name})
    # plate_type = jsonbody["plate_type"]
    for barcode in jsonbody["sample_barcodes"]:
        sample = m_sample.Sample.objects.get({"barcode": barcode})
        sample.unassign_workflow(workflow, batch_name)


def samples_overview(user):
    samples = []
    if user.has_permission("see_all_samples"):
        samples_db = m_sample.Sample.objects.raw({})
    else:
        group = user.group
        samples_db = m_sample.Sample.objects.raw({"properties.sample_info.summary.group": group})
    species_options = Species.get_name_list()
    columns = [
        {
            "data": "none",
            "type": "hidden"
        },
        {
            "data": "barcode",
            "title": "barcode",
            "readonly": "true",
            "unique": "true",
            "name": "barcode"
        },
        {
            "data": "name",
            "title": "name",
            "name": "name"
        },
        {
            "data": "submitted_on",
            "title": "Submission date",
            "readonly": "true",
            "name": "submitted_on"
        },
        {
            "data": "priority",
            "title": "Priority",
            "type": "select",
            "options": {"low": "Low", "high": "High"},
            "name": "priority"
        },
        {
            "data": "species",
            "title": "species",
            "type": "select",
            "options": species_options,
            "name": "species"

        },
        {
            "data": "group",
            "title": "supplying_lab",
            "name": "group"
        },
        {
            "data": "batch",
            "title": "batch",
            "type": "select",
            "multiple": "true",
            "readonly": "true",
            "name": "batch"
        },
        {
            "data":"genome_size",
            "title": "Genome size",
            "readonly": "true",
            "name": "genome_size"
        },
        {
            "data": "archived",
            "title": "archived",
            "type": "select",
            "options": ["true", "false"],
            "name": "archived"

        }
    ]
    for sample in samples_db:
        samples.append(sample.summary("datatable"))

    return {
        "samples": samples,
        "columns": columns,
        "workflows": m_workflow.Workflow.get_workflows(),
    }

def archived_samples():
    return {
        "columns": [
            {"name": "barcode"},
            {"name": "species"},
            {"name": "name"},
            {"name": "group"},
            {"name": "batch"},
            {"name": "archived"},
        ],
        "species": Species.get_name_list()
    }

def archive_samples(sample_barcodes, archive):
    samples = m_sample.Sample.objects.raw({"barcode": {"$in": sample_barcodes}})
    for sample in samples:
        sample.archived = archive
        sample.save()
    

## Views data

def get_assign_view(sample_barcodes, workflow_name,
                    batch_name, plate_type, suggested_step):
    """
    Get necessary info to render assign view: samples and available workflows.
    """

    workflow = m_workflow.Workflow.objects.get({"name": workflow_name})

    plate_view = m_sample.Sample.get_plate_view(workflow, batch_name,
                                                plate_type, True)
    total_in_plate = m_sample.Sample.plate_size(plate_type)

    samples = []
    i = 1
    steps = workflow.steps
    step_i = len(steps) - 1
    for sample in m_sample.Sample.objects.raw({"barcode": {"$in": sample_barcodes}}):
        s = sample.summary()
        s["seq"] = i
        samples.append(s)
        i += 1
        # Find the latest step that was finished in all samples
        found = False
        while step_i != 0 and found is False:
            if workflow.name not in sample.workflows:
                step_i = 0
                found = True
            elif steps[step_i].category in sample.workflows[workflow.name]:
                found = True
            else:
                step_i -= 1
    if len(samples) < total_in_plate:
        for i in range(total_in_plate - len(samples)):
            samples.append({
                    "seq": len(samples) + 1,
                    "barcode": None,
                    "species": "",
                    "group": ""
                })
    possible_starting_steps = [s["name"] for s in workflow.steps_denormalized[:step_i + 2]]

    columns = [
        {
            "id": "seq",
            "name": "Order"
        },
        {
            "id": "barcode",
            "name": "barcode"
        },
        {
            "id": "species",
            "name": "species",
        },
        {
            "id": "group",
            "name": "group",
        },
    ]
    return {
        "plate_view": plate_view,
        "samples": samples,
        "columns": columns,
        "workflow_name": workflow_name,
        "batch_name": batch_name,
        "possible_starting_steps": possible_starting_steps,
        "suggested_step": suggested_step,
        "reorganizing": False
    }

def reorganize_plate(workflow_name, batch_name):
    """
    Returns data for /samples/reorganize_plate
    """

    workflow = m_workflow.Workflow.objects.get({"name": workflow_name})

    plate_view = m_sample.Sample.get_plate_view(workflow, batch_name,
                                                plate=None, barcode_only=True)
    samples = []
    # Transpose the plate
    plate = zip(*plate_view["plate"])
    for row in plate:
        for s_b in row:
            if s_b is not None:
                sample = m_sample.Sample.objects.get({"barcode": s_b})
                summary = sample.summary()
                summary["seq"] = len(samples) + 1
                samples.append(summary)
            else:
                samples.append({
                    "seq": len(samples) + 1,
                    "barcode": None,
                    "species": "",
                    "group": ""
                })

    # Empty the plate as it is defined by the user again
    plate_view["plate"] = [[None for i in range(len(plate_view["plate"][0]))] 
                                 for j in range(len(plate_view["plate"]))]

    columns = [
        {
            "id": "seq",
            "name": "Order"
        },
        {
            "id": "barcode",
            "name": "barcode"
        },
        {
            "id": "species",
            "name": "species",
        },
        {
            "id": "group",
            "name": "group",
        }
    ]
    return {
        "columns": columns,
        "plate_view": plate_view,
        "workflow_name": workflow.name, 
        "batch_name": batch_name,
        "samples": samples,
        "reorganizing": True
    }

def data_source(ra, user):
    # Pagination
    start = ra.get("start", type=int)
    length = ra.get("length", type=int)

    # Ordering
    orderby = ra.get("order[0][column]", type=int)
    orderbyname = ra.get("columns[{}][data]".format(orderby), type=str)
    orderdir = ra.get("order[0][dir]", type=str)
    if orderdir == "asc":
        orderbydir = 1
    elif orderdir == "desc":
        orderbydir = -1
    else:
        return {"error": "Orderby direction not valid"}
    if orderbyname not in ["barcode", "species", "group", "batch"]:
        return {"error": "Orderby column '{}' not valid".format(orderbyname)}

    orderbypath_dict = {
        "barcode": "barcode",
        "species": "properties.sample_info.summary.submitted_species_name",
        "group": "properties.sample_info.summary.group"
    }
    orderbypath = orderbypath_dict[orderbyname]

    # Search 
    searchstr = ra.get("search[value]", type=str)
    if searchstr:
        qry = {
            "$text": {"$search": searchstr},
            "archived": True
        }
    else:
        qry = {"archived": True}

    allqry = {}
    if not user.has_permission("see_all_samples"):
        group = user.group
        qry["properties.sample_info.summary.group"] = group
        allqry["properties.sample_info.summary.group"] = group

    samples = m_sample.Sample.objects.raw(qry).order_by([(orderbypath, orderbydir)]).skip(start).limit(length)
    samples_total = m_sample.Sample.objects.raw(allqry).count()

    rows = []
    i = 0
    for sample in samples:
        summary = sample.summary()
        summary["DT_RowId"] = "row_" + str(i)
        summary["DT_RowData"] = {"pkey": i}
        rows.append(summary)
        i += 1

    data = {
    "draw": ra.get('draw', default=1, type=int),
    "recordsTotal": samples_total,
    "recordsFiltered": samples_total,
    "data": rows
    }
    return data

# sample info editing


def validate_sample_update(jsonbody):
    errors = {}


    # Missing columns
    columns = ["barcode", "species", "group", "name", "archived",
               "submitted_on", "priority", "batch", "genome_size"]

    missing_col = []
    for column in columns:
        if column not in jsonbody:
            missing_col.append("Missing column {}".format(column))
    if len(missing_col):
        errors["missing_column"] = missing_col

    # Barcode
    if "barcode" in jsonbody:
        sample = None
        try:
            sample = m_sample.Sample.objects.get({"barcode" : jsonbody["barcode"]})
        except pymodm.errors.DoesNotExist:
            errors["wrong_barcode"] = ["Wrong barcode."]

    
    # Species
    if "species" in jsonbody:
        try:
            sample = Species.objects.get({"name" : jsonbody["species"]})
        except pymodm.errors.DoesNotExist:
            errors["wrong_species"] = ["Species doesn't match species in database."]

    for col in jsonbody:
        if not m_sample.Sample.validate_field(col, jsonbody[col]):
            errors["validate_field_{}".format(col)] = ["Invalid field value."]

    return errors


def sample_update(jsondata):
    sample = m_sample.Sample.objects.get({"barcode": jsondata["barcode"]})
    
    # check which fields changed
    # species
    if jsondata["species"] != sample.properties.sample_info.summary.submitted_species_name:
        new_species = Species.objects.get({"name": jsondata["species"]})
        sample.update("species", new_species)

    # group
    if jsondata["group"] != sample.properties.sample_info.summary.group:
        sample.update("group", jsondata["group"])

    # name
    if jsondata["name"] != sample.properties.sample_info.summary.name:
        sample.update("name", jsondata["name"])

    # priority
    if jsondata["priority"] != sample.properties.sample_info.summary.priority:
        sample.update("priority", jsondata["priority"])

    # archived
    if jsondata["archived"] != sample.archived:
        sample.update("archived", jsondata["archived"])

    sample.save()

    return jsondata


def get_sample_details(sample_barcode, user):
    """
    Gets sample metadata and workflow results for sample details page.
    """
    if user.has_permission("samples_see_all"):
        sample = m_sample.Sample.objects.get({"barcode": sample_barcode})
    else:
        sample = m_sample.Sample.objects.get({"barcode": sample_barcode, 
                                              "properties.sample_info.summary.group": user.group})
    return {
        "sample": sample.detail_data()
    }

def validate_results_report(jsondata):
    errors = {}

    missing = expect(jsondata, ["sample_barcodes", "workflow_batch"])
    if len(missing):
        errors["missing_parameters"] = "Missing parameters {}".format(",".join(missing))
        return errors

    missing_barcodes = []
    for s_b in jsondata["sample_barcodes"]:
        try:
            sample = m_sample.Sample.objects.get({"barcode": s_b})
        except pymodm.errors.DoesNotExist:
            missing_barcodes.append(s_b)
    if len(missing_barcodes):
        errors["sample_barcodes"] = "Missing samples: ({})".format(", ".join(missing_barcodes))
    if not ": " in jsondata["workflow_batch"]:
        errors["workflow_batch"] = "Invalid workflow_batch"
    return errors


def get_results_report(jsondata):
    import pandas
    sample_data = []
    workflow_name, batch_name = jsondata["workflow_batch"].split(": ")
    for s_b in jsondata["sample_barcodes"]:
        sample = m_sample.Sample.objects.get({"barcode": s_b})
        sample_data.append(sample.result_report(workflow_name, batch_name))
    df = pandas.DataFrame(sample_data)
    tmp = fileutils.Tempfile()
    df.to_csv(tmp.filehandle.name, index=False)
    _id = tmp.save("miniLIMS_report_{}.csv".format(datetime.date.today()), temp=True)
    return url_for('lims.getfile', fileid=_id)

def barcode_view(user):
    group = user.group
    bp = BarcodeProvider(group)
    return {
        "group": group,
        "last_barcode": bp.last_provided()
    }
