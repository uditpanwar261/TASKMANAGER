from flask import Flask, render_template, request, jsonify, redirect, url_for, session, g
from datetime import datetime
import sqlite3
import hashlib
import os
import secrets

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))
DATABASE = os.environ.get('DATABASE_PATH', 'taskmanager.db')

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

@app.teardown_appcontext
def close_db(error):
    db = g.pop('db', None)
    if db: db.close()

def query_db(sql, args=(), one=False):
    cur = get_db().execute(sql, args)
    rv = cur.fetchall()
    return (rv[0] if rv else None) if one else rv

def execute_db(sql, args=()):
    db = get_db()
    cur = db.execute(sql, args)
    db.commit()
    return cur.lastrowid

def init_db():
    db = sqlite3.connect(DATABASE)
    db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            created_by INTEGER NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS project_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            role TEXT DEFAULT 'Member',
            joined_at TEXT DEFAULT (datetime('now')),
            UNIQUE(project_id, user_id)
        );
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'To Do',
            priority TEXT DEFAULT 'Medium',
            project_id INTEGER NOT NULL,
            assigned_to INTEGER,
            created_by INTEGER NOT NULL,
            due_date TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
    """)
    db.commit()
    db.close()

def hash_password(password):
    salt = secrets.token_hex(16)
    hashed = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}:{hashed}"

def verify_password(password, stored):
    try:
        salt, hashed = stored.split(':')
        return hashlib.sha256((salt + password).encode()).hexdigest() == hashed
    except: return False

def get_initials(name):
    parts = (name or '').strip().split()
    if len(parts) >= 2: return (parts[0][0] + parts[1][0]).upper()
    return parts[0][:2].upper() if parts else '??'

def is_overdue(due_date, status):
    if not due_date or status == 'Done': return False
    try: return datetime.strptime(due_date, '%Y-%m-%d') < datetime.utcnow()
    except: return False

def fmt_date(d):
    if not d: return None
    try: return datetime.strptime(d, '%Y-%m-%d').strftime('%b %d')
    except: return d

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session: return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def current_user():
    if 'user_id' not in session: return None
    return query_db("SELECT * FROM users WHERE id=?", [session['user_id']], one=True)

def get_role(project_id):
    user = current_user()
    if not user: return None
    m = query_db("SELECT role FROM project_members WHERE project_id=? AND user_id=?", [project_id, user['id']], one=True)
    return m['role'] if m else None

@app.route('/')
def index():
    return redirect(url_for('dashboard') if 'user_id' in session else url_for('login'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        d = request.get_json()
        name = (d.get('name') or '').strip()
        email = (d.get('email') or '').strip().lower()
        password = d.get('password') or ''
        if not name or not email or not password:
            return jsonify({'error': 'All fields are required'}), 400
        if len(password) < 6:
            return jsonify({'error': 'Password must be at least 6 characters'}), 400
        if query_db("SELECT id FROM users WHERE email=?", [email], one=True):
            return jsonify({'error': 'Email already registered'}), 400
        uid = execute_db("INSERT INTO users (name, email, password) VALUES (?,?,?)",
                         [name, email, hash_password(password)])
        session['user_id'] = uid
        return jsonify({'success': True, 'redirect': url_for('dashboard')})
    return render_template('auth.html', mode='signup')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        d = request.get_json()
        email = (d.get('email') or '').strip().lower()
        password = d.get('password') or ''
        user = query_db("SELECT * FROM users WHERE email=?", [email], one=True)
        if not user or not verify_password(password, user['password']):
            return jsonify({'error': 'Invalid email or password'}), 401
        session['user_id'] = user['id']
        return jsonify({'success': True, 'redirect': url_for('dashboard')})
    return render_template('auth.html', mode='login')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    user = current_user()
    projects_raw = query_db("""
        SELECT p.*, COUNT(t.id) as task_count
        FROM projects p JOIN project_members pm ON pm.project_id = p.id
        LEFT JOIN tasks t ON t.project_id = p.id
        WHERE pm.user_id=? GROUP BY p.id ORDER BY p.created_at DESC
    """, [user['id']])
    projects = []
    for p in projects_raw:
        members = query_db("SELECT u.name FROM project_members pm JOIN users u ON u.id=pm.user_id WHERE pm.project_id=?", [p['id']])
        projects.append({**dict(p), 'member_initials': [get_initials(m['name']) for m in members]})

    my_tasks = query_db("""
        SELECT t.*, p.name as project_name FROM tasks t
        JOIN projects p ON p.id=t.project_id WHERE t.assigned_to=? ORDER BY t.created_at DESC
    """, [user['id']])
    tasks_list = [dict(t) for t in my_tasks]
    for t in tasks_list:
        t['is_overdue'] = is_overdue(t['due_date'], t['status'])
        t['due_date_fmt'] = fmt_date(t['due_date'])

    return render_template('dashboard.html', user=dict(user),
        user_initials=get_initials(user['name']), projects=projects,
        my_tasks=tasks_list,
        total=len(tasks_list),
        todo=sum(1 for t in tasks_list if t['status']=='To Do'),
        in_progress=sum(1 for t in tasks_list if t['status']=='In Progress'),
        done=sum(1 for t in tasks_list if t['status']=='Done'),
        overdue=sum(1 for t in tasks_list if t['is_overdue']))

@app.route('/projects', methods=['POST'])
@login_required
def create_project():
    user = current_user()
    d = request.get_json()
    name = (d.get('name') or '').strip()
    if not name: return jsonify({'error': 'Project name is required'}), 400
    pid = execute_db("INSERT INTO projects (name, description, created_by) VALUES (?,?,?)",
                     [name, (d.get('description') or '').strip(), user['id']])
    execute_db("INSERT INTO project_members (project_id, user_id, role) VALUES (?,?,?)", [pid, user['id'], 'Admin'])
    return jsonify({'success': True, 'project_id': pid})

@app.route('/projects/<int:project_id>')
@login_required
def project_detail(project_id):
    user = current_user()
    role = get_role(project_id)
    if not role: return redirect(url_for('dashboard'))
    project = query_db("SELECT * FROM projects WHERE id=?", [project_id], one=True)
    if not project: return redirect(url_for('dashboard'))

    members = query_db("""
        SELECT pm.*, u.name as user_name, u.email as user_email
        FROM project_members pm JOIN users u ON u.id=pm.user_id WHERE pm.project_id=?
    """, [project_id])
    members_list = [{**dict(m), 'initials': get_initials(m['user_name'])} for m in members]

    tasks_raw = query_db("""
        SELECT t.*, u.name as assignee_name FROM tasks t
        LEFT JOIN users u ON u.id=t.assigned_to WHERE t.project_id=? ORDER BY t.created_at DESC
    """, [project_id])
    tasks = []
    for t in tasks_raw:
        td = dict(t)
        td['is_overdue'] = is_overdue(td['due_date'], td['status'])
        td['due_date_fmt'] = fmt_date(td['due_date'])
        td['assignee_initials'] = get_initials(td['assignee_name']) if td['assignee_name'] else None
        tasks.append(td)

    return render_template('project.html', project=dict(project), role=role,
        members=members_list, tasks=tasks, user=dict(user),
        user_initials=get_initials(user['name']),
        all_users=[dict(u) for u in query_db("SELECT id, name, email FROM users ORDER BY name")],
        todo_tasks=[t for t in tasks if t['status']=='To Do'],
        inprog_tasks=[t for t in tasks if t['status']=='In Progress'],
        done_tasks=[t for t in tasks if t['status']=='Done'])

@app.route('/projects/<int:project_id>/delete', methods=['POST'])
@login_required
def delete_project(project_id):
    if get_role(project_id) != 'Admin': return jsonify({'error': 'Admin only'}), 403
    execute_db("DELETE FROM tasks WHERE project_id=?", [project_id])
    execute_db("DELETE FROM project_members WHERE project_id=?", [project_id])
    execute_db("DELETE FROM projects WHERE id=?", [project_id])
    return jsonify({'success': True})

@app.route('/projects/<int:project_id>/invite', methods=['POST'])
@login_required
def invite_member(project_id):
    if get_role(project_id) != 'Admin': return jsonify({'error': 'Admin only'}), 403
    d = request.get_json()
    email = (d.get('email') or '').strip().lower()
    invite_role = d.get('role', 'Member')
    user = query_db("SELECT * FROM users WHERE email=?", [email], one=True)
    if not user: return jsonify({'error': 'No user found with that email'}), 404
    if query_db("SELECT id FROM project_members WHERE project_id=? AND user_id=?", [project_id, user['id']], one=True):
        return jsonify({'error': 'User is already a member'}), 400
    execute_db("INSERT INTO project_members (project_id, user_id, role) VALUES (?,?,?)", [project_id, user['id'], invite_role])
    return jsonify({'success': True, 'name': user['name'], 'initials': get_initials(user['name']), 'role': invite_role})

@app.route('/projects/<int:project_id>/members/<int:user_id>/remove', methods=['POST'])
@login_required
def remove_member(project_id, user_id):
    me = current_user()
    if get_role(project_id) != 'Admin' or me['id'] == user_id: return jsonify({'error': 'Not allowed'}), 403
    execute_db("DELETE FROM project_members WHERE project_id=? AND user_id=?", [project_id, user_id])
    return jsonify({'success': True})

@app.route('/projects/<int:project_id>/tasks', methods=['POST'])
@login_required
def create_task(project_id):
    user = current_user()
    if not get_role(project_id): return jsonify({'error': 'Not a member'}), 403
    d = request.get_json()
    title = (d.get('title') or '').strip()
    if not title: return jsonify({'error': 'Task title is required'}), 400
    assigned_to = d.get('assigned_to') or None
    due_date = d.get('due_date') or None
    tid = execute_db("""
        INSERT INTO tasks (title, description, priority, status, project_id, assigned_to, created_by, due_date)
        VALUES (?,?,?,?,?,?,?,?)
    """, [title, d.get('description',''), d.get('priority','Medium'), d.get('status','To Do'),
          project_id, assigned_to, user['id'], due_date])

    assignee_name = assignee_initials = None
    if assigned_to:
        a = query_db("SELECT name FROM users WHERE id=?", [assigned_to], one=True)
        if a:
            assignee_name = a['name']
            assignee_initials = get_initials(a['name'])

    return jsonify({'success': True, 'task': {
        'id': tid, 'title': title, 'status': d.get('status','To Do'),
        'priority': d.get('priority','Medium'),
        'assignee_name': assignee_name, 'assignee_initials': assignee_initials,
        'due_date': fmt_date(due_date), 'is_overdue': is_overdue(due_date, d.get('status','To Do'))
    }})

@app.route('/tasks/<int:task_id>/status', methods=['POST'])
@login_required
def update_task_status(task_id):
    task = query_db("SELECT * FROM tasks WHERE id=?", [task_id], one=True)
    if not task or not get_role(task['project_id']): return jsonify({'error': 'Not allowed'}), 403
    new_status = (request.get_json() or {}).get('status')
    if new_status not in ['To Do', 'In Progress', 'Done']: return jsonify({'error': 'Invalid status'}), 400
    execute_db("UPDATE tasks SET status=? WHERE id=?", [new_status, task_id])
    return jsonify({'success': True, 'status': new_status})

@app.route('/tasks/<int:task_id>/delete', methods=['POST'])
@login_required
def delete_task(task_id):
    user = current_user()
    task = query_db("SELECT * FROM tasks WHERE id=?", [task_id], one=True)
    if not task: return jsonify({'error': 'Not found'}), 404
    role = get_role(task['project_id'])
    if role != 'Admin' and task['created_by'] != user['id']: return jsonify({'error': 'Not allowed'}), 403
    execute_db("DELETE FROM tasks WHERE id=?", [task_id])
    return jsonify({'success': True})

@app.route('/api/users')
@login_required
def api_users():
    users = query_db("SELECT id, name, email FROM users ORDER BY name")
    return jsonify([{'id': u['id'], 'name': u['name'], 'initials': get_initials(u['name']), 'email': u['email']} for u in users])

init_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
