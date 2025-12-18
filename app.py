import os
import csv
from io import StringIO
from functools import wraps
from datetime import date, datetime, timedelta
import logging
from logging.handlers import RotatingFileHandler
from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, g, session, jsonify, make_response
)
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
from mysql.connector import Error

# ========== Keycloak Imports ==========
from keycloak import KeycloakOpenID
from jose import jwt, JWTError
import requests

# ========== Load Environment Variables ==========
from dotenv import load_dotenv
load_dotenv()  # This loads the .env file
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "dev-secret-key-change-in-production")

# ========== Enhanced Logging Configuration ==========
# Create logs directory if it doesn't exist
if not os.path.exists('logs'):
    os.makedirs('logs')

# Create log filename with current date only (one file per day)
log_filename = datetime.now().strftime('logs/app_%Y-%m-%d.log')

# Configure logging format
log_format = logging.Formatter(
    '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Console handler (terminal output)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(log_format)

# File handler (save to file with date/time)
file_handler = RotatingFileHandler(
    log_filename, 
    maxBytes=10485760,  # 10MB
    backupCount=10
)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(log_format)

# Configure root logger
logging.basicConfig(
    level=logging.DEBUG,
    handlers=[console_handler, file_handler]
)

# Set Flask app logger
app.logger.setLevel(logging.DEBUG)
app.logger.addHandler(file_handler)

# Log startup message
app.logger.info('=' * 100)
app.logger.info(f'[STARTUP] Flask Application Started - Log file: {log_filename}')
app.logger.info('=' * 100)

# ========== Request/Response Logging Middleware ==========
@app.before_request
def log_request_info():
    app.logger.info('=' * 100)
    app.logger.info(f'[REQUEST] {request.method} {request.url}')
    app.logger.info(f'[ENDPOINT] {request.endpoint}')
    app.logger.info(f'[IP] {request.remote_addr}')
    app.logger.info(f'[USER-AGENT] {request.user_agent}')
    
    if request.args:
        app.logger.info(f'[PARAMS] {dict(request.args)}')
    
    if request.form:
        # Don't log sensitive data like passwords
        safe_form = {k: '***' if 'password' in k.lower() else v for k, v in request.form.items()}
        app.logger.info(f'[FORM] {safe_form}')
    
    if request.is_json:
        try:
            json_data = request.get_json()
            safe_json = {k: '***' if 'password' in k.lower() else v for k, v in json_data.items()}
            app.logger.info(f'[JSON] {safe_json}')
        except:
            pass
    
    # Log session info
    if 'user_id' in session:
        app.logger.info(f'[SESSION] User: {session.get("user_name")} (ID: {session.get("user_id")})')
    
    app.logger.info('=' * 100)

@app.after_request
def log_response_info(response):
    status_text = '[OK]' if response.status_code < 400 else '[WARN]' if response.status_code < 500 else '[ERROR]'
    app.logger.info(f'{status_text} RESPONSE: {response.status_code} - {request.method} {request.path}')
    return response
# ==================== KEYCLOAK CONFIG ====================

KEYCLOAK_SERVER_URL = os.environ.get("KEYCLOAK_SERVER_URL", "http://localhost:8080")
KEYCLOAK_REALM = os.environ.get("KEYCLOAK_REALM", "HR-System")
KEYCLOAK_CLIENT_ID = os.environ.get("KEYCLOAK_CLIENT_ID", "hr-backend")
KEYCLOAK_CLIENT_SECRET = os.environ.get("KEYCLOAK_CLIENT_SECRET")
KEYCLOAK_FRONTEND_CLIENT_ID = os.environ.get("KEYCLOAK_FRONTEND_CLIENT_ID", "hr-frontend")

# Initialize Keycloak
keycloak_openid = KeycloakOpenID(
    server_url=KEYCLOAK_SERVER_URL,
    client_id=KEYCLOAK_CLIENT_ID,
    realm_name=KEYCLOAK_REALM,
    client_secret_key=KEYCLOAK_CLIENT_SECRET
)

# Get Keycloak public key for token verification
try:
    KEYCLOAK_PUBLIC_KEY = "-----BEGIN PUBLIC KEY-----\n" + \
        keycloak_openid.public_key() + \
        "\n-----END PUBLIC KEY-----"
    print("✅ Keycloak public key fetched successfully!")
except Exception as e:
    print(f"⚠️ Warning: Could not fetch Keycloak public key: {e}")
    KEYCLOAK_PUBLIC_KEY = None
# ==================== DB CONFIG ====================

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "127.0.0.1"),
    "user": os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", ""),
    "database": os.environ.get("DB_NAME", "hr_management"),
    "port": int(os.environ.get("DB_PORT", 3306)),
    "auth_plugin": "mysql_native_password",
}

def get_db():
    if hasattr(g, "db_conn") and g.db_conn and g.db_conn.is_connected():
        return g.db_conn
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
    except Error as e:
        raise RuntimeError(f"Cannot connect to DB: {e}")
    g.db_conn = conn
    return conn

@app.teardown_appcontext
def close_db(exception):
    conn = getattr(g, "db_conn", None)
    if conn:
        try:
            conn.close()
        except Exception:
            pass

# ==================== DB HELPERS ====================

def q1(sql, params=None):
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(sql, params or ())
        return cur.fetchone()
    finally:
        cur.close()

def qall(sql, params=None):
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(sql, params or ())
        return cur.fetchall()
    finally:
        cur.close()

def exec_sql(sql, params=None, *, commit=True):
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(sql, params or ())
        last_id = cur.lastrowid
        rc = cur.rowcount
        if commit:
            conn.commit()
        return last_id, rc
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()

# ==================== TOKEN VERIFICATION ====================

def verify_keycloak_token(token):
    """
    Verify JWT token from Keycloak
    Returns decoded token if valid, None otherwise
    """
    try:
        if not KEYCLOAK_PUBLIC_KEY:
            app.logger.error("Keycloak public key not available")
            return None
            
        # Remove "Bearer " prefix if exists
        if token.startswith("Bearer "):
            token = token[7:]
        
        # Decode and verify token
        decoded_token = jwt.decode(
            token,
            KEYCLOAK_PUBLIC_KEY,
            algorithms=["RS256"],
            audience="account",
            options={
                "verify_signature": True,
                "verify_aud": True,
                "verify_exp": True
            }
        )
        
        return decoded_token
    
    except JWTError as e:
        app.logger.error(f"JWT verification failed: {str(e)}")
        return None
    except Exception as e:
        app.logger.error(f"Token verification error: {str(e)}")
        return None


def get_user_roles(decoded_token):
    """
    Extract user roles from decoded token
    """
    try:
        realm_roles = decoded_token.get("realm_access", {}).get("roles", [])
        return realm_roles
    except Exception:
        return []


def check_role_permission(required_role, user_roles):
    """
    Check if user has required role
    """
    return required_role in user_roles

# ==================== AUTH DECORATORS (KEYCLOAK) ====================

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        # First check session (for compatibility)
        if "user_id" in session and "access_token" in session:
            # Verify token is still valid
            decoded_token = verify_keycloak_token(session["access_token"])
            if decoded_token:
                g.user_email = decoded_token.get("email")
                g.user_roles = get_user_roles(decoded_token)
                return f(*args, **kwargs)
        
        # No valid session, redirect to login
        flash("Please login first.", "danger")
        return redirect(url_for("login"))
    
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        # Check session
        if "user_id" not in session or "access_token" not in session:
            flash("Please login first.", "danger")
            return redirect(url_for("login"))
        
        # Verify token
        decoded_token = verify_keycloak_token(session["access_token"])
        if not decoded_token:
            flash("Invalid or expired session.", "danger")
            session.clear()
            return redirect(url_for("login"))
        
        # Get roles
        user_roles = get_user_roles(decoded_token)
        
        # Check if user has HR_ADMIN role
        if "HR_ADMIN" not in user_roles:
            flash("Access denied. Admin only.", "danger")
            return redirect(url_for("user_dashboard"))
        
        g.user_email = decoded_token.get("email")
        g.user_roles = user_roles
        
        return f(*args, **kwargs)
    
    return decorated


def user_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        # Check session
        if "user_id" not in session or "access_token" not in session:
            flash("Please login first.", "danger")
            return redirect(url_for("login"))
        
        # Verify token
        decoded_token = verify_keycloak_token(session["access_token"])
        if not decoded_token:
            flash("Invalid or expired session.", "danger")
            session.clear()
            return redirect(url_for("login"))
        
        # Get roles
        user_roles = get_user_roles(decoded_token)
        
        # Check if user has EMPLOYEE role (or any non-admin role)
        if "HR_ADMIN" in user_roles:
            flash("Access denied. User only.", "danger")
            return redirect(url_for("admin_dashboard"))
        
        g.user_email = decoded_token.get("email")
        g.user_roles = user_roles
        
        return f(*args, **kwargs)
    
    return decorated


def role_required(required_role):
    """
    Decorator to check specific Keycloak role
    Usage: @role_required('HR_OFFICER')
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if "access_token" not in session:
                return jsonify({"error": "Unauthorized"}), 401
            
            decoded_token = verify_keycloak_token(session["access_token"])
            if not decoded_token:
                return jsonify({"error": "Invalid token"}), 401
            
            user_roles = get_user_roles(decoded_token)
            
            if not check_role_permission(required_role, user_roles):
                return jsonify({"error": "Forbidden - Insufficient permissions"}), 403
            
            g.user_email = decoded_token.get("email")
            g.user_roles = user_roles
            
            return f(*args, **kwargs)
        
        return decorated
    return decorator

# ==================== USER HELPERS ====================

def find_user_by_email(email):
    return q1("SELECT * FROM users WHERE email = %s LIMIT 1", (email,))

def get_user_by_id(user_id):
    return q1("SELECT * FROM users WHERE user_id = %s", (user_id,))

def get_employee_by_user_id(user_id):
    """
    IMPORTANT:
    Your DB currently has duplicate employees for same user_id (e.g. user_id=2 twice).
    We take the latest employee_id to be stable.
    Better fix DB later with UNIQUE(user_id).
    """
    return q1("""
        SELECT
            e.employee_id,
            e.user_id,
            e.department_id,
            e.job_title_id,
            e.hire_date,
            e.status,
            d.department_name,
            j.title_name
        FROM employees e
        LEFT JOIN departments d ON e.department_id = d.department_id
        LEFT JOIN job_titles j ON e.job_title_id = j.job_title_id
        WHERE e.user_id = %s
        ORDER BY e.employee_id DESC
        LIMIT 1
    """, (user_id,))

def create_user(first_name, last_name, email, password, role_id=1):
    pw_hash = generate_password_hash(password)
    exec_sql(
        "INSERT INTO users (first_name, last_name, email, password, role_id) VALUES (%s,%s,%s,%s,%s)",
        (first_name, last_name, email, pw_hash, role_id),
    )

# ==================== MAIN ROUTES ====================

@app.route("/")
def index():
    if "user_id" in session:
        if session.get("role_id") == 2:
            return redirect(url_for("admin_dashboard"))
        return redirect(url_for("user_dashboard"))
    return redirect(url_for("login"))

# ==================== KEYCLOAK ROUTES ====================

@app.route("/keycloak-login")
def keycloak_login():
    """
    Redirect user to Keycloak login page
    """
    # استخدام dynamic redirect_uri
    redirect_uri = request.url_root.rstrip('/') + '/callback'
    
    authorization_url = (
        f"{KEYCLOAK_SERVER_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/auth"
        f"?client_id={KEYCLOAK_FRONTEND_CLIENT_ID}"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code"
        f"&scope=openid email profile"
    )
    
    print(f"🔍 Redirecting to Keycloak:")
    print(f"   Auth URL: {authorization_url}")
    print(f"   Redirect URI: {redirect_uri}")
    
    return redirect(authorization_url)

@app.route("/callback")
def keycloak_callback():
    """
    Handle callback from Keycloak after authentication
    """
    try:
        code = request.args.get('code')
        
        if not code:
            flash("Authentication failed. No authorization code received.", "danger")
            return redirect(url_for("login"))
        
        # Exchange code for token
        token_url = f"{KEYCLOAK_SERVER_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/token"
        
        # استخدام نفس الـ redirect_uri
        redirect_uri = request.url_root.rstrip('/') + '/callback'
        
        # ========== المهم: استخدام hr-frontend مش hr-backend ==========
        data = {
            'grant_type': 'authorization_code',
            'client_id': KEYCLOAK_FRONTEND_CLIENT_ID,  # ← frontend client
            'code': code,
            'redirect_uri': redirect_uri
        }
        
        print(f"🔍 Token exchange request:")
        print(f"   Token URL: {token_url}")
        print(f"   Redirect URI: {redirect_uri}")
        print(f"   Client ID: {KEYCLOAK_FRONTEND_CLIENT_ID}")  # ← تأكيد
        print(f"   Code: {code[:20]}...")
        
        response = requests.post(token_url, data=data)
        
        print(f"🔍 Token response status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"❌ Token response error: {response.text}")
            flash(f"Failed to obtain access token: {response.text}", "danger")
            return redirect(url_for("login"))
        
        token_data = response.json()
        access_token = token_data.get('access_token')
        
        print(f"✅ Token received successfully!")
        
        # Verify and decode token
        decoded_token = verify_keycloak_token(access_token)
        
        if not decoded_token:
            flash("Invalid token received.", "danger")
            return redirect(url_for("login"))
        
        # Get user email from token
        user_email = decoded_token.get('email')
        
        if not user_email:
            flash("Email not found in token.", "danger")
            return redirect(url_for("login"))
        
        print(f"🔍 User email from token: {user_email}")
        
        # Find user in database
        user = find_user_by_email(user_email.lower())
        
        if not user:
            flash("User not found in system. Please contact admin.", "danger")
            return redirect(url_for("login"))
        
        print(f"✅ User found in database: {user['first_name']} {user['last_name']}")
        
        # Store in session
        session["user_id"] = user["user_id"]
        session["user_name"] = f"{user['first_name']} {user['last_name']}"
        session["email"] = user["email"]
        session["role_id"] = user["role_id"]
        session["access_token"] = access_token
        
        # Get user roles from Keycloak
        user_roles = get_user_roles(decoded_token)
        
        print(f"✅ User roles: {user_roles}")
        
        flash(f"Welcome back, {user['first_name']}!", "success")
        
        # Redirect based on role
        if "HR_ADMIN" in user_roles:
            return redirect(url_for("admin_dashboard"))
        else:
            return redirect(url_for("user_dashboard"))
    
    except Exception as e:
        app.logger.error(f"Callback error: {str(e)}")
        print(f"❌ Callback exception: {str(e)}")
        import traceback
        traceback.print_exc()
        flash(f"Login error: {str(e)}", "danger")
        return redirect(url_for("login"))

# ==================== LOGIN & REGISTER ====================

@app.route("/login", methods=["GET"])
def login():
    """
    Show login page with Keycloak login button
    """
    # If already logged in, redirect to dashboard
    if "user_id" in session:
        if session.get("role_id") == 2:
            return redirect(url_for("admin_dashboard"))
        return redirect(url_for("user_dashboard"))
    
    return render_template("login.html", title="Login")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip() or None
        address = request.form.get("address", "").strip() or None
        emergency_name = request.form.get("emergency_name", "").strip() or None
        emergency_relationship = request.form.get("emergency_relationship", "").strip() or None
        emergency_phone = request.form.get("emergency_phone", "").strip() or None
        password = request.form.get("password", "").strip()

        if not first_name or not last_name or not email or not password:
            flash("Please fill in all required fields.", "danger")
            return redirect(url_for("register"))

        if find_user_by_email(email):
            flash("An account with that email already exists.", "danger")
            return redirect(url_for("register"))

        try:
            pw_hash = generate_password_hash(password)
            user_id, _ = exec_sql("""
                INSERT INTO users 
                (first_name, last_name, email, phone, address,
                 emergency_name, emergency_relationship, emergency_phone,
                 password, role_id)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,1)
            """, (first_name, last_name, email, phone, address,
                  emergency_name, emergency_relationship, emergency_phone, pw_hash))
            
            # Create employee record automatically for the new user
            exec_sql("""
                INSERT INTO employees (user_id, hire_date, status)
                VALUES (%s, CURDATE(), 'active')
            """, (user_id,))
            
            flash("Registration successful. You can now log in.", "success")
            return redirect(url_for("login"))
        except Exception as e:
            flash(f"Error during registration: {str(e)}", "danger")
            return redirect(url_for("register"))

    return render_template("register.html", title="Register")

@app.route("/logout")
def logout():
    """
    Logout from both Flask session and Keycloak
    """
    # Clear Flask session
    session.clear()
    
    # Redirect to Keycloak logout
    logout_url = (
        f"{KEYCLOAK_SERVER_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/logout"
        f"?redirect_uri=http://localhost:5000/login"
    )
    
    flash("You have been logged out successfully.", "success")
    return redirect(logout_url)

# ==================== ADMIN ROUTES ====================

@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    try:
        total_employees = (q1("SELECT COUNT(*) AS cnt FROM employees WHERE status='active'") or {}).get("cnt", 0)
        today_attendance = (q1("""
            SELECT COUNT(*) AS cnt
            FROM attendance
            WHERE attendance_date = CURDATE() AND status='present'
        """) or {}).get("cnt", 0)
        pending_leaves = (q1("SELECT COUNT(*) AS cnt FROM leaves WHERE status='pending'") or {}).get("cnt", 0)

        monthly_payroll = (q1("""
            SELECT COALESCE(SUM(basic_salary + bonus - deductions), 0) AS total
            FROM payroll
            WHERE MONTH(pay_date)=MONTH(CURDATE()) AND YEAR(pay_date)=YEAR(CURDATE())
        """) or {}).get("total", 0)

        recent_leaves = qall("""
            SELECT u.first_name, u.last_name, l.leave_type, l.start_date, l.end_date, l.status, l.reason
            FROM leaves l
            JOIN employees e ON l.employee_id = e.employee_id
            JOIN users u ON e.user_id = u.user_id
            ORDER BY l.leave_id DESC
            LIMIT 5
        """)

        return render_template(
            "admin/dashboard.html",
            total_employees=total_employees,
            today_attendance=today_attendance,
            pending_leaves=pending_leaves,
            monthly_payroll=monthly_payroll,
            recent_leaves=recent_leaves,
        )
    except Exception as e:
        app.logger.exception("Error loading admin dashboard")
        return render_template(
            "admin/dashboard.html",
            total_employees=0,
            today_attendance=0,
            pending_leaves=0,
            monthly_payroll=0,
            recent_leaves=[],
            error=str(e)
        )

@app.route("/admin/employees")
@admin_required
def admin_employees():
    print("=== ADMIN EMPLOYEES ROUTE HIT ===")
    try:
        print("Fetching employees...")
        employees = qall("""
            SELECT
                e.employee_id,
                e.user_id,
                u.first_name,
                u.last_name,
                u.email,
                u.phone,
                u.address,
                u.emergency_name,
                u.emergency_relationship,
                u.emergency_phone,
                d.department_name,
                d.department_id,
                j.title_name,
                j.job_title_id,
                e.status,
                u.role_id
            FROM employees e
            JOIN users u ON e.user_id = u.user_id
            LEFT JOIN departments d ON e.department_id = d.department_id
            LEFT JOIN job_titles j ON e.job_title_id = j.job_title_id
            ORDER BY e.employee_id DESC
        """)
        print(f"Employees fetched: {len(employees)}")
        departments = qall("SELECT department_id, department_name FROM departments ORDER BY department_name")
        job_titles = qall("SELECT job_title_id, title_name FROM job_titles ORDER BY title_name")
        print("Rendering employees.html template...")
        return render_template("admin/employees.html", employees=employees, departments=departments, job_titles=job_titles)
    except Exception as e:
        print(f"ERROR in admin_employees: {str(e)}")
        import traceback
        traceback.print_exc()
        flash(f"Error loading employees: {str(e)}", "danger")
        return redirect(url_for("admin_dashboard"))

@app.route("/admin/employees/add", methods=["GET", "POST"])
@admin_required
def admin_add_employee():
    if request.method == "POST":
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip() or None

        address = request.form.get("address", "").strip() or None
        emergency_name = request.form.get("emergency_name", "").strip() or None
        emergency_relationship = request.form.get("emergency_relationship", "").strip() or None
        emergency_phone = request.form.get("emergency_phone", "").strip() or None

        password = request.form.get("password", "").strip()
        role_id = int(request.form.get("role_id") or 1)
        department_id = request.form.get("department_id") or None
        job_title_id = request.form.get("job_title_id") or None
        hire_date = request.form.get("hire_date") or None
        status = request.form.get("status", "active")

        if not first_name or not last_name or not email or not password:
            flash("Please fill in all required fields.", "danger")
            return redirect(url_for("admin_add_employee"))

        if find_user_by_email(email):
            flash("An account with that email already exists.", "danger")
            return redirect(url_for("admin_add_employee"))

        try:
            pw_hash = generate_password_hash(password)
            user_id, _ = exec_sql("""
                INSERT INTO users
                (first_name, last_name, email, phone, address,
                 emergency_name, emergency_relationship, emergency_phone,
                 password, role_id)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (first_name, last_name, email, phone, address, emergency_name, emergency_relationship, emergency_phone, pw_hash, role_id))

            exec_sql("""
                INSERT INTO employees (user_id, department_id, job_title_id, hire_date, status)
                VALUES (%s,%s,%s,%s,%s)
            """, (user_id, department_id, job_title_id, hire_date, status))

            flash(f"Employee {first_name} {last_name} added successfully!", "success")
            return redirect(url_for("admin_employees"))
        except Exception as e:
            flash(f"Error adding employee: {str(e)}", "danger")
            return redirect(url_for("admin_add_employee"))

    departments = qall("SELECT department_id, department_name FROM departments ORDER BY department_name")
    job_titles = qall("SELECT job_title_id, title_name FROM job_titles ORDER BY title_name")
    return render_template("admin/add_employee.html", departments=departments, job_titles=job_titles)

@app.route("/admin/employees/edit/<int:employee_id>", methods=["GET", "POST"])
@admin_required
def admin_edit_employee(employee_id):
    if request.method == "POST":
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip() or None

        address = request.form.get("address", "").strip() or None
        emergency_name = request.form.get("emergency_name", "").strip() or None
        emergency_relationship = request.form.get("emergency_relationship", "").strip() or None
        emergency_phone = request.form.get("emergency_phone", "").strip() or None

        role_id = int(request.form.get("role_id") or 1)
        department_id = request.form.get("department_id") or None
        job_title_id = request.form.get("job_title_id") or None
        status = request.form.get("status", "active")

        try:
            emp_row = q1("SELECT user_id FROM employees WHERE employee_id = %s", (employee_id,))
            if not emp_row:
                flash("Employee not found.", "danger")
                return redirect(url_for("admin_employees"))
            user_id = emp_row["user_id"]

            exec_sql("""
                UPDATE users
                SET first_name=%s, last_name=%s, email=%s, phone=%s,
                    address=%s, emergency_name=%s, emergency_relationship=%s, emergency_phone=%s,
                    role_id=%s
                WHERE user_id=%s
            """, (first_name, last_name, email, phone, address, emergency_name, emergency_relationship, emergency_phone, role_id, user_id))

            exec_sql("""
                UPDATE employees
                SET status=%s, department_id=%s, job_title_id=%s
                WHERE employee_id=%s
            """, (status, department_id, job_title_id, employee_id))

            flash("Employee updated successfully!", "success")
            return redirect(url_for("admin_employees"))
        except Exception as e:
            flash(f"Error updating employee: {str(e)}", "danger")
            return redirect(url_for("admin_employees"))

    employee = q1("""
        SELECT
            e.employee_id,
            u.user_id,
            u.first_name,
            u.last_name,
            u.email,
            u.phone,
            u.address,
            u.emergency_name,
            u.emergency_relationship,
            u.emergency_phone,
            u.role_id,
            e.department_id,
            e.job_title_id,
            e.hire_date,
            e.status
        FROM employees e
        JOIN users u ON e.user_id = u.user_id
        WHERE e.employee_id = %s
    """, (employee_id,))
    if not employee:
        flash("Employee not found.", "danger")
        return redirect(url_for("admin_employees"))

    departments = qall("SELECT department_id, department_name FROM departments ORDER BY department_name")
    job_titles = qall("SELECT job_title_id, title_name FROM job_titles ORDER BY title_name")
    return render_template("admin/edit_employee.html", employee=employee, departments=departments, job_titles=job_titles)

@app.route("/admin/employees/delete/<int:employee_id>", methods=["DELETE", "POST"])
@admin_required
def admin_delete_employee(employee_id):
    try:
        emp_row = q1("SELECT user_id FROM employees WHERE employee_id=%s", (employee_id,))
        if not emp_row:
            if request.method == "DELETE":
                return jsonify({"success": False, "message": "Employee not found"}), 404
            flash("Employee not found.", "danger")
            return redirect(url_for("admin_employees"))

        user_id = emp_row["user_id"]
        
        # Delete related records first (foreign key constraints)
        # 1. Delete attendance records
        exec_sql("DELETE FROM attendance WHERE employee_id=%s", (employee_id,))
        
        # 2. Delete leave requests
        exec_sql("DELETE FROM leaves WHERE employee_id=%s", (employee_id,))
        
        # 3. Delete payroll records
        exec_sql("DELETE FROM payroll WHERE employee_id=%s", (employee_id,))
        
        # 4. Delete employee record
        exec_sql("DELETE FROM employees WHERE employee_id=%s", (employee_id,))
        
        # 5. Delete user account
        exec_sql("DELETE FROM users WHERE user_id=%s", (user_id,))

        if request.method == "DELETE":
            return jsonify({"success": True, "message": "Employee deleted successfully"})
        flash("Employee deleted successfully!", "success")
        return redirect(url_for("admin_employees"))
    except Exception as e:
        if request.method == "DELETE":
            return jsonify({"success": False, "message": str(e)}), 500
        flash(f"Error deleting employee: {str(e)}", "danger")
        return redirect(url_for("admin_employees"))

@app.route("/admin/attendance")
@admin_required
def admin_attendance():
    try:
        selected_date = request.args.get("date", date.today().strftime("%Y-%m-%d"))
        department_filter = request.args.get("department", "all")
        page = int(request.args.get("page", 1))
        per_page = 8
        offset = (page - 1) * per_page

        stats = q1("""
            SELECT
                COUNT(CASE WHEN status='present' THEN 1 END) AS total_present,
                COUNT(CASE WHEN TIME(check_in) > '09:00:00' AND status='present' THEN 1 END) AS late_arrivals,
                COUNT(CASE WHEN status='leave' THEN 1 END) AS on_leave,
                AVG(CASE WHEN status='present' AND check_in IS NOT NULL AND check_out IS NOT NULL
                    THEN TIME_TO_SEC(TIMEDIFF(check_out, check_in))/3600 END) AS avg_hours
            FROM attendance
            WHERE DATE(attendance_date)=%s
        """, (selected_date,)) or {}

        total_employees = (q1("SELECT COUNT(*) AS total_employees FROM employees WHERE status='active'") or {}).get("total_employees", 0) or 0

        total_present = stats.get("total_present") or 0
        late_arrivals = stats.get("late_arrivals") or 0
        attendance_percentage = (total_present / total_employees * 100) if total_employees else 0
        late_percentage = (late_arrivals / total_present * 100) if total_present else 0

        departments = qall("SELECT department_id, department_name FROM departments ORDER BY department_name")

        base_sql = """
            SELECT
                a.attendance_id,
                u.first_name,
                u.last_name,
                d.department_name,
                a.attendance_date,
                a.check_in,
                a.check_out,
                a.status,
                CASE
                    WHEN a.check_in IS NOT NULL AND a.check_out IS NOT NULL
                    THEN TIME_FORMAT(TIMEDIFF(a.check_out, a.check_in), '%Hh %im')
                    ELSE NULL
                END AS total_hours
            FROM attendance a
            JOIN employees e ON a.employee_id = e.employee_id
            JOIN users u ON e.user_id = u.user_id
            LEFT JOIN departments d ON e.department_id = d.department_id
            WHERE DATE(a.attendance_date) = %s
        """
        params = [selected_date]
        if department_filter != "all":
            base_sql += " AND e.department_id = %s"
            params.append(department_filter)

        count_sql = """
            SELECT COUNT(*) AS total
            FROM attendance a
            JOIN employees e ON a.employee_id = e.employee_id
            WHERE DATE(a.attendance_date)=%s
        """
        count_params = [selected_date]
        if department_filter != "all":
            count_sql += " AND e.department_id = %s"
            count_params.append(department_filter)

        total_records = (q1(count_sql, tuple(count_params)) or {}).get("total", 0) or 0
        total_pages = (total_records + per_page - 1) // per_page if total_records else 1

        base_sql += " ORDER BY a.check_in DESC LIMIT %s OFFSET %s"
        params.extend([per_page, offset])
        attendance_records = qall(base_sql, tuple(params))

        avg_hours = stats.get("avg_hours") or 0
        stats_out = {
            "total_present": total_present,
            "attendance_percentage": round(attendance_percentage, 1),
            "late_arrivals": late_arrivals,
            "late_percentage": round(late_percentage, 1),
            "on_leave": stats.get("on_leave") or 0,
            "avg_hours": f"{int(avg_hours)}h {int(((avg_hours) % 1) * 60)}m",
        }

        return render_template(
            "admin/attendance.html",
            stats=stats_out,
            attendance_records=attendance_records,
            departments=departments,
            selected_date=selected_date,
            department_filter=department_filter,
            current_page=page,
            total_pages=total_pages,
            total_records=total_records,
        )

    except Exception as e:
        return render_template(
            "admin/attendance.html",
            stats={"total_present": 0, "attendance_percentage": 0, "late_arrivals": 0, "late_percentage": 0, "on_leave": 0, "avg_hours": "0h 0m"},
            attendance_records=[],
            departments=[],
            selected_date=date.today().strftime("%Y-%m-%d"),
            department_filter="all",
            current_page=1,
            total_pages=1,
            total_records=0,
            error=str(e),
        )

@app.route("/admin/attendance/export")
@admin_required
def export_attendance_csv():
    try:
        selected_date = request.args.get("date", date.today().strftime("%Y-%m-%d"))
        department_filter = request.args.get("department", "all")
        
        base_sql = """
            SELECT
                u.first_name,
                u.last_name,
                d.department_name,
                a.attendance_date,
                a.check_in,
                a.check_out,
                a.status,
                CASE
                    WHEN a.check_in IS NOT NULL AND a.check_out IS NOT NULL
                    THEN TIME_FORMAT(TIMEDIFF(a.check_out, a.check_in), '%Hh %im')
                    ELSE NULL
                END AS total_hours
            FROM attendance a
            JOIN employees e ON a.employee_id = e.employee_id
            JOIN users u ON e.user_id = u.user_id
            LEFT JOIN departments d ON e.department_id = d.department_id
            WHERE a.attendance_date = %s
        """
        params = [selected_date]
        if department_filter != "all":
            base_sql += " AND e.department_id = %s"
            params.append(department_filter)
        
        base_sql += " ORDER BY a.check_in DESC"
        rows = qall(base_sql, tuple(params))

        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=[
            "first_name", "last_name", "department_name", "attendance_date", 
            "check_in", "check_out", "status", "total_hours"
        ])
        writer.writeheader()
        writer.writerows(rows)

        output.seek(0)
        resp = make_response(output.getvalue())
        resp.headers["Content-Disposition"] = f"attachment; filename=attendance_{selected_date}.csv"
        resp.headers["Content-type"] = "text/csv"
        return resp

    except Exception as e:
        flash(f"Error exporting attendance: {str(e)}", "danger")
        return redirect(url_for("admin_attendance"))

@app.route("/admin/leaves")
@admin_required
def admin_leaves():
    try:
        pending_count = (q1("SELECT COUNT(*) AS c FROM leaves WHERE status='pending'") or {}).get("c", 0)
        approved_count = (q1("SELECT COUNT(*) AS c FROM leaves WHERE status='approved'") or {}).get("c", 0)
        rejected_count = (q1("SELECT COUNT(*) AS c FROM leaves WHERE status='rejected'") or {}).get("c", 0)

        leave_requests = qall("""
            SELECT
                l.leave_id,
                l.leave_type,
                l.start_date,
                l.end_date,
                l.status,
                CURRENT_TIMESTAMP AS submitted_date,
                u.first_name,
                u.last_name,
                DATEDIFF(l.end_date, l.start_date) + 1 AS duration,
                COALESCE(l.reason, 'No reason provided') AS reason
            FROM leaves l
            JOIN employees e ON l.employee_id = e.employee_id
            JOIN users u ON e.user_id = u.user_id
            ORDER BY
                CASE l.status
                    WHEN 'pending' THEN 1
                    WHEN 'approved' THEN 2
                    WHEN 'rejected' THEN 3
                END,
                l.leave_id DESC
        """)

        return render_template(
            "admin/leaves.html",
            leave_requests=leave_requests,
            pending_count=pending_count or 0,
            approved_count=approved_count or 0,
            rejected_count=rejected_count or 0,
        )
    except Exception as e:
        return render_template(
            "admin/leaves.html",
            leave_requests=[],
            pending_count=0,
            approved_count=0,
            rejected_count=0,
            error=str(e),
        )

@app.route("/admin/leaves/<int:leave_id>/update", methods=["POST"])
@admin_required
def admin_update_leave(leave_id):
    new_status = request.form.get("status")
    if new_status not in ["approved", "rejected"]:
        flash("Invalid status.", "danger")
        return redirect(url_for("admin_leaves"))
    try:
        exec_sql("UPDATE leaves SET status=%s WHERE leave_id=%s", (new_status, leave_id))
        flash(f"Leave request {new_status} successfully!", "success")
    except Exception as e:
        flash(f"Error updating leave request: {str(e)}", "danger")
    return redirect(url_for("admin_leaves"))

@app.route("/admin/payroll")
@admin_required
def admin_payroll():
    """
    Admin payroll management page with full control over salaries, bonuses, and deductions
    """
    try:
        # Total payroll for all records
        total_payroll = (q1("""
            SELECT COALESCE(SUM(basic_salary + bonus - deductions), 0) AS total
            FROM payroll
        """) or {}).get("total", 0)

        # Current month payroll for comparison
        current_month_total = (q1("""
            SELECT COALESCE(SUM(basic_salary + bonus - deductions), 0) AS total
            FROM payroll
            WHERE MONTH(pay_date)=MONTH(CURDATE()) AND YEAR(pay_date)=YEAR(CURDATE())
        """) or {}).get("total", 0)

        last_month_total = (q1("""
            SELECT COALESCE(SUM(basic_salary + bonus - deductions), 0) AS total
            FROM payroll
            WHERE MONTH(pay_date)=MONTH(DATE_SUB(CURDATE(), INTERVAL 1 MONTH))
              AND YEAR(pay_date)=YEAR(DATE_SUB(CURDATE(), INTERVAL 1 MONTH))
        """) or {}).get("total", 0)

        change_percentage = round(((current_month_total - last_month_total) / last_month_total) * 100, 1) if last_month_total else 0

        # Get all employees with their latest payroll data (or show with no payroll)
        employees = qall("""
            SELECT
                e.employee_id,
                u.first_name,
                u.last_name,
                j.title_name AS role,
                COALESCE(p.basic_salary, 0) AS base_salary,
                COALESCE(p.bonus, 0) AS bonus,
                COALESCE(p.deductions, 0) AS deductions,
                COALESCE((p.basic_salary + p.bonus - p.deductions), 0) AS net_pay,
                COALESCE(DATE_FORMAT(p.pay_date, '%Y-%m-%d'), 'Not Set') AS pay_date,
                COALESCE(p.status, 'pending') AS status
            FROM employees e
            JOIN users u ON e.user_id = u.user_id
            LEFT JOIN job_titles j ON e.job_title_id = j.job_title_id
            LEFT JOIN (
                SELECT employee_id, basic_salary, bonus, deductions, pay_date, status,
                       ROW_NUMBER() OVER (PARTITION BY employee_id ORDER BY pay_date DESC) as rn
                FROM payroll
            ) p ON e.employee_id = p.employee_id AND p.rn = 1
            WHERE e.status = 'active'
            ORDER BY u.last_name, u.first_name
        """)
        
        # Get all active employees for the add transaction modal
        all_employees = qall("""
            SELECT
                e.employee_id,
                u.first_name,
                u.last_name,
                j.title_name AS role
            FROM employees e
            JOIN users u ON e.user_id = u.user_id
            LEFT JOIN job_titles j ON e.job_title_id = j.job_title_id
            WHERE e.status = 'active'
            ORDER BY u.last_name, u.first_name
        """)

        total_base_salary = sum((emp.get("base_salary") or 0) for emp in employees)
        total_bonuses = sum((emp.get("bonus") or 0) for emp in employees)
        total_deductions = sum((emp.get("deductions") or 0) for emp in employees)
        total_net_pay = sum((emp.get("net_pay") or 0) for emp in employees)

        today = datetime.now()
        if today.day <= 15:
            period_start = today.replace(day=1)
            period_end = today.replace(day=15)
            next_start = today.replace(day=16)
            next_end = today.replace(day=31) if today.month == 12 else (today.replace(month=today.month + 1, day=1) - timedelta(days=1))
        else:
            period_start = today.replace(day=16)
            period_end = today.replace(day=31) if today.month == 12 else (today.replace(month=today.month + 1, day=1) - timedelta(days=1))
            next_start = datetime(today.year + 1, 1, 1) if today.month == 12 else today.replace(month=today.month + 1, day=1)
            next_end = next_start.replace(day=15)

        stats = {
            "total_payroll": total_payroll,
            "current_month_payroll": current_month_total,
            "change_percentage": abs(change_percentage),
            "pay_period": f"{period_start.strftime('%b %d')}-{period_end.strftime('%d')}",
            "next_period": f"{next_start.strftime('%b %d')}-{next_end.strftime('%d')}",
            "processed": len([e for e in employees if e.get('status') == 'paid']),
            "pending": len([e for e in employees if e.get('status') == 'pending']),
        }

        totals = {
            "total_base_salary": total_base_salary,
            "total_bonuses": total_bonuses,
            "total_deductions": total_deductions,
            "total_net_pay": total_net_pay,
        }

        return render_template("admin/payroll.html", 
            stats=stats, 
            employees=employees, 
            all_employees=all_employees,
            totals=totals,
            now=datetime.now())

    except Exception as e:
        return render_template(
            "admin/payroll.html",
            stats={"total_payroll": 0, "change_percentage": 0, "pay_period": "N/A", "next_period": "N/A", "processed": 0, "pending": 0},
            employees=[],
            all_employees=[],
            totals={"total_base_salary": 0, "total_bonuses": 0, "total_deductions": 0, "total_net_pay": 0},
            error=str(e),
        )

@app.route("/admin/payroll/export")
@admin_required
def export_payroll_csv():
    try:
        rows = qall("""
            SELECT
                u.first_name,
                u.last_name,
                j.title_name AS role,
                p.basic_salary,
                p.bonus,
                p.deductions,
                (p.basic_salary + p.bonus - p.deductions) AS net_pay,
                DATE_FORMAT(p.pay_date, '%Y-%m-%d') AS pay_date,
                p.status
            FROM payroll p
            JOIN employees e ON p.employee_id = e.employee_id
            JOIN users u ON e.user_id = u.user_id
            LEFT JOIN job_titles j ON e.job_title_id = j.job_title_id
            ORDER BY p.pay_date DESC, u.last_name, u.first_name
        """)

        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=[
            "first_name", "last_name", "role", "basic_salary", "bonus", "deductions", "net_pay", "pay_date", "status"
        ])
        writer.writeheader()
        writer.writerows(rows)

        output.seek(0)
        resp = make_response(output.getvalue())
        resp.headers["Content-Disposition"] = f"attachment; filename=payroll_all_records_{date.today().strftime('%Y-%m-%d')}.csv"
        resp.headers["Content-type"] = "text/csv"
        return resp

    except Exception as e:
        flash(f"Error exporting payroll: {str(e)}", "danger")
        return redirect(url_for("admin_payroll"))

@app.route("/admin/payroll/process", methods=["POST"])
@admin_required
def process_payroll():
    """
    Process payroll for current month - creates payroll entries for all active employees
    """
    try:
        # Get all active employees
        employees = qall("""
            SELECT e.employee_id
            FROM employees e
            WHERE e.status = 'active'
        """)
        
        if not employees:
            flash("No active employees found.", "warning")
            return redirect(url_for("admin_payroll"))
        
        processed_count = 0
        current_month = datetime.now().strftime("%Y-%m-01")
        
        for emp in employees:
            # Check if payroll already exists for this month
            existing = q1("""
                SELECT payroll_id 
                FROM payroll 
                WHERE employee_id = %s 
                  AND MONTH(pay_date) = MONTH(CURDATE())
                  AND YEAR(pay_date) = YEAR(CURDATE())
            """, (emp['employee_id'],))
            
            if existing:
                continue  # Skip if already processed
            
            # Insert basic payroll entry - you may want to customize salary calculation
            exec_sql("""
                INSERT INTO payroll (employee_id, basic_salary, bonus, deductions, pay_date)
                VALUES (%s, 5000, 500, 300, %s)
            """, (emp['employee_id'], current_month))
            processed_count += 1
        
        if processed_count > 0:
            flash(f"Payroll processed successfully for {processed_count} employees!", "success")
        else:
            flash("Payroll already processed for this month.", "info")
        
        return redirect(url_for("admin_payroll"))
        
    except Exception as e:
        flash(f"Error processing payroll: {str(e)}", "danger")
        return redirect(url_for("admin_payroll"))

@app.route("/admin/payroll/update-salary", methods=["POST"])
@admin_required
def update_employee_salary():
    """Update employee salary, bonus, deductions, and status for current month"""
    try:
        employee_id = request.form.get("employee_id")
        base_salary = float(request.form.get("base_salary", 0))
        bonus = float(request.form.get("bonus", 0))
        deductions = float(request.form.get("deductions", 0))
        status = request.form.get("status", "pending")
        
        # Check if payroll exists for current month
        existing = q1("""
            SELECT payroll_id 
            FROM payroll 
            WHERE employee_id = %s 
              AND MONTH(pay_date) = MONTH(CURDATE())
              AND YEAR(pay_date) = YEAR(CURDATE())
        """, (employee_id,))
        
        if existing:
            # Update existing payroll
            exec_sql("""
                UPDATE payroll 
                SET basic_salary = %s, bonus = %s, deductions = %s, status = %s
                WHERE payroll_id = %s
            """, (base_salary, bonus, deductions, status, existing['payroll_id']))
            flash("Salary and status updated successfully!", "success")
        else:
            # Create new payroll entry
            current_month = datetime.now().strftime("%Y-%m-01")
            exec_sql("""
                INSERT INTO payroll (employee_id, basic_salary, bonus, deductions, pay_date, status)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (employee_id, base_salary, bonus, deductions, current_month, status))
            flash("Salary entry created successfully!", "success")
        
        return redirect(url_for("admin_payroll"))
        
    except Exception as e:
        flash(f"Error updating salary: {str(e)}", "danger")
        return redirect(url_for("admin_payroll"))

@app.route("/admin/payroll/add-bonus", methods=["POST"])
@admin_required
def add_bonus():
    """Add bonus to employee's current month payroll"""
    try:
        employee_id = request.form.get("employee_id")
        amount = float(request.form.get("amount", 0))
        reason = request.form.get("reason", "")
        
        # Check if payroll exists for current month
        existing = q1("""
            SELECT payroll_id, bonus 
            FROM payroll 
            WHERE employee_id = %s 
              AND MONTH(pay_date) = MONTH(CURDATE())
              AND YEAR(pay_date) = YEAR(CURDATE())
        """, (employee_id,))
        
        if existing:
            # Add to existing bonus
            new_bonus = existing['bonus'] + amount
            exec_sql("""
                UPDATE payroll 
                SET bonus = %s
                WHERE payroll_id = %s
            """, (new_bonus, existing['payroll_id']))
            flash(f"Bonus of ${amount:.2f} added successfully! Reason: {reason}", "success")
        else:
            # Create new payroll entry with bonus
            current_month = datetime.now().strftime("%Y-%m-01")
            exec_sql("""
                INSERT INTO payroll (employee_id, basic_salary, bonus, deductions, pay_date, status)
                VALUES (%s, 5000, %s, 0, %s, 'pending')
            """, (employee_id, amount, current_month))
            flash(f"Bonus of ${amount:.2f} added successfully!", "success")
        
        return redirect(url_for("admin_payroll"))
        
    except Exception as e:
        flash(f"Error adding bonus: {str(e)}", "danger")
        return redirect(url_for("admin_payroll"))

@app.route("/admin/payroll/add-deduction", methods=["POST"])
@admin_required
def add_deduction():
    """Add deduction to employee's current month payroll"""
    try:
        employee_id = request.form.get("employee_id")
        amount = float(request.form.get("amount", 0))
        reason = request.form.get("reason", "")
        
        # Check if payroll exists for current month
        existing = q1("""
            SELECT payroll_id, deductions 
            FROM payroll 
            WHERE employee_id = %s 
              AND MONTH(pay_date) = MONTH(CURDATE())
              AND YEAR(pay_date) = YEAR(CURDATE())
        """, (employee_id,))
        
        if existing:
            # Add to existing deductions
            new_deductions = existing['deductions'] + amount
            exec_sql("""
                UPDATE payroll 
                SET deductions = %s
                WHERE payroll_id = %s
            """, (new_deductions, existing['payroll_id']))
            flash(f"Deduction of ${amount:.2f} added successfully! Reason: {reason}", "success")
        else:
            # Create new payroll entry with deduction
            current_month = datetime.now().strftime("%Y-%m-01")
            exec_sql("""
                INSERT INTO payroll (employee_id, basic_salary, bonus, deductions, pay_date, status)
                VALUES (%s, 5000, 0, %s, %s, 'pending')
            """, (employee_id, amount, current_month))
            flash(f"Deduction of ${amount:.2f} added successfully!", "success")
        
        return redirect(url_for("admin_payroll"))
        
    except Exception as e:
        flash(f"Error adding deduction: {str(e)}", "danger")
        return redirect(url_for("admin_payroll"))

@app.route("/admin/payroll/add-transaction", methods=["POST"])
@admin_required
def add_payroll_transaction():
    """General route to add bonus or deduction - creates new payroll record"""
    try:
        employee_id = request.form.get("employee_id")
        transaction_type = request.form.get("transaction_type")
        amount = float(request.form.get("amount", 0))
        base_salary = float(request.form.get("base_salary", 5000))
        pay_month = request.form.get("pay_month")  # Format: YYYY-MM
        reason = request.form.get("reason", "")
        
        # Convert pay_month to pay_date (first day of month)
        pay_date = f"{pay_month}-01"
        
        # Check if payroll already exists for this employee and month
        existing = q1("""
            SELECT payroll_id, basic_salary, bonus, deductions 
            FROM payroll 
            WHERE employee_id = %s 
              AND DATE_FORMAT(pay_date, '%%Y-%%m') = %s
        """, (employee_id, pay_month))
        
        if existing:
            # Update existing record
            if transaction_type == "bonus":
                new_bonus = existing['bonus'] + amount
                exec_sql("UPDATE payroll SET bonus = %s WHERE payroll_id = %s", 
                        (new_bonus, existing['payroll_id']))
                flash(f"Bonus of ${amount:.2f} added to existing record! Reason: {reason}", "success")
            elif transaction_type == "deduction":
                new_deductions = existing['deductions'] + amount
                exec_sql("UPDATE payroll SET deductions = %s WHERE payroll_id = %s", 
                        (new_deductions, existing['payroll_id']))
                flash(f"Deduction of ${amount:.2f} added to existing record! Reason: {reason}", "success")
        else:
            # Create new record
            if transaction_type == "bonus":
                exec_sql("""
                    INSERT INTO payroll (employee_id, basic_salary, bonus, deductions, pay_date, status)
                    VALUES (%s, %s, %s, 0, %s, 'pending')
                """, (employee_id, base_salary, amount, pay_date))
                flash(f"New payroll record created with bonus of ${amount:.2f}! Reason: {reason}", "success")
            elif transaction_type == "deduction":
                exec_sql("""
                    INSERT INTO payroll (employee_id, basic_salary, bonus, deductions, pay_date, status)
                    VALUES (%s, %s, 0, %s, %s, 'pending')
                """, (employee_id, base_salary, amount, pay_date))
                flash(f"New payroll record created with deduction of ${amount:.2f}! Reason: {reason}", "success")
        
        return redirect(url_for("admin_payroll"))
        
    except Exception as e:
        flash(f"Error processing transaction: {str(e)}", "danger")
        return redirect(url_for("admin_payroll"))

# ==================== ANNOUNCEMENTS ROUTES ====================

@app.route("/admin/announcements")
@admin_required
def admin_announcements():
    """Admin page to manage holidays and notifications"""
    try:
        holidays = qall("""
            SELECT h.*, u.first_name, u.last_name
            FROM holidays h
            LEFT JOIN users u ON h.created_by = u.user_id
            ORDER BY h.holiday_date DESC
        """)
        
        notifications = qall("""
            SELECT n.*, u.first_name, u.last_name
            FROM notifications n
            LEFT JOIN users u ON n.created_by = u.user_id
            ORDER BY n.created_at DESC
        """)
        
        return render_template(
            "admin/announcements.html",
            holidays=holidays,
            notifications=notifications
        )
    except Exception as e:
        flash(f"Error loading announcements: {str(e)}", "danger")
        return redirect(url_for("admin_dashboard"))

@app.route("/admin/holidays/add", methods=["POST"])
@admin_required
def add_holiday():
    """Add a new holiday"""
    try:
        title = request.form.get("title", "").strip()
        holiday_date = request.form.get("holiday_date", "").strip()
        description = request.form.get("description", "").strip() or None
        
        if not title or not holiday_date:
            flash("Title and date are required!", "danger")
            return redirect(url_for("admin_announcements"))
        
        exec_sql("""
            INSERT INTO holidays (title, holiday_date, description, created_by)
            VALUES (%s, %s, %s, %s)
        """, (title, holiday_date, description, session["user_id"]))
        
        flash(f"Holiday '{title}' added successfully!", "success")
    except Exception as e:
        flash(f"Error adding holiday: {str(e)}", "danger")
    
    return redirect(url_for("admin_announcements"))

@app.route("/admin/holidays/delete/<int:holiday_id>", methods=["POST"])
@admin_required
def delete_holiday(holiday_id):
    """Delete a holiday"""
    try:
        exec_sql("DELETE FROM holidays WHERE holiday_id = %s", (holiday_id,))
        flash("Holiday deleted successfully!", "success")
    except Exception as e:
        flash(f"Error deleting holiday: {str(e)}", "danger")
    
    return redirect(url_for("admin_announcements"))

@app.route("/admin/notifications/add", methods=["POST"])
@admin_required
def add_notification():
    """Add a new notification"""
    try:
        title = request.form.get("title", "").strip()
        message = request.form.get("message", "").strip()
        notification_type = request.form.get("notification_type", "info")
        is_active = 1 if request.form.get("is_active") else 0
        
        if not title or not message:
            flash("Title and message are required!", "danger")
            return redirect(url_for("admin_announcements"))
        
        exec_sql("""
            INSERT INTO notifications (title, message, notification_type, is_active, created_by)
            VALUES (%s, %s, %s, %s, %s)
        """, (title, message, notification_type, is_active, session["user_id"]))
        
        flash(f"Notification '{title}' added successfully!", "success")
    except Exception as e:
        flash(f"Error adding notification: {str(e)}", "danger")
    
    return redirect(url_for("admin_announcements"))

@app.route("/admin/notifications/toggle/<int:notification_id>", methods=["POST"])
@admin_required
def toggle_notification(notification_id):
    """Toggle notification active status"""
    try:
        notif = q1("SELECT is_active FROM notifications WHERE notification_id = %s", (notification_id,))
        if notif:
            new_status = 0 if notif["is_active"] else 1
            exec_sql("UPDATE notifications SET is_active = %s WHERE notification_id = %s", (new_status, notification_id))
            flash("Notification status updated!", "success")
        else:
            flash("Notification not found!", "danger")
    except Exception as e:
        flash(f"Error updating notification: {str(e)}", "danger")
    
    return redirect(url_for("admin_announcements"))

@app.route("/admin/notifications/delete/<int:notification_id>", methods=["POST"])
@admin_required
def delete_notification(notification_id):
    """Delete a notification"""
    try:
        exec_sql("DELETE FROM notifications WHERE notification_id = %s", (notification_id,))
        flash("Notification deleted successfully!", "success")
    except Exception as e:
        flash(f"Error deleting notification: {str(e)}", "danger")
    
    return redirect(url_for("admin_announcements"))

# ==================== USER ROUTES ====================

@app.route("/user/dashboard")
@login_required
def user_dashboard():
    conn = get_db()
    cur = None

    try:
        cur = conn.cursor(dictionary=True)

        # جلب بيانات الموظف المرتبطة بالـ user
        employee = get_employee_by_user_id(session['user_id'])
        if not employee:
            flash(
                'Employee profile not found. Please contact admin to create employee record.',
                'danger'
            )
            return redirect(url_for('index'))

        # ================== Attendance Stats ==================
        cur.execute("""
            SELECT 
                COUNT(CASE WHEN status = 'present' THEN 1 END) AS present_days,
                COUNT(CASE WHEN status = 'absent' THEN 1 END) AS absent_days,
                COUNT(CASE WHEN status = 'leave' THEN 1 END) AS leave_days
            FROM attendance
            WHERE employee_id = %s
              AND MONTH(attendance_date) = MONTH(CURDATE())
              AND YEAR(attendance_date) = YEAR(CURDATE())
        """, (employee['employee_id'],))

        attendance_stats = cur.fetchone() or {}

        # ================== Pending Leaves ==================
        cur.execute("""
            SELECT COUNT(*) AS count
            FROM leaves
            WHERE employee_id = %s
              AND status = 'pending'
        """, (employee['employee_id'],))

        pending_leaves = cur.fetchone().get('count', 0)

        # ================== Current Month Payroll ==================
        cur.execute("""
            SELECT COALESCE(basic_salary + bonus - deductions, 0) AS net_pay
            FROM payroll
            WHERE employee_id = %s
              AND MONTH(pay_date) = MONTH(CURDATE())
              AND YEAR(pay_date) = YEAR(CURDATE())
            LIMIT 1
        """, (employee['employee_id'],))

        payroll_info = cur.fetchone()

        # ================== Final Stats Dict ==================
        stats = {
            'present_days': attendance_stats.get('present_days', 0) or 0,
            'absent_days': attendance_stats.get('absent_days', 0) or 0,
            'leave_days': attendance_stats.get('leave_days', 0) or 0,
            'pending_leaves': pending_leaves,
            'net_pay': payroll_info.get('net_pay', 0) if payroll_info else 0
        }

        # ================== Get Holidays (upcoming) ==================
        holidays = qall("""
            SELECT title, holiday_date as date
            FROM holidays
            WHERE holiday_date >= CURDATE()
            ORDER BY holiday_date ASC
            LIMIT 5
        """)
        
        # Format holidays for display
        formatted_holidays = []
        for h in holidays:
            formatted_holidays.append({
                'title': h['title'],
                'date': h['date'].strftime('%b %d, %Y') if h['date'] else 'N/A'
            })

        # ================== Get Active Notifications ==================
        notifications = qall("""
            SELECT title, message, created_at
            FROM notifications
            WHERE is_active = 1
            ORDER BY created_at DESC
            LIMIT 5
        """)
        
        # Format notifications for display
        formatted_notifications = []
        for n in notifications:
            formatted_notifications.append({
                'title': n['title'],
                'text': n['message'],
                'time': n['created_at'].strftime('%b %d, %Y at %I:%M %p') if n['created_at'] else 'Recently'
            })

        return render_template(
            "user/home.html",
            employee=employee,
            stats=stats,
            user_name=session.get("user_name"),
            holidays=formatted_holidays,
            notifications=formatted_notifications
        )

    except Exception as e:
        app.logger.exception("Error loading user dashboard")
        flash(f"Dashboard error: {e}", "danger")
        return redirect(url_for("index"))

    finally:
        if cur:
            cur.close()


@app.route("/user/profile")
@login_required
def user_profile():
    try:
        user = get_user_by_id(session["user_id"])
        employee = get_employee_by_user_id(session["user_id"])
        if not user or not employee:
            flash("Profile not found.", "danger")
            return redirect(url_for("user_dashboard"))
        
        # حساب البيانات الإضافية المطلوبة في القالب
        # حساب عدد سنوات الخدمة
        hire_date = employee.get('hire_date')
        tenure_years = 0
        if hire_date:
            if isinstance(hire_date, str):
                hire_date = datetime.strptime(hire_date, '%Y-%m-%d').date()
            tenure_years = (date.today() - hire_date).days // 365
        
        # حساب نسبة الحضور
        attendance_data = q1("""
            SELECT 
                COUNT(CASE WHEN status='present' THEN 1 END) as present_count,
                COUNT(*) as total_count
            FROM attendance
            WHERE employee_id = %s
              AND YEAR(attendance_date) = YEAR(CURDATE())
        """, (employee['employee_id'],)) or {}
        
        total_att = attendance_data.get('total_count', 0) or 0
        present_att = attendance_data.get('present_count', 0) or 0
        attendance_rate = round((present_att / total_att * 100) if total_att > 0 else 0)
        
        # حساب عدد الإجازات المأخوذة
        leaves_taken = (q1("""
            SELECT COUNT(*) as count
            FROM leaves
            WHERE employee_id = %s
              AND status = 'approved'
              AND YEAR(start_date) = YEAR(CURDATE())
        """, (employee['employee_id'],)) or {}).get('count', 0) or 0
        
        # تجميع البيانات
        user_data = {
            'user_id': user['user_id'],
            'employee_id': employee['employee_id'],
            'first_name': user.get('first_name', ''),
            'last_name': user.get('last_name', ''),
            'full_name': f"{user.get('first_name', '')} {user.get('last_name', '')}".strip(),
            'email': user.get('email', ''),
            'phone': user.get('phone', ''),
            'address': user.get('address', ''),
            'department': employee.get('department_name', 'N/A'),
            'position': employee.get('title_name', 'N/A'),
            'join_date': hire_date.strftime('%Y-%m-%d') if hire_date else 'N/A',
            'tenure_years': tenure_years,
            'attendance_rate': attendance_rate,
            'leaves_taken': leaves_taken,
            'emergency_name': user.get('emergency_name', ''),
            'emergency_relationship': user.get('emergency_relationship', ''),
            'emergency_phone': user.get('emergency_phone', '')
        }
        
        return render_template("user/profile.html", d={'user': user_data})
    except Exception as e:
        flash(f"Error loading profile: {str(e)}", "danger")
        return redirect(url_for("user_dashboard"))

@app.route("/user/attendance")
@login_required
def user_attendance():
    try:
        employee = get_employee_by_user_id(session["user_id"])
        if not employee:
            flash("Employee profile not found.", "danger")
            return redirect(url_for("user_dashboard"))

        selected_month = request.args.get("month", datetime.now().strftime("%Y-%m"))
        page = int(request.args.get("page", 1))
        per_page = 10
        offset = (page - 1) * per_page

        attendance_records = qall("""
            SELECT
                attendance_id, attendance_date, check_in, check_out, status,
                CASE
                    WHEN check_in IS NOT NULL AND check_out IS NOT NULL
                    THEN TIME_FORMAT(TIMEDIFF(check_out, check_in), '%Hh %im')
                    ELSE 'N/A'
                END AS total_hours
            FROM attendance
            WHERE employee_id=%s AND DATE_FORMAT(attendance_date, '%Y-%m')=%s
            ORDER BY attendance_date DESC
            LIMIT %s OFFSET %s
        """, (employee["employee_id"], selected_month, per_page, offset))

        total_records = (q1("""
            SELECT COUNT(*) AS total
            FROM attendance
            WHERE employee_id=%s AND DATE_FORMAT(attendance_date, '%Y-%m')=%s
        """, (employee["employee_id"], selected_month)) or {}).get("total", 0)

        total_pages = (total_records + per_page - 1) // per_page if total_records else 1

        stats = q1("""
            SELECT
                COUNT(CASE WHEN status='present' THEN 1 END) AS present_count,
                COUNT(CASE WHEN status='absent' THEN 1 END) AS absent_count,
                COUNT(CASE WHEN status='leave' THEN 1 END) AS leave_count,
                AVG(CASE WHEN status='present' AND check_in IS NOT NULL AND check_out IS NOT NULL
                    THEN TIME_TO_SEC(TIMEDIFF(check_out, check_in))/3600 END) AS avg_hours
            FROM attendance
            WHERE employee_id=%s AND DATE_FORMAT(attendance_date, '%Y-%m')=%s
        """, (employee["employee_id"], selected_month)) or {}

        avg_hours = stats.get("avg_hours") or 0
        stats_dict = {
            "present_count": stats.get("present_count") or 0,
            "absent_count": stats.get("absent_count") or 0,
            "leave_count": stats.get("leave_count") or 0,
            "avg_hours": f"{int(avg_hours)}h {int(((avg_hours) % 1) * 60)}m",
        }

        # إنشاء calendar data
        year, month = map(int, selected_month.split('-'))
        month_label = datetime(year, month, 1).strftime('%B %Y')
        
        # جلب بيانات الحضور للشهر الحالي للتقويم مع تحديد Late
        calendar_data = qall("""
            SELECT 
                DAY(attendance_date) as day, 
                status,
                check_in
            FROM attendance
            WHERE employee_id=%s 
              AND DATE_FORMAT(attendance_date, '%%Y-%%m')=%s
        """, (employee["employee_id"], selected_month))
        
        calendar_days = {}
        for rec in calendar_data:
            day_num = rec['day']
            status = rec['status']
            check_in = rec['check_in']
            
            # تحديد الحالة النهائية للتقويم
            if status == 'present':
                # تحويل check_in لـ string للمقارنة
                check_in_str = str(check_in) if check_in else ''
                if check_in_str and check_in_str > '09:00:00':
                    calendar_days[day_num] = 'late'
                else:
                    calendar_days[day_num] = 'present'
            elif status == 'absent':
                calendar_days[day_num] = 'absent'
            elif status == 'leave':
                calendar_days[day_num] = 'none'  # أو ممكن نعمل class جديد للـ leave
            else:
                calendar_days[day_num] = 'none'
        
        # تنسيق recent check-ins
        recent_checkins = []
        for rec in attendance_records[:10]:  # آخر 10 سجلات
            recent_checkins.append({
                'date': rec['attendance_date'].strftime('%b %d, %Y') if hasattr(rec['attendance_date'], 'strftime') else str(rec['attendance_date']),
                'in': rec['check_in'].strftime('%H:%M') if rec['check_in'] and hasattr(rec['check_in'], 'strftime') else (str(rec['check_in'])[:5] if rec['check_in'] else 'N/A'),
                'out': rec['check_out'].strftime('%H:%M') if rec['check_out'] and hasattr(rec['check_out'], 'strftime') else (str(rec['check_out'])[:5] if rec['check_out'] else 'N/A'),
                'total': rec['total_hours']
            })
        
        # حساب عدد الأيام المتأخرة
        late_count = (q1("""
            SELECT COUNT(*) as count
            FROM attendance
            WHERE employee_id=%s 
              AND DATE_FORMAT(attendance_date, '%%Y-%%m')=%s
              AND TIME(check_in) > '09:00:00'
              AND status='present'
        """, (employee["employee_id"], selected_month)) or {}).get('count', 0) or 0
        
        # التحقق من حالة الحضور اليوم
        today_attendance = q1("""
            SELECT 
                attendance_date,
                check_in, 
                check_out, 
                status,
                CASE
                    WHEN check_in IS NOT NULL AND check_out IS NOT NULL
                    THEN TIME_FORMAT(TIMEDIFF(check_out, check_in), '%Hh %im')
                    ELSE NULL
                END AS total_hours
            FROM attendance
            WHERE employee_id=%s AND attendance_date = CURDATE()
        """, (employee["employee_id"],))
        
        today_status = 'Not checked in yet'
        today_checked_in = False
        today_checked_out = False
        today_date = datetime.now().strftime('%A, %B %d, %Y')
        today_check_in = None
        today_check_out = None
        today_total_hours = None
        today_is_late = False
        
        if today_attendance:
            check_in_time = today_attendance['check_in']
            check_out_time = today_attendance['check_out']
            
            if check_in_time:
                today_checked_in = True
                time_str = check_in_time.strftime('%I:%M %p') if hasattr(check_in_time, 'strftime') else str(check_in_time)[:5]
                today_check_in = time_str
                
                # التحقق من التأخير
                check_in_str = str(check_in_time) if check_in_time else ''
                if check_in_str and check_in_str > '09:00:00':
                    today_is_late = True
                
                if check_out_time:
                    today_checked_out = True
                    out_str = check_out_time.strftime('%I:%M %p') if hasattr(check_out_time, 'strftime') else str(check_out_time)[:5]
                    today_check_out = out_str
                    today_total_hours = today_attendance.get('total_hours')
                    today_status = f'✓ Checked in at {time_str}, Checked out at {out_str}'
                else:
                    today_status = f'✓ Checked in at {time_str}'
        
        data = {
            'attendance_stats': {
                'present': stats_dict['present_count'],
                'absent': stats_dict['absent_count'],
                'late': late_count
            },
            'calendar': {
                'month_label': month_label,
                'days': calendar_days
            },
            'recent_checkins': recent_checkins,
            'attendance_records': attendance_records,
            'today_status': today_status,
            'today_checked_in': today_checked_in,
            'today_checked_out': today_checked_out,
            'today_date': today_date,
            'today_check_in': today_check_in,
            'today_check_out': today_check_out,
            'today_total_hours': today_total_hours,
            'today_is_late': today_is_late
        }
        
        return render_template("user/attendance.html", d=data)
    except Exception as e:
        flash(f"Error loading attendance: {str(e)}", "danger")
        return redirect(url_for("user_dashboard"))

@app.route("/user/leaves", methods=["GET", "POST"])
@login_required
def user_leaves():
    employee = get_employee_by_user_id(session["user_id"])
    if not employee:
        flash("Employee profile not found.", "danger")
        return redirect(url_for("user_dashboard"))

    if request.method == "POST":
        try:
            leave_type = request.form.get("leave_type", "").strip()
            start_date = request.form.get("start_date", "").strip()
            end_date = request.form.get("end_date", "").strip()
            reason = request.form.get("reason", "").strip() or None

            if not leave_type or not start_date or not end_date:
                flash("Please fill in all required fields.", "danger")
                return redirect(url_for("user_leaves"))

            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d")
            if start > end:
                flash("Start date must be before end date.", "danger")
                return redirect(url_for("user_leaves"))

            overlap = (q1("""
                SELECT COUNT(*) AS c
                FROM leaves
                WHERE employee_id=%s
                  AND status IN ('pending','approved')
                  AND (
                        (start_date <= %s AND end_date >= %s)
                     OR (start_date >= %s AND end_date <= %s)
                  )
            """, (employee["employee_id"], end_date, start_date, start_date, end_date)) or {}).get("c", 0)

            if overlap and overlap > 0:
                flash("You already have a leave request for this period.", "danger")
                return redirect(url_for("user_leaves"))

            exec_sql("""
                INSERT INTO leaves (employee_id, leave_type, start_date, end_date, reason, status)
                VALUES (%s,%s,%s,%s,%s,'pending')
            """, (employee["employee_id"], leave_type, start_date, end_date, reason))

            flash("Leave request submitted successfully!", "success")
            return redirect(url_for("user_leaves"))

        except Exception as e:
            flash(f"Error submitting leave request: {str(e)}", "danger")
            return redirect(url_for("user_leaves"))

    try:
        leaves = qall("""
            SELECT
                leave_id, leave_type, start_date, end_date, status,
                COALESCE(reason, '') AS reason,
                DATEDIFF(end_date, start_date) + 1 AS duration
            FROM leaves
            WHERE employee_id=%s
            ORDER BY
                CASE status
                    WHEN 'pending' THEN 1
                    WHEN 'approved' THEN 2
                    WHEN 'rejected' THEN 3
                END,
                leave_id DESC
        """, (employee["employee_id"],))

        approved_leaves = (q1("""
            SELECT COUNT(*) AS approved_leaves
            FROM leaves
            WHERE employee_id=%s
              AND status='approved'
              AND YEAR(start_date)=YEAR(CURDATE())
        """, (employee["employee_id"],)) or {}).get("approved_leaves", 0) or 0

        remaining_leaves = 21 - approved_leaves
        
        # تنسيق leave_history للقالب
        leave_history = []
        for leave in leaves:
            leave_history.append({
                'type': leave['leave_type'].replace('_', ' ').title(),
                'date': f"{leave['start_date'].strftime('%b %d') if hasattr(leave['start_date'], 'strftime') else str(leave['start_date'])} - {leave['end_date'].strftime('%b %d, %Y') if hasattr(leave['end_date'], 'strftime') else str(leave['end_date'])}",
                'days': leave['duration'],
                'status': leave['status'].title()
            })
        
        data = {
            'leave_history': leave_history
        }
        
        return render_template("user/leaves.html", d=data)
    except Exception as e:
        flash(f"Error loading leaves: {str(e)}", "danger")
        return redirect(url_for("user_dashboard"))

@app.route("/user/leaves/<int:leave_id>/cancel", methods=["POST"])
@login_required
def user_cancel_leave(leave_id):
    employee = get_employee_by_user_id(session["user_id"])
    if not employee:
        flash("Employee profile not found.", "danger")
        return redirect(url_for("user_dashboard"))

    try:
        leave = q1("""
            SELECT leave_id, status
            FROM leaves
            WHERE leave_id=%s AND employee_id=%s
        """, (leave_id, employee["employee_id"]))
        if not leave:
            flash("Leave request not found.", "danger")
            return redirect(url_for("user_leaves"))

        if leave["status"] != "pending":
            flash("You can only cancel pending leave requests.", "danger")
            return redirect(url_for("user_leaves"))

        exec_sql("DELETE FROM leaves WHERE leave_id=%s", (leave_id,))
        flash("Leave request cancelled successfully!", "success")
        return redirect(url_for("user_leaves"))
    except Exception as e:
        flash(f"Error cancelling leave: {str(e)}", "danger")
        return redirect(url_for("user_leaves"))

@app.route("/update_profile", methods=["POST"])
@login_required
def update_profile():
    """
    Update user profile information
    """
    try:
        data = request.get_json()
        user_id = data.get('user_id') or session.get('user_id')
        
        if not user_id or int(user_id) != int(session.get('user_id')):
            return jsonify({"success": False, "message": "Unauthorized"}), 403
        
        # Update user table
        exec_sql("""
            UPDATE users 
            SET first_name = %s,
                last_name = %s,
                email = %s,
                phone = %s,
                address = %s,
                emergency_name = %s,
                emergency_relationship = %s,
                emergency_phone = %s
            WHERE user_id = %s
        """, (
            data.get('first_name', '').strip(),
            data.get('last_name', '').strip(),
            data.get('email', '').strip(),
            data.get('phone', '').strip() or None,
            data.get('address', '').strip() or None,
            data.get('emergency_name', '').strip() or None,
            data.get('emergency_relationship', '').strip() or None,
            data.get('emergency_phone', '').strip() or None,
            user_id
        ))
        
        # Update session
        session['user_name'] = f"{data.get('first_name', '')} {data.get('last_name', '')}".strip()
        session['email'] = data.get('email', '')
        
        return jsonify({"success": True, "message": "Profile updated successfully!"})
        
    except Exception as e:
        app.logger.exception("Error updating profile")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/user/payroll")
@login_required
def user_payroll():
    try:
        employee = get_employee_by_user_id(session["user_id"])
        if not employee:
            flash("Employee profile not found.", "danger")
            return redirect(url_for("user_dashboard"))

        payroll_history = qall("""
            SELECT
                payroll_id, basic_salary, bonus, deductions,
                (basic_salary + bonus - deductions) AS net_pay,
                pay_date, DATE_FORMAT(pay_date, '%Y-%m') AS pay_period
            FROM payroll
            WHERE employee_id=%s
            ORDER BY pay_date DESC
            LIMIT 12
        """, (employee["employee_id"],))

        current_month = datetime.now().strftime("%Y-%m")
        current_payroll = None
        for p in payroll_history:
            if p["pay_period"] == current_month:
                current_payroll = p
                break
        if not current_payroll and payroll_history:
            current_payroll = payroll_history[0]
        
        # تنسيق البيانات للقالب salary.html
        if current_payroll:
            salary_current = {
                'basic': f"${current_payroll.get('basic_salary', 0):,.2f}",
                'allowances': f"${current_payroll.get('bonus', 0):,.2f}",
                'deductions': f"${current_payroll.get('deductions', 0):,.2f}",
                'net': f"${current_payroll.get('net_pay', 0):,.2f}"
            }
        else:
            salary_current = {
                'basic': '$0.00',
                'allowances': '$0.00',
                'deductions': '$0.00',
                'net': '$0.00'
            }
        
        # KPIs للراتب
        total_earned_year = sum(p.get('net_pay', 0) for p in payroll_history)
        salary_kpis = [
            {'icon': 'trend', 'label': 'Total Earned (Year)', 'value': f"${total_earned_year:,.2f}"},
            {'icon': 'doc', 'label': 'Payslips', 'value': str(len(payroll_history))},
            {'icon': 'money', 'label': 'Avg Monthly', 'value': f"${(total_earned_year / len(payroll_history)):,.2f}" if payroll_history else '$0.00'}
        ]
        
        # تنسيق payslips history
        payslips = []
        for p in payroll_history:
            pay_date = p.get('pay_date')
            if pay_date:
                if isinstance(pay_date, str):
                    pay_date = datetime.strptime(pay_date, '%Y-%m-%d')
                month_str = pay_date.strftime('%B %Y')
            else:
                month_str = p.get('pay_period', 'N/A')
            
            payslips.append({
                'month': month_str,
                'basic': f"${p.get('basic_salary', 0):,.2f}",
                'allow': f"${p.get('bonus', 0):,.2f}",
                'ded': f"${p.get('deductions', 0):,.2f}",
                'net': f"${p.get('net_pay', 0):,.2f}"
            })
        
        # Earnings breakdown
        if current_payroll:
            earnings_breakdown = [
                {'name': 'Basic Salary', 'value': f"${current_payroll.get('basic_salary', 0):,.2f}"},
                {'name': 'Bonuses & Allowances', 'value': f"${current_payroll.get('bonus', 0):,.2f}"}
            ]
            total_earnings = f"${(current_payroll.get('basic_salary', 0) + current_payroll.get('bonus', 0)):,.2f}"
        else:
            earnings_breakdown = []
            total_earnings = '$0.00'
        
        # Deductions breakdown
        if current_payroll:
            deductions_breakdown = [
                {'name': 'Tax & Insurance', 'value': f"${current_payroll.get('deductions', 0):,.2f}"}
            ]
            total_deductions = f"${current_payroll.get('deductions', 0):,.2f}"
        else:
            deductions_breakdown = []
            total_deductions = '$0.00'
        
        data = {
            'salary_current': salary_current,
            'salary_kpis': salary_kpis,
            'payslips': payslips,
            'earnings_breakdown': earnings_breakdown,
            'total_earnings': total_earnings,
            'deductions_breakdown': deductions_breakdown,
            'total_deductions': total_deductions
        }
        
        return render_template("user/salary.html", d=data)

    except Exception as e:
        flash(f"Error loading payroll: {str(e)}", "danger")
        return redirect(url_for("user_dashboard"))

@app.route("/user/payroll/export")
@login_required
def user_export_payroll():
    """
    Your previous code says PDF but it was CSV.
    We'll keep CSV (simpler + matches your existing behavior).
    """
    try:
        employee = get_employee_by_user_id(session["user_id"])
        if not employee:
            flash("Employee profile not found.", "danger")
            return redirect(url_for("user_payroll"))

        payroll = q1("""
            SELECT
                payroll_id, basic_salary, bonus, deductions,
                (basic_salary + bonus - deductions) AS net_pay,
                DATE_FORMAT(pay_date, '%Y-%m-%d') AS pay_date
            FROM payroll
            WHERE employee_id=%s
              AND MONTH(pay_date)=MONTH(CURDATE())
              AND YEAR(pay_date)=YEAR(CURDATE())
            LIMIT 1
        """, (employee["employee_id"],))

        if not payroll:
            flash("No payroll data available for this month.", "warning")
            return redirect(url_for("user_payroll"))

        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=["Description", "Amount"])
        writer.writeheader()
        writer.writerows([
            {"Description": "Basic Salary", "Amount": f'{payroll["basic_salary"]:.2f}'},
            {"Description": "Bonus", "Amount": f'{payroll["bonus"]:.2f}'},
            {"Description": "Deductions", "Amount": f'{payroll["deductions"]:.2f}'},
            {"Description": "Net Pay", "Amount": f'{payroll["net_pay"]:.2f}'},
        ])

        output.seek(0)
        resp = make_response(output.getvalue())
        resp.headers["Content-Disposition"] = f"attachment; filename=payroll_{payroll['pay_date']}.csv"
        resp.headers["Content-type"] = "text/csv"
        return resp

    except Exception as e:
        flash(f"Error exporting payroll: {str(e)}", "danger")
        return redirect(url_for("user_payroll"))

# ==================== API ROUTES ====================

@app.route("/api/attendance/check-in", methods=["POST"])
@login_required
def api_check_in():
    try:
        employee = get_employee_by_user_id(session["user_id"])
        if not employee:
            return jsonify({"success": False, "message": "Employee not found"}), 404

        existing = q1("""
            SELECT attendance_id
            FROM attendance
            WHERE employee_id=%s AND attendance_date=CURDATE()
            LIMIT 1
        """, (employee["employee_id"],))
        if existing:
            return jsonify({"success": False, "message": "Already checked in today"}), 400

        exec_sql("""
            INSERT INTO attendance (employee_id, attendance_date, check_in, status)
            VALUES (%s, CURDATE(), CURTIME(), 'present')
        """, (employee["employee_id"],))

        return jsonify({"success": True, "message": "Checked in successfully", "check_in_time": datetime.now().strftime("%H:%M:%S")})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/attendance/check-out", methods=["POST"])
@login_required
def api_check_out():
    try:
        employee = get_employee_by_user_id(session["user_id"])
        if not employee:
            return jsonify({"success": False, "message": "Employee not found"}), 404

        att = q1("""
            SELECT attendance_id
            FROM attendance
            WHERE employee_id=%s AND attendance_date=CURDATE()
            LIMIT 1
        """, (employee["employee_id"],))
        if not att:
            return jsonify({"success": False, "message": "No check-in found for today"}), 400

        exec_sql("""
            UPDATE attendance
            SET check_out = CURTIME()
            WHERE attendance_id=%s
        """, (att["attendance_id"],))

        return jsonify({"success": True, "message": "Checked out successfully", "check_out_time": datetime.now().strftime("%H:%M:%S")})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

# ==================== ERROR HANDLERS ====================

@app.errorhandler(404)
def not_found(e):
    if "user_id" in session:
        if session.get("role_id") == 2:
            return redirect(url_for("admin_dashboard"))
        return redirect(url_for("user_dashboard"))
    return redirect(url_for("login"))

@app.errorhandler(500)
def server_error(e):
    flash("An internal error occurred. Please try again.", "danger")
    if "user_id" in session:
        if session.get("role_id") == 2:
            return redirect(url_for("admin_dashboard"))
        return redirect(url_for("user_dashboard"))
    return redirect(url_for("login"))

# ==================== USER IMPORT ROUTES ====================

@app.route("/admin/user-import", methods=["GET"])
@admin_required
def admin_user_import():
    return render_template("admin/user_import.html")

@app.route("/admin/user-import/upload", methods=["POST"])
@admin_required
def admin_user_import_upload():
    try:
        if 'csv_file' not in request.files:
            flash("No file selected", "danger")
            return redirect(url_for("admin_user_import"))
        
        file = request.files['csv_file']
        
        if file.filename == '':
            flash("No file selected", "danger")
            return redirect(url_for("admin_user_import"))
        
        if not file.filename.endswith('.csv'):
            flash("Please upload a CSV file", "danger")
            return redirect(url_for("admin_user_import"))
        
        csv_content = file.read().decode('utf-8')
        app.logger.info(f"Processing CSV file: {file.filename}")
        
        success_count, errors = bulk_import_users(csv_content)
        app.logger.info(f"Import result: {success_count} successful, {len(errors)} errors")
        
        if success_count > 0:
            flash(f"Successfully imported {success_count} users to Keycloak", "success")
        elif not errors:
            flash("No users were imported. Please check your CSV file.", "warning")
        
        if errors:
            session['import_errors'] = errors[:10]
            flash(f"Some users failed to import. {len(errors)} errors found.", "warning")
        
        return redirect(url_for("admin_user_import"))
        
    except Exception as e:
        app.logger.exception(f"Import failed: {str(e)}")
        flash(f"Import failed: {str(e)}", "danger")
        return redirect(url_for("admin_user_import"))

@app.route("/admin/user-import/template")
@admin_required
def admin_user_import_template():
    template = """username,email,password,role
john.doe,john@example.com,password123,EMPLOYEE
jane.admin,jane@example.com,admin123,HR_ADMIN"""
    
    output = StringIO()
    output.write(template)
    output.seek(0)
    
    resp = make_response(output.getvalue())
    resp.headers["Content-Disposition"] = "attachment; filename=user_import_template.csv"
    resp.headers["Content-type"] = "text/csv"
    return resp

# ==================== KEYCLOAK ADMIN API HELPERS ====================

KEYCLOAK_MASTER_REALM = "master"

def get_keycloak_admin_token():
    try:
        token_url = f"{KEYCLOAK_SERVER_URL}/realms/{KEYCLOAK_MASTER_REALM}/protocol/openid-connect/token"
        data = {
            'username': os.environ.get("KEYCLOAK_ADMIN_USER", "admin"),
            'password': os.environ.get("KEYCLOAK_ADMIN_PASSWORD", "admin"),
            'grant_type': 'password',
            'client_id': 'admin-cli'
        }
        
        response = requests.post(token_url, data=data)
        if response.status_code == 200:
            return response.json().get('access_token')
        else:
            app.logger.error(f"Failed to get admin token: {response.text}")
            return None
    except Exception as e:
        app.logger.error(f"Error getting admin token: {str(e)}")
        return None

def create_keycloak_user(user_data, token):
    try:
        create_url = f"{KEYCLOAK_SERVER_URL}/admin/realms/{KEYCLOAK_REALM}/users"
        
        payload = {
            "username": user_data['username'],
            "email": user_data['email'],
            "enabled": True,
            "emailVerified": True,
            "credentials": [{
                "type": "password",
                "value": user_data['password'],
                "temporary": False
            }]
        }
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        response = requests.post(create_url, json=payload, headers=headers)
        
        if response.status_code in [201, 200]:
            location = response.headers.get('Location')
            user_id = location.split('/')[-1] if location else None
            
            if user_id and user_data['role']:
                assign_role_to_user(user_id, user_data['role'], token)
            
            return True, "User created successfully"
        else:
            return False, f"Failed to create user: {response.text}"
            
    except Exception as e:
        return False, f"Error creating user: {str(e)}"

def assign_role_to_user(user_id, role_name, token):
    try:
        roles_url = f"{KEYCLOAK_SERVER_URL}/admin/realms/{KEYCLOAK_REALM}/roles/{role_name}"
        headers = {"Authorization": f"Bearer {token}"}
        
        response = requests.get(roles_url, headers=headers)
        if response.status_code != 200:
            return False
        
        role_data = response.json()
        
        assign_url = f"{KEYCLOAK_SERVER_URL}/admin/realms/{KEYCLOAK_REALM}/users/{user_id}/role-mappings/realm"
        assign_response = requests.post(assign_url, json=[role_data], headers=headers)
        
        return assign_response.status_code in [200, 204]
        
    except Exception as e:
        app.logger.error(f"Error assigning role: {str(e)}")
        return False

def bulk_import_users(csv_content):
    try:
        csv_file = StringIO(csv_content)
        csv_reader = csv.DictReader(csv_file)
        
        fieldnames = csv_reader.fieldnames
        
        if not fieldnames:
            return 0, ["CSV file is empty or has no headers"]
        
        required_columns = ['username', 'email', 'password', 'role']
        missing = [col for col in required_columns if col not in fieldnames]
        if missing:
            return 0, [f"Missing columns: {', '.join(missing)}"]
        
        admin_token = get_keycloak_admin_token()
        if not admin_token:
            return 0, ["Failed to authenticate with Keycloak admin"]
        
        success_count = 0
        errors = []
        rows = list(csv_reader)
        
        for index, row in enumerate(rows, start=1):
            user_data = {
                'username': str(row.get('username', '')).strip(),
                'email': str(row.get('email', '')).strip().lower(),
                'password': str(row.get('password', '')),
                'role': str(row.get('role', '')).strip().upper()
            }
            
            if user_data['role'] not in ['EMPLOYEE', 'HR_ADMIN']:
                errors.append(f"Row {index}: Invalid role '{user_data['role']}'. Must be EMPLOYEE or HR_ADMIN")
                continue
            
            if not user_data['username']:
                errors.append(f"Row {index}: Username is required")
                continue
            
            if not user_data['email']:
                errors.append(f"Row {index}: Email is required")
                continue
            
            if not user_data['password']:
                errors.append(f"Row {index}: Password is required")
                continue
            
            success, message = create_keycloak_user(user_data, admin_token)
            
            if success:
                success_count += 1
                try:
                    existing_user = find_user_by_email(user_data['email'])
                    if not existing_user:
                        role_id = 2 if user_data['role'] == 'HR_ADMIN' else 1
                        
                        create_user(
                            first_name=user_data['username'].split('.')[0] if '.' in user_data['username'] else user_data['username'],
                            last_name=user_data['username'].split('.')[1] if '.' in user_data['username'] else "User",
                            email=user_data['email'],
                            password=user_data['password'],
                            role_id=role_id
                        )
                        
                        new_user = find_user_by_email(user_data['email'])
                        if new_user:
                            exec_sql("""
                                INSERT INTO employees (user_id, hire_date, status)
                                VALUES (%s, CURDATE(), 'active')
                            """, (new_user['user_id'],))
                            
                except Exception as db_error:
                    app.logger.warning(f"Could not create user in local DB: {db_error}")
                    errors.append(f"Row {index}: Created in Keycloak but failed in local DB: {str(db_error)}")
            else:
                errors.append(f"Row {index}: {message}")
        
        return success_count, errors
        
    except Exception as e:
        app.logger.error(f"Import error: {str(e)}")
        return 0, [f"Import error: {str(e)}"]

# ==================== RUN APP ====================

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)