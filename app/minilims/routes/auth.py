import functools
import requests
import uuid
from flask import (
    Blueprint, flash, jsonify, g, redirect, render_template, request, session, url_for, current_app
)
from werkzeug.security import check_password_hash, generate_password_hash

import minilims.services.auth as s_auth
from minilims.models.user import User
from bson.objectid import ObjectId
from pymongo import errors
import msal


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

@bp.route("/graphcall")
def graphcall():
    token = _get_token_from_cache(current_app.config["SCOPE"])
    if not token:
        return redirect(url_for("auth.login"))
    graph_data = requests.get(  # Use token to call downstream service
        current_app.config["ENDPOINT"],
        headers={'Authorization': 'Bearer ' + token['access_token']},
        ).json()
    return render_template('auth/display.html', result=graph_data)

@bp.route('/login')
def login():
    session["state"] = str(uuid.uuid4())
    # Technically we could use empty list [] as scopes to do just sign in,
    # here we choose to also collect end user consent upfront
    auth_url = _build_auth_url(scopes=current_app.config["SCOPE"], state=session["state"])
    return render_template("auth/login.html", auth_url=auth_url, version=msal.__version__)

@bp.route("/getAToken")  # Its absolute URL must match your app's redirect_uri set in AAD
def authorized():
    if request.args.get('state') != session.get("state"):
        return redirect(url_for("index"))  # No-OP. Goes back to Index page
    if "error" in request.args:  # Authentication/Authorization failure
        return render_template("auth_error.html", result=request.args)
    if request.args.get('code'):
        cache = _load_cache()
        result = _build_msal_app(cache=cache).acquire_token_by_authorization_code(
            request.args['code'],
            scopes=current_app.config["SCOPE"],  # Misspelled scope would cause an HTTP 400 error here
            redirect_uri=url_for("auth.authorized", _external=True))
        if "error" in result:
            return render_template("auth_error.html", result=result)
        session["user"] = result.get("id_token_claims")
        _save_cache(cache)
    return redirect(url_for("samples.submit"))


# def login():
#     if request.method == 'POST':
#         username = request.form['username']
#         password = request.form['password']
#         error = None
#         try:
#             user = User.objects.get({"username":username})
#         except User.DoesNotExist:
#             error = "Incorrect username."
#         else:
#             if not check_password_hash(user.password, password):
#                 error = 'Incorrect password.'

#         if error is None:
#             session.clear()
#             session['user_id'] = str(user._id)
#             return redirect(url_for('index'))

#         flash(error)

#     return render_template('auth/login.html')

# @bp.before_app_request
# def load_logged_in_user():
#     user_id = session.get('user_id')
#     if user_id is None:
#         g.user = None
#     else:
#         try:
#             g.user = User.objects.get({"_id": ObjectId(user_id)})
#         except User.DoesNotExist:
#             g.user = None

@bp.route('/logout')
def logout():
    # session.clear()
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


def _build_msal_app(cache=None, authority=None):
    return msal.ConfidentialClientApplication(
        current_app.config["CLIENT_ID"], authority=authority or current_app.config["AUTHORITY"],
        client_credential=current_app.config["CLIENT_SECRET"], token_cache=cache)

def _build_auth_url(authority=None, scopes=None, state=None):
    return _build_msal_app(authority=authority).get_authorization_request_url(
        scopes or [],
        state=state or str(uuid.uuid4()),
        redirect_uri=url_for("auth.authorized", _external=True))

def _load_cache():
    cache = msal.SerializableTokenCache()
    if session.get("token_cache"):
        cache.deserialize(session["token_cache"])
    return cache

def _save_cache(cache):
    if cache.has_state_changed:
        session["token_cache"] = cache.serialize()

def _get_token_from_cache(scope=None):
    cache = _load_cache()  # This web app maintains one cache per session
    cca = _build_msal_app(cache=cache)
    accounts = cca.get_accounts()
    if accounts:  # So all account(s) belong to the current signed-in user
        result = cca.acquire_token_silent(scope, account=accounts[0])
        _save_cache(cache)
        return result