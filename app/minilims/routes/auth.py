import functools

from flask import (
    Blueprint, flash, jsonify, g, redirect, render_template, request, session, url_for
)
from werkzeug.security import check_password_hash, generate_password_hash

import minilims.services.auth as s_auth
from minilims.models.user import User
from bson.objectid import ObjectId
from pymongo import errors


bp = Blueprint('auth', __name__, url_prefix='/auth')

@bp.route('/register', methods=('GET', 'POST'))
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        error = s_auth.register_user(username, password)
        if error is None:
            flash("Registered successfully")
            return redirect(url_for('auth.login'))
        else:
            flash(error)

    return render_template('auth/register.html')

@bp.route('/login', methods=('GET', 'POST'))
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        error = None
        try:
            user = User.objects.get({"username":username})
        except User.DoesNotExist:
            error = "Incorrect username."
        else:
            if not check_password_hash(user.password, password):
                error = 'Incorrect password.'

        if error is None:
            session.clear()
            session['user_id'] = str(user._id)
            return redirect(url_for('index'))

        flash(error)

    return render_template('auth/login.html')

@bp.before_app_request
def load_logged_in_user():
    user_id = session.get('user_id')
    if user_id is None:
        g.user = None
    else:
        try:
            g.user = User.objects.get({"_id": ObjectId(user_id)})
        except User.DoesNotExist:
            g.user = None

@bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@bp.route('/u/<username>/addrole/<rolename>', methods=["POST"])
def add_role_to_user(username, rolename):
    """
    Requires admin role. Adds role to user.
    """
    errors = s_auth.validate_add_role_to_user(username, rolename, g.user)

    if len(errors) == 0:
        s_auth.add_role_to_user(username, rolename)
        status = "OK"
    else:
        status = "Fail"
    return jsonify({
        "errors": errors,
        "status": status
    })

@bp.route('/u/<username>/removerole/<rolename>', methods=["POST"])
def remove_role_from_user(username, rolename):
    """
    Requires admin role. Removes role from user.
    """
    errors = s_auth.validate_remove_role_from_user(username, rolename)

    if len(errors) == 0:
        s_auth.remove_role_from_user(username, rolename)
        status = "OK"
    else:
        status = "Fail"
    return jsonify({
        "errors": errors,
        "status": status
    })

def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('auth.login'))

        return view(**kwargs)

    return wrapped_view

def login_required_API(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return jsonify({"error": "Permission denied", "code": "401"}), 401

        return view(**kwargs)

    return wrapped_view

def permission_required(permission):
    def _permission_required(view):
        @functools.wraps(view)
        def wrapped_view(**kwargs):
            if g.user is None:
                return redirect(url_for('auth.login'))
            if not g.user.has_permission(permission):
                return render_template("auth/unauthorized.html")
            return view(**kwargs)

        return wrapped_view
    return _permission_required

def permission_required_API(permission):
    def _permission_required_API(view):
        @functools.wraps(view)
        def wrapped_view(**kwargs):
            if g.user is None:
                return redirect(url_for('auth.login'))
            if not g.user.has_permission(permission):
                return jsonify({"error": "Forbidden", "code": "403"}), 403
            return view(**kwargs)

        return wrapped_view
    return _permission_required_API