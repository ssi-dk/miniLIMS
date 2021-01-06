Intro
=====

MiniLIMS is designed so that the source code for the application itself is as separated as possible from the specifics of any one installation. 
The configuration for each setup is in the ``/app/instance`` folder. When installing MiniLIMS for the first time, the instance folder should be created.
The folder ``/app/instance_example`` can be used as a template.

The config files are:

* config.py: General configuration file to adjust miniLIMS
* steps: Directory containing all steps to be imported. One subdirectory per step.
* workflows.json: Describes the workflows to be imported.
* species.json: Optional. List of species. It can be imported into the database to initialize the database. Species can later be added or removed from the database via the web interface.
* user_roles.json: List of roles to import into the database. A role has a name and a list of permissions.

Workflow config files
---------------------

``config.py`` and the ``steps`` directory are read when the flask server is launched and while it is running.
They are described in the :ref:`workflow_config_ref` section.

Other config files
------------------

The other ``.json`` files have to be imported manually into the database and should be imported once. 
This can be done with the command ``flask import-config``.

