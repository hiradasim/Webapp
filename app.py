import json
import re
from pathlib import Path
from datetime import datetime, timedelta
from collections import Counter
from flask import Flask, request, session, redirect, url_for, render_template, jsonify, send_from_directory
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
    """Return active tasks for a given user."""
    users = load_users()
    return users.get(username, {}).get('tasks', [])


def get_all_tasks(username):
    """Return active and past tasks for stats/trends."""
    users = load_users()
    udata = users.get(username, {})
    return udata.get('tasks', []) + udata.get('past_tasks', [])


def get_user_performance(username):
    """Calculate task statistics for the user."""
    tasks = get_all_tasks(username)
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


def build_trend(tasks):
    """Return cumulative task creation/completion counts by date."""
    created_counts = Counter()
    done_counts = Counter()
    for t in tasks:
        created = datetime.fromisoformat(t.get('created_at')).date().isoformat()
        created_counts[created] += 1
        for h in t.get('history', []):
            if h.get('status') == 'Done':
                finished = datetime.fromisoformat(h['timestamp']).date().isoformat()
                done_counts[finished] += 1
    dates = sorted(set(created_counts) | set(done_counts))
    trend = []
    cumulative_created = 0
    cumulative_done = 0
    for d in dates:
        cumulative_created += created_counts.get(d, 0)
        cumulative_done += done_counts.get(d, 0)
        trend.append({'date': d, 'created': cumulative_created, 'done': cumulative_done})
    return trend


def weekly_completion(tasks, days: int = 7):
    """Return counts of completed tasks for each of the past ``days`` days."""
    today = datetime.utcnow().date()
    labels = []
    counts = []
    for i in range(days):
        day = today - timedelta(days=days - i - 1)
        labels.append(day.isoformat())
        done = 0
        for t in tasks:
            for h in t.get('history', []):
                if h.get('status') == 'Done':
                    ts = datetime.fromisoformat(h['timestamp']).date()
                    if ts == day:
                        done += 1
        counts.append(done)
    return {'labels': labels, 'data': counts}

@app.template_filter('overdue_class')
def overdue_class(task):
    due = task.get('due_date')
    if not due:
        return ''
    try:
        due_date = datetime.fromisoformat(due).date()
    except ValueError:
        return ''
    if due_date < datetime.utcnow().date() and task.get('status') != 'Done':
        return 'list-group-item-danger'
    return ''

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
        # create a new task
        if 'task' in request.form:
            task = request.form['task']
            priority = request.form.get('priority', 'Mid')
            assignee = request.form.get('assignee', username)
            due_date = request.form.get('due_date') or None
            if task:
                target = assignee if can_assign else username
                target_data = users.get(target)
                if target_data:
                    now = datetime.utcnow().isoformat()
                    target_data.setdefault('tasks', [])
                    target_data['tasks'].append({
                        'description': task,
                        'priority': priority,
                        'status': 'Incomplete',
                        'notes': [],
                        'due_date': due_date,
                        'created_at': now,
                        'history': [{
                            'status': 'Incomplete',
                            'timestamp': now,
                            'action': 'created'
                        }],
                    })
                    save_users(users)
        # add a note to an existing task
        elif 'note' in request.form and 'task_index' in request.form:
            target = request.form.get('user', username)
            idx = int(request.form['task_index'])
            note = request.form['note'].strip()
            tasks_list = users.get(target, {}).get('tasks', [])
            if note and 0 <= idx < len(tasks_list):
                entry = {
                    'text': note,
                    'timestamp': datetime.utcnow().isoformat(),
                    'author': username,
                }
                tasks_list[idx].setdefault('notes', []).append(entry)
                save_users(users)
        # reassign a task to another user
        elif 'task_index' in request.form and 'reassign' in request.form and can_assign:
            source = request.form.get('user', username)
            idx = int(request.form['task_index'])
            new_user = request.form['reassign']
            if new_user in users and source in users:
                tasks_list = users[source]['tasks']
                if 0 <= idx < len(tasks_list):
                    task = tasks_list.pop(idx)
                    task.setdefault('history', []).append({
                        'status': task.get('status'),
                        'timestamp': datetime.utcnow().isoformat(),
                        'action': f'reassigned_to_{new_user}'
                    })
                    users[new_user]['tasks'].append(task)
                    save_users(users)
        # update status of a task
        elif 'task_index' in request.form and 'status' in request.form:
            target = request.form.get('user', username)
            if target == username or can_assign:
                idx = int(request.form['task_index'])
                new_status = request.form['status']
                tasks_list = users.get(target, {}).get('tasks', [])
                if 0 <= idx < len(tasks_list):
                    task = tasks_list[idx]
                    task['status'] = new_status
                    task.setdefault('history', []).append({
                        'status': new_status,
                        'timestamp': datetime.utcnow().isoformat(),
                        'action': 'status_change'
                    })
                    if new_status == 'Done':
                        users[target].setdefault('past_tasks', []).append(task)
                        tasks_list.pop(idx)
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
    performance = get_user_performance(username)
    all_tasks = user_data.get('tasks', []) + user_data.get('past_tasks', [])
    trend = build_trend(all_tasks)
    return render_template(
        'tasks.html',
        user=username,
        role=role,
        branches=user_data.get('branches', []),
        can_assign=False,
        tasks=user_data.get('tasks', []),
        past_tasks=user_data.get('past_tasks', []),
        stats=performance,
        trend=trend,
    )


@app.route('/graph')
def graph():
    """Display progress bars and weekly charts for all users."""
    if 'username' not in session:
        return redirect(url_for('login'))
    users = load_users()
    stats = {}
    for uname, udata in users.items():
        perf = get_user_performance(uname)

        week = weekly_completion(udata.get('tasks', []) + udata.get('past_tasks', []))

        stats[uname] = {'performance': perf, 'week': week}
    return render_template('graph.html', stats=stats)


@app.route('/tasks/<user>/<int:index>')
def task_detail(user, index):
    """Display details and history for a single task."""
    if 'username' not in session:
        return redirect(url_for('login'))
    users = load_users()
    tasks = users.get(user, {}).get('tasks', [])
    if index < 0 or index >= len(tasks):
        return redirect(url_for('tasks'))
    task = tasks[index]
    return render_template('task_detail.html', task=task, user=user, index=index)

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
    @app.route('/manifest.json')
def manifest():
    response = send_from_directory('static', 'manifest.json')
    response.headers['Content-Type'] = 'application/manifest+json'
    return response


@app.route('/service-worker.js')
def service_worker():
    response = send_from_directory('static', 'service-worker.js')
    response.headers['Content-Type'] = 'application/javascript'
    return response

if __name__ == '__main__':
    app.run(debug=True)
