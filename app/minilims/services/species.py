from minilims.models.species import Species
from minilims.utils import expect
from pymodm.errors import DoesNotExist



def get_species_view():
    species_list = Species.objects.raw({})
    rows = []
    columns = [
        {
            "name": "name",
            "title": "name",
            "data": "name",
            "unique": True,
            "type": "text",
            "pattern": "[\\\\w\\\\s\\\\.]+",  # Four backslash convert to one when in JS.
            "hoverMsg": "Can only contain letters, spaces or periods."
        },
        {
            "name": "aliases",
            "title": "aliases (comma separated)",
            "data": "aliases",
            "type": "text",
        }
    ]
    step_columns = []
    for species in species_list:
        summary = species.summary()
        for column in summary:
            # if column not in step_columns and column not in ["name", "aliases"]:
                # step_columns.append(column)
            if column == "v":
                for w_name, steps in summary["v"].items():
                    for s_name, fields in steps.items():
                        for field in fields:
                            column_name = f"v.{w_name}.{s_name}.{field}"
                            if column_name not in step_columns:
                                step_columns.append(column_name)
        rows.append(summary)
    colums = columns + [{"title": c, "data": c} for c in step_columns]
    return {
        "rows": rows,
        "columns": colums
    }

def validate_species_delete(jsondata):
    missing = expect(jsondata, ["name"])
    if len(missing):
        return {"missing values": [f"Missing values: {missing}"]}
    s_name = jsondata["name"]
    try:
        found_species = Species.objects.get({"name": s_name})
    except DoesNotExist:
        return {"not_found": [f"Species {s_name} not found"]}
    return {}


def validate_species(jsondata, method):
    missing = expect(jsondata, ["name", "aliases"])
    if len(missing):
        return {"missing values": [f"Missing values: {missing}"]}
    
    errors = {}

    aliases = [s.strip() for s in jsondata["aliases"].split(",")]
    if method == "PUT":
        for name in [jsondata["name"]] + aliases:
            try:
                Species.objects.get({"$or": [{"name": name}, {"alias": name}]})
            except DoesNotExist:
                pass
            else:
                errors["name"] = [f"Name/alias {name} already exists in the database as name or alias"]
    elif method == "POST":
        s_name = jsondata["name"]
        try:
            found_species = Species.objects.get({"name": s_name})
        except DoesNotExist:
            errors["not_found"] = [f"Species {s_name} not found"]
        for name in [s_name] + aliases:
            try:
                Species.objects.get({"$and": [{"$or": [{"name": name}, {"alias": name}]}, {"name": {"$ne": s_name}}]})
            except DoesNotExist:
                pass
            else:
                errors["name"] = [f"Name/alias {name} already exists in the database as name or alias"]

    for key, value in jsondata.items():
        if key not in ["name", "aliases", "editRow"]:
            if len(key.split(".")) != 4:
                errors[f"invalid_field_{key}"] = [f"Field {key} was unexpected. Contact Admin."]
            if len(value) == 0:
                errors[f"empty_value_{key}"] = [f"Field {key} contains an empty value {value}"]

    return errors

def species_put(jsondata):
    step_variables = {}
    for field, value in jsondata.items():
        if field == "name":
            name = value
        elif field == "aliases":
            alias = [s.strip() for s in jsondata["aliases"].split(",")]
        else:
            _, workflow_name, step_name, field_name = field.split(".")
            # Save variable in the right place in the dict tree. Create subdictionaries as needed.
            workflow_dict = step_variables.get(workflow_name,{})
            step_dict = workflow_dict.get(step_name,{})
            step_dict[field_name] = value
            workflow_dict[step_name] = step_dict
            step_variables[workflow_name] = workflow_dict
    new_species = Species(name=name, alias=alias,
                          step_variables=step_variables).save()

    return new_species.summary()

def species_edit(jsondata):
    species = Species.objects.get({"name": jsondata["name"]})
    species.alias = [s.strip() for s in jsondata["aliases"].split(",")]
    step_variables = {}
    for key, value in jsondata.items():
        if key.startswith("v."):
            _, workflow_name, step_name, field_name = key.split(".")
            # Save variable in the right place in the dict tree. Create subdictionaries as needed.
            workflow_dict = step_variables.get(workflow_name,{})
            step_dict = workflow_dict.get(step_name,{})
            step_dict[field_name] = value
            workflow_dict[step_name] = step_dict
            step_variables[workflow_name] = workflow_dict
    species.step_variables = step_variables
    species.save()
    return species.summary()


def species_delete(jsondata):
    Species.objects.get({"name": jsondata["name"]}).delete()
