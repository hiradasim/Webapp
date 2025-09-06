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
        'owner': {
            'password': 'secret',
            'role': 'Owner',
            'branches': ['Mzone', 'UNIPRO'],
            'tasks': []
        },
        'worker': {
            'password': 'secret',
            'role': 'Worker',
            'branches': ['Mzone'],
            'tasks': []
        }
    }
    data_file.write_text(json.dumps(data))
    monkeypatch.setattr('app.DATA_PATH', data_file)
    with app.test_client() as client:
        yield client


def test_owner_can_assign_to_others(client):
    resp = client.post('/login', data={'username': 'owner', 'password': 'secret'}, follow_redirects=True)
    assert b"All Users' Tasks" in resp.data

    assert b"worker's Tasks" in resp.data

    # owner assigns task to worker
    resp = client.post(
        '/tasks',
        data={'task': 'Delegate', 'priority': 'High', 'assignee': 'worker'},
        follow_redirects=True,
    )
    assert b'Delegate' in resp.data

    users = load_users()
    assert {
        'description': 'Delegate',
        'priority': 'High',
        'status': 'Incomplete',

    } in users['worker']['tasks']


def test_worker_cannot_assign_or_view_others(client):
    resp = client.post('/login', data={'username': 'worker', 'password': 'secret'}, follow_redirects=True)
    assert b"All Users' Tasks" not in resp.data

    assert b"owner's Tasks" not in resp.data

    resp = client.post(
        '/tasks',
        data={'task': 'Own Task', 'priority': 'Low', 'assignee': 'owner'},
        follow_redirects=True,
    )
    assert b'Own Task' in resp.data

    users = load_users()
    assert {
        'description': 'Own Task',
        'priority': 'Low',
        'status': 'Incomplete',

    } in users['worker']['tasks']
    assert {
        'description': 'Own Task',
        'priority': 'Low',
        'status': 'Incomplete',

    } not in users['owner']['tasks']


def test_requires_login(client):
    resp = client.get('/tasks')
    # should redirect to login
    assert resp.status_code == 302


def test_user_can_update_status(client):
    client.post('/login', data={'username': 'worker', 'password': 'secret'}, follow_redirects=True)
    client.post('/tasks', data={'task': 'Progress Task', 'priority': 'Mid'}, follow_redirects=True)
    resp = client.post(
        '/tasks',
        data={'task_index': '0', 'status': 'Done', 'user': 'worker'},
        follow_redirects=True,
    )
    assert b'Done' in resp.data
    users = load_users()
    assert users['worker']['tasks'][0]['status'] == 'Done'


def test_chat_requires_login(client):
    resp = client.post('/chat', json={'message': 'hi'})
    assert resp.status_code == 401


def test_chat_returns_performance_summary(client):
    client.post('/login', data={'username': 'worker', 'password': 'secret'}, follow_redirects=True)
    client.post('/tasks', data={'task': 'A', 'priority': 'High'}, follow_redirects=True)
    client.post('/tasks', data={'task': 'B', 'priority': 'Low'}, follow_redirects=True)
    client.post('/tasks', data={'task_index': '0', 'status': 'Done', 'user': 'worker'}, follow_redirects=True)
    resp = client.post('/chat', json={'message': 'stats'})
    assert resp.status_code == 200
    data = resp.get_json()
    assert '2 tasks' in data['reply']
    assert '1 completed' in data['reply']

