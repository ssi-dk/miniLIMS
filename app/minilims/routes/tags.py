# from minilims.models.tag import Tag
from flask import (
    Blueprint, jsonify, request
)
from minilims.routes.auth import login_required, permission_required_API
import minilims.services.tags as tags_s

bp = Blueprint('tags', __name__, url_prefix='/tags')


@bp.route('/all')
@login_required
def tags_overview():
    # Render view with info of all tags
    return


@bp.route('/', methods=["POST"])
@permission_required_API("tags_admin")
def create_new_tag():
    errors = tags_s.validate_and_add(request.json)
    if len(errors) == 0:
        status = "OK"
    else:
        status = "Fail"
    return jsonify(
        errors=errors,
        status=status
    )


@bp.route('/<tagvalue>', methods=["DELETE"])
@permission_required_API("tags_admin")
def delete_tag(tagvalue):
    errors = tags_s.validate_and_delete(tagvalue)
    if len(errors) == 0:
        status = "OK"
    else:
        status = "Fail"
    return jsonify(
        errors=errors,
        status=status
    )

@bp.route('/<tagvalue>/assign_to_samples', methods=["POST"])
@permission_required_API("tags_admin")
def assign_tag_to_samples(tagvalue):
    errors = tags_s.validate_and_assign_to_sample(tagvalue, request.json)
    if len(errors) == 0:
        status = "OK"
    else:
        status = "Fail"
    return jsonify(
        errors=errors,
        status=status
    )


@bp.route('/<tagvalue>/remove_from_samples', methods=["POST"])
@permission_required_API("tags_admin")
def remove_tag_from_samples(tagvalue):
    errors = tags_s.validate_and_remove_from_sample(tagvalue, request.json)
    if len(errors) == 0:
        status = "OK"
    else:
        status = "Fail"
    return jsonify(
        errors=errors,
        status=status
    )
