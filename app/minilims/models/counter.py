from pymodm import MongoModel, fields, EmbeddedMongoModel
from pymodm.errors import DoesNotExist

class Counter(MongoModel):
    name = fields.CharField(required=True)
    count = fields.IntegerField(default=0)

    def increase(self, amount=1):
        self.count = self.count + amount
        self.save()


class BarcodeProvider():
    def __init__(self, group):
        if len(group) != 3:
            lg = len(group)
            raise ValueError(f"Group name should have 3 characters. Provided {group} has {lg}.")
        self.group = group.upper()
        self.name = f"system_barcode_counter_{group}"
        try:
            self.counter = Counter.objects.get({"name": self.name})
        except DoesNotExist:
            self.counter = Counter(name=self.name)
            self.counter.save()

    def _cnt2bc(self, cnt):
        return f"{self.group}{cnt:06}" #6 zero padding
    
    def _bc2cnt(self, bc):
        group = bc[:3]
        if group != self.group:
            raise ValueError("Invalid group in barcode name. Barcode should match with user group.")
        cnt = int(bc[3:])
        if len(bc[3:]) > 6:
            if cnt < 10^len(bc[3:]):
                raise ValueError(("Invalid barcode. Long barcodes (more than 6 digits) only accepted for"
                                  " high numbers (1.000.000 for 7 digits etc)."))
        return cnt


    def current(self):
        """
        Return current value for barcode.
        """
        return self.counter.count

    def last_provided(self):
        """
        Returns last barcode provided.
        """
        last = self.current()
        if last == 0:
            return None
        return self._cnt2bc(last - 1)

    def get_barcodes(self, count):
        """
        Get a list of new unused barcodes
        """
        current = self.current()
        barcodes = []
        for i in range(count):
            n = i + current
            barcodes.append(self._cnt2bc(n))
        self.counter.increase(count)
        return barcodes
    
    def has_been_provided(self, barcode):
        """
        Checks if the barcode has been provided.
        """
        count = self._bc2cnt(barcode)
        return count < self.current()