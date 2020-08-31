from pymongo.write_concern import WriteConcern
from pymongo.operations import IndexModel
from pymodm import MongoModel, fields
from minilims.models.role import Role


class User(MongoModel):
    email = fields.EmailField(required=True)
    # username = fields.CharField(required=True) # Initials
    # password = fields.CharField(required=True)
    oid =  fields.CharField(required=True)
    display_name = fields.CharField()
    
    group = fields.CharField()
    meta = {
        "indexes": [
            {
                "fields": ["username"],
                "unique": True
            }
        ]
    }
    roles = fields.ListField(fields.ReferenceField(Role), blank=True)
    permissions_denormalized = fields.ListField(fields.CharField(), blank=True)

    def _denormalize_roles(self):
        permissions_denormalized = []
        for role in self.roles:
            permissions_denormalized.extend(role.permissions)
        #  Remove duplicates
        self.permissions_denormalized = list(set(permissions_denormalized))

    def add_role(self, rolename):
        role_o = Role.objects.get({"name": rolename})  # Will throw DoesNotExist if invalid
        if role_o in self.roles:
            return "Already Exists"
        self.roles.append(role_o)
        self._denormalize_roles()
        self.save()

    def remove_role(self, rolename):
        role_o = Role.objects.get({"name": rolename})  # Will throw DoesNotExist if invalid
        if role_o not in self.roles:
            return "User doesn't have role"
        self.roles.remove(role_o)
        self._denormalize_roles()
        self.save()

    def has_permission(self, permission):
        """
        Check if a user is allowed to do an action.
        """
        return ("admin_all" in self.permissions_denormalized
                or permission in self.permissions_denormalized)


    class Meta:
        write_concern = WriteConcern(j=True)
        indexes = [IndexModel([("username", 1)], unique=True)]