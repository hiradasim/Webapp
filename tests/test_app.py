import json
import io
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))
import pytest
from app import app, load_users

@pytest.fixture
def client(tmp_path, monkeypatch):
    data_file = tmp_path / 'users.json'
    messages_file = tmp_path / 'messages.json'
    upload_dir = tmp_path / 'uploads'
    upload_dir.mkdir()
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
        },
        'other': {
            'password': 'secret',
            'role': 'Worker',
            'branches': ['Other'],
            'tasks': []
        }
    }
    data_file.write_text(json.dumps(data))
    messages_file.write_text('[]')
    monkeypatch.setattr('app.DATA_PATH', data_file)
    monkeypatch.setattr('app.CHAT_PATH', messages_file)
    monkeypatch.setattr('app.UPLOAD_FOLDER', upload_dir)
    with app.test_client() as client:
        client.upload_dir = upload_dir
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
    task = users['worker']['tasks'][0]
    assert task['description'] == 'Delegate'
    assert task['priority'] == 'High'
    assert task['status'] == 'Incomplete'


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
    worker_task = users['worker']['tasks'][0]
    assert worker_task['description'] == 'Own Task'
    assert worker_task['priority'] == 'Low'
    assert worker_task['status'] == 'Incomplete'
    assert all(t['description'] != 'Own Task' for t in users['owner']['tasks'])


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
    task = users['worker']['tasks'][0]
    assert task['status'] == 'Done'
    assert any(h['status'] == 'Done' for h in task.get('history', []))


def test_add_note_and_reassign(client):
    client.post('/login', data={'username': 'owner', 'password': 'secret'}, follow_redirects=True)
    client.post('/tasks', data={'task': 'NoteMe', 'priority': 'Mid', 'assignee': 'worker'}, follow_redirects=True)
    client.get('/logout')

    client.post('/login', data={'username': 'worker', 'password': 'secret'}, follow_redirects=True)
    client.post('/tasks', data={'task_index': '0', 'user': 'worker', 'note': 'first note'}, follow_redirects=True)
    users = load_users()
    assert users['worker']['tasks'][0]['notes'][0]['text'] == 'first note'
    client.get('/logout')

    client.post('/login', data={'username': 'owner', 'password': 'secret'}, follow_redirects=True)
    client.post('/tasks', data={'task_index': '0', 'user': 'worker', 'reassign': 'other'}, follow_redirects=True)
    users = load_users()
    assert users['worker']['tasks'] == []
    assert users['other']['tasks'][0]['description'] == 'NoteMe'

def test_chat_requires_login(client):
    resp = client.post('/chat/messages', data={'message': 'hi'})
    assert resp.status_code == 401


def test_chat_visibility_and_attachments(client):
    client.post('/login', data={'username': 'worker', 'password': 'secret'}, follow_redirects=True)
    data = {
        'message': '@owner secret',
        'file': (io.BytesIO(b'hello'), 'note.txt')
    }
    resp = client.post('/chat/messages', data=data, content_type='multipart/form-data')
    assert resp.status_code == 200
    client.get('/logout')

    client.post('/login', data={'username': 'owner', 'password': 'secret'}, follow_redirects=True)
    resp = client.get('/chat/messages')
    msgs = resp.get_json()['messages']
    assert any(m['text'] == '@owner secret' for m in msgs)
    attachment_path = client.upload_dir / 'note.txt'
    assert attachment_path.exists()
    client.get('/logout')

    client.post('/login', data={'username': 'other', 'password': 'secret'}, follow_redirects=True)
    resp = client.get('/chat/messages')
    msgs = resp.get_json()['messages']
    assert all(m['text'] != '@owner secret' for m in msgs)

