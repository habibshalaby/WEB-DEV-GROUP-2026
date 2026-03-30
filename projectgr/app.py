"""
IY470 Group Project - Gym Membership Signup System
Flask backend for: home, userinfo, membership, checkout, confirmation, login pages
"""

from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import random
import string
import os

app = Flask(__name__,template_folder='templates',
            static_folder='static')
app.secret_key = 'iy470_gym_secret_key_change_in_production'

# ─────────────────────────────────────────────
# DATABASE CONFIGURATION
# ─────────────────────────────────────────────
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:rootouassim@localhost/gym_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


# ─────────────────────────────────────────────
# DATABASE MODELS
# ─────────────────────────────────────────────

class MembershipOption(db.Model):
    """Stores available membership options for each gym."""
    __tablename__ = 'membership_options'

    id          = db.Column(db.Integer, primary_key=True)
    gym         = db.Column(db.String(50), nullable=False)      # 'ugym' or 'powerzone'
    option_name = db.Column(db.String(100), nullable=False)
    base_price  = db.Column(db.Float, nullable=False)
    is_addon    = db.Column(db.Boolean, default=False)          # True = add-on (requires gym membership)
    discount_eligible = db.Column(db.Boolean, default=True)     # False = massage/physio (no discount)

    def __repr__(self):
        return f'<MembershipOption {self.gym} - {self.option_name}: £{self.base_price}>'


class Member(db.Model):
    """Stores registered gym members and their membership IDs."""
    __tablename__ = 'members'

    id            = db.Column(db.Integer, primary_key=True)
    membership_id = db.Column(db.String(20), unique=True, nullable=False)
    full_name     = db.Column(db.String(100), nullable=False)
    email         = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    date_of_birth = db.Column(db.Date, nullable=False)
    member_type   = db.Column(db.String(20), nullable=False)    # 'standard', 'student', 'young_adult', 'pensioner'
    gym           = db.Column(db.String(50), nullable=False)    # 'ugym' or 'powerzone'
    gym_option    = db.Column(db.String(100), nullable=True)    # chosen gym tier
    addons        = db.Column(db.String(255), nullable=True)    # comma-separated add-ons
    total_price   = db.Column(db.Float, nullable=False)
    joined_date   = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Member {self.membership_id} - {self.full_name}>'


# ─────────────────────────────────────────────
# PRICING DATA  (mirrors the spec tables)
# ─────────────────────────────────────────────

UGYM_PRICES = {
    'joining_fee':          10,
    'super_off_peak':       16,
    'off_peak':             21,
    'anytime':              30,
    'pool_standalone':      25,
    'pool_addon':           15,
    'classes_standalone':   20,
    'classes_addon':        10,
    'massage_standalone':   30,
    'massage_addon':        25,
    'physio_standalone':    25,
    'physio_addon':         20,
}

POWERZONE_PRICES = {
    'joining_fee':          30,
    'super_off_peak':       13,
    'off_peak':             19,
    'anytime':              24,
    'pool_standalone':      20,
    'pool_addon':           12.5,
    'classes_standalone':   20,
    'classes_addon':        0,
    'massage_standalone':   30,
    'massage_addon':        25,
    'physio_standalone':    30,
    'physio_addon':         25,
}

# Discount rates per gym per member type
# Key: (gym, member_type)  Value: discount fraction (0.0 = no discount)
DISCOUNTS = {
    ('ugym',      'student'):      0.20,
    ('ugym',      'young_adult'):  0.20,
    ('ugym',      'pensioner'):    0.15,
    ('powerzone', 'student'):      0.15,
    ('powerzone', 'young_adult'):  0.15,
    ('powerzone', 'pensioner'):    0.20,
}

# Items NOT eligible for discount (spec: "not applicable to massage and physiotherapy")
NO_DISCOUNT_ITEMS = {'massage_standalone', 'massage_addon', 'physio_standalone', 'physio_addon'}


# ─────────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────────

def calculate_age(dob: datetime.date) -> int:
    """Return the person's current age in years."""
    today = datetime.today().date()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def classify_member(age: int, is_student: bool) -> str:
    """
    Return the membership category string based on age and student status.
    Returns None if the user is under 16 (ineligible).
    """
    if age < 16:
        return None                         # under age – blocked
    if is_student:
        return 'student'
    if age < 25:
        return 'young_adult'
    if age > 66:
        return 'pensioner'
    return 'standard'


def calculate_total(gym: str, gym_option: str, addons: list, member_type: str) -> dict:
    """
    Calculate the full monthly cost breakdown for a user.

    Parameters
    ----------
    gym         : 'ugym' or 'powerzone'
    gym_option  : key from UGYM_PRICES / POWERZONE_PRICES, or None if no gym membership
    addons      : list of add-on keys (e.g. ['pool_addon', 'classes_addon'])
    member_type : 'standard' | 'student' | 'young_adult' | 'pensioner'

    Returns
    -------
    dict with keys: joining_fee, base_monthly, discount_amount, final_monthly, total_first_month
    """
    prices        = UGYM_PRICES if gym == 'ugym' else POWERZONE_PRICES
    discount_rate = DISCOUNTS.get((gym, member_type), 0.0)

    joining_fee        = prices['joining_fee']
    discountable_total = 0.0   # items eligible for discount (pre-discount price)
    no_discount_total  = 0.0   # massage & physio — never discounted

    # Gym tier cost
    if gym_option and gym_option in prices:
        cost = prices[gym_option]
        if gym_option not in NO_DISCOUNT_ITEMS:
            discountable_total += cost
        else:
            no_discount_total += cost

    # Add-on costs
    for addon in addons:
        if addon in prices:
            cost = prices[addon]
            if addon not in NO_DISCOUNT_ITEMS:
                discountable_total += cost
            else:
                no_discount_total += cost

    # Apply discount only to eligible items
    discount_amount = round(discountable_total * discount_rate, 2)
    base_monthly    = round(discountable_total + no_discount_total, 2)
    final_monthly   = round(base_monthly - discount_amount, 2)
    total_first_month = round(joining_fee + final_monthly, 2)

    return {
        'joining_fee':       joining_fee,
        'base_monthly':      base_monthly,
        'discount_amount':   discount_amount,
        'final_monthly':     final_monthly,
        'total_first_month': total_first_month,
        'discount_rate_pct': int(discount_rate * 100),
    }


def recommend_gym(member_type: str, gym_option_key: str, addons: list) -> str:
    """
    Compare total cost at both gyms for the same selections and return
    the cheaper one.  Returns 'ugym' or 'powerzone'.
    """
    ugym_total      = calculate_total('ugym',      gym_option_key, addons, member_type)['total_first_month']
    powerzone_total = calculate_total('powerzone', gym_option_key, addons, member_type)['total_first_month']
    return 'ugym' if ugym_total <= powerzone_total else 'powerzone'


def generate_membership_id(gym: str) -> str:
    """
    Generate a unique membership ID.
    Format: UG-XXXXXX (uGym) or PZ-XXXXXX (Power Zone)
    """
    prefix  = 'UG' if gym == 'ugym' else 'PZ'
    while True:
        suffix  = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        mid     = f'{prefix}-{suffix}'
        exists  = Member.query.filter_by(membership_id=mid).first()
        if not exists:
            return mid


def hash_password(password: str) -> str:
    """Simple hash – replace with werkzeug.security in production."""
    import hashlib
    return hashlib.sha256(password.encode()).hexdigest()


# ─────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────

# ── 1. HOME ──────────────────────────────────

@app.route('/')
@app.route('/home')
def home():
    """
    Landing page.
    Shows both gyms (uGym & Power Zone) with a brief intro and a
    'Get Started' button that leads to the user-info form.
    Clears any leftover signup data (but keeps login session).
    """
    session.pop('user', None)
    session.pop('order', None)
    session.pop('membership_id', None)
    return render_template('home.html')


# ── 2. USER INFO ─────────────────────────────

@app.route('/userinfo', methods=['GET', 'POST'])
def userinfo():
    """
    Collects personal details: name, email, date of birth, and whether
    the user is a student.

    GET  → show the form
    POST → validate inputs, classify membership type, store in session,
           redirect to /membership
    """
    if request.method == 'POST':
        full_name  = request.form.get('full_name', '').strip()
        email      = request.form.get('email', '').strip()
        dob_str    = request.form.get('date_of_birth', '').strip()
        password   = request.form.get('password', '').strip()
        # Template sends a <select name="status"> with values 'student' or 'none'
        is_student = request.form.get('status') == 'student'

        # ── Validation ──────────────────────────
        errors = []

        if not full_name:
            errors.append('Full name is required.')

        if not password or len(password) < 6:
            errors.append('Password must be at least 6 characters.')

        if not email or '@' not in email:
            errors.append('A valid email address is required.')

        dob = None
        if not dob_str:
            errors.append('Date of birth is required.')
        else:
            try:
                dob = datetime.strptime(dob_str, '%Y-%m-%d').date()
                age = calculate_age(dob)
            except ValueError:
                errors.append('Invalid date format. Please use YYYY-MM-DD.')

        if errors:
            return render_template('userinfo.html', errors=errors,
                                   form_data=request.form)

        # ── Future date blocked ──
        if dob > datetime.today().date():
            errors.append('Date of birth cannot be in the future.')
            return render_template('userinfo.html', errors=errors,
                                   form_data=request.form)

        # ── Unrealistic age blocked ──
        if age > 120:
            errors.append('Please enter a valid date of birth.')
            return render_template('userinfo.html', errors=errors,
                                   form_data=request.form)

        # ── Age restriction (under 16 blocked) ──
        if age < 16:
            errors.append('You must be at least 16 years old to join either gym.')
            return render_template('userinfo.html', errors=errors,
                                   form_data=request.form)

        member_type = classify_member(age, is_student)

        # ── Store in session ─────────────────────
        session['user'] = {
            'full_name':   full_name,
            'email':       email,
            'dob':         dob_str,
            'age':         age,
            'is_student':  is_student,
            'member_type': member_type,
            'password':    password if password else 'default123',
        }

        return redirect(url_for('membership'))

    # GET – show the form (logout and home already clear stale data)
    return render_template('userinfo.html', errors=[], form_data={})


# ── 3. MEMBERSHIP ────────────────────────────

@app.route('/membership', methods=['GET', 'POST'])
def membership():
    """
    Lets the user choose:
      - A gym (uGym / Power Zone / let the system recommend)
      - A gym-access tier  (super off-peak / off-peak / anytime / none)
      - Optional add-ons   (pool, classes, massage, physiotherapy)

    GET  → show membership options with prices for both gyms
    POST → calculate costs, optionally recommend gym, store in session,
           redirect to /checkout
    """
    if 'user' not in session:
        return redirect(url_for('userinfo'))

    user = session['user']

    if request.method == 'POST':
        gym_choice   = request.form.get('gym_choice', '').strip()
        gym_option   = request.form.get('gym_option', '').strip()
        # JS sends comma-separated string in a single hidden input
        addons_raw   = request.form.get('addons', '').strip()
        addons       = [a.strip() for a in addons_raw.split(',') if a.strip()]
        # Normalize: JS uses 'power', Flask expects 'powerzone'
        if gym_choice == 'power':
            gym_choice = 'powerzone'
        # Normalize: JS uses hyphens (super-off-peak), Flask keys use underscores
        gym_option = gym_option.replace('-', '_')

        errors = []

        # Must pick at least a gym tier OR an add-on (can't sign up for nothing)
        if not gym_option and not addons:
            errors.append('Please select at least one membership option.')
            return render_template('membership.html', user=user,
                                   ugym_prices=UGYM_PRICES,
                                   powerzone_prices=POWERZONE_PRICES,
                                   editing=session.get('editing'),
                                   errors=errors)

        # Resolve "recommend" choice
        if gym_choice == 'recommend':
            gym_choice = recommend_gym(user['member_type'], gym_option, addons)

        if gym_choice not in ('ugym', 'powerzone'):
            errors.append('Please select a gym.')
            return render_template('membership.html', user=user,
                                   ugym_prices=UGYM_PRICES,
                                   powerzone_prices=POWERZONE_PRICES,
                                   editing=session.get('editing'),
                                   errors=errors)

        # Calculate costs
        cost_breakdown = calculate_total(gym_choice, gym_option, addons, user['member_type'])

        session['order'] = {
            'gym':          gym_choice,
            'gym_option':   gym_option,
            'addons':       addons,
            'member_type':  user['member_type'],
            **cost_breakdown,
        }

        return redirect(url_for('checkout'))

    # GET – render with prices for both gyms
    return render_template('membership.html',
                           user=user,
                           ugym_prices=UGYM_PRICES,
                           powerzone_prices=POWERZONE_PRICES,
                           editing=session.get('editing'),
                           errors=[])


# ── 4. CHECKOUT ──────────────────────────────

@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    """
    Shows a full order summary (selected gym, options, discounts, total).
    No real payment processing – clicking 'Pay' creates the membership record
    and redirects to /confirmation.

    If session['editing'] exists, this is a membership edit:
      - Shows old vs new price comparison
      - Updates existing member instead of creating new one

    GET  → display order summary
    POST → create/update Member record in DB, redirect to /confirmation
    """
    if 'user' not in session or 'order' not in session:
        return redirect(url_for('userinfo'))

    user     = session['user']
    order    = session['order']
    editing  = session.get('editing', None)

    # Calculate price difference for edits
    if editing:
        old_monthly = editing['old_monthly']
        new_monthly = order['final_monthly']
        price_diff  = round(new_monthly - old_monthly, 2)
        order['old_monthly'] = old_monthly
        order['price_diff']  = price_diff

    if request.method == 'POST':

        if editing:
            # ── EDIT MODE: update existing member ──
            member = Member.query.get(editing['member_id'])
            if not member:
                flash('Member not found. Please log in again.', 'warning')
                return redirect(url_for('login'))

            member.gym        = order['gym']
            member.gym_option = order.get('gym_option', '')
            member.addons     = ','.join(order.get('addons', []))
            member.total_price = order['final_monthly']
            db.session.commit()

            # Clean up session
            session.pop('order', None)
            session.pop('editing', None)

            flash('Your membership has been updated!', 'success')
            return redirect(url_for('member_dashboard'))

        else:
            # ── NEW SIGNUP MODE ──
            dob = datetime.strptime(user['dob'], '%Y-%m-%d').date()

            # Check for duplicate email
            existing = Member.query.filter_by(email=user['email']).first()
            if existing:
                flash('An account with this email already exists. Please log in.', 'warning')
                return redirect(url_for('login'))

            # Generate unique membership ID
            membership_id = generate_membership_id(order['gym'])

            # Persist new member
            new_member = Member(
                membership_id = membership_id,
                full_name     = user['full_name'],
                email         = user['email'],
                password_hash = hash_password(user.get('password', 'default123')),
                date_of_birth = dob,
                member_type   = user['member_type'],
                gym           = order['gym'],
                gym_option    = order.get('gym_option', ''),
                addons        = ','.join(order.get('addons', [])),
                total_price   = order['final_monthly'],
            )
            db.session.add(new_member)
            db.session.commit()

            # Save membership_id in session for confirmation page
            session['membership_id'] = membership_id
            session.pop('order', None)

            return redirect(url_for('confirmation'))

    return render_template('checkout.html', user=user, order=order, editing=editing)


# ── 5. CONFIRMATION ──────────────────────────

@app.route('/confirmation')
def confirmation():
    """
    Displays the membership confirmation with:
      - The generated membership ID
      - The chosen gym and plan summary
      - Total cost paid

    Clears the session after display so a fresh sign-up can begin.
    """
    if 'membership_id' not in session:
        return redirect(url_for('home'))

    membership_id = session['membership_id']
    user          = session.get('user', {})

    # Look up the member record for a full summary
    member = Member.query.filter_by(membership_id=membership_id).first()

    # Clear session after displaying confirmation
    session.pop('membership_id', None)
    session.pop('user', None)

    return render_template('confirmation.html',
                           membership_id=membership_id,
                           member=member,
                           user=user)


# ── 6. LOGIN ─────────────────────────────────

@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    Allows an existing member to log in using either:
      - Email + password
      - Membership ID (spec: "use this ID to access their membership on the website")

    GET  → show login form
    POST → authenticate, redirect to member dashboard or show error
    """
    if request.method == 'POST':
        email         = request.form.get('email', '').strip()
        password      = request.form.get('password', '').strip()
        membership_id = request.form.get('membership_id', '').strip()

        errors = []

        # ── Option A: Login via Membership ID ──
        if membership_id:
            member = Member.query.filter_by(membership_id=membership_id).first()
            if not member:
                errors.append('No membership found with that ID. Please check and try again.')
                return render_template('login.html', errors=errors)

            session['logged_in_member_id'] = member.membership_id
            flash(f'Welcome back, {member.full_name}!', 'success')
            return redirect(url_for('member_dashboard'))

        # ── Option B: Login via Email + Password ──
        if not email or not password:
            errors.append('Please enter email + password, or use your Membership ID.')
            return render_template('login.html', errors=errors)

        member = Member.query.filter_by(email=email).first()

        if not member or member.password_hash != hash_password(password):
            errors.append('Invalid email or password. Please try again.')
            return render_template('login.html', errors=errors)

        # Successful login – store in session
        session['logged_in_member_id'] = member.membership_id
        flash(f'Welcome back, {member.full_name}!', 'success')
        return redirect(url_for('member_dashboard'))

    return render_template('login.html', errors=[])


@app.route('/logout')
def logout():
    """Clear ALL session data and redirect to home."""
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('home'))


@app.route('/dashboard')
def member_dashboard():
    """
    Shows the logged-in member their membership details.
    Redirects to /login if not authenticated.
    """
    if 'logged_in_member_id' not in session:
        return redirect(url_for('login'))

    member = Member.query.filter_by(
        membership_id=session['logged_in_member_id']
    ).first()

    if not member:
        session.pop('logged_in_member_id', None)
        return redirect(url_for('login'))

    return render_template('dashboard.html', member=member)


@app.route('/edit-membership')
def edit_membership():
    """
    Allows a logged-in member to change their membership.
    Loads their data into session and redirects to /membership.
    """
    if 'logged_in_member_id' not in session:
        return redirect(url_for('login'))

    member = Member.query.filter_by(
        membership_id=session['logged_in_member_id']
    ).first()

    if not member:
        return redirect(url_for('login'))

    # Populate session with existing member data
    session['user'] = {
        'full_name':   member.full_name,
        'email':       member.email,
        'dob':         member.date_of_birth.strftime('%Y-%m-%d'),
        'member_type': member.member_type,
        'password':    '',  # not needed for edit
    }

    # Flag that we are editing, store old price for comparison
    session['editing'] = {
        'member_id':   member.id,
        'old_monthly': member.total_price,
        'old_gym':     member.gym,
        'old_option':  member.gym_option or '',
        'old_addons':  member.addons or '',
    }

    return redirect(url_for('membership'))


# ─────────────────────────────────────────────
# DATABASE INITIALISATION + SEED DATA
# ─────────────────────────────────────────────

def seed_membership_options():
    """
    Populate the membership_options table from spec data if empty.
    Called once at startup.
    """
    if MembershipOption.query.count() > 0:
        return  # already seeded

    options = [
        # ── uGym ──────────────────────────────────────────────────────────
        MembershipOption(gym='ugym', option_name='Super Off-Peak',          base_price=16,   is_addon=False, discount_eligible=True),
        MembershipOption(gym='ugym', option_name='Off-Peak',                base_price=21,   is_addon=False, discount_eligible=True),
        MembershipOption(gym='ugym', option_name='Anytime',                 base_price=30,   is_addon=False, discount_eligible=True),
        MembershipOption(gym='ugym', option_name='Swimming Pool (standalone)', base_price=25, is_addon=False, discount_eligible=True),
        MembershipOption(gym='ugym', option_name='Swimming Pool (add-on)',  base_price=15,   is_addon=True,  discount_eligible=True),
        MembershipOption(gym='ugym', option_name='Classes (standalone)',    base_price=20,   is_addon=False, discount_eligible=True),
        MembershipOption(gym='ugym', option_name='Classes (add-on)',        base_price=10,   is_addon=True,  discount_eligible=True),
        MembershipOption(gym='ugym', option_name='Massage (standalone)',    base_price=30,   is_addon=False, discount_eligible=False),
        MembershipOption(gym='ugym', option_name='Massage (add-on)',        base_price=25,   is_addon=True,  discount_eligible=False),
        MembershipOption(gym='ugym', option_name='Physiotherapy (standalone)', base_price=25, is_addon=False, discount_eligible=False),
        MembershipOption(gym='ugym', option_name='Physiotherapy (add-on)',  base_price=20,   is_addon=True,  discount_eligible=False),
        # ── Power Zone ────────────────────────────────────────────────────
        MembershipOption(gym='powerzone', option_name='Super Off-Peak',          base_price=13,   is_addon=False, discount_eligible=True),
        MembershipOption(gym='powerzone', option_name='Off-Peak',                base_price=19,   is_addon=False, discount_eligible=True),
        MembershipOption(gym='powerzone', option_name='Anytime',                 base_price=24,   is_addon=False, discount_eligible=True),
        MembershipOption(gym='powerzone', option_name='Swimming Pool (standalone)', base_price=20, is_addon=False, discount_eligible=True),
        MembershipOption(gym='powerzone', option_name='Swimming Pool (add-on)',  base_price=12.5, is_addon=True,  discount_eligible=True),
        MembershipOption(gym='powerzone', option_name='Classes (standalone)',    base_price=20,   is_addon=False, discount_eligible=True),
        MembershipOption(gym='powerzone', option_name='Classes (add-on)',        base_price=0,    is_addon=True,  discount_eligible=True),
        MembershipOption(gym='powerzone', option_name='Massage (standalone)',    base_price=30,   is_addon=False, discount_eligible=False),
        MembershipOption(gym='powerzone', option_name='Massage (add-on)',        base_price=25,   is_addon=True,  discount_eligible=False),
        MembershipOption(gym='powerzone', option_name='Physiotherapy (standalone)', base_price=30, is_addon=False, discount_eligible=False),
        MembershipOption(gym='powerzone', option_name='Physiotherapy (add-on)',  base_price=25,   is_addon=True,  discount_eligible=False),
    ]
    db.session.bulk_save_objects(options)
    db.session.commit()
    print('✔ Membership options seeded.')


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────

if __name__ == '__main__':
    # Use absolute path so Flask always finds templates/ and static/
    app.root_path = os.path.dirname(os.path.abspath(__file__))

    with app.app_context():
        db.create_all()         # create tables if they don't exist
        seed_membership_options()

    app.run(debug=True)