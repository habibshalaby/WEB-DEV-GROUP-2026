"""
IY470 Group Project - UPower Gym Membership System
Flask backend using mysql.connector
Database: system_foundation | User: root
"""

from flask import Flask, render_template, request, redirect, url_for, session, flash
from datetime import datetime
import mysql.connector
import random, string, hashlib, os

app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = 'iy470_gym_secret_key_change_in_production'

# ─── DATABASE CONNECTION (your credentials) ───
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'passwd': 'rootouassim',
    'database': 'system_foundation',
}


def get_db():
    """Connect to the database. Returns (connection, cursor)."""
    conn = mysql.connector.connect(**DB_CONFIG)
    return conn, conn.cursor(dictionary=True)


def close_db(conn, cur):
    cur.close()
    conn.close()


# ─── DATABASE SETUP ───
def setup_database():
    """
    Step 1: Connect WITHOUT database → create it if missing
    Step 2: Connect WITH database → create tables if missing
    Step 3: Seed gym_options if empty
    """

    # ── Step 1: Create database if it doesn't exist ──
    print('Connecting to MySQL...')
    try:
        conn = mysql.connector.connect(
            host='localhost',
            user='root',
            passwd='rootouassim',
        )
        cur = conn.cursor()
        cur.execute("CREATE DATABASE IF NOT EXISTS system_foundation")
        conn.commit()
        cur.close()
        conn.close()
        print('✔ Database "system_foundation" ready.')
    except mysql.connector.Error as err:
        print(f'✘ MySQL connection failed: {err}')
        print('  Make sure MySQL is running and your credentials are correct.')
        print('  User: root | Password: rootouassim')
        exit(1)

    # ── Step 2: Create tables ──
    conn, cur = get_db()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS gym_options (
            gym_id INT AUTO_INCREMENT PRIMARY KEY,
            gym_name VARCHAR(50) NOT NULL,
            option_name VARCHAR(100) NOT NULL,
            base_price DECIMAL(10, 2) NOT NULL,
            joining_fee DECIMAL(10, 2) NOT NULL,
            is_addon BOOLEAN DEFAULT FALSE,
            discount_eligible BOOLEAN DEFAULT TRUE,
            student_discount_pct DECIMAL(5, 2) NOT NULL DEFAULT 0,
            pensioner_discount_pct DECIMAL(5, 2) NOT NULL DEFAULT 0
        )
    """)
    print('✔ Table "gym_options" ready.')

    cur.execute("""
        CREATE TABLE IF NOT EXISTS members (
            id INT AUTO_INCREMENT PRIMARY KEY,
            membership_id VARCHAR(20) UNIQUE NOT NULL,
            member_fullname VARCHAR(100) NOT NULL,
            email VARCHAR(120) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            date_of_birth DATE NOT NULL,
            age INT NOT NULL,
            gender ENUM('Male', 'Female', 'Other', 'Rather not say') NOT NULL DEFAULT 'Rather not say',
            status VARCHAR(50) NOT NULL,
            gym_name VARCHAR(50) NOT NULL,
            gym_option VARCHAR(100) DEFAULT NULL,
            addons VARCHAR(255) DEFAULT NULL,
            total_monthly_price DECIMAL(10, 2) NOT NULL,
            registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
        )
    """)
    print('✔ Table "members" ready.')
    conn.commit()

    # ── Step 3: Seed gym_options if empty ──
    cur.execute("SELECT COUNT(*) AS cnt FROM gym_options")
    count = cur.fetchone()['cnt']

    if count == 0:
        rows = [
            # uGym options (gym_name, option_name, base_price, joining_fee, is_addon, discount_eligible, student_disc, pensioner_disc)
            ('uGym', 'Super Off-Peak',              16,    10, False, True,  20, 15),
            ('uGym', 'Off-Peak',                    21,    10, False, True,  20, 15),
            ('uGym', 'Anytime',                     30,    10, False, True,  20, 15),
            ('uGym', 'Swimming Pool (standalone)',   25,    10, False, True,  20, 15),
            ('uGym', 'Swimming Pool (add-on)',       15,    10, True,  True,  20, 15),
            ('uGym', 'Classes (standalone)',          20,    10, False, True,  20, 15),
            ('uGym', 'Classes (add-on)',              10,    10, True,  True,  20, 15),
            ('uGym', 'Massage (standalone)',          30,    10, False, False, 20, 15),
            ('uGym', 'Massage (add-on)',              25,    10, True,  False, 20, 15),
            ('uGym', 'Physiotherapy (standalone)',    25,    10, False, False, 20, 15),
            ('uGym', 'Physiotherapy (add-on)',        20,    10, True,  False, 20, 15),
            # Power Zone options
            ('Power Zone', 'Super Off-Peak',              13,    30, False, True,  15, 20),
            ('Power Zone', 'Off-Peak',                    19,    30, False, True,  15, 20),
            ('Power Zone', 'Anytime',                     24,    30, False, True,  15, 20),
            ('Power Zone', 'Swimming Pool (standalone)',   20,    30, False, True,  15, 20),
            ('Power Zone', 'Swimming Pool (add-on)',       12.5,  30, True,  True,  15, 20),
            ('Power Zone', 'Classes (standalone)',          20,    30, False, True,  15, 20),
            ('Power Zone', 'Classes (add-on)',              0,     30, True,  True,  15, 20),
            ('Power Zone', 'Massage (standalone)',          30,    30, False, False, 15, 20),
            ('Power Zone', 'Massage (add-on)',              25,    30, True,  False, 15, 20),
            ('Power Zone', 'Physiotherapy (standalone)',    30,    30, False, False, 15, 20),
            ('Power Zone', 'Physiotherapy (add-on)',        25,    30, True,  False, 15, 20),
        ]
        cur.executemany("""INSERT INTO gym_options
            (gym_name, option_name, base_price, joining_fee, is_addon,
             discount_eligible, student_discount_pct, pensioner_discount_pct)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""", rows)
        conn.commit()
        print(f'✔ Seeded {len(rows)} gym options into database.')
    else:
        print(f'✔ gym_options already has {count} rows — skipping seed.')

    close_db(conn, cur)
    print('════════════════════════════════════════')
    print('  DATABASE SETUP COMPLETE')
    print('  Database: system_foundation')
    print('  Tables:   gym_options, members')
    print('════════════════════════════════════════')

# ─── PRICING DATA ───
UGYM_PRICES = {
    'joining_fee':10,'super_off_peak':16,'off_peak':21,'anytime':30,
    'pool_standalone':25,'pool_addon':15,'classes_standalone':20,'classes_addon':10,
    'massage_standalone':30,'massage_addon':25,'physio_standalone':25,'physio_addon':20,
}
POWERZONE_PRICES = {
    'joining_fee':30,'super_off_peak':13,'off_peak':19,'anytime':24,
    'pool_standalone':20,'pool_addon':12.5,'classes_standalone':20,'classes_addon':0,
    'massage_standalone':30,'massage_addon':25,'physio_standalone':30,'physio_addon':25,
}
DISCOUNTS = {
    ('ugym','student'):0.20,('ugym','young_adult'):0.20,('ugym','pensioner'):0.15,
    ('powerzone','student'):0.15,('powerzone','young_adult'):0.15,('powerzone','pensioner'):0.20,
}
NO_DISCOUNT_ITEMS = {'massage_standalone','massage_addon','physio_standalone','physio_addon'}

# ─── HELPERS ───
def calculate_age(dob):
    today = datetime.today().date()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

def classify_member(age, is_student):
    if age < 16: return None
    if is_student: return 'student'
    if age < 25: return 'young_adult'
    if age > 66: return 'pensioner'
    return 'standard'

def calculate_total(gym, gym_option, addons, member_type):
    prices = UGYM_PRICES if gym == 'ugym' else POWERZONE_PRICES
    rate = DISCOUNTS.get((gym, member_type), 0.0)
    jf = prices['joining_fee']; disc_t = 0.0; nodisc_t = 0.0
    if gym_option and gym_option in prices:
        c = prices[gym_option]
        if gym_option not in NO_DISCOUNT_ITEMS: disc_t += c
        else: nodisc_t += c
    for a in addons:
        if a in prices:
            c = prices[a]
            if a not in NO_DISCOUNT_ITEMS: disc_t += c
            else: nodisc_t += c
    da = round(disc_t * rate, 2); bm = round(disc_t + nodisc_t, 2)
    fm = round(bm - da, 2); tf = round(jf + fm, 2)
    return {'joining_fee':jf,'base_monthly':bm,'discount_amount':da,
            'final_monthly':fm,'total_first_month':tf,'discount_rate_pct':int(rate*100)}

def recommend_gym(mt, go, ad):
    u = calculate_total('ugym', go, ad, mt)['total_first_month']
    p = calculate_total('powerzone', go, ad, mt)['total_first_month']
    return 'ugym' if u <= p else 'powerzone'

def generate_membership_id(gym):
    prefix = 'UG' if gym == 'ugym' else 'PZ'
    conn, cur = get_db()
    while True:
        s = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        mid = f'{prefix}-{s}'
        cur.execute("SELECT id FROM members WHERE membership_id=%s", (mid,))
        if not cur.fetchone():
            close_db(conn, cur); return mid

def hash_password(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def _map_member(m):
    """Map DB column names to template-expected names."""
    if not m: return m
    
    m['full_name']     = m['member_fullname']
    m['gym']           = m['gym_name']
    m['total_price']   = float(m['total_monthly_price'])
    m['member_type']   = m['status']
    m['joined_date']   = m['registration_date']
    return m

# ─── ROUTES ───

@app.route('/')
@app.route('/home')
def home():
    session.pop('user', None); session.pop('order', None); session.pop('membership_id', None)
    return render_template('home.html')

@app.route('/userinfo', methods=['GET','POST'])
def userinfo():
    if request.method == 'POST':
        fn = request.form.get('full_name','').strip()
        em = request.form.get('email','').strip()
        ds = request.form.get('date_of_birth','').strip()
        pw = request.form.get('password','').strip()
        st = request.form.get('status') == 'student'
        errors = []
        if not fn: errors.append('Full name is required.')
        if not pw or len(pw)<6: errors.append('Password must be at least 6 characters.')
        if not em or '@' not in em: errors.append('A valid email is required.')
        dob = None
        if not ds: errors.append('Date of birth is required.')
        else:
            try: dob = datetime.strptime(ds,'%Y-%m-%d').date(); age = calculate_age(dob)
            except: errors.append('Invalid date format.')
        if errors: return render_template('userinfo.html', errors=errors, form_data=request.form)
        if dob > datetime.today().date():
            return render_template('userinfo.html', errors=['DOB cannot be in the future.'], form_data=request.form)
        if age > 120:
            return render_template('userinfo.html', errors=['Please enter a valid DOB.'], form_data=request.form)
        if age < 16:
            return render_template('userinfo.html', errors=['You must be at least 16 to join.'], form_data=request.form)
        mt = classify_member(age, st)
        session['user'] = {'full_name':fn,'email':em,'dob':ds,'age':age,'is_student':st,'member_type':mt,'password':pw or 'default123'}
        return redirect(url_for('membership'))
    return render_template('userinfo.html', errors=[], form_data={})

@app.route('/membership', methods=['GET','POST'])
def membership():
    if 'user' not in session: return redirect(url_for('userinfo'))
    user = session['user']
    if request.method == 'POST':
        gc = request.form.get('gym_choice','').strip()
        go = request.form.get('gym_option','').strip()
        ar = request.form.get('addons','').strip()
        ad = [a.strip() for a in ar.split(',') if a.strip()]
        if gc == 'power': gc = 'powerzone'
        go = go.replace('-','_')
        errors = []
        if not go and not ad:
            errors.append('Please select at least one option.')
            return render_template('membership.html', user=user, ugym_prices=UGYM_PRICES,
                                   powerzone_prices=POWERZONE_PRICES, editing=session.get('editing'), errors=errors)
        if gc == 'recommend': gc = recommend_gym(user['member_type'], go, ad)
        if gc not in ('ugym','powerzone'):
            errors.append('Please select a gym.')
            return render_template('membership.html', user=user, ugym_prices=UGYM_PRICES,
                                   powerzone_prices=POWERZONE_PRICES, editing=session.get('editing'), errors=errors)
        cost = calculate_total(gc, go, ad, user['member_type'])
        session['order'] = {'gym':gc,'gym_option':go,'addons':ad,'member_type':user['member_type'],**cost}
        return redirect(url_for('checkout'))
    return render_template('membership.html', user=user, ugym_prices=UGYM_PRICES,
                           powerzone_prices=POWERZONE_PRICES, editing=session.get('editing'), errors=[])

@app.route('/checkout', methods=['GET','POST'])
def checkout():
    if 'user' not in session or 'order' not in session: return redirect(url_for('userinfo'))
    user = session['user']; order = session['order']; editing = session.get('editing')
    if editing:
        order['old_monthly'] = editing['old_monthly']
        order['price_diff'] = round(order['final_monthly'] - editing['old_monthly'], 2)
    if request.method == 'POST':
        conn, cur = get_db()
        if editing:
            cur.execute("UPDATE members SET gym_name=%s, gym_option=%s, addons=%s, total_monthly_price=%s WHERE id=%s",
                        (order['gym'], order.get('gym_option',''), ','.join(order.get('addons',[])), order['final_monthly'], editing['member_id']))
            conn.commit(); close_db(conn, cur)
            session.pop('order',None); session.pop('editing',None)
            flash('Your membership has been updated!','success')
            return redirect(url_for('member_dashboard'))
        else:
            dob = datetime.strptime(user['dob'],'%Y-%m-%d').date()
            cur.execute("SELECT id FROM members WHERE email=%s", (user['email'],))
            if cur.fetchone():
                close_db(conn, cur); flash('Email already exists. Please log in.','warning')
                return redirect(url_for('login'))
            mc = generate_membership_id(order['gym'])
            cur.execute("""INSERT INTO members
                (membership_id, member_fullname, email, password_hash, date_of_birth, age,
                 status, gym_name, gym_option, addons, total_monthly_price)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (mc, user['full_name'], user['email'], hash_password(user.get('password','default123')),
                 dob, user.get('age', calculate_age(dob)), user['member_type'],
                 order['gym'], order.get('gym_option',''), ','.join(order.get('addons',[])), order['final_monthly']))
            conn.commit(); close_db(conn, cur)
            session['membership_id'] = mc; session.pop('order',None)
            return redirect(url_for('confirmation'))
    return render_template('checkout.html', user=user, order=order, editing=editing)

@app.route('/confirmation')
def confirmation():
    if 'membership_id' not in session: return redirect(url_for('home'))
    mc = session['membership_id']; user = session.get('user',{})
    conn, cur = get_db()
    cur.execute("SELECT * FROM members WHERE membership_id=%s", (mc,))
    member = _map_member(cur.fetchone())
    close_db(conn, cur)
    session.pop('membership_id',None); session.pop('user',None)
    return render_template('confirmation.html', membership_id=mc, member=member, user=user)

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        em = request.form.get('email','').strip()
        pw = request.form.get('password','').strip()
        mi = request.form.get('membership_id','').strip()
        errors = []

        # All three fields required
        if not mi or not em or not pw:
            errors.append('Please enter your Membership ID, email, and password.')
            return render_template('login.html', errors=errors)

        conn, cur = get_db()

        # Find member by membership code
        cur.execute("SELECT * FROM members WHERE membership_id=%s", (mi,))
        m = cur.fetchone()
        close_db(conn, cur)

        if not m:
            errors.append('No membership found with that ID.')
            return render_template('login.html', errors=errors)

        # Verify email matches
        if m['email'] != em:
            errors.append('Email does not match this Membership ID.')
            return render_template('login.html', errors=errors)

        # Verify password matches
        if m['password_hash'] != hash_password(pw):
            errors.append('Incorrect password. Please try again.')
            return render_template('login.html', errors=errors)

        # All three correct — login
        session['logged_in_member_id'] = m['membership_id']
        flash(f"Welcome back, {m['member_fullname']}!", 'success')
        return redirect(url_for('member_dashboard'))

    return render_template('login.html', errors=[])

@app.route('/logout')
def logout():
    session.clear(); flash('You have been logged out.','info')
    return redirect(url_for('home'))

@app.route('/dashboard')
def member_dashboard():
    if 'logged_in_member_id' not in session: return redirect(url_for('login'))
    conn, cur = get_db()
    cur.execute("SELECT * FROM members WHERE membership_id=%s", (session['logged_in_member_id'],))
    member = _map_member(cur.fetchone()); close_db(conn, cur)
    if not member: session.pop('logged_in_member_id',None); return redirect(url_for('login'))
    return render_template('dashboard.html', member=member)

@app.route('/edit-membership')
def edit_membership():
    if 'logged_in_member_id' not in session: return redirect(url_for('login'))
    conn, cur = get_db()
    cur.execute("SELECT * FROM members WHERE membership_id=%s", (session['logged_in_member_id'],))
    m = cur.fetchone(); close_db(conn, cur)
    if not m: return redirect(url_for('login'))
    dob = m['date_of_birth']
    if isinstance(dob, str): dob = datetime.strptime(dob,'%Y-%m-%d').date()
    session['user'] = {'full_name':m['member_fullname'],'email':m['email'],'dob':dob.strftime('%Y-%m-%d'),'member_type':m['status'],'password':''}
    session['editing'] = {'member_id':m['id'],'old_monthly':float(m['total_monthly_price']),
                          'old_gym':m['gym_name'],'old_option':m['gym_option'] or '','old_addons':m['addons'] or ''}
    return redirect(url_for('membership'))

# ─── ENTRY POINT ───
if __name__ == '__main__':
    app.root_path = os.path.dirname(os.path.abspath(__file__))

    print('════════════════════════════════════════')
    print('  UPOWER GYM MEMBERSHIP SYSTEM')
    print('  Starting up...')
    print('════════════════════════════════════════')

    setup_database()

    print()
    print('  Server: http://127.0.0.1:5000/home')
    print('  Press Ctrl+C to stop')
    print('════════════════════════════════════════')
    print()

    app.run(debug=True)