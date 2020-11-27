Entities
========

This are the different entities handled by miniLIMS. You should be aware of what they are and how they interact.

Sample
------

A sample is an isolate (?) that has been assigned a barcode. One sample has one barcode, and one barcode refers to only one sample. This is the main entity miniLIMS tracks.

Some of its properties are:

* Barcode
* Supplied species
* Supplying lab
* Supplying date
* Step results

Workflow
--------

A sequence of steps in a determined order. Samples can be a assigned to multiple workflows. When a sample is assigned to a workflow, it becomes part of a batch.

Batch
-----

When one or more samples are added to a workflow, they are either added to an existing batch or a new batch. A batch is a group of samples going through a workflow.
A batch has a name (that has to be unique to that workflow), a plate type, and information on what position each sample is in that plate.

Step
----

Steps are designed to mirror the lab process, and they are the smallest unit of analysis. 
They exist to keep track of what physical step was done in the lab, and/or to execute a script against the sample and step results contained in the sample.
A step processes one or more samples. 

A step doesn't go from start to finish in one go, instead it has an intermediate stage. Sometimes steps require the system to provide
values to the user, or the user to provide values to the system. This is done in the intermediate stage. Instead of just providing or receiving values,
the step can also have scripts attached, and process those values before returning them. A script has access to values from other steps, so they can be used to combine information
from multiple sources.




