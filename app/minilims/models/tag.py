import re
from pymodm import MongoModel, fields
from pymodm.errors import ValidationError

HEX = re.compile("^#(?:[0-9a-fA-F]{3}){1,2}$")
VALID_STYLES = ("primary","secondary","success","danger","warning","info","light","dark")

class Tag(MongoModel):
    # Keeps track of what tags exists and what style they have
    value = fields.CharField(primary_key=True, required=True, max_length=10)
    style = fields.CharField(required=True, default="secondary", choices=VALID_STYLES) # Should be a hex color code.
    description = fields.CharField(max_length=250)  # Shown when hovering the mouse over the tag

    #def clean(self):
        # if HEX.match(self.style) is None:
        #     raise ValidationError("Invalid HEX color value. Example: \"#FFFFFF\".")
    
    @classmethod
    def get_display_data(cls):
        """
        Get a dict with the styling for each tag
        """
        all_tags = cls.objects.all()
        # Dict can be reversed if too many tags make the object too big
        styling = {t.pk: {"style": t.style, "desc": t.description} for t in all_tags}
        return styling

    @classmethod
    def validate_field(cls, value):
        """
        Validate field for sample form submission.
        """
        if isinstance(value, list):
            count = cls.objects.raw({"_id": {"$in": value}}).count()
            if count == len(value):
                return True
        return False