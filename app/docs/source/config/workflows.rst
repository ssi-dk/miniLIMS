Workflow management
===================
.. _workflow_config_ref:

Workflows
---------

Work on the samples in MiniLIMS are organized in Workflows. 
A workflow is composed of steps in a particular order. 


A workflow also has one or more "plates" that samples can be organized into and will determine their position coordinates.
Internally, MiniLIMS stores the order of the samples and the type of plate. From that information the coordinates can be obtained.
Currently plates can't be configured and are hard-coded.

Batches
-------

When samples are assigned to a workflow, they are assigned to a Batch. Samples can be added to an existing batch or to a new one.
The batch name must be unique for the workflow. When assigning them to a batch, the user must choose a plate and a position for each sample in that plate. 
The position of the samples can be adjusted later.

Steps
-----

A step is the unit of "processing" a sample goes through. It usually represents a physical step in the laboratory but can also be bioinformatic or other processing.
Each step has to be started and ended. This is because there is a state while executing the step where the user may need to obtain or provide values for the step to be done properly.
So the flow through a step may be:

* User selects which samples should go through a step and starts the step.
* The system may do some processing at this stage (called "stepstart" in the scripts).
* The "running step" view will be shown to the user. In this view the user may be able to access files/values, or provide files/values.
* The user finishes the step. In this stage the system may do some calculations (called "stepend" in the scripts).
* The user is shown a summary with the values from the step.

A step can be started and continued later, or cancelled and restarted.

Configuration
*************

Step configuration is inside the /app/instance folder. Each step is composed of a folder with the following structure:

stepname
 - __init__.py
 - Other optional files required by the step.

The __init__.py file should have a dictionary named step with the following fields:

* name: Internal name to be referenced by other steps/workflows. Shouldn't be changed.
* display_name: Step name to be shown to the user, it can be renamed.
* category: This value should be the same for multiple steps that are equivalent. This field is used to reference step results and requeriments.
  For example, some step may require a sample to have gone through a purification step, but the system has two purification steps. 
  If those two steps share the same category and that category is specified in requeriments, the system will accept any of the two steps to pass requeriments.
  Note that this functionality has not been tested or developed much currently.
* version: To be updated when a step changes. Stored when a step runs.
* details: Dictionary, currently only contains a entry named "description". The value is shown on each step to the user.
* requirements: Requirements for this step to run. Not currently checked.
* input_output: List with scripts to run. Described in the next section.

Input/Output
************

This section specifies the values/files provided to the user and expected by this step. 
This list can have up to two dictionaries, one for each stage. The dictionaries have these values:

* name: Not currently used.
* display_name: Not currently used.
* script: Optional, the name of the function that will run at this stage. If not defined nothing will run.
* stage: Either "stepstart" or "stepend". 
  "stepstart" will run when the user starts the step, and generally will generate values required in the step. 
  "stepend" will run when the user finishes the step, and will usually process the user inputs into the system.
* "input_values" or "output_values": Values that will be expected from the user, given to the user and/or from the scripts.
  In this case, "input" or "output" are from the system's perspective, so an output value in a "stepstart" stage will be shown to the user.
  It is a list with dictionaries. These dictionaries refer to one value per dictionary.

The "input_values" or "output_values" elements are:

* name: Name of the value to be used internally.
* display_name: If this value is shown to the user, the system will use this name.
* scope: "sample" if this value belongs to one sample only or "all" if it belongs to all samples in the batch. A value belonging to "all" wouldn't make sense if taken out of the other sample's context. For example, the concentration of pooling all samples.
* type_: Used internally to distinguish files from others, and by the front-end to know what kind of input to show to the user.
* showuser: Boolean. If true, this value will be shown to the user to fill out/see, if false, it will be stored internally without showing it to the user. 

Special considerations:

If name is an input to a script, it can be used to refer to values from other steps. 
Separate the step name from the value name "other_step_name.value_name"
It can also get the value from a different workflow but that is more unusual, in that case it would be "workflow_name.step_name.value_name"

It is possible to obtain the samples information to be used inside a script by using name "samples" and type_ "sample_properties". 

To obtain the batch name inside a script by using name "batch" and type_ "sample_properties". 

To obtain the user that started or finished the step, use the type_ "user_started" or "user_ended" and scope "all".

Scripts
*******

As explained above, when defining the input_output values you can specify a property named script. 
Script should match the name of a function available in the same file. 
That function can access the values defined in "input_values" in the same order as defined.
The name should be the same, replacing periods with underscores if required.
"step_name.value_name" would be "step_name_value_name" when defining the function.

The function can use these values to do calculations and generate output values that can be provided when returning the function in a dictionary.
The returned dictionary should have a key named samples if there are sample-scoped values. 
Inside this dictionary there should be a value-key pair with key being each sample's barcode and the value being a dictionary with key-value pairs with key being value name and value being the value.
Similarly there can be an "all" dictionary with key-value pairs, key being the value name and value the value.

When using and generating files, you should use the functions in minilims.utils.file_utils to save files to the database.