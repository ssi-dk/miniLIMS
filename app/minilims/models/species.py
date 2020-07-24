from pymodm import MongoModel, fields, EmbeddedMongoModel, errors

class Species(MongoModel):
    name = fields.CharField(required=True)
    alias = fields.ListField(field=fields.CharField())
    step_variables = fields.DictField(required=True)
    
    def get_step_variable(self, workflow, step_name, variable_name):
        return self.step_variables[workflow][step_name][variable_name]

    def summary(self):
        summary = {
            "name": self.name,
            "aliases": self.alias,
            "v": self.step_variables
        }
        # for workflow, w_data in self.step_variables.items():
        #     for step, s_data in w_data.items():
        #         for variable, value in s_data.items():
        #             summary[f"{workflow}__{step}__{variable}"] = value
        return summary

    @staticmethod
    def get_species(spe_string):
        """
        Search db for species using name & alias
        """
        try:
            species = Species.objects.get({"name": spe_string})
        except errors.DoesNotExist:
            try:
                species = Species.objects.get({"alias": spe_string})
            except errors.DoesNotExist:
                return None
        return species
    
    @classmethod
    def get_name_list(cls, alias=False):
        if alias:
            list_species = []
            for species in cls.objects.raw({}):
                if len(species.alias) >= 1:
                    list_species.append(species.alias[0])
                else:
                    list_species.append(species.name)
            return list_species
        return [x.name for x in cls.objects.raw({})]