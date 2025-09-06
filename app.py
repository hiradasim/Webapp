import json
from pathlib import Path
from flask import Flask, request, session, redirect, url_for, render_template

app = Flask(__name__)
app.secret_key = "supersecret"
DATA_PATH = Path('data/users.json')

def load_users():
    with DATA_PATH.open() as f:
        return json.load(f)

def save_users(users):
    with DATA_PATH.open('w') as f:
        json.dump(users, f, indent=2)

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
                })
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

if __name__ == '__main__':
    app.run(debug=True)
