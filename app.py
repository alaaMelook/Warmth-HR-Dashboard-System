import os
import csv
from io import StringIO
from functools import wraps
from datetime import date, datetime, timedelta

from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, g, session, jsonify, make_response
)
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
from mysql.connector import Error

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "dev-secret-key-change-in-production")

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

# ==================== AUTH DECORATORS ====================

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please login first.", "danger")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please login first.", "danger")
            return redirect(url_for("login"))
        if session.get("role_id") != 2:
            flash("Access denied. Admin only.", "danger")
            return redirect(url_for("user_dashboard"))
        return f(*args, **kwargs)
    return decorated

def user_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please login first.", "danger")
            return redirect(url_for("login"))
        if session.get("role_id") != 1:
            flash("Access denied. User only.", "danger")
            return redirect(url_for("admin_dashboard"))
        return f(*args, **kwargs)
    return decorated

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

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()

        if not email or not password:
            flash("Please fill in both fields.", "danger")
            return redirect(url_for("login"))

        user = find_user_by_email(email)
        if not user:
            flash("Invalid email or password.", "danger")
            return redirect(url_for("login"))

        stored_pw = user.get("password") or ""
        try:
            valid = check_password_hash(stored_pw, password)
        except Exception:
            valid = False

        if not valid:
            flash("Invalid email or password.", "danger")
            return redirect(url_for("login"))

        session["user_id"] = user["user_id"]
        session["user_name"] = f"{user.get('first_name','')} {user.get('last_name','')}".strip()
        session["email"] = user["email"]
        session["role_id"] = user["role_id"]

        flash(f"Welcome back, {user.get('first_name','')}!", "success")
        return redirect(url_for("admin_dashboard" if user["role_id"] == 2 else "user_dashboard"))

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
    session.clear()
    flash("You have been logged out successfully.", "success")
    return redirect(url_for("login"))

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
                COUNT(CASE WHEN check_in > '09:00:00' AND status='present' THEN 1 END) AS late_arrivals,
                COUNT(CASE WHEN status='leave' THEN 1 END) AS on_leave,
                AVG(CASE WHEN status='present' AND check_in IS NOT NULL AND check_out IS NOT NULL
                    THEN TIME_TO_SEC(TIMEDIFF(check_out, check_in))/3600 END) AS avg_hours
            FROM attendance
            WHERE attendance_date=%s
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
            WHERE a.attendance_date = %s
        """
        params = [selected_date]
        if department_filter != "all":
            base_sql += " AND e.department_id = %s"
            params.append(department_filter)

        count_sql = """
            SELECT COUNT(*) AS total
            FROM attendance a
            JOIN employees e ON a.employee_id = e.employee_id
            WHERE a.attendance_date=%s
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
    NOTE: payroll table has NO status column in your DB dump.
    So we treat payroll as list/history only.
    """
    try:
        total_payroll = (q1("""
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

        change_percentage = round(((total_payroll - last_month_total) / last_month_total) * 100, 1) if last_month_total else 0

        employees = qall("""
            SELECT
                u.first_name,
                u.last_name,
                j.title_name AS role,
                p.basic_salary AS base_salary,
                p.bonus,
                p.deductions,
                (p.basic_salary + p.bonus - p.deductions) AS net_pay,
                DATE_FORMAT(p.pay_date, '%Y-%m-%d') AS pay_date
            FROM payroll p
            JOIN employees e ON p.employee_id = e.employee_id
            JOIN users u ON e.user_id = u.user_id
            LEFT JOIN job_titles j ON e.job_title_id = j.job_title_id
            WHERE MONTH(p.pay_date)=MONTH(CURDATE()) AND YEAR(p.pay_date)=YEAR(CURDATE())
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
            "change_percentage": abs(change_percentage),
            "pay_period": f"{period_start.strftime('%b %d')}-{period_end.strftime('%d')}",
            "next_period": f"{next_start.strftime('%b %d')}-{next_end.strftime('%d')}",
        }

        totals = {
            "total_base_salary": total_base_salary,
            "total_bonuses": total_bonuses,
            "total_deductions": total_deductions,
            "total_net_pay": total_net_pay,
        }

        return render_template("admin/payroll.html", stats=stats, employees=employees, totals=totals)

    except Exception as e:
        return render_template(
            "admin/payroll.html",
            stats={"total_payroll": 0, "change_percentage": 0, "pay_period": "N/A", "next_period": "N/A"},
            employees=[],
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
                DATE_FORMAT(p.pay_date, '%Y-%m-%d') AS pay_date
            FROM payroll p
            JOIN employees e ON p.employee_id = e.employee_id
            JOIN users u ON e.user_id = u.user_id
            LEFT JOIN job_titles j ON e.job_title_id = j.job_title_id
            WHERE MONTH(p.pay_date)=MONTH(CURDATE()) AND YEAR(p.pay_date)=YEAR(CURDATE())
            ORDER BY u.last_name, u.first_name
        """)

        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=[
            "first_name", "last_name", "role", "basic_salary", "bonus", "deductions", "net_pay", "pay_date"
        ])
        writer.writeheader()
        writer.writerows(rows)

        output.seek(0)
        resp = make_response(output.getvalue())
        resp.headers["Content-Disposition"] = f"attachment; filename=payroll_{date.today().strftime('%Y-%m')}.csv"
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

        return render_template(
            "user/home.html",   # تأكد إن الملف ده موجود
            employee=employee,
            stats=stats,
            user_name=session.get("user_name")
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
        
        # جلب بيانات الحضور للشهر الحالي للتقويم
        calendar_data = qall("""
            SELECT DAY(attendance_date) as day, status
            FROM attendance
            WHERE employee_id=%s 
              AND DATE_FORMAT(attendance_date, '%%Y-%%m')=%s
        """, (employee["employee_id"], selected_month))
        
        calendar_days = {}
        for rec in calendar_data:
            calendar_days[rec['day']] = rec['status']
        
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
            'recent_checkins': recent_checkins
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

# ==================== RUN APP ====================

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)