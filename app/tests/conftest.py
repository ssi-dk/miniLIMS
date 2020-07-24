import os
import pytest
from minilims import create_app
from flask_pymongo import PyMongo
from minilims.models.user import User
import tests.db_data as db_data


@pytest.fixture(scope="session", autouse=True)
def app():
    app = create_app({
        'LIMIT_SUBMITTED_BARCODES_TO_PROVIDED': False,
        'SECRET_KEY':'dev', # change for production
        'TESTING': True,
        'MONGO_URI': 'mongodb://' + os.environ['MONGODB_USERNAME'] + ':' + os.environ['MONGODB_PASSWORD'] + '@' + os.environ['MONGODB_HOSTNAME'] + ':27017/' + os.environ['MONGODB_DATABASE'] + '?authSource=' + os.environ['MONGODB_AUTH_DATABASE']
    })
    with app.app_context():
        db = PyMongo(app).db
        db_data.clear_db(db)
        db_data.populate_db()
        yield app
        # clear_db(db)

@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()

class AuthActions(object):
    def __init__(self, client):
        self._client = client

    def login(self, username='test', password='test'):
        return self._client.post(
            '/auth/login',
            data={'username': username, 'password': password},
            # follow_redirects=True
        )

    def logout(self):
        return self._client.get('/auth/logout')


@pytest.fixture
def auth(client):
    return AuthActions(client)
