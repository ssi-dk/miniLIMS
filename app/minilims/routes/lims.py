from flask import (
    Blueprint, flash, g, jsonify, render_template, redirect,
    request, make_response, current_app, url_for
)
from werkzeug.exceptions import abort
from minilims.routes.auth import login_required, permission_required_API, permission_required
import minilims.models.step_instance as m_step_instance
import minilims.services.lims as lims_service
import minilims.services.species as species_service
import minilims.utils.fileutils as fileutils
import minilims.errors
import bson.errors
import bson.objectid
import json

bp = Blueprint('lims', __name__)

@bp.route('/')
@login_required
def index():
    # Get overview data
    data = lims_service.get_workflows_overview(g.user)
    
    return render_template('lims/overview.html', data=data)


@bp.route('/batch')
@login_required
def batch_overview():
    # Get overview data
    data = lims_service.get_batch_overview()
    return render_template('lims/batch_overview.html', data=data)


@bp.route('/steps/<step_name>')
@permission_required_API("workflows_see_results")
def step_overview(step_name):
    data = lims_service.get_step_overview(step_name)
    return render_template('lims/step.html', data=data)

# @bp.route('/steps/<step_name>')
# @bp.route('/steps/<step_name>/samples/<workflow_batch_name>')
# def step_samples(step_name, workflow_batch_name):
#     data = lims_service.get_step_samples(step_name, workflow_batch_name)
#     return data


@bp.route('/steps/<step_name>/start', methods=["POST"])
@permission_required_API("workflows_progress")
def step_start(step_name):
    errors = lims_service.validate_step_start(step_name, request.json)

    if len(errors) == 0:
        sample_barcodes = request.json["sample_barcodes"]
        workflow_name, batch_name = request.json["workflow_batch"].split(": ")
        try:
            si_id = lims_service.start_step(step_name, sample_barcodes, workflow_name, batch_name, g.user)
        except (minilims.errors.MissingValueError, minilims.errors.ScriptExecutionError) as e:
            return jsonify(
                errors=["Error while starting step: {}".format(e)],
                status="Fail",
                data={}
            )
        status = "OK"
        data = {"step_instance_id": str(si_id)}
    else:
        status = "Fail"
        data = {}
    return jsonify(
        errors=errors,
        status=status,
        data=data
    )

@bp.route('/stepinstance/<stepinstanceid>')
@permission_required_API("workflows_see_results")
def step_started(stepinstanceid):
    try:
        data = lims_service.get_step_started(stepinstanceid)
    except (minilims.errors.MissingValueError, minilims.errors.ScriptExecutionError) as e:
        flash(str(e), "danger")
        step_name = m_step_instance.Step_instance.objects.get(
            {"_id": bson.objectid.ObjectId(stepinstanceid)}).step.name
        return step_overview(step_name)
    if data == None:
        abort(404)
    return render_template('lims/step_started.html', data=data)

@bp.route('/stepinstance/<stepinstanceid>/cancel', methods=["POST"])
@permission_required_API("workflows_progress")
def step_cancel(stepinstanceid):

    errors, data = lims_service.validate_step_instance_cancel_start(stepinstanceid, g.user)

    if len(errors) == 0:
        lims_service.step_instance_cancel_start(stepinstanceid, g.user)
        flash("Step cancelled successfully.", "success")
        status = "Cancelled"
    else:
        status = "Fail"
    return jsonify(
        errors=errors,
        status=status,
        data={"step_instance_id": stepinstanceid, "step_name": data["step_name"]}
    )

@bp.route('/stepinstance/<stepinstanceid>/end', methods=["POST"])
@permission_required_API("workflows_progress")
def step_end(stepinstanceid):
    params = {
        "files": request.files,
        "params": json.loads(request.form.get("params", '{}'))
    }
    errors = lims_service.validate_step_end(stepinstanceid, params)

    if len(errors) == 0:
        try:
            data = lims_service.end_step(stepinstanceid, params, g.user)
        except (minilims.errors.MissingValueError, minilims.errors.ScriptExecutionError) as e:
            return jsonify(
                errors=["Error while finishing step: {}".format(e)],
                status="Fail",
                data={}
            )
        except Exception as e:
            raise e
            return jsonify(
                errors=["Unexpected error ocurred. Most likely processing step inputs."],
                status="Fail",
                data={}
            )
        suggested_step = data["suggested_step"]
        alternative_steps = data["alternative_steps"]
        if len(data["qc_actions_msg"]):
            flash(data["qc_actions_msg"], "warning")
        flash("Step finished successfully.", "success")
        status = "OK"
    else:
        suggested_step = None
        alternative_steps = None
        status = "Fail"
    return jsonify(
        errors=errors,
        status=status,
        suggested_step=suggested_step,
        alternative_steps=alternative_steps
    )

@bp.route('/files/<fileid>')
@permission_required_API("workflows_progress")
def getfile(fileid):

    try:
        _id = bson.objectid.ObjectId(fileid)
    except bson.errors.InvalidId:
        current_app.logger.info("Invalid file id requested: {}".format(fileid))
        return jsonify(errors={"fileid": "invalid fileid {}".format(fileid)})

    f = fileutils.get_file(_id)
    response = make_response(f.read())
    filename = f.filename
    response.headers["Content-Disposition"] = 'attachment; filename="{}"'.format(filename)
    # response.mimetype = f.content_type
    return response


@bp.route('/stepinstance/<stepinstanceid>/finished')
@permission_required("workflows_progress")
def step_finished(stepinstanceid):
    recommended_step = request.args.get('sug_step')
    alternative_step_names = request.args.get('alt_steps')
    reassign_qc_fail = request.args.get('reassign')
    data = lims_service.get_step_finished(stepinstanceid, recommended_step, alternative_step_names, reassign_qc_fail)
    return render_template("lims/step_finished.html", data=data)

@bp.route('/steps/<stepname>/details')
@permission_required("workflows_see_results")
def step_details(stepname):
    data = lims_service.get_step_details(stepname)
    return render_template("lims/step_details.html", data=data)

@bp.route('/stepinstance/<stepinstanceid>/delete', methods=["POST"])
@permission_required_API("workflows_progress") # Maybe create a workflows_delete
def delete_step(stepinstanceid):
    errors = lims_service.validate_delete_step_instance(stepinstanceid)

    if len(errors) == 0:
        lims_service.delete_step_instance(stepinstanceid)
        flash("Step instance deleted successfully.", "success")
        status = "Deleted"
    else:
        status = "Fail"
    return jsonify(
        errors=errors,
        status=status,
        data={"step_instance_id": stepinstanceid}
    )


@bp.route('/test')
@permission_required("workflows_see_results")
def test_function():
    from minilims.models.sample import Sample
    from minilims.models.workflow import Workflow
    workflow = Workflow.objects.get({"name": "wgs_routine"})
    view = Sample.get_plate_view(workflow, "Batch01", "96plate", True)
    return jsonify(view)

@bp.route('/species', methods=["GET","PUT","POST","DELETE"])
@permission_required("admin_species")
def species():
    if request.method == "GET":
        data = species_service.get_species_view()
        return render_template("lims/species_data.html", data=data)
    elif request.method == "PUT":
        jsonbody = request.json
        for key in ["undefined", "addRowBtn"]:
            if key in jsonbody:
                del jsonbody[key]

        errors = species_service.validate_species(request.json, "PUT")
        if len(errors) == 0:
            data = species_service.species_put(request.json)
            return jsonify(data)
        else:
            return jsonify(errors=errors), 422
    elif request.method == "POST":
        jsonbody = request.json
        for key in ["undefined", "editRowBtn"]:
            if key in jsonbody:
                del jsonbody[key]

        errors = species_service.validate_species(request.json, "POST")
        if len(errors) == 0:
            data = species_service.species_edit(request.json)
            return jsonify(data)
        else:
            return jsonify(errors=errors), 422
    elif request.method == "DELETE":
        errors = species_service.validate_species_delete(request.json)
        if len(errors) == 0:
            data = species_service.species_delete(request.json)
            return jsonify(data)
        else:
            return jsonify(errors=errors), 422

@bp.route("/warning_reset_db")
@permission_required("admin_all")
def warning_reset_db():
    """
    WARNING: This button resets the db, enable only for debugging purposes in test environment
    """
    import minilims.services.db
    if current_app.config["DEBUG"]:
        minilims.services.db.clear_db(current_app)
        minilims.services.db.test_dev(0)
        flash("Database reset", "success")
    else:
        flash("Not allowed by config", "danger")
    return redirect(url_for("lims.index"))
