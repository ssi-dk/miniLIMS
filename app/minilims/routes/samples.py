from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for,
    jsonify
)
from werkzeug.exceptions import abort
from flask import current_app
from pymodm import errors
import minilims.services.samples as sample_service
import minilims.models.sample as sample_m
from minilims.routes.auth import login_required, permission_required, permission_required_API
from minilims.models.counter import BarcodeProvider

import minilims.services.db

bp = Blueprint('samples', __name__, url_prefix='/samples')


@bp.route('/')
@permission_required("samples_see_own")
def samples():
    data = sample_service.samples_overview(g.user)
    return render_template('samples/samples.html', data=data)

@bp.route('/archived')
@permission_required("samples_see_own")
def archived():
    data = sample_service.archived_samples()
    return render_template('samples/samples-server.html', data=data)


@bp.route('/submit')
@permission_required("samples_submit")
def submit():
    # Get overview data
    data = {"columns": sample_m.Sample.columns("submit")}
    return render_template('samples/submit.html', data=data)

@bp.route('/data-source')
@permission_required_API("samples_see_own")
def data_source():
    data = sample_service.data_source(request.args, g.user)
    
    return jsonify(data)

@bp.route('/data-source/update', methods=["POST"])
#@permission_required_API("samples_edit_all")
def update():
    # Update a row
    data = request.json
    # Also checks permissions
    errors = sample_service.validate_sample_update(data)
    if len(errors) == 0:
        row = sample_service.sample_update(data)
        return jsonify(row)
    else:
        return jsonify({"errors": errors}), 422

@bp.route('/submit', methods=["POST"])
@permission_required_API("samples_submit")
def submit_api():
    errors = sample_service.validate_samplesheet(request.json, g.user)

    if len(errors) == 0:
        sample_service.submit_samplesheet(request.json, g.user)
        status = "OK"
        flash("Samples submitted successfully", "success")
    else:
        status = "Fail"
    return jsonify(
        errors=errors,
        status=status
    )

@bp.route('/validate', methods=["POST"])
@permission_required_API("samples_submit")
def validate():
    errors = sample_service.validate_samplesheet(request.json, g.user)
    # Get overview data
    return jsonify(
        errors=errors
    )

@bp.route('/assign', methods=["POST"])
@login_required
def assign_samples_view():
    sample_barcodes = request.form.getlist("sample_barcodes[]")
    workflow = request.form["workflow"]
    plate_type = request.form["plate_type"]
    batch_name = request.form["batch_name"]
    suggested_step = request.form.get("suggested_step")

    errors = sample_service.validate_assign({
        "sample_barcodes": sample_barcodes,
        "workflow": workflow,
        "batch_name": batch_name,
        "plate_type": plate_type
    })
    if len(errors):
        for e,v in errors.items():
            flash("Error assigning samples: {}: {}".format(e, v), "danger")
        return redirect(url_for('samples.samples'))
    data = sample_service.get_assign_view(sample_barcodes, workflow,
                                          batch_name, plate_type,
                                          suggested_step)

    return render_template('samples/assign.html', data=data)

@bp.route('/assign-api', methods=["POST"])
@permission_required_API("samples_assign")
def assign_samples_API():
    errors = sample_service.validate_assign(request.json)
    if len(errors) == 0:
        sample_service.assign_samples(request.json)
        flash("Samples assigned successfully.", "success")
        status = "OK"
    else:
        status = "Fail"
    return jsonify(
        errors=errors,
        status=status
    )

@bp.route('/reorganize_plate/<workflow_name>/<batch_name>',)
@permission_required_API("samples_assign")
def reorganize_plate(workflow_name, batch_name):
    data = sample_service.reorganize_plate(workflow_name, batch_name)
    return render_template("samples/assign.html", data=data)


@bp.route('/unassign', methods=["PUT"])
@permission_required_API("samples_assign")
def unassign_samples_API():
    errors, warnings = sample_service.validate_unassign(request.json)
    if len(errors) == 0:
        sample_service.unassign_samples(request.json)
        for warning in warnings:
            flash(warnings[warning], "warning")
        flash("Samples unassigned successfully.", "success")
        status = "OK"
    else:
        status = "Fail"
    return jsonify(
        errors=errors,
        warnings=warnings,
        status=status
    )

@bp.route('/archive', methods=["PUT"])
@permission_required_API("samples_submit")
def archive_samples_API():
    print('r', request.json)
    if request.json.get("archive", "") == "archive":
        archive = True
        flash("Samples archived successfully.", "success")
    else:
        archive = False
        flash("Samples unarchived successfully.", "success")
    sample_service.archive_samples(request.json["sample_barcodes"], archive)
    status = "OK" # It always works for now
    return jsonify(
        errors=[],
        status=status
    )

@bp.route('/details/<sample_barcode>')
@permission_required("samples_see_own")
def details(sample_barcode):
    # Get sample overview data
    try:
        data = sample_service.get_sample_details(sample_barcode, g.user)
    except errors.DoesNotExist:
        data = {
            "missing_sample": "Sample not found in the database."
        }
    return render_template('samples/details.html', data=data)

@bp.route('/searchbox')
@permission_required_API("samples_see_all")
def searchbox_suggestion():
    """
    Generate a list of potential results for barcode search
    """
    query = request.args.get("term")
    sample_barcodes = sample_m.Sample.searchbox_suggestion(query)
    return jsonify(sample_barcodes)


@bp.route('/batch_names')
@permission_required_API("samples_see_all")
def batch_names():
    """
    Generate a list of potential results for barcode search
    """
    query = request.args.get("term")
    workflow = request.args.get("workflow")
    return jsonify(sample_m.Sample.get_batch_names(query, workflow))

@bp.route('/results_report', methods=["POST"])
@permission_required_API("samples_see_all")
def result_chain():
    """
    Download report file.
    """
    data = {}
    errors = sample_service.validate_results_report(request.json)
    if len(errors) == 0:
        data['file_id'] = sample_service.get_results_report(request.json)
        status = "OK"
    else:
        status = "Fail"
    return jsonify(
        errors=errors,
        data=data,
        status=status
    )

@bp.route('/barcodes')
@permission_required_API("samples_submit")
def barcodes():
    """
    Barcode view
    """
    data = sample_service.barcode_view(g.user)
    return render_template('samples/barcodes.html', data=data)

@bp.route('/barcodes/new/<count>', methods=["GET"])
@permission_required_API("samples_submit")
def new_barcodes(count):
    """
    Return new barcode list
    """
    try:
        count = int(count)
    except ValueError:
        return jsonify(errors={"count": "Provided count is not int"})

    group = g.user.group

    bc = BarcodeProvider(group).get_barcodes(count)
    status = "OK"
    return jsonify(
        data=bc,
        status=status
    )
