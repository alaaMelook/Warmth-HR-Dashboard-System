from flask import Flask, request, jsonify, render_template, redirect, url_for
from flask_mysqldb import MySQL
from flask_bcrypt import Bcrypt
from flask_jwt_extended import (
    JWTManager, create_access_token,
    jwt_required, get_jwt_identity,
    verify_jwt_in_request
)
from datetime import date, datetime, timedelta

app = Flask(__name__)
bcrypt = Bcrypt(app)

# --------------------
# Config MySQL
# --------------------
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'hr_management'
mysql = MySQL(app)

# --------------------
# Config JWT
# --------------------
app.config['JWT_SECRET_KEY'] = 'super-secret'
jwt = JWTManager(app)


# --------------------
# Register User (Signup)
# --------------------
@app.route('/register', methods=['POST'])
def register():
    data = request.json or {}
    first_name = data.get('first_name')
    last_name = data.get('last_name')
    email = data.get('email')
    password = data.get('password')

    if not first_name or not last_name or not email or not password:
        return jsonify({"error": "Missing required fields"}), 400

    hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

    cursor = mysql.connection.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (first_name, last_name, email, password) VALUES (%s,%s,%s,%s)",
            (first_name, last_name, email, hashed_password)
        )
        mysql.connection.commit()
        return jsonify({"message": "User registered successfully!"}), 201
    except Exception as e:
        mysql.connection.rollback()
        return jsonify({"error": str(e)}), 400


# --------------------
# Login
# --------------------
@app.route('/login', methods=['POST'])
def login():
    data = request.json or {}
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"error": "Missing email or password"}), 400

    cursor = mysql.connection.cursor()
    cursor.execute("SELECT user_id, password, role_id FROM users WHERE email=%s", (email,))
    user = cursor.fetchone()

    if user and bcrypt.check_password_hash(user[1], password):
        access_token = create_access_token(identity=user[0])
        role = 'admin' if user[2] == 2 else 'user'
        return jsonify({"token": access_token, "role": role}), 200
    else:
        return jsonify({"error": "Invalid credentials"}), 401


# --------------------
# Add Employee (Only Admin)
# --------------------
@app.route('/add_employee', methods=['POST'])
@jwt_required()
def add_employee():
    current_user = get_jwt_identity()
    cursor = mysql.connection.cursor()

    cursor.execute("SELECT role_id FROM users WHERE user_id=%s", (current_user,))
    row = cursor.fetchone()
    if not row:
        return jsonify({"error": "User not found"}), 404

    role = row[0]
    if role != 2:
        return jsonify({"error": "Access denied"}), 403

    data = request.json or {}
    user_id = data.get('user_id')
    department_id = data.get('department_id')
    job_title_id = data.get('job_title_id')

    if not user_id:
        return jsonify({"error": "Missing user_id"}), 400

    cursor.execute(
        "INSERT INTO employees (user_id, department_id, job_title_id, hire_date) VALUES (%s,%s,%s,CURDATE())",
        (user_id, department_id, job_title_id)
    )
    mysql.connection.commit()
    return jsonify({"message": "Employee added successfully"}), 201


# --------------------
# Attendance
# --------------------
@app.route('/attendance', methods=['POST'])
@jwt_required()
def attendance():
    data = request.json or {}
    employee_id = data.get('employee_id')
    check_in = data.get('check_in')
    check_out = data.get('check_out')
    status = data.get('status', 'present')

    if not employee_id:
        return jsonify({"error": "Missing employee_id"}), 400

    cursor = mysql.connection.cursor()
    cursor.execute(
        "INSERT INTO attendance (employee_id, attendance_date, check_in, check_out, status) "
        "VALUES (%s,CURDATE(),%s,%s,%s)",
        (employee_id, check_in, check_out, status)
    )
    mysql.connection.commit()
    return jsonify({"message": "Attendance recorded"}), 201


# --------------------
# Request Leave
# --------------------
@app.route('/leave', methods=['POST'])
@jwt_required()
def request_leave():
    data = request.json or {}
    employee_id = data.get('employee_id')
    leave_type = data.get('leave_type')
    start_date = data.get('start_date')
    end_date = data.get('end_date')

    if not employee_id or not leave_type or not start_date or not end_date:
        return jsonify({"error": "Missing required fields"}), 400

    cursor = mysql.connection.cursor()
    cursor.execute(
        "INSERT INTO leaves (employee_id, leave_type, start_date, end_date) VALUES (%s,%s,%s,%s)",
        (employee_id, leave_type, start_date, end_date)
    )
    mysql.connection.commit()
    return jsonify({"message": "Leave requested"}), 201


# ==============================
# USER PORTAL HELPERS
# ==============================
def _fmt_time(t):
    if not t:
        return None
    try:
        return t.strftime("%I:%M %p").lstrip("0")
    except Exception:
        return str(t)

def _time_diff_hm(t1, t2):
    if not t1 or not t2:
        return "0h 0m"
    dt1 = datetime.combine(date.today(), t1)
    dt2 = datetime.combine(date.today(), t2)
    if dt2 < dt1:
        dt2 += timedelta(days=1)
    mins = int((dt2 - dt1).total_seconds() // 60)
    return f"{mins//60}h {mins%60}m"

def _currency(v):
    try:
        return f"₹{float(v):,.0f}"
    except Exception:
        return str(v)

def _get_user_id_from_request(default=1):
    # 1) JWT (optional)
    try:
        verify_jwt_in_request(optional=True)
        uid = get_jwt_identity()
        if uid:
            return int(uid)
    except Exception:
        pass

    # 2) query param
    q = request.args.get("user_id")
    if q and str(q).isdigit():
        return int(q)

    return default

def _fetchone(cursor, q, params=()):
    cursor.execute(q, params)
    return cursor.fetchone()

def _fetchall(cursor, q, params=()):
    cursor.execute(q, params)
    return cursor.fetchall()


# ==============================
# USER PORTAL DATA (DB-READY)
# ==============================
def get_portal_data():
    uid = _get_user_id_from_request(default=1)
    today = date.today()
    now = datetime.now()
    d = {}

    cursor = mysql.connection.cursor()

    # ✅ هنا عدلنا select يجيب address + emergency_*
    u = _fetchone(cursor, """
        SELECT u.user_id, u.first_name, u.last_name, u.email, u.phone,
               u.address, u.emergency_name, u.emergency_relationship, u.emergency_phone,
               u.created_at,
               e.employee_id, e.hire_date,
               dep.department_name,
               jt.title_name
        FROM users u
        LEFT JOIN employees e ON e.user_id = u.user_id
        LEFT JOIN departments dep ON dep.department_id = e.department_id
        LEFT JOIN job_titles jt ON jt.job_title_id = e.job_title_id
        WHERE u.user_id = %s
        LIMIT 1
    """, (uid,))

    if not u:
        d["user"] = {
            "user_id": uid,
            "first_name": "User",
            "last_name": "",
            "full_name": f"User {uid}",
            "employee_id": "N/A",
            "position": "N/A",
            "department": "N/A",
            "email": "",
            "phone": "",
            "address": "—",
            "emergency_name": None,
            "emergency_relationship": None,
            "emergency_phone": None,
            "join_date": "",
            "tenure_years": "0.0",
            "attendance_rate": 0,
            "leaves_taken": "0/0",
        }
        employee_id = None
    else:
        (
            user_id, first, last, email, phone,
            address, em_name, em_rel, em_phone,
            created_at,
            employee_id, hire_date,
            dep_name,
            title_name
        ) = u

        full_name = f"{first} {last}".strip()
        join_date = hire_date.strftime("%m/%d/%Y") if hire_date else ""
        tenure_years = "0.0"
        if hire_date:
            tenure_years = f"{(today - hire_date).days / 365:.1f}"

        d["user"] = {
            "user_id": user_id,
            "first_name": first,
            "last_name": last,
            "full_name": full_name,
            "employee_id": f"EMP{employee_id:03d}" if employee_id else "N/A",
            "position": title_name or "N/A",
            "department": dep_name or "N/A",
            "email": email,
            "phone": phone or "",
            "address": address or "—",
            "emergency_name": em_name,
            "emergency_relationship": em_rel,
            "emergency_phone": em_phone,
            "join_date": join_date,
            "tenure_years": tenure_years,
        }

    # كروت الهوم (placeholder – زي ما كنت عامل)
    home_cards = {
        "today_status": "No Record",
        "check_in": "—",
        "working_hours": "0h 0m",
        "current_time": now.strftime("%I:%M %p").lstrip("0"),
        "leave_balance_days": 0,
        "month_days": "0/0",
        "attendance_rate": 0,
    }

    # علشان الصفحات تشتغل حتى لو مفيش بيانات كفاية:
    d["home_cards"] = home_cards
    d["holidays"] = [
        {"title": "Christmas Day", "date": "Dec 25, 2025"},
        {"title": "New Year's Day", "date": "Jan 1, 2026"},
    ]
    d["notifications"] = [
        {"text": "Your leave request has been updated", "time": "2 hours ago"},
    ]
    d["leave_balance"] = []
    d["leave_history"] = []
    d["attendance_stats"] = {"present": 0, "absent": 0, "late": 0}
    d["calendar"] = {"month_label": today.strftime("%B %Y"), "days": {}}
    d["recent_checkins"] = []
    d["salary_current"] = {"net": "₹0", "basic": "₹0", "allowances": "₹0", "deductions": "₹0"}
    d["salary_kpis"] = []
    d["payslips"] = []
    d["earnings_breakdown"] = []
    d["deductions_breakdown"] = []
    d["total_earnings"] = "₹0"
    d["total_deductions"] = "₹0"

    return d


# ==============================
# UPDATE PROFILE API (for profile.html fetch)
# ==============================
@app.route("/update_profile", methods=["POST"])
def update_profile():
    data = request.get_json(silent=True) or {}

    user_id = data.get("user_id")
    if not user_id or not str(user_id).isdigit():
        return jsonify({"success": False, "message": "Invalid user_id"}), 400
    user_id = int(user_id)

    first_name = (data.get("first_name") or "").strip()
    last_name = (data.get("last_name") or "").strip()
    email = (data.get("email") or "").strip()
    phone = (data.get("phone") or "").strip() or None
    address = (data.get("address") or "").strip() or None

    emergency_name = (data.get("emergency_name") or "").strip() or None
    emergency_relationship = (data.get("emergency_relationship") or "").strip() or None
    emergency_phone = (data.get("emergency_phone") or "").strip() or None

    if not first_name or not last_name or not email:
        return jsonify({"success": False, "message": "First name, last name, and email are required."}), 400

    cursor = mysql.connection.cursor()

    # user exists?
    cursor.execute("SELECT user_id FROM users WHERE user_id=%s", (user_id,))
    if not cursor.fetchone():
        return jsonify({"success": False, "message": "User not found"}), 404

    # email unique?
    cursor.execute("SELECT user_id FROM users WHERE email=%s AND user_id<>%s", (email, user_id))
    if cursor.fetchone():
        return jsonify({"success": False, "message": "Email already exists for another user."}), 400

    try:
        cursor.execute("""
            UPDATE users
            SET first_name=%s,
                last_name=%s,
                email=%s,
                phone=%s,
                address=%s,
                emergency_name=%s,
                emergency_relationship=%s,
                emergency_phone=%s
            WHERE user_id=%s
        """, (
            first_name, last_name, email, phone, address,
            emergency_name, emergency_relationship, emergency_phone,
            user_id
        ))
        mysql.connection.commit()
        return jsonify({"success": True}), 200

    except Exception as e:
        mysql.connection.rollback()
        return jsonify({"success": False, "message": str(e)}), 500


# ==============================
# PORTAL ROUTES
# ==============================
@app.route("/")
def root():
    # يفتح البورتال مباشرة
    return redirect(url_for("portal_home", user_id=1))

@app.route("/portal")
def portal_home():
    data = get_portal_data()
    return render_template("user/home.html", d=data)

@app.route("/portal/attendance")
def portal_attendance():
    data = get_portal_data()
    return render_template("user/attendance.html", d=data)

@app.route("/portal/leaves")
def portal_leaves():
    data = get_portal_data()
    return render_template("user/leaves.html", d=data)

@app.route("/portal/salary")
def portal_salary():
    data = get_portal_data()
    return render_template("user/salary.html", d=data)

@app.route("/portal/profile")
def portal_profile():
    data = get_portal_data()
    return render_template("user/profile.html", d=data)


# --------------------
# Run Flask App
# --------------------
if __name__ == "__main__":
    print("==== REGISTERED ROUTES ====")
    for r in app.url_map.iter_rules():
        print(r.rule)
    print("===========================")
    app.run(debug=True)