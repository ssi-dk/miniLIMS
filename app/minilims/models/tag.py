import re
from pymodm import MongoModel, fields
from pymodm.errors import ValidationError

HEX = re.compile("^#(?:[0-9a-fA-F]{3}){1,2}$")

class Tag(MongoModel):
    # Keeps track of what tags exists and what style they have
    value = fields.CharField(primary_key=True, required=True)
    style = fields.CharField(required=True, default="#FFFFFF") # Should be a hex color code.

    def clean(self):
        if HEX.match(self.style) is None:
            raise ValidationError("Invalid HEX color value. Example: \"#FFFFFF\".")