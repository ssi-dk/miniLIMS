from flask_pymongo import PyMongo
from pymodm.connection import connect

import click
from flask import current_app, g
from flask.cli import with_appcontext

import minilims.services.lims as lims_s


def load_db(app):
    with app.app_context():
        connect(current_app.config["MONGO_URI"])


def clear_db(app):
    with app.app_context():
        connect(current_app.config["MONGO_URI"])
        db = PyMongo(app).db
        db.sample.delete_many({})
        db.step.delete_many({})
        db.step_instance.delete_many({})
        db.workflow.delete_many({})
        # yield app


# Click provides a command-line interface for the app
@click.command('clear-db')
@with_appcontext
def clear_db_command():
    """Clear the existing data."""
    clear_db(current_app)
    click.echo('Initialized the database.')


# Click provides a command-line interface for the app
@click.command('import-config')
@with_appcontext
def import_config_command():
    """Initialize with workflows and user permissions from config."""
    lims_s.init_config()
    click.echo('Imported config from {}.'.format(current_app.instance_path))


def init_commands(app):
    app.cli.add_command(clear_db_command)
    app.cli.add_command(import_config_command)
    app.cli.add_command(test_dev_command)
    app.cli.add_command(create_demo_users_command)


# Click provides a command-line interface for the app
@click.command('create-demo-users')
@with_appcontext
def create_demo_users_command():
    """Create demo users in db."""
    from minilims.services.auth import register
    lims_s.init_user_roles()
    users = [
        {
            "mail": "supplying_lab@test.com",
            "password": "supplying lab",
            "roles": ["supplying_lab_user"],
            "group": "ABC"
        },
        {
            "mail": "supplying_lab_DEF@test.com",
            "password": "supplying lab DEF",
            "roles": ["supplying_lab_user"],
            "group": "DEF"
        },
        {
            "mail": "lab_manager@test.com",
            "password": "lab manager",
            "roles": ["NGS_lab_manager"],
            "group": "ABC"
        },
        {
            "mail": "lab_technician@test.com",
            "password": "lab technician",
            "roles": ["lab_technician"],
            "group": "ABC"
        }
    ]

    for user in users:
        error = register(user)
        if error is not None:
            user_mail = user["mail"]
            print(f"Error creating user {user_mail}: ", error)

    click.echo('Demo users created.')

@click.command('test_dev')
@click.argument('stop_at_step', required=False)
@with_appcontext
def test_dev_command(stop_at_step=-1):
    test_dev(stop_at_step)


def test_dev(stop_at_step):
    import tests.data_test as dt
    from minilims.models.step import Step
    from minilims.models.step_instance import Step_instance
    import minilims.services.tags as s_tags
    try:
        import tests.data_test_real as dtr
        real_test = True
    except ImportError:
        real_test = False
    from tests.test_lims import Helper
    client = current_app.test_client()
    helper = Helper(client)
    clear_db(current_app)
    lims_s.init_workflows()
    if real_test:
        step_data_dict = dtr.step_data
        samplesheet = dtr.samplesheets
        sample_barcodes = dtr.barcodes
        workflow = dtr.workflows[0]

    else:
        step_data_dict = dt.step_data
        samplesheet = dt.samplesheets_success
        sample_barcodes = dt.barcodes[0]
        workflow = dt.workflows[3]
    # s_lims.import_steps(workflow["steps"])
    # s_lims.import_workflow(workflow)

    from tests.conftest import AuthActions
    auth = AuthActions(client)
    auth.login()
    helper.submit_samples(samplesheet)

    #Add tag for testing
    s_tags.validate_and_add({"value": "testtag", "description": "Hello world"})
    s_tags.validate_and_add({"value": "testtag2", "style": "danger", "description": "This is a longer description"})
    s_tags.validate_and_assign_to_sample("testtag", {"sample_barcodes": [sample_barcodes[0]]})
    s_tags.validate_and_assign_to_sample("testtag2", {"sample_barcodes": [sample_barcodes[0]]})

    batch_name = "test_batch"

    helper.assign_samples(sample_barcodes, workflow["name"], batch_name)
    i = 0
    for stepname in workflow["steps"]:
        if i == int(stop_at_step):
            print("Reached step {}. Stopping".format(stop_at_step))
            break
        i += 1
        print("starting step {}".format(stepname))
        step_data = step_data_dict[stepname]
        start_data = step_data[0]
        start_data["sample_barcodes"] = sample_barcodes
        start_data["workflow_batch"] = "{}: {}".format(workflow["name"], batch_name)

        helper.start_step(stepname, start_data)
        step = Step.objects.get({"name":stepname})

        step_i = Step_instance.objects.get({
            "step": step._id,
            "status": "started",
            "result_samples.{}".format(sample_barcodes[0]): {"$exists": True}
        })

        helper.end_step(str(step_i._id), step_data[1])

