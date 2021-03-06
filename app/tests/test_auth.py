import pytest
from flask import g, session


def test_register(client, app):
    assert client.get('/auth/register').status_code == 200
    from minilims.models.user import User
    response = client.post(
        '/auth/register', data={'email': 'testregister@test.com', 'password': 'testregister'}
    )
    assert 'http://localhost/auth/login' == response.headers['Location']

    with app.app_context():
        assert User.objects.get({"email": "testregister@test.com"}) is not None

@pytest.mark.parametrize(('email', 'password', 'message'), (
    ('', '', b'Email is required.'),
    ('a', '', b'Password is required.'),
    ('test@test.com', 'test', b'already registered'),
))
def test_register_validate_input(client, email, password, message):
    response = client.post(
        '/auth/register',
        data={'email': email, 'password': password},
        follow_redirects=True
    )
    assert message in response.data

def test_login(client, auth):
    assert client.get('/auth/login').status_code == 200
    response = auth.login()
    assert response.headers['Location'] == 'http://localhost/'

    with client:
        client.get('/')
        assert session['user'] == "5dbbefc2263b8ecd0c83dad5"
        assert g.user.email == 'test@test.com'


@pytest.mark.parametrize(('email', 'password', 'message'), (
    ('a', 'test', b'Incorrect email.'),
    ('test@test.com', 'a', b'Incorrect password.'),
))
def test_login_validate_input(auth, email, password, message):
    response = auth.login(email, password)
    assert message in response.data

def test_logout(client, auth):
    auth.login()

    with client:
        auth.logout()
        assert 'user_id' not in session


def test_add_permission():
    from minilims.models.user import User
    from minilims.models.role import Role
    Role(name="testrole", permissions=["permission1"]).save()
    user_o = User(email="test_role@test.com", password="test").save()
    assert user_o.has_permission("permission1") == False
    user_o.add_role("testrole")
    assert user_o.has_permission("permission1") == True
    user_o.remove_role("testrole")
    assert user_o.has_permission("permission1") == False

def test_add_permission_request(client, auth):
    from minilims.models.user import User
    from minilims.models.role import Role
    Role(name="test_role2admin", permissions=["admin_all"]).save()
    role_o_user = Role(name="test_role2user", permissions=["admin_all"]).save()
    client.post(
        '/auth/register',
        data={'email': "test_user2admin@test.com", 'password': "test"},
        follow_redirects=True
    )
    client.post(
        '/auth/register',
        data={'email': "test_user2lab@test.com", 'password': "test"},
        follow_redirects=True
    )
    user_o_admin = User.objects.get({"email": "test_user2admin@test.com"})
    user_o_admin.add_role("test_role2admin")

    with client:
        auth.login("test_user2admin@test.com", "test")
        response = client.post("/auth/u/test_user2lab@test.com/addrole/test_role2user")
        assert response.json["status"] == "OK"
        user_o_lab = User.objects.get({"email": "test_user2lab@test.com"})
        user_o_lab.refresh_from_db()
        assert role_o_user in user_o_lab.roles

        response = client.post("/auth/u/test_user2lab@test.com/removerole/test_role2user")
        assert response.json["status"] == "OK"
        user_o_lab.refresh_from_db()
        assert not role_o_user in user_o_lab.roles
