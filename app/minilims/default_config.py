# https://flask.palletsprojects.com/en/1.1.x/config/
import os

class Config(object):
    MONGO_URI = 'mongodb://' + os.environ['MONGODB_USERNAME'] + ':' + os.environ['MONGODB_PASSWORD'] + '@' + \
                os.environ['MONGODB_HOSTNAME'] + ':27017/' + os.environ['MONGODB_DATABASE'] + \
                '?authSource=' + os.environ['MONGODB_AUTH_DATABASE']
    TMPDIR='/tmp'
    LIMIT_SUBMITTED_BARCODES_TO_PROVIDED=True  # Only allows barcodes that have been provided to the user via the 
                                               # /samples/barcodes route to be submitted to the system.