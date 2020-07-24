# Based on code from https://lkubuntu.wordpress.com/2012/10/02/writing-a-python-plugin-api/
import importlib
import os


main_module = "__init__"

loader_details = (
    importlib.machinery.ExtensionFileLoader,
    importlib.machinery.EXTENSION_SUFFIXES
    )

class Steploader():
    def __init__(self, step_folder):
        self.step_folder = step_folder
        self.toolsfinder = importlib.machinery.FileFinder(step_folder, loader_details)

    def find_steps(self):
        """
        Returns list of strings, names of steps available in the steps dir.
        """
        steps = []
        ls = os.listdir(self.step_folder)
        for item in ls:
            location = os.path.join(self.step_folder, item, "__init__.py")
            if os.path.isfile(location):
                steps.append(item)
        return steps

    def get_step(self, name):
        location = os.path.join(self.step_folder, name, "__init__.py")
        if not os.path.isfile(location):
            raise ValueError("Cannot find step '{}' in steps dir.".format(name))
        info = importlib.util.spec_from_file_location(name, location)
        return {"name": name, "info": info}

    def load_step(self, step):
        return step["info"].loader.load_module()

    def get_and_load(self, name):
        return self.load_step(self.get_step(name))