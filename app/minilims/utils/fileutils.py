import os
import tempfile
import pymodm
import gridfs

class Tempfile:
    """
    Usage: 
    with Tempfile() as tmp:
        tmp.write("Text")
    pymodmfile = tmp.save()

    Or:
    with Tempfile() as tmp:
        pass
    functionthatsavestopath(tmp.name)
    pymodmfile = tmp.save()
    """

    def __init__(self):
        self.filehandle = tempfile.NamedTemporaryFile()

    def __enter__(self):
        return self.filehandle
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.filehandle.close()
    
    def save(self, filename, temp=False):
        """
        Temp files can be deleted anytime. They are created to be downloaded immediately.
        """
        db = pymodm.connection._get_db()
        fs = gridfs.GridFS( db )
        _id = fs.put( open( self.filehandle.name, 'rb'), filename=filename, temporary=temp)
        return _id

def get_file(_id):
    db = pymodm.connection._get_db()
    fs = gridfs.GridFS( db )

    return fs.get(_id)

def save_file(filename, fileobject, temp=False):
    """
    Temp files can be deleted anytime. They are created to be downloaded immediately.
    """
    db = pymodm.connection._get_db()
    fs = gridfs.GridFS( db )
    return fs.put(fileobject, filename=filename, temporary=temp)

def delete_file(_id):
    db = pymodm.connection._get_db()
    fs = gridfs.GridFS( db )
    return fs.delete(_id)