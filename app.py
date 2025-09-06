import json
import re
from pathlib import Path
from flask import Flask, request, session, redirect, url_for, render_template, jsonify
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "supersecret"
DATA_PATH = Path('data/users.json')
CHAT_PATH = Path('data/messages.json')
UPLOAD_FOLDER = Path('static/uploads')


@app.template_filter('priority_class')
def priority_class(priority):
    return {
        'High': 'bg-danger',
        'Mid': 'bg-warning text-dark',
        'Low': 'bg-success',
    }.get(priority, 'bg-secondary')

def load_users():
    with DATA_PATH.open() as f:
        return json.load(f)

def save_users(users):
    with DATA_PATH.open('w') as f:
        json.dump(users, f, indent=2)


def load_messages():
    if CHAT_PATH.exists():
        with CHAT_PATH.open() as f:
            return json.load(f)
    return []


def save_messages(messages):
    CHAT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CHAT_PATH.open('w') as f:
        json.dump(messages, f, indent=2)


def get_user_tasks(username):
    """Return the task list for a given user."""
    users = load_users()
    return users.get(username, {}).get('tasks', [])


def get_user_performance(username):
    """Calculate task statistics for the user."""
    tasks = get_user_tasks(username)
    total = len(tasks)
    done = sum(1 for t in tasks if t.get('status') == 'Done')
    pending = total - done
    priorities = {"High": 0, "Mid": 0, "Low": 0}
    for t in tasks:
        p = t.get('priority', 'Mid')
        priorities[p] = priorities.get(p, 0) + 1
    completion = (done / total * 100) if total else 0
    return {
        'total': total,
        'done': done,
        'pending': pending,
        'completion_rate': completion,
        'priority': priorities,
    }

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        users = load_users()
        user = users.get(username)
        if user and user['password'] == password:
            session['username'] = username
            return redirect(url_for('tasks'))
        else:
            return render_template('login.html', error='Invalid credentials')
    return render_template('login.html')

@app.route('/tasks', methods=['GET', 'POST'])
def tasks():
    if 'username' not in session:
        return redirect(url_for('login'))

    users = load_users()
    username = session['username']
    user_data = users[username]
    role = user_data.get('role')
    can_assign = role in {'Owner', 'Leader', 'IT'}

    if request.method == 'POST':
        if 'task' in request.form:
            task = request.form['task']
            priority = request.form.get('priority', 'Mid')
            assignee = request.form.get('assignee', username)
            if task:
                target = assignee if can_assign else username
                target_data = users.get(target)
                if target_data:
                    target_data['tasks'].append({
                        'description': task,
                        'priority': priority,
                        'status': 'Incomplete',
                    })
                    save_users(users)
        elif 'task_index' in request.form and 'status' in request.form:
            target = request.form.get('user', username)
            if target == username:
                idx = int(request.form['task_index'])
                new_status = request.form['status']
                tasks_list = users[target]['tasks']
                if 0 <= idx < len(tasks_list):
                    tasks_list[idx]['status'] = new_status
                    save_users(users)


    if can_assign:
        return render_template(
            'tasks.html',
            user=username,
            role=role,
            branches=user_data.get('branches', []),
            can_assign=True,
            all_users=users,
        )
    return render_template(
        'tasks.html',
        user=username,
        role=role,
        branches=user_data.get('branches', []),
        can_assign=False,
        tasks=user_data['tasks'],
    )

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))


@app.route('/chat')
def chat():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('chat.html')


@app.route('/chat/messages', methods=['GET', 'POST'])
def chat_messages():
    if 'username' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    if request.method == 'POST':
        text = request.form.get('message', '').strip()
        if not text and 'file' not in request.files:
            return jsonify({'error': 'No content'}), 400
        users = load_users()
        sender = session['username']
        tags = {t for t in re.findall(r'@([\w]+)', text)}
        recipients = set()
        for t in tags:
            if t in users:
                recipients.add(t)
            else:
                for uname, udata in users.items():
                    if t in udata.get('branches', []):
                        recipients.add(uname)
        if recipients:
            recipients.add(sender)
        attachments = []
        file = request.files.get('file')
        if file and file.filename:
            UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
            filename = secure_filename(file.filename)
            save_path = UPLOAD_FOLDER / filename
            file.save(save_path)
            attachments.append(f'uploads/{filename}')
        messages = load_messages()
        messages.append({
            'sender': sender,
            'text': text,
            'recipients': list(recipients),
            'attachments': attachments,
        })
        save_messages(messages)
        return jsonify({'status': 'ok'})

    username = session['username']
    messages = load_messages()
    visible = [
        m for m in messages
        if not m['recipients'] or username in m['recipients']
    ]
    return jsonify({'messages': visible})

if __name__ == '__main__':
    app.run(debug=True)
