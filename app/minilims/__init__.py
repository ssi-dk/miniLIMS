import os
from datetime import date
from flask import Flask, request, jsonify, render_template
from flask.json import JSONEncoder
from flask_session import Session 

class CustomJSONEncoder(JSONEncoder):
    def default(self, o):
        if isinstance(o, date):
            return o.isoformat()

        return super().default(o)

def create_app(config=None):
    # Create and configure the app
    app = Flask(__name__, instance_relative_config=True)
    app.json_encoder = CustomJSONEncoder
    app.config.from_object('minilims.default_config.Config')
    

    if config is not None:
        # load the instance config, if it exists, when not testing
        app.config.from_mapping(config)  # , silent=True)
    # load the test config if passed in
    app.config.from_pyfile("./config.py", silent=True)
    Session(app)
    # Initialize mongodb extension
    from minilims.services import db
    db.load_db(app)
    db.init_commands(app)

    from minilims.routes import auth
    app.register_blueprint(auth.bp)

    from minilims.routes import lims
    app.register_blueprint(lims.bp)
    app.add_url_rule('/', endpoint='index')

    from minilims.routes import samples
    app.register_blueprint(samples.bp)

    from minilims.routes import tags
    app.register_blueprint(tags.bp)

    return app
