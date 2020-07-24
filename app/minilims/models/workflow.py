from pymongo.operations import IndexModel
from pymodm import MongoModel, fields, EmbeddedMongoModel
from minilims.models.step import Step

class Workflow(MongoModel):
    name = fields.CharField(required=True)
    display_name = fields.CharField(required=True)
    steps = fields.ListField(fields.ReferenceField(Step))
    valid_plate_types = fields.ListField(fields.CharField(choices=["96plate"]))
    steps_denormalized = fields.ListField(fields.DictField())

    def denormalize_steps(self):
        steps_denormalized = []
        for step in self.steps:
            steps_denormalized.append({
                "_id": step._id,
                "name": step.name,
                "category": step.category
            })
        self.steps_denormalized = steps_denormalized


    class Meta:
        indexes = [IndexModel([("name", 1)], unique=True)]
    
    @classmethod
    def get_workflows(cls):
        """
        Returns list of available workflows
        """
        workflows = cls.objects.raw({}).project({"name": 1,
                                                 "display_name": 1,
                                                 "valid_plate_types": 1,
                                                 "_id": 0})
        return [x.to_son().to_dict() for x in workflows]

    @staticmethod
    def find_steps(step_names):
        """
        Provided a list of step names, it will search and
        add them to self.steps as references.
        Steps must exist already.
        """
        step_o_list = []
        for step in step_names:
            step_o_list.append(Step.objects.get({"name":step}))
        return step_o_list


    def valid_next_step(self, last_step, next_step):

        i = None
        if last_step == "root":
            i = -1
        else:
            for i in range(len(self.steps_denormalized)):
                if self.steps_denormalized[i]["category"] == last_step:
                    break
        if i is None or i == len(self.steps_denormalized) - 1: # none or last step
            return False
        next_s = self.steps_denormalized[i+1]
        if next_step == next_s["category"]:
            return True
        else:
            return False
    
    def get_prev_step(self, step_name):
        """
        Returns previous step to the one provided.
        """
        index = None
        for i in range(len(self.steps_denormalized)):
            step = self.steps_denormalized[i]
            if step["name"] == step_name:
                index = i
        if index is None:
            raise ValueError("Step not in workflow")
        if index == 0:
            return "root"
        else:
            return self.steps_denormalized[index - 1]["name"]
    
    def next_step(self, step_name):
        """
        Returns next step to the one provided. None if last step 
        """
        index = None
        for i in range(len(self.steps_denormalized)):
            step = self.steps_denormalized[i]
            if step["name"] == step_name:
                index = i
        if index is None:
            raise ValueError("Step not in workflow")
        if index == len(self.steps_denormalized) - 1:
            return "_workflow_finished"
        else:
            return self.steps_denormalized[index + 1]["name"]
