import pytest

def test_init_db_command(runner, monkeypatch):
    class Recorder(object):
        called = False

    def fake_init_db(app):
        Recorder.called = True

    monkeypatch.setattr('minilims.services.db.clear_db', fake_init_db)
    result = runner.invoke(args=['clear-db'])
    assert 'Initialized' in result.output
    assert Recorder.called
