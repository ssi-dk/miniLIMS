from flask import g
from pymodm.errors import DoesNotExist
from pymongo.errors import DuplicateKeyError
from werkzeug.security import check_password_hash, generate_password_hash

import minilims.models.user as m_user
import minilims.models.role as m_role

def register(acc):
    m_user.User(
        oid=acc["id"],
        display_name=acc["displayName"],
        email=acc["mail"]
    ).save()

def check_if_user_exists(oid):
    return m_user.User.objects.raw({"oid": oid}).count() > 0

# def register_user(username, password, roles=[], group="default"):
#     error = None
#     if not username:
#         error = 'Username is required.'
#     elif not password:
#         error = 'Password is required.'
#     else:
#         try:
#             user = m_user.User(username=username,
#                                password=generate_password_hash(password),
#                                group=group).save(force_insert=True)
#             for role in roles:
#                 user.add_role(role)
#         except DuplicateKeyError:
#             error = 'User {} is already registered.'.format(username)
#     return error

def validate_add_role_to_user(email, rolename, submitter):
    """
    Check user has admin role, role and email exist,
    and user doesn't have that role.
    """
    errors = {}
    print(submitter)
    if not g.user.has_permission("admin_user_roles"):
        errors["user_permissions"] = "Unauthorized."
        return errors
    
    try:
        user_o = m_user.User.objects.get({"email": email})
    except DoesNotExist:
        errors["target_user"] = "Target user does not exist."
        return errors
    
    try:
        role_o = m_role.Role.objects.get({"name": rolename})
    except DoesNotExist:
        errors["role"] = "Role does not exist."
        return errors
    
    if role_o in user_o.roles:
        errors["target_user"] = "Target user has role already."

    return errors

def add_role_to_user(email, rolename):
    """
    Add role to user
    """
    user_o = m_user.User.objects.get({"email": email})
    user_o.add_role(rolename)

def validate_remove_role_from_user(email, rolename):
    """
    Check user has admin role, role and email exist,
    and user has that role.
    """
    errors = {}
    submitter = g.user
    if not g.user.has_permission("admin_user_roles"):
        errors["user_permissions"] = "Unauthorized."
        return errors
    
    try:
        user_o = m_user.User.objects.get({"email": email})
    except DoesNotExist:
        errors["target_user"] = "Target user does not exist."
        return errors
    
    try:
        role_o = m_role.Role.objects.get({"name": rolename})
    except DoesNotExist:
        errors["role"] = "Role does not exist."
        return errors
    
    if role_o not in user_o.roles:
        errors["target_user"] = "Target user doesn't have role."

    return errors

def remove_role_from_user(email, rolename):
    """
    Remove role from user
    """
    user_o = m_user.User.objects.get({"email": email})
    user_o.remove_role(rolename)