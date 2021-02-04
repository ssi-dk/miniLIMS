import re
import datetime
from flask import current_app
from pymodm import MongoModel, fields, EmbeddedMongoModel, errors, connection

from pymongo.write_concern import WriteConcern
from pymongo.operations import IndexModel
from pymongo import TEXT

from minilims.models.user import User
from minilims.models.step import Step
from minilims.models.tag import Tag
from minilims.models.species import Species
from minilims.models.workflow import Workflow
import minilims.errors
import bson


class MapField(fields.MongoBaseField):
    """
    A field that maps a string to a specified field type. Similar to
    a fields.DictField, except the values in the dict must match the specified
    field type.
    """
    def __init__(self, field, *args, **kwargs):
        kwargs.setdefault('default', dict)
        super(MapField, self).__init__(*args, **kwargs)
        self.field = field

    def to_python(self, value):
        return {k: self.field.to_python(v) for k, v in value.items()}

    def to_mongo(self, value):
        return bson.SON([(k, self.field.to_mongo(v)) for k, v in value.items()])


class PositionInPlate(EmbeddedMongoModel):
    index = fields.IntegerField(required=True)
    plate_type = fields.CharField(required=True, choices=["96plate"])

    def get_coordinates(self, index=False):
        """
        Returns coordinates (row, column)
        """
        if self.plate_type == "96plate":
            rows = ["A", "B", "C", "D", "E", "F", "G", "H"]
            columns = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
            i = self.index
            if index:
                return (
                    i % len(rows),  # row
                    i // len(rows)  # column
                )
            else:
                return (
                    rows[i % len(rows)],  # row
                    columns[i // len(rows)]  # column
                )
        else:
            return (self.index, 0)


class Batch(EmbeddedMongoModel):
    workflow = fields.ReferenceField(Workflow, required=True)
    step_cat = fields.CharField(required=True)
    batch_name = fields.CharField(required=True)
    batch_created_on = fields.DateTimeField(required=True)
    position = fields.EmbeddedDocumentField(PositionInPlate, required=True)
    archived = fields.BooleanField(required=True, default=False)


class S_summary(EmbeddedMongoModel):  
    name = fields.CharField(required=True)
    group = fields.CharField(required=True)
    submitter = fields.ReferenceField(User, required=True)
    priority = fields.IntegerField(required=True)
    submitted_species = fields.ReferenceField(Species, required=True)
    submitted_species_name = fields.CharField(required=True)
    emails = fields.ListField(field=fields.EmailField(), blank=True)
    costcenter = fields.CharField(required=True, blank=True)
    submission_comments = fields.CharField(required=True, blank=True)
    supplied_plate_name = fields.CharField(required=True, blank=True)
    position_in_supplied_plate = fields.CharField(required=True, blank=True)


class S_info(EmbeddedMongoModel):
    summary = fields.EmbeddedDocumentField(S_summary)


class S_properties(EmbeddedMongoModel):
    sample_info = fields.EmbeddedDocumentField(S_info)


class WorkflowResults(EmbeddedMongoModel):
    parent = fields.CharField(blank=True)
    status = fields.CharField(required=True, choices=["started", "finished"])
    step_instance = fields.ReferenceField("Step_instance", mongo_name="_step_instance", blank=True)
    start_date = fields.DateTimeField(required=True)
    finish_date = fields.DateTimeField()
    all = fields.DictField()
    sample = fields.DictField()
    batch_name = fields.CharField()
    index = fields.IntegerField()


class Sample(MongoModel):
    barcode = fields.CharField(required=True)
    tags = fields.ListField(fields.ReferenceField(Tag), blank=True)
    properties = fields.EmbeddedDocumentField(S_properties, required=True)
    batches = fields.EmbeddedDocumentListField(Batch)
    workflows = MapField(MapField(fields.EmbeddedDocumentListField(WorkflowResults)))
    submitted_on = fields.DateTimeField(required=True)
    archived = fields.BooleanField(required=True, default=False)
    comments = fields.CharField(default="", blank=True, required=True)

    class Meta:
        write_concern = WriteConcern(j=True)
        indexes = [
            IndexModel([("barcode", 1)], unique=True),
            IndexModel([
                ("barcode", TEXT),
                ("properties.sample_info.summary.name", TEXT),
                ("properties.sample_info.summary.submitted_species_name", TEXT),
                ("properties.sample_info.summary.emails", TEXT),
                ("properties.sample_info.summary.group", TEXT),
                ("workflows.*.root.0.sample.batch_name", TEXT)
            ], name="textindex")
        ]

    @staticmethod
    def plate_size(plate):
        if plate == "96plate":
            return 96

    @staticmethod
    def _validate_type(type_, value):
        if type_ == "basicalphanum":
            value = str(value)
            return not bool(re.compile(r'[^A-Za-z0-9]').search(value))
        elif type_ == "alphanum":
            value = str(value)
            return not bool(re.compile(r'[^A-Za-z0-9_\-]').search(value))
        elif type_ == "species":
            value = str(value)
            return not bool(re.compile(r'[^A-Za-z\. ]').search(value))
        elif type_ == "barcode":
            value = str(value)
            return not bool(re.compile(r'[^A-Za-z0-9_\-]').search(value))
        elif type_ == "email":
            value = str(value)
            # from emailregex.com
            return bool(re.compile(r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)").search(value))
        elif type_ == "boolean":
            return isinstance(value, bool)

    @staticmethod
    def validate_field(field, value):
        """
        Returns false if the field is not valid.
        """
        if field == "species":
            return True  # valid if in species list.
        elif field == "group":  # This for now, but should be validated in full list of groups.
            return Sample._validate_type("alphanum", value)
        elif field in ("name", "sampleid", "barcode", "batch_name"):
            return Sample._validate_type("barcode", value)
        elif field == "emails":
            email_list = re.split("[;,\s]+", value)
            for e in email_list:
                if not Sample._validate_type("email", e):
                    return False
            return True
        elif field == "archived":
            if value == "True":
                value = True
            elif value == "False":
                value = False
            return Sample._validate_type("boolean", value)
        elif field == "organism":
            return Sample._validate_type("species", value)
        elif field == "priority":
            try:
                return 1 <= int(value) <= 4
            except ValueError:
                return False
        elif field == "tags":
            return Tag.validate_field(value)
        elif field in ["comments", "costcenter", "submission_comments", "supplyinglab"]:
            # Always valid
            return True
        else:
            return False

    @staticmethod
    def columns(template, species_options=None, custom_mapping=None):
        from minilims.models.species import Species
        columns = {
            "submit": [
                {
                    "data": "SampleID",
                    "unique": True,
                    "required": True
                },
                {
                    "data": "Barcode",
                    "unique": True,
                    "required": True
                },
                {
                    "data": "Organism",
                    "type": "select",
                    "options": Species.get_name_list(alias=True),
                    "required": True
                },
                {
                    "defaultContent": "",
                    "data": "Emails"
                },
                {
                    "defaultContent": "",
                    "data": "Priority",
                    "type": "select",
                    "options": ["low", "high"],
                    "required": True,
                },
                # {
                #     "defaultContent": "",
                #     "data": "SupplyDate",
                # },
                {
                    "defaultContent": "",
                    "data": "Costcenter"
                },
                {
                    "data": "PlateName",
                    "defaultContent": "",
                },
                {
                    "data": "WellPositionInSuppliedPlate",
                    "defaultContent": "",
                },
                {
                    "defaultContent": "",
                    "data": "Comments",
                    "type": "textarea"
                }
            ],
            "sample_list_view": [
                {
                    "data": "none",
                    "type": "hidden"
                },
                {
                    "data": "barcode",
                    "title": "barcode",
                    "readonly": "true",
                    "unique": "true",
                    "name": "barcode",
                },
                {
                    "data": "tags",
                    "title": "tags",
                    "type": "select",
                    "multiple": "true",
                    "options": [str(x.pk) for x in Tag.objects.project({"_id": 1}).all()],
                    "name": "tags"
                },
                {
                    "data": "submitted_on",
                    "title": "Submission date",
                    "readonly": "true",
                    "name": "submitted_on"
                },
                {
                    "data": "name",
                    "title": "SampleID",
                    "name": "name"
                },
                {
                    "data": "priority",
                    "title": "Priority",
                    "type": "select",
                    "options": current_app.config["PRIORITY"],
                    "name": "priority",
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
                    "data": "costcenter",
                    "title": "Cost Center",
                    "name": "costcenter"
                },
                {
                    "data": "batch",
                    "title": "batch",
                    # "type": "select",
                    # "multiple": "true",
                    "readonly": "true",
                    "name": "batch"
                },
                {
                    "data": "genome_size",
                    "title": "Genome size",
                    "readonly": "true",
                    "name": "genome_size",
                    
                },
                {
                    "data": "supplied_plate_name",
                    "title": "Supplied Plate Name",
                    "readonly": "true",
                    "name": "supplied_plate_name"
                },
                {
                    "data": "position_in_supplied_plate",
                    "title": "Position in Supplied Plate",
                    "readonly": "true",
                    "name": "position_in_supplied_plate"
                },
                {
                    "data": "submission_comments",
                    "title": "Submission Comments",
                    "readonly": "true",
                    "name": "submission_comments"
                },
                {
                    "data": "comments",
                    "title": "Comments",
                    "name": "comments"
                },
                {
                    "data": "archived",
                    "title": "archived",
                    "type": "select",
                    "options": ["True", "False"],
                    "name": "archived"
                }
            ]
        }
        if template == "submit" and custom_mapping is not None:
            customized_columns = []
            for coldata in columns[template]:
                data_l = coldata["data"].lower()
                # change only if in mapping
                coldata["data"] = custom_mapping.get(data_l, coldata["data"])
                coldata["title"] = custom_mapping.get(data_l, coldata["data"])
                customized_columns.append(coldata)
            return customized_columns

        return columns[template]

    @classmethod
    def searchbox_suggestion(cls, query):
        if cls.validate_field("barcode", query):
            samples = cls.objects.raw({"barcode": {"$regex": query}}).project({"barcode": 1, "_id": 0}).limit(10)
            return [sample.barcode for sample in samples]
        else:
            return []

    @classmethod
    def get_batch_names(cls, query=None, workflow_name=None):
        if query is None:
            return cls.objects.raw({})._collection.distinct("batches.batch_name")
        else:
            try:
                workflow = Workflow.objects.get({"name": workflow_name})
            except errors.DoesNotExist:
                workflow = None
            if cls.validate_field("barcode", query) and workflow is not None:
                batches = cls.objects.aggregate(
                    {
                        "$unwind": {
                            "path": "$batches"
                        }
                    },
                    {
                        "$match": {
                            "batches.workflow": workflow._id
                        }
                    },
                    {
                        "$group": {
                            "_id": "$batches.batch_name"
                        }
                    }
                )
                return [x["_id"] for x in batches]
            else:
                return []

    @classmethod
    def get_batch_overview(cls):
        overview_query = list(cls.objects.aggregate(
            {
                "$match": {
                    "archived": False
                }
            },
            {
                "$unwind": {
                    "path": "$batches"
                }
            },
            {
                "$group": {
                    "_id": {
                        "batch_name": "$batches.batch_name",
                        "workflow_id": "$batches.workflow",
                        "step_cat": "$batches.step_cat",
                        "plate_type": "$batches.position.plate_type"
                    },
                    "count": {
                        "$sum": 1.0
                    },
                    "batch_created_on": {
                        "$min": "$batches.batch_created_on"
                    }
                }
            },
            {
                "$group": {
                    "_id": {
                        "batch_name": "$_id.batch_name",
                        "workflow_id": "$_id.workflow_id",
                        "plate_type": "$_id.plate_type"
                    },
                    "count": {
                        "$sum": "$count"
                    },
                    "batch_created_on": {
                        "$min": "$batch_created_on"
                    },
                    "steps": {"$push": "$$ROOT"}
                }
            },
            {
                "$group": {
                    "_id": "$_id.workflow_id",
                    "batches": {"$push": "$$ROOT"},
                    "count": {"$sum": "$count"}
                }
            },
            {
                "$lookup": {
                    "from": "workflow",
                    "localField": "_id",
                    "foreignField": "_id",
                    "as": "workflow"
                }
            },
            {
                "$project": {
                    "_id": 1,
                    "batches._id.batch_name": 1,
                    "batches._id.plate_type": 1,
                    "batches._id.step_cat": 1,
                    "batches.count": 1,
                    "batches.batch_created_on": 1,
                    "count": 1,
                    "batches.steps.count": 1,
                    "batches.steps._id.step_cat": 1,
                    "name": {"$arrayElemAt": ["$workflow.name", 0]}
                }
            }
        ))
        for workflow in overview_query:
            # Dict to cache step names to avoid multiple queries for the same name.
            step_cache = {}
            workflow_db = Workflow.objects.get({"_id": workflow["_id"]})
            workflow["_id"] = str(workflow["_id"])
            workflow["display_name"] = workflow_db.display_name
            for batch in workflow["batches"]:
                step_i = 0
                step_entries = []
                # The first step of the list that has partial count will be finished,
                # the rest will be partially finished so this should be false for them.
                first_finished_true = False
                if batch["steps"][step_i]["_id"]["step_cat"] == "root":
                    step_entries.append({"step_name": "root",
                                         "step_d_name": "Assigned",
                                         "count": batch["steps"][step_i]["count"],
                                         "finished": True})
                    step_i += 1
                    first_finished_true = True
                steps_progress = [0, len(workflow_db.steps)]
                for step in workflow_db.steps:
                    # Check if step is in dict cache before querying
                    if step.pk not in step_cache:
                        step_cache[str(step.pk)] = {
                            "d_name": step.display_name, 
                            "cat": step.category,
                            "name": step.name}
                    step_data = step_cache[str(step.pk)]

                    if step_i < len(batch["steps"]) and batch["steps"][step_i]["_id"]["step_cat"] == step_data["cat"]:
                        if not first_finished_true:
                            finished = True
                            first_finished_true = True
                            steps_progress[0] += 1
                        else:
                            finished = False
                        step_entries.append({
                            "step_d_name": step_data["d_name"],
                            "step_name": step_data["name"],
                            "count": batch["steps"][step_i]["count"],
                            "finished": finished
                        })
                        step_i += 1
                    else:
                        if not first_finished_true:
                            finished = True
                            steps_progress[0] += 1
                        else:
                            finished = False
                        step_entries.append(
                            {
                                "step_d_name": step_data["d_name"],
                                "step_name": step_data["name"],
                                "count": 0,
                                "finished": finished
                            })
                batch["steps"] = step_entries
                batch["progress"] = steps_progress

        # overview_query = list(overview_query)
        return overview_query

    @classmethod
    def get_unassigned(cls, count=False, group=None):
        query = {"$or": [{"batches": {"$size": 0}}, {"batches": {"$exists": False}}]}
        if group is not None:
            query["properties.sample_info.summary.group"] = group
        if count:
            return cls.objects.raw(query).count()
        else:
            return cls.objects.raw(query)

    @classmethod
    def get_archived(cls, count=False, group=None):
        query = {"archived": True}
        if group is not None:
            query["properties.sample_info.summary.group"] = group
        if count:
            return cls.objects.raw(query).count()
        else:
            return cls.objects.raw(query)

    @classmethod
    def get_plate_view(cls, workflow, batch_name, plate=None, barcode_only=False):
        """
        Generate plate view object including where samples are.
        """

        if plate is None:
            samples = list(cls.objects.raw({"batches": {"$elemMatch": {"batch_name": batch_name,
                                                                       "workflow": workflow.pk,
                                                                       "archived": False}}}))

            for sample in samples:
                pt = sample.get_batches(workflow.name, batch_name)[0].position.plate_type
                if plate is None:
                    plate = pt
                else:
                    if plate != pt:
                        raise ValueError((f"Some samples belong to different plates in the same batch."
                                          " Workflow: {workflow.name}. Batch: {batch_name}"))

        if plate == "96plate":
            plate_view = {
                "plate": [[None for i in range(12)] for j in range(8)],  # List per row
                "free_spots": [],
                "plate_type": plate
            }
            taken_spots = [False]*96
            for sample in cls.objects.raw({"batches": {"$elemMatch": {"batch_name": batch_name,
                                                                      "workflow": workflow.pk,
                                                                      "archived": False}}}):
                pos = sample.get_batches(workflow.name, batch_name)[0].position
                taken_spots[pos.index] = True
                coord = pos.get_coordinates(True)
                if barcode_only:
                    plate_view["plate"][coord[0]][coord[1]] = sample.barcode
                else:
                    plate_view["plate"][coord[0]][coord[1]] = sample
            for i in range(len(taken_spots)):
                if not taken_spots[i]:
                    plate_view["free_spots"].append(i)
        else:
            return None
        return plate_view

    # @classmethod
    # def get_step_table(cls, sample_ids):

    #     db = connection._get_db()
    #     samples = list(db[cls._mongometa.collection_name].find({
    #         "_id": {"$in": sample_ids}
    #     },{
    #         "barcode": 1,
    #         "comments": 1,
    #         "batches": 1,
    #         "properties.sample_info.summary."
    #         "_id": 0
    #     }))
    #     return samples

    def update(self, field, new_value):
        if field == "species":
            self.properties.sample_info.summary.submitted_species = new_value
            self.properties.sample_info.summary.submitted_species_name = new_value.name
        elif field == "group":
            self.properties.sample_info.summary.group = new_value
        elif field == "name":
            self.properties.sample_info.summary.name = new_value
        elif field == "archived":
            if new_value.lower() == "true":
                new_value = True
            else:
                new_value = False
            self.archived = new_value
        elif field == "priority":
            self.properties.sample_info.summary.priority = new_value
        elif field == "costcenter":
            self.properties.sample_info.summary.costcenter = new_value
        elif field == "comments":
            self.comments = new_value
        elif field == "tags":
            tags = Tag.objects.raw({"_id": {"$in": new_value}})
            self.tags = tags
        else:
            raise ValueError("Field not valid")

    def update_last_workflow(self, workflow, batch_name, step_cat):
        for wlf in self.batches:
            if wlf.workflow == workflow and wlf.batch_name == batch_name:
                wlf.step_cat = step_cat

    def assign_workflow(self, workflow, batch_name, index, plate_type, prev_step_cat):

        batches = self.get_batches(workflow.name, batch_name)
        if len(batches) > 0:
            batch = batches[0]  # Assuming only one archived batch can be here.
            batch.archived = False
            batch.step_cat = prev_step_cat
            batch.position = PositionInPlate(plate_type=plate_type, index=index)
        else:
            wlf = Batch(workflow=workflow,
                        step_cat=prev_step_cat,
                        batch_name=batch_name,
                        batch_created_on=datetime.datetime.now(),
                        position=PositionInPlate(plate_type=plate_type, index=index),
                        archived=False
                        )
            self.batches.append(wlf)
            if prev_step_cat == "root":
                step_i = WorkflowResults(
                    parent=None,
                    sample={},
                    start_date=datetime.datetime.now(),
                    finish_date=datetime.datetime.now(),
                    status="finished",
                    step_instance=None,
                    batch_name=batch_name,
                    index=index
                )
                if workflow.name not in self.workflows:
                    self.workflows[workflow.name] = {"root": [step_i]}
                else:
                    self.workflows[workflow.name]["root"] = [step_i]
        self.save()

    def reorganize(self, workflow, batch_name, new_index):
        batches = self.get_batches(workflow.name, batch_name)
        if len(batches) == 0:
            raise ValueError("Sample tried to be reorganized into a workflow-batch that doesn't exist.")
        else:
            batch = batches[0]
            batch.position.index = new_index
        self.save()

    def unassign_workflow(self, workflow, batch_name):
        """
        Sets the batch as archived
        """
        for batch in self.batches:
            if batch.workflow == workflow and batch.batch_name == batch_name:
                batch.archived = True
        self.save()

    def get_batches(self, workflow_name, batch_name=None):
        """
        Get batches with given name
        """
        if batch_name is None:
            return [b for b in self.batches if b.workflow.name == workflow_name]
        else:
            return [b for b in self.batches if b.batch_name == batch_name and b.workflow.name == workflow_name]

    def finish_step(self, step_instance, save):
        """
        Updates batches
        """
        step_cat = step_instance.step.category
        workflow_name, prev_step = self.get_prev_step(step_cat)
        workflow = Workflow.objects.get({"name": workflow_name})
        self.update_last_workflow(workflow, step_instance.batch, step_cat)
        for i in range(len(self.workflows[workflow_name][step_cat])):
            instance = self.workflows[workflow_name][step_cat][i]
            if step_instance == instance.step_instance:
                self.workflows[workflow_name][step_cat][i].finish_date = datetime.datetime.now()
                self.workflows[workflow_name][step_cat][i].status = "finished"
                self.workflows[workflow_name][step_cat][i].all = step_instance.result_all
                self.workflows[workflow_name][step_cat][i].sample = step_instance.result_samples[self.barcode]
        if save:
            self.save()
        recommended_next = workflow.next_step(step_instance.step.name)
        if recommended_next == "_workflow_finished":
            self.finish_workflow(workflow, step_instance.batch, step_cat)
        return recommended_next

    def find_workflow_for_step(self, step_cat):
        """
        Returns a list of workflows for which this sample contains a result for the given step category.
        Random order.
        """
        workflows = []
        for workflow, steps in self.workflows.items():
            if step_cat in steps.keys():
                workflows.append(workflow)
        return workflows

    def _find_valid_prev_steps(self, next_step):
        """
        Return list of workflows this sample belongs to and 
        this step is a valid option for.
        """
        workflows = []
        for wlf in self.batches:
            prev_step = wlf.step_cat
            workflow = wlf.workflow
            if not wlf.archived:
                valid = workflow.valid_next_step(prev_step, next_step)
                if valid:
                    workflows.append((workflow.name, prev_step))
        return workflows

    def get_prev_step(self, step_name):
        """
        Given a step name return prev step and workflow name. Use this instead of _find_valid_prev_steps.
        Returns (workflow_name, step_name)
        """
        workflows = self._find_valid_prev_steps(step_name)
        if len(workflows) == 0:
            raise ValueError("No workflow available for sample {} and step {}.".format(self.barcode, step_name))
        elif len(workflows) > 1:
            current_app.logger.warning(
                "Sample {} can init step {} in more than one workflow: {}. Choosing first".format(
                    self.barcode, step_name, workflows))
        return workflows[0]

    def valid_next_step(self, next_step, batch_name):
        """
        Checks if the provided step is valid for this sample.
        """
        for batch in self.batches:
            if not batch.archived and batch.batch_name == batch_name:
                workflow = batch.workflow
                last_step = batch.step_cat
                valid_w = workflow.valid_next_step(last_step, next_step)
                if valid_w:
                    return True
        return False

    def send_to_step(self, step_name, workflow_name=None):
        if workflow_name is None:
            step = Step.objects.get({"name": step_name})
            workflows = self.find_workflow_for_step(step.category)
            if len(workflows) == 1:
                workflow_name = workflows[0]
            elif len(workflows) == 0:
                raise ValueError("No workflow available for sample {} and step {}.".format(self.barcode, step_name))
            else:
                current_app.logger.warning(
                    "Sample {} can init step {} in more than one workflow: {}. Choosing first".format(
                        self.barcode, step_name, workflows))
                workflow_name = workflows[0]
        workflow = Workflow.objects.get({"name": workflow_name})
        prev_step = workflow.get_prev_step(step_name)
        if prev_step is None:
            raise ValueError("No workflow available for sample {} and step {}.".format(self.barcode, step_name))
        self.update_last_workflow(workflow, prev_step)
        self.save()

    def init_step(self, step_instance):
        """
        Initialises step in sample. If step can belong to more than
        one workflow the sample is in, throw an error.
        """
        workflow_name, prev_step = self.get_prev_step(step_instance.step.category)
        prev_step_attempts = self.workflows[workflow_name][prev_step]
        instance_index = len(prev_step_attempts) - 1
        batch = self.get_batches(workflow_name, step_instance.batch)
        step_result_sample = WorkflowResults(
            parent="{}.{}.{}".format(workflow_name, prev_step, instance_index),
            status="started",
            step_instance=step_instance._id,
            start_date=datetime.datetime.now(),
            batch_name=step_instance.batch,
            index=batch[0].position.index
        )
        step_attempts = self.workflows[workflow_name].get(step_instance.step.category, [])
        step_attempts.append(step_result_sample)
        self.workflows[workflow_name][step_instance.step.category] = step_attempts
        self.save()

        return step_instance.batch

    def result_chain(self, chain, exit_match=None):
        """
        Recursive. From a list with a single WorkflowResults it'll return the full result chain from root.
        Exit match: (workflow_name, step_cat)
        """
        last = chain[-1]
        if last.parent is None:
            return chain
        workflow_name_c, step_cat_c, attempt = last.parent.split(".")
        chain.append(self.workflows[workflow_name_c][step_cat_c][int(attempt)])
        if exit_match is not None and exit_match[0] == workflow_name_c and exit_match[1] == step_cat_c:
            return chain
        return self.result_chain(chain, exit_match)

    def find_result(self, workflow_name, step_cat, scope, field_name, step_instance):
        root = None
        self.refresh_from_db()  # Required
        for attempt in self.workflows[workflow_name][step_instance.step.category]:
            if attempt.step_instance == step_instance:
                root = attempt
        chain = self.result_chain([root], (workflow_name, step_cat))
        try:
            return getattr(chain[-1], scope)[field_name]
        except KeyError:
            raise minilims.errors.MissingValueError(
                "Value (w) {} (s) {} (sc) {} (f) {} for barcode {} not found in results.".format(
                    workflow_name, step_cat, scope, field_name, self.barcode))

    def finish_workflow(self, workflow, batch_name, prev_step_cat):
        step_cat = "_workflow_finished"
        prev_step_attempts = self.workflows[workflow.name][prev_step_cat]
        instance_index = len(prev_step_attempts) - 1
        step_result_sample = WorkflowResults(
            parent="{}.{}.{}".format(workflow.name, prev_step_cat, instance_index),
            status="finished",
            step_instance=None,
            all={},
            sample={},
            start_date=datetime.datetime.now(),
            finish_date=datetime.datetime.now(),
            batch_name=batch_name
        )
        step_attempts = self.workflows[workflow.name].get(step_cat, [])
        step_attempts.append(step_result_sample)
        self.workflows[workflow.name][step_cat] = step_attempts
        self.update_last_workflow(workflow, batch_name, step_cat)
        self.save()

    def summary(self, frmt="dict"):
        batches = []
        positions = {}
        for b in self.batches:
            if not b.archived:
                batches.append("{}: {}".format(b.workflow.name, b.batch_name))
                coord = b.position.get_coordinates()
                workflow_batch = "{}: {}".format(b.workflow.name, b.batch_name)
                positions[workflow_batch] = {
                    "coords": "".join([str(coord[0]), str(coord[1])]),
                    "index": b.position.index
                } 
        if len(batches):
            batch = ", ".join(batches)
        else:
            batch = "Unassigned"

        genome_size = self.properties.sample_info.summary.submitted_species.step_variables.get(
            "wgs_routine", {}).get("wgs_08_normalization_pool", {}).get("genome_size")

        if frmt == "dict":
            result = {
                    "barcode": self.barcode,
                    "name": self.properties.sample_info.summary.name,
                    "group": self.properties.sample_info.summary.group,
                    "species": self.properties.sample_info.summary.submitted_species.name,
                    "batch": batch,
                    "archived": str(self.archived),
                    "submitted_on": self.submitted_on
                }
        elif frmt == "datatable":
            result = {
                    "none": "",  # For checkbox
                    "tags": [x.pk for x in self.tags],
                    "barcode": self.barcode,
                    "name": self.properties.sample_info.summary.name,
                    "group": self.properties.sample_info.summary.group,
                    "species": self.properties.sample_info.summary.submitted_species.name,
                    "batch": batch,
                    "submission_comments": self.properties.sample_info.summary.submission_comments,
                    "costcenter": self.properties.sample_info.summary.costcenter,
                    "archived": str(self.archived),
                    "batch_json": batches,
                    "positions": positions,
                    "genome_size": genome_size,
                    "submitted_on": self.submitted_on.date(),
                    "priority": self.properties.sample_info.summary.priority,
                    "comments": self.comments,
                    "supplied_plate_name": self.properties.sample_info.summary.supplied_plate_name,
                    "position_in_supplied_plate": self.properties.sample_info.summary.position_in_supplied_plate
            }
        elif frmt == "step_table":
            result = {
                    "none": "",  # For checkbox
                    "barcode": self.barcode,
                    "species": self.properties.sample_info.summary.submitted_species.name,
                    "positions": positions,
                    "comments": self.comments,
                    "batch": batch
            }
        else:
            result = {}
        return result

    def result_report(self, workflow_name, batch_name):
        batch = self.get_batches(workflow_name, batch_name)
        if len(batch) == 0:
            return {}
        data = {}
        data['barcode'] = self.barcode
        batch = batch[0]

        # Find the last step done from this branch and chain back
        chain = None
        for step_name in ["_workflow_finished"] + [b.name for b in batch.workflow.steps[::-1]]:
            if step_name in self.workflows[workflow_name]:
                for step_i in self.workflows[workflow_name][step_name][::-1]:
                    if step_i.batch_name == batch_name:
                        chain = [step_i]
                        break
                if chain is not None:
                    break
        chain = self.result_chain(chain)

        for step_i_r in chain[::-1]:
            if step_i_r.step_instance is not None:
                step_name = step_i_r.step_instance.step.name
            else:
                step_name = "root"
            for k, v in step_i_r.sample.items():
                data[".".join([step_name, k])] = str(v)
            for k, v in step_i_r.all.items():
                data[".".join([step_name, "all", k])] = str(v)
        return data

    def is_allowed(self, user):
        """
        Returns true if user is in the same group
        """
        return self.properties.sample_info.summary.group == user.group

    def detail_data(self):
        """
        Generate dict with data for sample details view
        """
        batches = []
        for batch in self.batches:
            workflow_name = batch.workflow.name
            batch_name = batch.batch_name
            workflow_o = batch.workflow
            workflow_data = self.workflows[workflow_name]
            workflow_steps = []
            for step_name, step_i_list in workflow_data.items():
                step_i_found = False
                for step_i in step_i_list[::-1]:
                    if step_i.batch_name == batch_name:
                        step_i_found = step_i
                if step_i_found is False:
                    continue
                step_i = step_i_found
                if step_name == "root":
                    step_name = "Workflow initialization"
                elif step_name == "_workflow_finished":
                    step_name = "Workflow finished"
                else:
                    step = Step.objects.project({"display_name": 1}).get({"name": step_name})
                    step_name = step.display_name
                if step_i.step_instance is None:
                    workflow_steps.append({
                        "name": step_name,
                        "attempt": len(step_i_list),
                        "start_date": step_i.start_date,
                        "finish_date": step_i.finish_date,
                        "values_all": step_i.all,
                        "values_sample": step_i.sample
                    })
                else:
                    val = step_i.step_instance.summary_values()
                    workflow_steps.append({
                        "id": step_i.step_instance._id,
                        "name": step_name,
                        "attempt": len(step_i_list),
                        "start_date": step_i.start_date,
                        "finish_date": step_i.finish_date,
                        "values_all": val["values_all"],
                        "values_samples": val["values_samples"],
                        "fields_samples": val["fields_samples"]
                    })
            batches.append({
                "display_name": workflow_o.display_name,
                "steps": workflow_steps,
                "batch_name": batch_name,
                "position": "".join(map(str, batch.position.get_coordinates()))
            })

        return {
            "barcode": self.barcode,
            "tags": [x.pk for x in self.tags],
            "properties": {
                "group": self.properties.sample_info.summary.group,
                "name": self.properties.sample_info.summary.name,
                "species": self.properties.sample_info.summary.submitted_species.name,
                "priority": self.properties.sample_info.summary.priority,
                "emails": self.properties.sample_info.summary.emails,
                "submitted_on": self.submitted_on,
                "additional_metadata": []
            },
            "batches": batches
        }

    def assign_tag(self, tag):
        if tag not in self.tags:
            self.tags.append(tag)
        self.save()

    def unassign_tag(self, tag):
        if tag in self.tags:
            self.tags.remove(tag)
        self.save()
