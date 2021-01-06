Code and Testing
================

The source code for MiniLIMS is organized in modules: routes (front-end endpoints), services (business logic) and models (representation of the data and logic specific to them).
Inside these modules they are organized by the domain (samples, lims, auth, db...).

There is a test suite available in the tests folder that will run through most of the Lims logic and some of the logic in the other modules.
There are some tests in the end that cover a full workflow with expected input and output, and there is a setup specific test that will go over an example with real data.

To test and manage the system there are also some commands in ``minilims.services.db`` where an admin can import settings.

For debugging purposes, it is also possible to import some samples into a predefined workflow and avance the system to a specific step.
The command to do this is ``flask test_dev N``, where N is the step the system should advance to. 
There is more details about the internals of this command in the source code at ``minilims.services.db``.





