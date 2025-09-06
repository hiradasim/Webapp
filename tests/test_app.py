import json
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))
import pytest
from app import app, DATA_PATH, load_users, save_users

@pytest.fixture
def client(tmp_path, monkeypatch):
    data_file = tmp_path / 'users.json'
    data = {
        'testuser': {'password': 'secret', 'tasks': []}
    }
    data_file.write_text(json.dumps(data))
    monkeypatch.setattr('app.DATA_PATH', data_file)
    with app.test_client() as client:
        yield client


def test_login_and_add_task(client):
    # login
    resp = client.post('/login', data={'username': 'testuser', 'password': 'secret'}, follow_redirects=True)
    assert b"testuser's Tasks" in resp.data

    # add a task
    resp = client.post('/tasks', data={'task': 'Test Task'}, follow_redirects=True)
    assert b'Test Task' in resp.data

    # verify persistence
    users = load_users()
    assert 'Test Task' in users['testuser']['tasks']


def test_requires_login(client):
    resp = client.get('/tasks')
    # should redirect to login
    assert resp.status_code == 302
