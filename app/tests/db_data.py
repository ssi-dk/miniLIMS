import os
from flask import current_app
import json

from minilims.models.user import User
from minilims.models.species import Species

def clear_db(db):
    db.sample.delete_many({})
    db.step.delete_many({})
    db.step_instance.delete_many({})
    db.user.delete_many({})
    db.role.delete_many({})
    db.species.delete_many({})
    db.workflow.delete_many({})
    db.fs.files.delete_many({})
    db.fs.chunks.delete_many({})


def populate_db():
    User(email="test@test.com",
         password="pbkdf2:sha256:150000$L3ipk11Y$c4511ddc1cef3d638e7c60985a7f925574dd8a8ede8fa6d0e0369bb83affcb11",
         _id="5dbbefc2263b8ecd0c83dad5",
         group="TST",
         permissions_denormalized=["admin_all"]
         ).save(force_insert=True)
    species_list = []
    file_path = os.path.join(current_app.instance_path, "species.json")
    if os.path.exists(file_path):
        with open(file_path) as conf_io:
            species_source_list = json.loads(conf_io.read())
            for species in species_source_list:
                species_list.append(Species(**species))
    Species.objects.bulk_create(species_list)