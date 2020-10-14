from minilims.models.counter import BarcodeProvider
from flask import current_app
from minilims.models.species import Species
from minilims.models.sample import Sample
from pymodm.errors import DoesNotExist




### Validation parameters
required_columns = ["sampleid", "barcode", "organism"]
valid_columns = required_columns + ["emails", "priority", "supplydate",
                                    "costcenter", "comments"]
species_col = "organism"

dont_validate_columns = ["supplydate"] #Not stored


###

def validate(json, user):
    priority_map = {v: k for k, v in current_app.config["PRIORITY"].items()}
    errors = {}
    json, row_errors = validate_rows(json, user.group, priority_map)
    if row_errors:
        errors["rows"] = row_errors
    general_errors = validate_barcodes(json)
    if general_errors:
        errors["general"] = general_errors
    return errors


def validate_rows(json, group, priority_map):
    errors = {}
    lowercase_table = []
    for i in range(len(json)):
        row = json[i]
        # Convert keys to lowercase
        lowercase_row = {}
        original_len = len(row.keys())
        for key, value in row.items():
            lowercase_row[key.lower()] = value
        row = lowercase_row
        lowercase_table.append(lowercase_row)
        row_errors = validate_columns(row, original_len)
        row_errors.extend(validate_fields(row, priority_map))
        row_errors.extend(validate_species(row))
        row_errors.extend(validate_barcode(row, group))
        if row_errors:
            errors[str(i + 1)] = row_errors
    return lowercase_table, errors

def validate_species(row):
    
    if species_col in row:
        r_spe = row[species_col]
        try:
            species = Species.objects.get({"name": r_spe})
        except DoesNotExist:
            try:
                species = Species.objects.get({"alias": r_spe})
            except DoesNotExist:
                return ["Species {} not in database. Contact admin.".format(r_spe)]
    return []


def validate_barcode(row, group):
    errors = []
    if "barcode" in row:
        r_bar = row["barcode"]
        raised = False
        try:
            sample = Sample.objects.get({"barcode":r_bar})
        except DoesNotExist:
            raised = True
        if not raised:
            errors.append(f"Barcode {r_bar} already exists in the db. Duplicates are not allowed.")
        if current_app.config["LIMIT_SUBMITTED_BARCODES_TO_PROVIDED"]:
            bp = BarcodeProvider(group)
            if not bp.has_been_provided(r_bar):
                errors.append(f"Invalid barcode {r_bar}. It has not been provided. Go to the Barcodes section to request barcodes if needed.")
    return errors


def validate_columns(row, original_len):
    """
    Validate that all columns are there. We use only the first row as
    the json generator should include all columns in each row
    """
    errors = []
    columns = row.keys()
    if len(columns) != original_len:
        errors.append("At least one column is duplicate (with different casing)")
    extra = list(set(columns) - set(valid_columns))
    missing = list(set(required_columns) - set(columns))
    if extra:
        errors.append("Invalid extra column(s): {}".format(extra))
    if missing:
        errors.append("Missing required column(s): {}".format(missing))
    return errors

def validate_barcodes(json):
    dupes = []
    barcodes = []
    for row in json:
        if "barcode" in row:
            if row["barcode"] in barcodes:
                dupes.append(row["barcode"])
            else:
                barcodes.append(row["barcode"])
    if len(dupes):
        return ["Duplicate barcodes: {}".format(dupes)]
    return []


def validate_fields(row, priority_map):
    """
    Validate all fields in a row using Sample.validate
    """
    errors = []
    for col, value in row.items():
        # Map priority "name" to "number" i.e. "low" to 1, as defined in config.PRIORITY
        if col == "priority":
            value = priority_map[value.lower()]
        if col not in dont_validate_columns and not Sample.validate_field(col, value):
            errors.append("Invalid value for field {} ({})".format(col, value))
    return errors