class MissingValueError(Exception):
    def __init__(self, *args):
        if args:
            self.message = args[0]
        else:
            self.message = None

    def __str__(self):
        if self.message:
            return 'MissingValueError, {0} '.format(self.message)
        else:
            return 'MissingValueError has been raised'


class ScriptExecutionError(Exception):
    def __init__(self, *args):
        if args:
            self.message = args[0]
        else:
            self.message = None

    def __str__(self):
        if self.message:
            return 'ScriptExecutionError, {0} '.format(self.message)
        else:
            return 'ScriptExecutionError has been raised'
