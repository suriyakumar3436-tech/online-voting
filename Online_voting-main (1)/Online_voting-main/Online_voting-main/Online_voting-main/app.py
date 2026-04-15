from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import hashlib
import os
from functools import wraps
from datetime import timedelta, datetime

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'college_voting_secret_key_2026')
app.permanent_session_lifetime = timedelta(days=1)

# ─────────────────────────────────────────
#  Auto DB — SQLite locally, PostgreSQL on Render
# ─────────────────────────────────────────

DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db():
    if DATABASE_URL:
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        conn.autocommit = False
        return conn
    else:
        import sqlite3
        DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'voting.db')
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

def ph():
    """Return correct placeholder for current DB"""
    return '%s' if DATABASE_URL else '?'

def serial():
    return 'SERIAL' if DATABASE_URL else 'INTEGER'

def autoincrement():
    return '' if DATABASE_URL else 'AUTOINCREMENT'

# ─────────────────────────────────────────
#  Database Initialization
# ─────────────────────────────────────────

def init_db():
    conn = get_db()
    if DATABASE_URL:
        c = conn.cursor()
        execute = c.execute
    else:
        c = conn.cursor()
        execute = c.execute

    # Students table — admin adds students, they only login
    if DATABASE_URL:
        c.execute('''CREATE TABLE IF NOT EXISTS students (
            id SERIAL PRIMARY KEY,
            roll_number TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            department TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            has_voted INTEGER DEFAULT 0,
            voted_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS candidates (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            position TEXT NOT NULL,
            department TEXT NOT NULL,
            manifesto TEXT,
            symbol TEXT,
            image TEXT,
            vote_count INTEGER DEFAULT 0,
            UNIQUE(name, position)
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS votes (
            id SERIAL PRIMARY KEY,
            roll_number TEXT NOT NULL,
            candidate_id INTEGER NOT NULL,
            position TEXT NOT NULL,
            voted_at TEXT DEFAULT CURRENT_TIMESTAMP
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS admins (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS election_settings (
            id INTEGER PRIMARY KEY DEFAULT 1,
            election_name TEXT DEFAULT 'Student Council Election 2026',
            voting_open INTEGER DEFAULT 1
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS activity_log (
            id SERIAL PRIMARY KEY,
            roll_number TEXT,
            action TEXT NOT NULL,
            details TEXT,
            ip_address TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS student_activity (
            id SERIAL PRIMARY KEY,
            roll_number TEXT NOT NULL,
            student_name TEXT,
            department TEXT,
            action TEXT NOT NULL,
            page TEXT,
            details TEXT,
            ip_address TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP
        )''')

        # Admin
        admin_pass = hashlib.sha256('spartanze'.encode()).hexdigest()
        c.execute("INSERT INTO admins (username, password) VALUES (%s, %s) ON CONFLICT (username) DO NOTHING", ('admin', admin_pass))
        c.execute("INSERT INTO election_settings (id, election_name, voting_open) VALUES (1, 'Student Council Election 2026', 1) ON CONFLICT (id) DO NOTHING")

        candidates = [
            ('SURIYA', 'President', 'Computer Science', 'I will build a stronger, more connected student community.', '🦁', 'suriya.jpg.png'),
            ('SARUGEH', 'President', 'Electronics', 'Empowering every student voice with transparency.', '🌟', 'sarugesh.jpg.jpg'),
        ]
        for cd in candidates:
            c.execute("INSERT INTO candidates (name, position, department, manifesto, symbol, image) VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (name, position) DO NOTHING", cd)

    else:
        # SQLite
        c.execute('''CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            roll_number TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            department TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            has_voted INTEGER DEFAULT 0,
            voted_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            position TEXT NOT NULL,
            department TEXT NOT NULL,
            manifesto TEXT,
            symbol TEXT,
            image TEXT,
            vote_count INTEGER DEFAULT 0,
            UNIQUE(name, position)
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            roll_number TEXT NOT NULL,
            candidate_id INTEGER NOT NULL,
            position TEXT NOT NULL,
            voted_at TEXT DEFAULT CURRENT_TIMESTAMP
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS election_settings (
            id INTEGER PRIMARY KEY DEFAULT 1,
            election_name TEXT DEFAULT 'Student Council Election 2026',
            voting_open INTEGER DEFAULT 1
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            roll_number TEXT,
            action TEXT NOT NULL,
            details TEXT,
            ip_address TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS student_activity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            roll_number TEXT NOT NULL,
            student_name TEXT,
            department TEXT,
            action TEXT NOT NULL,
            page TEXT,
            details TEXT,
            ip_address TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP
        )''')

        admin_pass = hashlib.sha256('spartanze'.encode()).hexdigest()
        c.execute("INSERT OR IGNORE INTO admins (username, password) VALUES (?, ?)", ('admin', admin_pass))
        c.execute("INSERT OR IGNORE INTO election_settings (id, election_name, voting_open) VALUES (1, 'Student Council Election 2026', 1)")

        candidates = [
            ('SURIYA', 'President', 'Computer Science', 'I will build a stronger, more connected student community.', '🦁', 'suriya.jpg.png'),
            ('SARUGEH', 'President', 'Electronics', 'Empowering every student voice with transparency.', '🌟', 'sarugesh.jpg.jpg'),
        ]
        for cd in candidates:
            c.execute("INSERT OR IGNORE INTO candidates (name, position, department, manifesto, symbol, image) VALUES (?,?,?,?,?,?)", cd)

    conn.commit()
    conn.close()

# ─────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def db_fetch_one(query, params=()):
    conn = get_db()
    c = conn.cursor()
    c.execute(query, params)
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def db_fetch_all(query, params=()):
    conn = get_db()
    c = conn.cursor()
    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def db_execute(query, params=()):
    conn = get_db()
    c = conn.cursor()
    c.execute(query, params)
    conn.commit()
    conn.close()

# ─────────────────────────────────────────
#  Activity Logs
# ─────────────────────────────────────────

def log_activity(action, details='', roll_number='Guest'):
    try:
        ip = request.remote_addr
        p = ph()
        db_execute(
            f"INSERT INTO activity_log (roll_number, action, details, ip_address) VALUES ({p},{p},{p},{p})",
            (roll_number, action, details, ip)
        )
    except:
        pass

def log_student_activity(action, page, details=''):
    try:
        roll = session.get('student_roll', 'Guest')
        name = session.get('student_name', 'Unknown')
        ip = request.remote_addr
        p = ph()
        student = db_fetch_one(f"SELECT department FROM students WHERE roll_number={p}", (roll,))
        dept = student['department'] if student else 'Unknown'
        db_execute(
            f'''INSERT INTO student_activity
               (roll_number, student_name, department, action, page, details, ip_address)
               VALUES ({p},{p},{p},{p},{p},{p},{p})''',
            (roll, name, dept, action, page, details, ip)
        )
    except:
        pass

# ─────────────────────────────────────────
#  Auth Decorators
# ─────────────────────────────────────────

def student_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'student_roll' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'admin_logged_in' not in session:
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated

# ─────────────────────────────────────────
#  Public Routes
# ─────────────────────────────────────────

@app.route('/')
def home():
    return render_template('home.html')

# ─────────────────────────────────────────
#  Student Login ONLY — No Register
# ─────────────────────────────────────────

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        roll = request.form['roll_number'].strip().upper()
        password = request.form['password'].strip()
        p = ph()

        student = db_fetch_one(
            f"SELECT * FROM students WHERE roll_number={p} AND password={p}",
            (roll, hash_password(password))
        )

        if student:
            session.permanent = True
            session['student_roll'] = student['roll_number']
            session['student_name'] = student['name']
            session['has_voted'] = bool(student['has_voted'])
            log_activity('LOGIN', 'Student logged in', roll)
            log_student_activity('LOGGED_IN', 'Login Page', f'Roll:{roll}')
            return jsonify({'success': True, 'has_voted': bool(student['has_voted'])})
        else:
            log_activity('LOGIN_FAILED', f'Failed login attempt: {roll}', roll)
            return jsonify({'success': False, 'message': 'Invalid Roll Number or Password!'})

    return render_template('login.html')

@app.route('/logout')
def logout():
    log_activity('LOGOUT', 'Student logged out', session.get('student_roll', 'Unknown'))
    log_student_activity('LOGGED_OUT', 'Logout', 'Session ended')
    session.clear()
    return redirect(url_for('home'))

# ─────────────────────────────────────────
#  Voting Routes
# ─────────────────────────────────────────

@app.route('/vote')
@student_required
def vote():
    if session.get('has_voted'):
        return redirect(url_for('thank_you'))

    settings = db_fetch_one("SELECT * FROM election_settings WHERE id=1")

    # Check if voting is open
    if not settings['voting_open']:
        return render_template('voting_closed.html',
                               student_name=session['student_name'])

    candidates_raw = db_fetch_all("SELECT * FROM candidates ORDER BY position, name")

    positions = {}
    for c in candidates_raw:
        pos = c['position']
        if pos not in positions:
            positions[pos] = []
        positions[pos].append(c)

    log_student_activity('VISITED_VOTE_PAGE', 'Vote Page', 'Opened voting page')

    return render_template('vote.html',
                           positions=positions,
                           student_name=session['student_name'],
                           election_name=settings['election_name'] if settings else 'Student Council Election 2026')

@app.route('/submit_vote', methods=['POST'])
@student_required
def submit_vote():
    if session.get('has_voted'):
        return jsonify({'success': False, 'message': 'You have already voted!'})

    # Check voting is open
    settings = db_fetch_one("SELECT * FROM election_settings WHERE id=1")
    if not settings['voting_open']:
        return jsonify({'success': False, 'message': 'Voting is currently closed!'})

    data = request.get_json()
    votes = data.get('votes', {})
    p = ph()
    roll = session['student_roll']

    conn = get_db()
    c = conn.cursor()

    # Double check in DB
    c.execute(f"SELECT has_voted FROM students WHERE roll_number={p}", (roll,))
    student = c.fetchone()
    if not student or dict(student)['has_voted']:
        conn.close()
        return jsonify({'success': False, 'message': 'You have already voted!'})

    try:
        for position, candidate_id in votes.items():
            candidate_id = int(candidate_id)
            c.execute(
                f"INSERT INTO votes (roll_number, candidate_id, position) VALUES ({p},{p},{p})",
                (roll, candidate_id, position)
            )
            c.execute(
                f"UPDATE candidates SET vote_count = vote_count + 1 WHERE id={p}",
                (candidate_id,)
            )

        c.execute(
            f"UPDATE students SET has_voted=1, voted_at={p} WHERE roll_number={p}",
            (datetime.now().isoformat(), roll)
        )
        conn.commit()
        session['has_voted'] = True
        log_activity('VOTE', 'Student voted successfully', roll)
        log_student_activity('VOTED', 'Vote Page', f'Voted for {len(votes)} positions')
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        print(f"Vote error: {e}")
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()

@app.route('/thank_you')
@student_required
def thank_you():
    log_student_activity('VISITED_THANKYOU', 'Thank You Page', 'Vote confirmed')
    return render_template('thank_you.html', student_name=session['student_name'])

# ─────────────────────────────────────────
#  Admin Routes
# ─────────────────────────────────────────

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        p = ph()

        admin = db_fetch_one(
            f"SELECT * FROM admins WHERE username={p} AND password={p}",
            (username, hash_password(password))
        )

        if admin:
            session['admin_logged_in'] = True
            session['admin_username'] = username
            log_activity('ADMIN_LOGIN', f'Admin logged in: {username}', 'ADMIN')
            return jsonify({'success': True})
        return jsonify({'success': False, 'message': 'Invalid credentials!'})

    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    session.pop('admin_username', None)
    return redirect(url_for('home'))

# ── Admin: Add Student (replaces public register) ──

@app.route('/admin/add_student', methods=['GET', 'POST'])
@admin_required
def admin_add_student():
    if request.method == 'POST':
        roll = request.form['roll_number'].strip().upper()
        name = request.form['name'].strip()
        dept = request.form['department'].strip()
        email = request.form.get('email',roll+'@college.edu').strip()
        # Default password = roll number itself
        password = request.form.get('password', roll).strip()
        p = ph()

        conn = get_db()
        c = conn.cursor()
        try:
            c.execute(
                f"INSERT INTO students (roll_number, name, department, email, password) VALUES ({p},{p},{p},{p},{p})",
                (roll, name, dept, email, hash_password(password))
            )
            conn.commit()
            log_activity('ADMIN_ADD_STUDENT', f'Admin added student: {roll}', 'ADMIN')
            return jsonify({'success': True, 'message': f'Student {roll} added! Default password: {password}'})
        except Exception as e:
            conn.rollback()
            err = str(e)
            if 'roll_number' in err or 'unique' in err.lower():
                return jsonify({'success': False, 'message': 'Roll number already exists!'})
            return jsonify({'success': False, 'message': 'Email already exists!'})
        finally:
            conn.close()

    return render_template('admin_add_student.html')

# ── Admin: Delete Student ──

@app.route('/admin/delete_student/<roll>', methods=['POST'])
@admin_required
def delete_student(roll):
    p = ph()
    try:
        db_execute(f"DELETE FROM students WHERE roll_number={p}", (roll,))
        log_activity('ADMIN_DELETE_STUDENT', f'Admin deleted student: {roll}', 'ADMIN')
        return jsonify({'success': True, 'message': f'Student {roll} deleted!'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

# ── Admin: Reset Student Vote ──

@app.route('/admin/reset_vote/<roll>', methods=['POST'])
@admin_required
def reset_vote(roll):
    p = ph()
    try:
        db_execute(f"UPDATE students SET has_voted=0, voted_at=NULL WHERE roll_number={p}", (roll,))
        db_execute(f"DELETE FROM votes WHERE roll_number={p}", (roll,))
        log_activity('ADMIN_RESET_VOTE', f'Admin reset vote for: {roll}', 'ADMIN')
        return jsonify({'success': True, 'message': f'Vote reset for {roll}!'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

# ── Admin: Results ──

@app.route('/admin/results')
@admin_required
def admin_results():
    p = ph()
    candidates = db_fetch_all("SELECT * FROM candidates ORDER BY position, vote_count DESC")
    total_students = db_fetch_one("SELECT COUNT(*) as cnt FROM students")['cnt']
    total_voted = db_fetch_one("SELECT COUNT(*) as cnt FROM students WHERE has_voted=1")['cnt']
    settings = db_fetch_one("SELECT * FROM election_settings WHERE id=1")

    positions = {}
    for c in candidates:
        pos = c['position']
        if pos not in positions:
            positions[pos] = []
        positions[pos].append(c)

    turnout = round((total_voted / total_students * 100), 1) if total_students > 0 else 0

    return render_template('results.html',
                           positions=positions,
                           total_students=total_students,
                           total_voted=total_voted,
                           turnout=turnout,
                           election_name=settings['election_name'])

# ── Admin: Activity Log ──

@app.route('/admin/activity')
@admin_required
def admin_activity():
    logs = db_fetch_all("SELECT * FROM activity_log ORDER BY timestamp DESC LIMIT 100")
    return render_template('activity.html', logs=logs)

# ── Admin: All Students ──

@app.route('/admin/students')
@admin_required
def admin_students():
    students = db_fetch_all("SELECT * FROM students ORDER BY created_at DESC")
    activities = db_fetch_all("SELECT * FROM student_activity ORDER BY timestamp DESC")
    return render_template('students.html', students=students, activities=activities)

# ── Admin: Toggle Voting ──

@app.route('/admin/toggle_voting', methods=['POST'])
@admin_required
def toggle_voting():
    p = ph()
    current = db_fetch_one("SELECT voting_open FROM election_settings WHERE id=1")
    new_val = 0 if current['voting_open'] else 1
    db_execute(f"UPDATE election_settings SET voting_open={p} WHERE id=1", (new_val,))
    return jsonify({'success': True, 'voting_open': bool(new_val)})

# ─────────────────────────────────────────
#  App Startup
# ─────────────────────────────────────────

app.jinja_env.filters['enumerate'] = enumerate

with app.app_context():
    init_db()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
