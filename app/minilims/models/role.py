from pymongo.write_concern import WriteConcern
from pymongo.operations import IndexModel
from pymodm import MongoModel, fields


class Role(MongoModel):
    """
    Used to store permissions for each type of role.
    """
    name = fields.CharField(required=True)
    permissions = fields.ListField(fields.CharField(), required=True)

    class Meta:
        write_concern = WriteConcern(j=True)
        indexes = [IndexModel([("name", 1)], unique=True)]