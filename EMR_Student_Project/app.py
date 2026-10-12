import os, sqlite3, secrets, hmac
from functools import wraps
from datetime import datetime, date
from flask import Flask, render_template, request, redirect, url_for, flash, session, g, abort
from werkzeug.security import generate_password_hash, check_password_hash

ROOT = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(ROOT, 'emr.db')
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('EMR_SECRET_KEY', 'development-key-change-before-deployment')
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('EMR_HTTPS') == '1'


def db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys=ON')
    return g.db

@app.teardown_appcontext
def close_db(error=None):
    conn = g.pop('db', None)
    if conn is not None: conn.close()


def init_db():
    conn = db()
    conn.executescript('''
    CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, full_name TEXT NOT NULL, password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('Administrator','Receptionist','Clinician','Pharmacist')), active INTEGER NOT NULL DEFAULT 1, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS patients(id INTEGER PRIMARY KEY, patient_number TEXT UNIQUE NOT NULL, first_name TEXT NOT NULL, last_name TEXT NOT NULL, date_of_birth TEXT, sex TEXT, phone TEXT, address TEXT, created_by INTEGER, created_at TEXT DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(created_by) REFERENCES users(id));
    CREATE TABLE IF NOT EXISTS visits(id INTEGER PRIMARY KEY, patient_id INTEGER NOT NULL, visit_date TEXT NOT NULL, reason TEXT NOT NULL, diagnosis TEXT, treatment_notes TEXT, clinician_id INTEGER, created_at TEXT DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(patient_id) REFERENCES patients(id) ON DELETE CASCADE, FOREIGN KEY(clinician_id) REFERENCES users(id));
    CREATE TABLE IF NOT EXISTS medicines(id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, strength TEXT, form TEXT, quantity INTEGER NOT NULL DEFAULT 0 CHECK(quantity>=0), reorder_level INTEGER NOT NULL DEFAULT 10 CHECK(reorder_level>=0), updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS audit_logs(id INTEGER PRIMARY KEY, user_id INTEGER, action TEXT NOT NULL, details TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(user_id) REFERENCES users(id));
    ''')
    if conn.execute('SELECT COUNT(*) n FROM users').fetchone()['n'] == 0:
        demo = [('admin','Demo Administrator','Admin123!','Administrator'),('reception','Demo Receptionist','Reception123!','Receptionist'),('clinician','Demo Clinician','Clinician123!','Clinician'),('pharmacy','Demo Pharmacist','Pharmacy123!','Pharmacist')]
        for u,n,p,r in demo: conn.execute('INSERT INTO users(username,full_name,password_hash,role) VALUES(?,?,?,?)',(u,n,generate_password_hash(p),r))
    if conn.execute('SELECT COUNT(*) n FROM medicines').fetchone()['n'] == 0:
        conn.executemany('INSERT INTO medicines(name,strength,form,quantity,reorder_level) VALUES(?,?,?,?,?)', [('Paracetamol','500 mg','Tablet',120,20),('Oral Rehydration Salts','Standard','Sachet',35,10),('Amoxicillin','250 mg','Capsule',18,10)])
    conn.commit()


def audit(action, details=''):
    db().execute('INSERT INTO audit_logs(user_id,action,details) VALUES(?,?,?)',(session.get('user_id'),action,details[:250])); db().commit()


def login_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not session.get('user_id'):
            flash('Please sign in to continue.','warning'); return redirect(url_for('login'))
        return fn(*args, **kwargs)
    return wrapped


def roles_required(*roles):
    def deco(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            if not session.get('user_id'): return redirect(url_for('login'))
            if session.get('role') not in roles: abort(403)
            return fn(*args, **kwargs)
        return wrapped
    return deco

@app.before_request
def csrf_check():
    if 'csrf_token' not in session: session['csrf_token'] = secrets.token_urlsafe(24)
    if request.method == 'POST':
        token = request.form.get('csrf_token','')
        if not token or not hmac.compare_digest(token, session.get('csrf_token','')):
            abort(400, description='The form could not be verified. Refresh and try again.')

@app.context_processor
def globals_for_templates():
    return {'csrf_token':session.get('csrf_token',''), 'current_year':datetime.now().year}

@app.route('/')
def home(): return redirect(url_for('dashboard')) if session.get('user_id') else render_template('landing.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username=request.form.get('username','').strip(); password=request.form.get('password','')
        user=db().execute('SELECT * FROM users WHERE username=? AND active=1',(username,)).fetchone()
        if user and check_password_hash(user['password_hash'],password):
            session.clear(); session.update(user_id=user['id'], username=user['username'], full_name=user['full_name'], role=user['role'], csrf_token=secrets.token_urlsafe(24))
            audit('login',f"{user['username']} signed in"); return redirect(url_for('dashboard'))
        flash('Incorrect username/password or inactive account.','danger')
    return render_template('login.html')

@app.post('/logout')
@login_required
def logout():
    audit('logout',f"{session.get('username')} signed out"); session.clear(); flash('You have signed out.','success'); return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    c=db(); stats={'patients':c.execute('SELECT COUNT(*) n FROM patients').fetchone()['n'],'visits_today':c.execute("SELECT COUNT(*) n FROM visits WHERE date(visit_date)=date('now','localtime')").fetchone()['n'],'medicines':c.execute('SELECT COUNT(*) n FROM medicines').fetchone()['n'],'low_stock':c.execute('SELECT COUNT(*) n FROM medicines WHERE quantity<=reorder_level').fetchone()['n']}
    recent=c.execute('SELECT v.*,p.patient_number,p.first_name,p.last_name FROM visits v JOIN patients p ON p.id=v.patient_id ORDER BY v.id DESC LIMIT 5').fetchall()
    return render_template('dashboard.html',stats=stats,recent=recent)

@app.route('/patients')
@login_required
def patients():
    q=request.args.get('q','').strip(); c=db()
    if q:
        like='%'+q+'%'; rows=c.execute('SELECT * FROM patients WHERE patient_number LIKE ? OR first_name LIKE ? OR last_name LIKE ? OR phone LIKE ? ORDER BY id DESC LIMIT 200',(like,like,like,like)).fetchall()
    else: rows=c.execute('SELECT * FROM patients ORDER BY id DESC LIMIT 200').fetchall()
    return render_template('patients.html',patients=rows,q=q)

@app.route('/patients/new',methods=['GET','POST'])
@login_required
@roles_required('Administrator','Receptionist')
def patient_new():
    if request.method=='POST':
        first=request.form.get('first_name','').strip(); last=request.form.get('last_name','').strip(); dob=request.form.get('date_of_birth','').strip() or None
        sex=request.form.get('sex','').strip() or None; phone=request.form.get('phone','').strip() or None; address=request.form.get('address','').strip() or None
        if not first or not last: flash('First and last name are required.','danger'); return render_template('patient_form.html')
        if dob:
            try:
                if date.fromisoformat(dob)>date.today(): raise ValueError
            except ValueError: flash('Enter a valid date of birth that is not in the future.','danger'); return render_template('patient_form.html')
        number='PAT-'+datetime.now().strftime('%y%m%d')+'-'+secrets.token_hex(3).upper(); c=db()
        cur=c.execute('INSERT INTO patients(patient_number,first_name,last_name,date_of_birth,sex,phone,address,created_by) VALUES(?,?,?,?,?,?,?,?)',(number,first,last,dob,sex,phone,address,session['user_id'])); c.commit(); audit('patient_created',number); flash(f'Patient {number} registered.','success'); return redirect(url_for('patient_detail',patient_id=cur.lastrowid))
    return render_template('patient_form.html')

@app.route('/patients/<int:patient_id>')
@login_required
def patient_detail(patient_id):
    c=db(); p=c.execute('SELECT * FROM patients WHERE id=?',(patient_id,)).fetchone()
    if not p: abort(404)
    visits=c.execute('SELECT v.*,u.full_name clinician_name FROM visits v LEFT JOIN users u ON u.id=v.clinician_id WHERE v.patient_id=? ORDER BY v.id DESC',(patient_id,)).fetchall()
    return render_template('patient_detail.html',patient=p,visits=visits)

@app.route('/patients/<int:patient_id>/visits/new',methods=['GET','POST'])
@login_required
@roles_required('Administrator','Clinician')
def visit_new(patient_id):
    c=db(); p=c.execute('SELECT * FROM patients WHERE id=?',(patient_id,)).fetchone()
    if not p: abort(404)
    now=datetime.now().strftime('%Y-%m-%dT%H:%M')
    if request.method=='POST':
        vd=request.form.get('visit_date','').strip(); reason=request.form.get('reason','').strip(); diagnosis=request.form.get('diagnosis','').strip() or None; notes=request.form.get('treatment_notes','').strip() or None
        try: datetime.fromisoformat(vd)
        except ValueError: flash('Enter a valid visit date and time.','danger'); return render_template('visit_form.html',patient=p,now_value=now)
        if not reason: flash('Reason for visit is required.','danger'); return render_template('visit_form.html',patient=p,now_value=now)
        cur=c.execute('INSERT INTO visits(patient_id,visit_date,reason,diagnosis,treatment_notes,clinician_id) VALUES(?,?,?,?,?,?)',(patient_id,vd,reason,diagnosis,notes,session['user_id'])); c.commit(); audit('visit_created',f'Visit {cur.lastrowid} for {p["patient_number"]}'); flash('Visit saved.','success'); return redirect(url_for('patient_detail',patient_id=patient_id))
    return render_template('visit_form.html',patient=p,now_value=now)

@app.route('/medicines')
@login_required
@roles_required('Administrator','Pharmacist','Clinician')
def medicines(): return render_template('medicines.html',medicines=db().execute('SELECT * FROM medicines ORDER BY name').fetchall())

@app.route('/medicines/new',methods=['GET','POST'])
@login_required
@roles_required('Administrator','Pharmacist')
def medicine_new():
    if request.method=='POST':
        name=request.form.get('name','').strip(); strength=request.form.get('strength','').strip() or None; form=request.form.get('form','').strip() or None
        try:
            qty=int(request.form.get('quantity','0')); reorder=int(request.form.get('reorder_level','10'))
            if qty<0 or reorder<0: raise ValueError
        except ValueError: flash('Stock values must be whole numbers at least zero.','danger'); return render_template('medicine_form.html')
        if not name: flash('Medicine name is required.','danger'); return render_template('medicine_form.html')
        try:
            c=db(); c.execute('INSERT INTO medicines(name,strength,form,quantity,reorder_level) VALUES(?,?,?,?,?)',(name,strength,form,qty,reorder)); c.commit(); audit('medicine_created',name); flash('Medicine added.','success'); return redirect(url_for('medicines'))
        except sqlite3.IntegrityError: flash('A medicine with that name already exists.','danger')
    return render_template('medicine_form.html')

@app.post('/medicines/<int:medicine_id>/stock')
@login_required
@roles_required('Administrator','Pharmacist')
def stock_update(medicine_id):
    try: change=int(request.form.get('change','0'))
    except ValueError: flash('Enter a whole-number stock adjustment.','danger'); return redirect(url_for('medicines'))
    c=db(); m=c.execute('SELECT * FROM medicines WHERE id=?',(medicine_id,)).fetchone()
    if not m: abort(404)
    new=m['quantity']+change
    if new<0: flash('Stock cannot become negative.','danger')
    else: c.execute('UPDATE medicines SET quantity=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',(new,medicine_id)); c.commit(); audit('stock_updated',f'{m["name"]}: {change:+d}, total {new}'); flash('Stock updated.','success')
    return redirect(url_for('medicines'))

@app.route('/reports')
@login_required
@roles_required('Administrator','Clinician')
def reports():
    rows=db().execute('SELECT substr(visit_date,1,7) month,COUNT(*) total FROM visits GROUP BY substr(visit_date,1,7) ORDER BY month DESC LIMIT 12').fetchall()
    return render_template('reports.html',monthly=rows)

@app.route('/users',methods=['GET','POST'])
@login_required
@roles_required('Administrator')
def users():
    c=db()
    if request.method=='POST':
        username=request.form.get('username','').strip(); full=request.form.get('full_name','').strip(); password=request.form.get('password',''); role=request.form.get('role','')
        if not username or not full or len(password)<8 or role not in ('Administrator','Receptionist','Clinician','Pharmacist'): flash('Fill all fields and use a password of at least 8 characters.','danger')
        else:
            try: c.execute('INSERT INTO users(username,full_name,password_hash,role) VALUES(?,?,?,?)',(username,full,generate_password_hash(password),role)); c.commit(); audit('user_created',f'{username} ({role})'); flash('Account created.','success'); return redirect(url_for('users'))
            except sqlite3.IntegrityError: flash('Username already exists.','danger')
    return render_template('users.html',users=c.execute('SELECT id,username,full_name,role,active,created_at FROM users ORDER BY id').fetchall())

@app.post('/users/<int:user_id>/toggle')
@login_required
@roles_required('Administrator')
def toggle_user(user_id):
    if user_id==session.get('user_id'): flash('You cannot deactivate your own account.','danger'); return redirect(url_for('users'))
    c=db(); u=c.execute('SELECT * FROM users WHERE id=?',(user_id,)).fetchone()
    if not u: abort(404)
    c.execute('UPDATE users SET active=? WHERE id=?',(0 if u['active'] else 1,user_id)); c.commit(); audit('user_status_changed',u['username']); flash('Account status updated.','success'); return redirect(url_for('users'))

@app.route('/audit')
@login_required
@roles_required('Administrator')
def audit_page():
    rows=db().execute('SELECT a.*,u.username FROM audit_logs a LEFT JOIN users u ON u.id=a.user_id ORDER BY a.id DESC LIMIT 100').fetchall()
    return render_template('audit.html',logs=rows)

@app.errorhandler(403)
def forbidden(e): return render_template('error.html',code=403,message='You do not have permission to access this page.'),403
@app.errorhandler(404)
def not_found(e): return render_template('error.html',code=404,message='The requested page or record could not be found.'),404
@app.errorhandler(400)
def bad_request(e): return render_template('error.html',code=400,message=getattr(e,'description','The request could not be processed.')),400

with app.app_context(): init_db()
if __name__=='__main__': app.run(debug=True)  # Development only; do not expose publicly.
