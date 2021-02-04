from minilims.models.counter import BarcodeProvider
from flask import current_app
from minilims.models.species import Species
from minilims.models.sample import Sample
from pymodm.errors import DoesNotExist


def validate(json, user):
    validation_config = current_app.config["SAMPLESHEET_COLUMNS"]
    priority_map = {v: k for k, v in current_app.config["PRIORITY"].items()}
    errors = {}
    warnings = {}
    # print("precustom", json)
    # json, conflicting_column_names = map_column_names(json, validation_config["custom_mapping"])
    # print("postcustom", json)
    # if conflicting_column_names:
    #     errors["conflicting_columns"] = conflicting_column_names
    json, row_errors, extra_columns = validate_rows(json, user.group, priority_map, validation_config)
    if row_errors:
        errors["rows"] = row_errors
    general_errors = validate_barcodes(json)
    if general_errors:
        errors["general"] = general_errors
    if extra_columns:
        warnings["general"] = ["Extra columns: " + ",".join(extra_columns)]
    return {
        "errors": errors,
        "warnings": warnings
    }


def map_column_names(json, custom_mapping):
    if len(custom_mapping.keys()) == 0:
        return json, []
    updated_json = []
    conflicting_column_names = []
    for row in json:
        for colname, customname in custom_mapping.items():
            colname_in_row = colname in row
            customname_in_row = customname in row
            if colname_in_row and customname_in_row:
                conflicting_column_names.append((colname, customname))
            if customname_in_row:
                row[colname] = row["customname"]
                del row[customname]
        updated_json.append(row)
    return updated_json, conflicting_column_names


def validate_rows(json, group, priority_map, validation_config):
    errors = {}
    lowercase_table = []
    reverse_custom_mapping = {v: k for k, v in validation_config["custom_mapping"].items()}
    extra_columns = set()
    for i in range(len(json)):
        row = json[i]
        # Convert keys to lowercase
        lowercase_row = {}
        original_len = len(row.keys())
        for key, value in row.items():
            # Switch to lowecase and replace custom columns
            colname = reverse_custom_mapping.get(key, key.lower())
            lowercase_row[colname] = value
        row = lowercase_row
        lowercase_table.append(lowercase_row)
        row_errors, extra_columns = validate_columns(row, original_len, validation_config, extra_columns)
        row_errors.extend(validate_fields(row, priority_map, validation_config))
        row_errors.extend(validate_species(row))
        row_errors.extend(validate_barcode(row, group))
        if row_errors:
            errors[str(i + 1)] = row_errors
    return lowercase_table, errors, extra_columns


def validate_species(row):
    species_col = "organism"
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
    barcode_col = "barcode"
    if barcode_col in row:
        r_bar = row[barcode_col]
        raised = False
        try:
            sample = Sample.objects.get({barcode_col: r_bar})
        except DoesNotExist:
            raised = True
        if not raised:
            errors.append(f"Barcode {r_bar} already exists in the db. Duplicates are not allowed.")
        if current_app.config["LIMIT_SUBMITTED_BARCODES_TO_PROVIDED"]:
            bp = BarcodeProvider(group)
            if not bp.has_been_provided(r_bar):
                errors.append((f"Invalid barcode {r_bar}. It has not been provided. Go to the Barcodes"
                               " section to request barcodes if needed."))
    return errors


def validate_columns(row, original_len, validation_config, extra_columns):
    """
    Validate that all columns are there.
    """
    errors = []
    columns = row.keys()
    if len(columns) != original_len:
        errors.append("At least one column is duplicate (with different casing)")
    valid_columns = (validation_config["required"] +
                     validation_config["optional"]["validate"] +
                     validation_config["optional"]["dont_validate"])
    extra = set(columns) - set(valid_columns)
    missing = list(set(validation_config["required"]) - set(columns))
    if extra:
        extra_columns = extra_columns | extra
    if missing:
        errors.append("Missing required column(s): {}".format(missing))
    return errors, extra_columns


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


def validate_fields(row, priority_map, validation_config):
    """
    Validate all fields in a row using Sample.validate
    """
    errors = []
    for col, value in row.items():
        # Map priority "name" to "number" i.e. "low" to 1, as defined in config.PRIORITY
        if col == "priority":
            value = priority_map[value.lower()]
        if col in validation_config["optional"]["validate"] or col in validation_config["required"]:
            if not Sample.validate_field(col, value):
                errors.append("Invalid value for field {} ({})".format(col, value))

    return errors
