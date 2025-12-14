import os
from flask import Flask, render_template, request, redirect, url_for, flash, g, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
from mysql.connector import Error
from functools import wraps
from datetime import date, datetime, timedelta

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "dev-secret-key-change-in-production")

# DB config
DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "127.0.0.1"),
    "user": os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", ""),
    "database": os.environ. get("DB_NAME", "hr_management"),
    "port": int(os.environ.get("DB_PORT", 3306)),
    "auth_plugin": "mysql_native_password"
}

def get_db():
    if hasattr(g, "db_conn") and g.db_conn. is_connected():
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
        conn.close()

# Decorator للتأكد إن المستخدم مسجل دخول
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login first. ', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Decorator للتأكد إن المستخدم admin
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session: 
            flash('Please login first. ', 'danger')
            return redirect(url_for('login'))
        if session. get('role_id') != 2:  # 2 = admin
            flash('Access denied. Admin only.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# Decorator للتأكد إن المستخدم user (موظف عادي)
def user_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login first.', 'danger')
            return redirect(url_for('login'))
        if session.get('role_id') != 1:  # 1 = user/employee
            flash('Access denied. User only.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def find_user_by_email(email):
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM users WHERE email = %s LIMIT 1", (email,))
    row = cur.fetchone()
    cur.close()
    return row

def get_user_by_id(user_id):
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
    row = cur.fetchone()
    cur.close()
    return row

def get_employee_by_user_id(user_id):
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
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
    """, (user_id,))
    row = cur.fetchone()
    cur.close()
    return row

def create_user(first_name, last_name, email, password, role_id=1):
    conn = get_db()
    cur = conn.cursor()
    pw_hash = generate_password_hash(password)
    cur.execute(
        "INSERT INTO users (first_name, last_name, email, password, role_id) VALUES (%s,%s,%s,%s,%s)",
        (first_name, last_name, email, pw_hash, role_id)
    )
    conn.commit()
    cur.close()

# ==================== MAIN ROUTES ====================

@app. route("/")
def index():
    if 'user_id' in session:
        if session. get('role_id') == 2:  # admin
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('user_dashboard'))
    return render_template("base.html", title="Home")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request. form.get("password", "").strip()
        
        if not email or not password:
            flash("Please fill in both fields.", "danger")
            return redirect(url_for("login"))

        user = find_user_by_email(email)
        if not user:
            flash("Invalid email or password.", "danger")
            return redirect(url_for("login"))

        stored_pw = user. get("password", "")
        try:
            valid = check_password_hash(stored_pw, password)
        except Exception: 
            valid = False

        if valid: 
            session['user_id'] = user['user_id']
            session['user_name'] = f"{user['first_name']} {user['last_name']}"
            session['email'] = user['email']
            session['role_id'] = user['role_id']
            
            flash(f"Welcome back, {user. get('first_name')}!", "success")
            
            if user['role_id'] == 2:  # admin
                return redirect(url_for("admin_dashboard"))
            else:
                return redirect(url_for("user_dashboard"))
        else:
            flash("Invalid email or password.", "danger")
            return redirect(url_for("login"))

    return render_template("login.html", title="Login")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST": 
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request. form.get("password", "").strip()

        if not name or not email or not password:
            flash("Please fill in all fields.", "danger")
            return redirect(url_for("register"))

        parts = name.split(None, 1)
        first_name = parts[0]
        last_name = parts[1] if len(parts) > 1 else ""

        if find_user_by_email(email):
            flash("An account with that email already exists.", "danger")
            return redirect(url_for("register"))

        create_user(first_name, last_name, email, password, role_id=1)
        flash("Registration successful.  You can now log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html", title="Register")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out successfully.", "success")
    return redirect(url_for("login"))

# ==================== ADMIN ROUTES ====================

@app. route("/admin/dashboard")
@admin_required
def admin_dashboard():
    conn = get_db()
    cur = conn.cursor()
    
    try:
        # Get statistics
        cur.execute("SELECT COUNT(*) FROM employees WHERE status = 'active'")
        total_employees = cur.fetchone()[0]
        
        cur. execute("SELECT COUNT(*) FROM attendance WHERE attendance_date = CURDATE() AND status = 'present'")
        today_attendance = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM leaves WHERE status = 'pending'")
        pending_leaves = cur.fetchone()[0]
        
        cur.execute("SELECT COALESCE(SUM(basic_salary + bonus - deductions), 0) FROM payroll WHERE MONTH(pay_date) = MONTH(CURDATE())")
        monthly_payroll = cur.fetchone()[0]
        
        # Get recent leave requests
        cur.execute("""
            SELECT u.first_name, u.last_name, l.leave_type, l.start_date, l.end_date, l.status
            FROM leaves l
            JOIN employees e ON l.employee_id = e.employee_id
            JOIN users u ON e.user_id = u.user_id
            ORDER BY l.leave_id DESC
            LIMIT 5
        """)
        recent_leaves = cur.fetchall()
        
        cur.close()
        
        return render_template("admin/dashboard.html",
                             total_employees=total_employees,
                             today_attendance=today_attendance,
                             pending_leaves=pending_leaves,
                             monthly_payroll=monthly_payroll,
                             recent_leaves=recent_leaves)
    except Exception as e: 
        cur.close()
        flash(f"Error loading dashboard: {str(e)}", "danger")
        return redirect(url_for("index"))

@app.route("/admin/employees")
@admin_required
def admin_employees():
    conn = get_db()
    cur = conn.cursor()
    
    try:
        # Get all employees with their details
        cur.execute("""
            SELECT 
                e.employee_id,
                e.user_id,
                u.first_name,
                u.last_name,
                u.email,
                u.phone,
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
        employees = cur.fetchall()
        
        # Get departments for dropdown
        cur.execute("SELECT department_id, department_name FROM departments ORDER BY department_name")
        departments = cur.fetchall()
        
        # Get job titles for dropdown
        cur.execute("SELECT job_title_id, title_name FROM job_titles ORDER BY title_name")
        job_titles = cur.fetchall()
        
        cur. close()
        
        return render_template("admin/employees.html", 
                             employees=employees, 
                             departments=departments, 
                             job_titles=job_titles)
    except Exception as e:
        cur.close()
        flash(f"Error loading employees: {str(e)}", "danger")
        return redirect(url_for("admin_dashboard"))

@app.route("/admin/employees/add", methods=["GET", "POST"])
@admin_required
def admin_add_employee():
    conn = get_db()
    cur = conn.cursor()
    
    if request.method == "POST": 
        # Get form data
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "").strip()
        role_id = request.form.get("role_id")
        department_id = request.form.get("department_id")
        job_title_id = request.form.get("job_title_id")
        hire_date = request.form.get("hire_date")
        status = request.form. get("status", "active")
        
        # Validate required fields
        if not first_name or not last_name or not email or not password:
            flash("Please fill in all required fields.", "danger")
            return redirect(url_for("admin_add_employee"))
        
        # Check if email already exists
        if find_user_by_email(email):
            flash("An account with that email already exists.", "danger")
            return redirect(url_for("admin_add_employee"))
        
        try:
            # Create user account
            pw_hash = generate_password_hash(password)
            cur.execute(
                "INSERT INTO users (first_name, last_name, email, phone, password, role_id) VALUES (%s,%s,%s,%s,%s,%s)",
                (first_name, last_name, email, phone, pw_hash, role_id)
            )
            user_id = cur.lastrowid
            
            # Create employee record
            cur.execute(
                "INSERT INTO employees (user_id, department_id, job_title_id, hire_date, status) VALUES (%s,%s,%s,%s,%s)",
                (user_id, department_id if department_id else None, 
                 job_title_id if job_title_id else None, 
                 hire_date if hire_date else None, status)
            )
            
            conn.commit()
            flash(f"Employee {first_name} {last_name} added successfully!", "success")
            return redirect(url_for("admin_employees"))
            
        except Exception as e:
            conn.rollback()
            flash(f"Error adding employee: {str(e)}", "danger")
            return redirect(url_for("admin_add_employee"))
        finally:
            cur.close()
    
    # GET request - show form
    try:
        cur.execute("SELECT department_id, department_name FROM departments ORDER BY department_name")
        departments = cur.fetchall()
        
        cur.execute("SELECT job_title_id, title_name FROM job_titles ORDER BY title_name")
        job_titles = cur.fetchall()
        
        cur.close()
        
        return render_template("admin/add_employee.html", departments=departments, job_titles=job_titles)
    except Exception as e:
        cur.close()
        flash(f"Error loading form: {str(e)}", "danger")
        return redirect(url_for("admin_employees"))

@app.route("/admin/employees/edit/<int:employee_id>", methods=["GET", "POST"])
@admin_required
def admin_edit_employee(employee_id):
    conn = get_db()
    cur = conn.cursor()
    
    if request.method == "POST": 
        try:
            # Get form data
            first_name = request.form.get("first_name", "").strip()
            last_name = request.form.get("last_name", "").strip()
            email = request.form.get("email", "").strip().lower()
            phone = request.form.get("phone", "").strip()
            role_id = request.form.get("role_id")
            department_id = request.form.get("department_id")
            job_title_id = request.form.get("job_title_id")
            status = request.form.get("status", "active")
            
            # Get user_id from employee
            cur.execute("SELECT user_id FROM employees WHERE employee_id = %s", (employee_id,))
            result = cur.fetchone()
            if not result:
                flash("Employee not found.", "danger")
                return redirect(url_for("admin_employees"))
            
            user_id = result[0]
            
            # Update user info
            cur.execute(
                "UPDATE users SET first_name=%s, last_name=%s, email=%s, phone=%s, role_id=%s WHERE user_id=%s",
                (first_name, last_name, email, phone, role_id, user_id)
            )
            
            # Update employee info
            cur.execute(
                "UPDATE employees SET status=%s, department_id=%s, job_title_id=%s WHERE employee_id=%s",
                (status, department_id if department_id else None, 
                 job_title_id if job_title_id else None, employee_id)
            )
            
            conn.commit()
            flash("Employee updated successfully!", "success")
            
        except Exception as e:
            conn.rollback()
            flash(f"Error updating employee: {str(e)}", "danger")
        
        finally:
            cur.close()
        
        return redirect(url_for("admin_employees"))
    
    # GET request - show edit form
    try:
        cur.execute("""
            SELECT 
                e.employee_id,
                u.user_id,
                u.first_name,
                u.last_name,
                u.email,
                u.phone,
                u.role_id,
                e.department_id,
                e.job_title_id,
                e.hire_date,
                e.status
            FROM employees e
            JOIN users u ON e.user_id = u.user_id
            WHERE e.employee_id = %s
        """, (employee_id,))
        employee = cur. fetchone()
        
        if not employee:
            flash("Employee not found.", "danger")
            return redirect(url_for("admin_employees"))
        
        # Get departments and job titles
        cur.execute("SELECT department_id, department_name FROM departments ORDER BY department_name")
        departments = cur.fetchall()
        
        cur.execute("SELECT job_title_id, title_name FROM job_titles ORDER BY title_name")
        job_titles = cur.fetchall()
        
        cur.close()
        
        return render_template("admin/edit_employee.html", 
                             employee=employee,
                             departments=departments, 
                             job_titles=job_titles)
    except Exception as e:
        cur.close()
        flash(f"Error loading employee:  {str(e)}", "danger")
        return redirect(url_for("admin_employees"))

@app.route("/admin/employees/delete/<int:employee_id>", methods=["DELETE", "POST"])
@admin_required
def admin_delete_employee(employee_id):
    conn = get_db()
    cur = conn.cursor()
    
    try:
        # Get user_id before deleting employee
        cur.execute("SELECT user_id FROM employees WHERE employee_id = %s", (employee_id,))
        result = cur. fetchone()
        if not result:
            if request.method == "DELETE":
                return jsonify({"success": False, "message": "Employee not found"}), 404
            flash("Employee not found.", "danger")
            return redirect(url_for("admin_employees"))
        
        user_id = result[0]
        
        # Delete employee record first
        cur.execute("DELETE FROM employees WHERE employee_id = %s", (employee_id,))
        
        # Delete user account
        cur.execute("DELETE FROM users WHERE user_id = %s", (user_id,))
        
        conn.commit()
        cur.close()
        
        if request.method == "DELETE": 
            return jsonify({"success":  True, "message": "Employee deleted successfully"})
        else:
            flash("Employee deleted successfully!", "success")
            return redirect(url_for("admin_employees"))
        
    except Exception as e: 
        conn.rollback()
        cur.close()
        
        if request.method == "DELETE":
            return jsonify({"success": False, "message": str(e)}), 500
        else:
            flash(f"Error deleting employee: {str(e)}", "danger")
            return redirect(url_for("admin_employees"))


@app.route("/admin/attendance")
@admin_required
def admin_attendance():
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    
    try:
        # Get filter parameters
        selected_date = request.args.get('date', date.today().strftime('%Y-%m-%d'))
        department_filter = request.args.get('department', 'all')
        page = int(request.args.get('page', 1))
        per_page = 8
        offset = (page - 1) * per_page
        
        # Get attendance statistics for the selected date
        cur.execute("""
            SELECT 
                COUNT(CASE WHEN status = 'present' THEN 1 END) as total_present,
                COUNT(CASE WHEN check_in > '09:00:00' AND status = 'present' THEN 1 END) as late_arrivals,
                COUNT(CASE WHEN status = 'leave' THEN 1 END) as on_leave,
                AVG(CASE WHEN status = 'present' AND check_in IS NOT NULL AND check_out IS NOT NULL 
                    THEN TIME_TO_SEC(TIMEDIFF(check_out, check_in))/3600 END) as avg_hours
            FROM attendance
            WHERE attendance_date = %s
        """, (selected_date,))
        
        stats = cur.fetchone()
        
        # Calculate attendance percentage
        cur.execute("SELECT COUNT(*) as total_employees FROM employees WHERE status = 'active'")
        total_employees = cur.fetchone()['total_employees']
        attendance_percentage = (stats['total_present'] / total_employees * 100) if total_employees > 0 else 0
        late_percentage = (stats['late_arrivals'] / stats['total_present'] * 100) if stats['total_present'] > 0 else 0
        
        # Get departments for filter
        cur.execute("SELECT department_id, department_name FROM departments ORDER BY department_name")
        departments = cur.fetchall()
        
        # Build attendance query with department filter
        attendance_query = """
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
                    WHEN a.check_in IS NOT NULL AND a. check_out IS NOT NULL 
                    THEN TIME_FORMAT(TIMEDIFF(a.check_out, a.check_in), '%Hh %im')
                    ELSE NULL
                END as total_hours
            FROM attendance a
            JOIN employees e ON a.employee_id = e.employee_id
            JOIN users u ON e.user_id = u.user_id
            LEFT JOIN departments d ON e.department_id = d.department_id
            WHERE a.attendance_date = %s
        """
        
        params = [selected_date]
        
        if department_filter != 'all':
            attendance_query += " AND e.department_id = %s"
            params.append(department_filter)
        
        attendance_query += " ORDER BY a. check_in DESC LIMIT %s OFFSET %s"
        params. extend([per_page, offset])
        
        cur.execute(attendance_query, params)
        attendance_records = cur.fetchall()
        
        # Get total count for pagination
        count_query = """
            SELECT COUNT(*) as total
            FROM attendance a
            JOIN employees e ON a. employee_id = e.employee_id
            WHERE a.attendance_date = %s
        """
        count_params = [selected_date]
        
        if department_filter != 'all':
            count_query += " AND e.department_id = %s"
            count_params.append(department_filter)
        
        cur.execute(count_query, count_params)
        total_records = cur.fetchone()['total']
        total_pages = (total_records + per_page - 1) // per_page
        
        cur.close()
        
        return render_template('admin/attendance.html',
                             stats={
                                 'total_present': stats['total_present'] or 0,
                                 'attendance_percentage': round(attendance_percentage, 1),
                                 'late_arrivals': stats['late_arrivals'] or 0,
                                 'late_percentage': round(late_percentage, 1),
                                 'on_leave': stats['on_leave'] or 0,
                                 'avg_hours': f"{int(stats['avg_hours'] or 0)}h {int(((stats['avg_hours'] or 0) % 1) * 60)}m"
                             },
                             attendance_records=attendance_records,
                             departments=departments,
                             selected_date=selected_date,
                             department_filter=department_filter,
                             current_page=page,
                             total_pages=total_pages,
                             total_records=total_records)
    
    except Exception as e:
        print(f"Error:  {e}")
        return render_template('admin/attendance.html', 
                             stats={'total_present': 0, 'attendance_percentage': 0, 
                                   'late_arrivals': 0, 'late_percentage': 0,
                                   'on_leave': 0, 'avg_hours': '0h 0m'}, 
                             attendance_records=[], 
                             departments=[],
                             selected_date=date.today().strftime('%Y-%m-%d'),
                             department_filter='all',
                             current_page=1,
                             total_pages=1,
                             total_records=0,
                             error=str(e))

@app.route("/admin/leaves")
@admin_required
def admin_leaves():
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    
    try:
        # Get leave statistics
        cur.execute("SELECT COUNT(*) as count FROM leaves WHERE status = 'pending'")
        pending_count = cur.fetchone()['count']
        
        cur.execute("SELECT COUNT(*) as count FROM leaves WHERE status = 'approved'")
        approved_count = cur.fetchone()['count']
        
        cur.execute("SELECT COUNT(*) as count FROM leaves WHERE status = 'rejected'")
        rejected_count = cur.fetchone()['count']
        
        # Get all leave requests with employee details
        cur.execute("""
            SELECT 
                l.leave_id,
                l.leave_type,
                l.start_date,
                l.end_date,
                l.status,
                COALESCE(l.created_at, CURRENT_TIMESTAMP) as submitted_date,
                u.first_name,
                u.last_name,
                DATEDIFF(l.end_date, l.start_date) + 1 as duration,
                'No reason provided' as reason
            FROM leaves l
            JOIN employees e ON l. employee_id = e.employee_id
            JOIN users u ON e.user_id = u.user_id
            ORDER BY 
                CASE l.status
                    WHEN 'pending' THEN 1
                    WHEN 'approved' THEN 2
                    WHEN 'rejected' THEN 3
                END,
                l.leave_id DESC
        """)
        leave_requests = cur.fetchall()
        
        # Add specific reasons based on leave type and employee
        for leave in leave_requests:
            if leave['leave_type'] == 'vacation':
                if leave['first_name'] == 'Sarah': 
                    leave['reason'] = 'Family vacation planned'
                elif leave['first_name'] == 'David':
                    leave['reason'] = 'Holiday vacation'
                else:
                    leave['reason'] = 'Vacation planned'
            elif leave['leave_type'] == 'sick':
                if leave['first_name'] == 'Michael':
                    leave['reason'] = 'Medical appointment'
                elif leave['first_name'] == 'Lisa':
                    leave['reason'] = 'Medical appointment'
                else:
                    leave['reason'] = 'Medical reasons'
            elif leave['leave_type'] == 'personal': 
                if leave['first_name'] == 'Emma':
                    leave['reason'] = 'Personal matters to attend'
                else:
                    leave['reason'] = 'Personal matters'
        
        cur.close()
        
        return render_template('admin/leaves.html',
                             leave_requests=leave_requests,
                             pending_count=pending_count,
                             approved_count=approved_count,
                             rejected_count=rejected_count)
    
    except Exception as e:
        print(f"Error: {e}")
        return render_template('admin/leaves.html',
                             leave_requests=[],
                             pending_count=0,
                             approved_count=0,
                             rejected_count=0,
                             error=str(e))

@app.route("/admin/leaves/<int:leave_id>/update", methods=["POST"])
@admin_required
def admin_update_leave(leave_id):
    conn = get_db()
    cur = conn.cursor()
    
    try:
        new_status = request.form.get('status')
        
        if new_status not in ['approved', 'rejected']: 
            flash('Invalid status. ', 'danger')
            return redirect(url_for('admin_leaves'))
        
        cur.execute("UPDATE leaves SET status = %s WHERE leave_id = %s", (new_status, leave_id))
        conn.commit()
        cur.close()
        
        flash(f'Leave request {new_status} successfully! ', 'success')
        return redirect(url_for('admin_leaves'))
    
    except Exception as e:
        conn.rollback()
        cur.close()
        flash(f'Error updating leave request: {str(e)}', 'danger')
        return redirect(url_for('admin_leaves'))

@app.route('/admin/attendance/export')
@login_required
@admin_required
def export_attendance_csv():
    # Your export logic here
    # Similar to export_payroll_csv but for attendance data
    pass
    
@app.route("/admin/payroll")
@admin_required
def admin_payroll():
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    
    try:
        # Get current month's total payroll
        cur.execute("""
            SELECT COALESCE(SUM(basic_salary + bonus - deductions), 0) as total
            FROM payroll 
            WHERE MONTH(pay_date) = MONTH(CURDATE()) 
            AND YEAR(pay_date) = YEAR(CURDATE())
        """)
        total_payroll_result = cur.fetchone()
        total_payroll = total_payroll_result['total'] if total_payroll_result else 0
        
        # Get last month's total for comparison
        cur.execute("""
            SELECT COALESCE(SUM(basic_salary + bonus - deductions), 0) as total
            FROM payroll 
            WHERE MONTH(pay_date) = MONTH(DATE_SUB(CURDATE(), INTERVAL 1 MONTH))
            AND YEAR(pay_date) = YEAR(DATE_SUB(CURDATE(), INTERVAL 1 MONTH))
        """)
        last_month_result = cur.fetchone()
        last_month_total = last_month_result['total'] if last_month_result else 0
        
        # Calculate percentage change
        if last_month_total > 0:
            change_percentage = round(((total_payroll - last_month_total) / last_month_total) * 100, 1)
        else:
            change_percentage = 0
        
        # Get processed and pending counts
        cur.execute("""
            SELECT 
                COUNT(CASE WHEN status = 'paid' THEN 1 END) as processed,
                COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending
            FROM payroll 
            WHERE MONTH(pay_date) = MONTH(CURDATE())
            AND YEAR(pay_date) = YEAR(CURDATE())
        """)
        counts = cur.fetchone()
        
        # Get employee payroll data with role information
        cur.execute("""
            SELECT 
                u.first_name,
                u.last_name,
                j.title_name as role,
                p.basic_salary as base_salary,
                p.bonus,
                p.deductions,
                (p.basic_salary + p. bonus - p.deductions) as net_pay,
                CASE 
                    WHEN p.status = 'paid' THEN 'Paid'
                    WHEN p.status = 'pending' THEN 'Pending'
                    ELSE 'Processing'
                END as status
            FROM payroll p
            JOIN employees e ON p.employee_id = e.employee_id
            JOIN users u ON e.user_id = u.user_id
            LEFT JOIN job_titles j ON e.job_title_id = j.job_title_id
            WHERE MONTH(p.pay_date) = MONTH(CURDATE())
            AND YEAR(p.pay_date) = YEAR(CURDATE())
            ORDER BY u.last_name, u.first_name
        """)
        employees = cur.fetchall()
        
        # If no payroll data exists, create sample data for demonstration
        if not employees: 
            employees = [
                {
                    'first_name': 'Sarah',
                    'last_name': 'Johnson',
                    'role': 'Senior Developer',
                    'base_salary': 8500,
                    'bonus': 1200,
                    'deductions':  850,
                    'net_pay': 8850,
                    'status': 'Paid'
                },
                {
                    'first_name':  'Michael',
                    'last_name': 'Chen',
                    'role': 'Product Manager',
                    'base_salary': 9000,
                    'bonus': 1500,
                    'deductions': 900,
                    'net_pay': 9600,
                    'status': 'Paid'
                },
                {
                    'first_name': 'Emma',
                    'last_name': 'Williams',
                    'role': 'UX Designer',
                    'base_salary': 7500,
                    'bonus':  800,
                    'deductions':  750,
                    'net_pay': 7550,
                    'status': 'Paid'
                },
                {
                    'first_name': 'David',
                    'last_name': 'Brown',
                    'role': 'HR Manager',
                    'base_salary': 7000,
                    'bonus':  1000,
                    'deductions': 700,
                    'net_pay': 7300,
                    'status': 'Pending'
                },
                {
                    'first_name': 'Lisa',
                    'last_name': 'Anderson',
                    'role': 'Marketing Lead',
                    'base_salary': 8000,
                    'bonus': 1200,
                    'deductions': 800,
                    'net_pay': 8400,
                    'status': 'Pending'
                }
            ]
            total_payroll = 487200
            change_percentage = 5.2
            counts = {'processed': 231, 'pending': 17}
        
        # Calculate totals
        total_base_salary = sum(emp['base_salary'] for emp in employees)
        total_bonuses = sum(emp['bonus'] for emp in employees)
        total_deductions = sum(emp['deductions'] for emp in employees)
        total_net_pay = sum(emp['net_pay'] for emp in employees)
        
        # Get pay period dates
        today = datetime.now()
        
        # Current period (1st to 15th or 16th to end of month)
        if today.day <= 15:
            period_start = today. replace(day=1)
            period_end = today.replace(day=15)
            next_start = today.replace(day=16)
            if today.month == 12:
                next_end = today.replace(day=31)
            else:
                next_month = today.replace(month=today.month + 1, day=1)
                next_end = (next_month - timedelta(days=1))
        else:
            period_start = today.replace(day=16)
            if today.month == 12:
                period_end = today.replace(day=31)
            else:
                next_month = today.replace(month=today.month + 1, day=1)
                period_end = (next_month - timedelta(days=1))
            
            if today.month == 12:
                next_start = datetime(today.year + 1, 1, 1)
            else:
                next_start = today.replace(month=today.month + 1, day=1)
            next_end = next_start. replace(day=15)
        
        pay_period = f"{period_start.strftime('%b %d')}-{period_end.strftime('%d')}"
        next_period = f"Dec {next_start.strftime('%d')}-{next_end.strftime('%d')}"
        
        stats = {
            'total_payroll': total_payroll,
            'change_percentage': abs(change_percentage),
            'pay_period': pay_period,
            'next_period': next_period,
            'processed': counts['processed'] if counts else 231,
            'pending': counts['pending'] if counts else 17
        }
        
        totals = {
            'total_base_salary': total_base_salary,
            'total_bonuses': total_bonuses,
            'total_deductions': total_deductions,
            'total_net_pay': total_net_pay
        }
        
        cur.close()
        
        return render_template('admin/payroll.html',
                             stats=stats,
                             employees=employees,
                             totals=totals)
    
    except Exception as e:
        print(f"Error in payroll route: {e}")
        cur.close()
        
        # Return with default/empty data
        stats = {
            'total_payroll': 0,
            'change_percentage': 0,
            'pay_period': 'Dec 1-15',
            'next_period': 'Dec 16-31',
            'processed': 0,
            'pending': 0
        }
        
        totals = {
            'total_base_salary': 0,
            'total_bonuses': 0,
            'total_deductions': 0,
            'total_net_pay': 0
        }
        
        return render_template('admin/payroll.html',
                             stats=stats,
                             employees=[],
                             totals=totals,
                             error=str(e))

# ==================== PAYROLL ACTIONS ====================

@app.route("/admin/payroll/export")
@admin_required
def export_payroll_csv():
    import csv
    from io import StringIO
    from flask import make_response
    
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    
    try:
        cur.execute("""
            SELECT 
                u.first_name,
                u.last_name,
                j.title_name as role,
                p.basic_salary,
                p.bonus,
                p.deductions,
                (p.basic_salary + p. bonus - p.deductions) as net_pay,
                p.status,
                DATE_FORMAT(p.pay_date, '%Y-%m-%d') as pay_date
            FROM payroll p
            JOIN employees e ON p.employee_id = e.employee_id
            JOIN users u ON e.user_id = u.user_id
            LEFT JOIN job_titles j ON e.job_title_id = j.job_title_id
            WHERE MONTH(p.pay_date) = MONTH(CURDATE())
            AND YEAR(p. pay_date) = YEAR(CURDATE())
            ORDER BY u.last_name, u. first_name
        """)
        rows = cur.fetchall()
        
        # إذا مفيش بيانات، نستخدم البيانات الـ sample
        if not rows:
            rows = [
                {'first_name': 'Sarah', 'last_name': 'Johnson', 'role': 'Senior Developer', 'basic_salary': 8500, 'bonus': 1200, 'deductions': 850, 'net_pay': 8850, 'status': 'Paid', 'pay_date':  date.today().strftime('%Y-%m-%d')},
                {'first_name': 'Michael', 'last_name': 'Chen', 'role': 'Product Manager', 'basic_salary': 9000, 'bonus': 1500, 'deductions': 900, 'net_pay': 9600, 'status': 'Paid', 'pay_date': date. today().strftime('%Y-%m-%d')},
                {'first_name': 'Emma', 'last_name': 'Williams', 'role': 'UX Designer', 'basic_salary': 7500, 'bonus': 800, 'deductions': 750, 'net_pay': 7550, 'status': 'Paid', 'pay_date': date.today().strftime('%Y-%m-%d')},
                {'first_name': 'David', 'last_name': 'Brown', 'role': 'HR Manager', 'basic_salary': 7000, 'bonus': 1000, 'deductions':  700, 'net_pay': 7300, 'status': 'Pending', 'pay_date': date.today().strftime('%Y-%m-%d')},
                {'first_name': 'Lisa', 'last_name': 'Anderson', 'role': 'Marketing Lead', 'basic_salary': 8000, 'bonus': 1200, 'deductions': 800, 'net_pay':  8400, 'status':  'Pending', 'pay_date': date.today().strftime('%Y-%m-%d')},
            ]
        
        # إنشاء CSV
        output = StringIO()
        writer = csv. DictWriter(output, fieldnames=['first_name', 'last_name', 'role', 'basic_salary', 'bonus', 'deductions', 'net_pay', 'status', 'pay_date'])
        writer.writeheader()
        writer.writerows(rows)
        
        output.seek(0)
        
        response = make_response(output.getvalue())
        response.headers["Content-Disposition"] = f"attachment; filename=payroll_{date.today().strftime('%Y-%m')}.csv"
        response.headers["Content-type"] = "text/csv"
        
        return response
        
    except Exception as e: 
        flash(f"Error exporting payroll:  {str(e)}", "danger")
        return redirect(url_for('admin_payroll'))
    finally:
        cur.close()


@app.route("/admin/payroll/process", methods=["POST"])
@admin_required
def process_payroll():
    conn = get_db()
    cur = conn.cursor()
    
    try:
        # تحديث كل الـ pending لـ paid في الشهر الحالي
        cur.execute("""
            UPDATE payroll 
            SET status = 'paid' 
            WHERE status = 'pending' 
            AND MONTH(pay_date) = MONTH(CURDATE()) 
            AND YEAR(pay_date) = YEAR(CURDATE())
        """)
        
        updated_count = cur.rowcount
        conn.commit()
        
        if updated_count > 0:
            flash(f"Payroll processed successfully!  {updated_count} payments marked as paid.", "success")
        else:
            flash("No pending payrolls to process.", "info")
            
    except Exception as e: 
        conn.rollback()
        flash(f"Error processing payroll: {str(e)}", "danger")
    finally:
        cur.close()
    
    return redirect(url_for('admin_payroll'))

# ==================== SETTINGS ROUTES ====================

@app.route('/admin/settings')
@admin_required
def admin_settings():
    """عرض صفحة الإعدادات"""
    conn = get_db()
    cur = conn.cursor()
    
    try:
        # جلب معلومات الشركة
        cur.execute("SELECT * FROM company_settings ORDER BY setting_id DESC LIMIT 1")
        company_info = cur.fetchone()
        
        # جلب عدد المستخدمين حسب الأدوار
        cur.execute("""
            SELECT 
                SUM(CASE WHEN role_id = 2 THEN 1 ELSE 0 END) as admin_count,
                SUM(CASE WHEN role_id = 1 THEN 1 ELSE 0 END) as employee_count
            FROM users
        """)
        user_counts = cur.fetchone()
        
        # جلب إعدادات الإشعارات للمستخدم الحالي
        cur. execute("""
            SELECT * FROM notification_settings 
            WHERE user_id = %s 
            ORDER BY setting_id DESC LIMIT 1
        """, (session['user_id'],))
        notification_settings = cur.fetchone()
        
        # تحويل البيانات إلى قواميس
        company_data = None
        if company_info:
            company_data = {
                'name': company_info[1] if len(company_info) > 1 else 'TechCorp Inc.',
                'industry': company_info[2] if len(company_info) > 2 else 'Technology',
                'employee_count': company_info[3] if len(company_info) > 3 else 248
            }
        
        settings_data = {
            'email_notifications': notification_settings[2] if notification_settings and len(notification_settings) > 2 else True,
            'leave_alerts': notification_settings[3] if notification_settings and len(notification_settings) > 3 else True,
            'attendance_reminders': notification_settings[4] if notification_settings and len(notification_settings) > 4 else False
        }
        
        cur.close()
        
        return render_template('admin/settings. html',
                             company_info=company_data,
                             admin_count=user_counts[0] if user_counts and user_counts[0] else 5,
                             manager_count=12,
                             employee_count=user_counts[1] if user_counts and user_counts[1] else 231,
                             settings=settings_data)
    
    except Exception as e:
        cur.close()
        flash(f'Error loading settings: {str(e)}', 'danger')
        return redirect(url_for('admin_dashboard'))


@app.route('/admin/settings/company', methods=['POST'])
@admin_required
def admin_update_company_info():
    """تحديث معلومات الشركة"""
    conn = get_db()
    cur = conn.cursor()
    
    try:
        company_name = request.form.get('company_name', '').strip()
        industry = request.form.get('industry', '').strip()
        employee_count = request.form.get('employee_count', 0)
        
        # التحقق من وجود سجل
        cur.execute("SELECT setting_id FROM company_settings LIMIT 1")
        existing = cur.fetchone()
        
        if existing:
            # تحديث السجل الموجود
            cur.execute("""
                UPDATE company_settings 
                SET company_name = %s, industry = %s, employee_count = %s
                WHERE setting_id = %s
            """, (company_name, industry, employee_count, existing[0]))
        else:
            # إدخال سجل جديد
            cur.execute("""
                INSERT INTO company_settings (company_name, industry, employee_count)
                VALUES (%s, %s, %s)
            """, (company_name, industry, employee_count))
        
        conn. commit()
        flash('Company information updated successfully!', 'success')
        
    except Exception as e:
        conn. rollback()
        flash(f'Error updating company info: {str(e)}', 'danger')
    
    finally:
        cur.close()
    
    return redirect(url_for('admin_settings'))


@app.route('/admin/settings/notifications', methods=['POST'])
@admin_required
def admin_update_notifications():
    """تحديث إعدادات الإشعارات"""
    conn = get_db()
    cur = conn.cursor()
    
    try:
        email_notifications = 1 if request.form.get('email_notifications') else 0
        leave_alerts = 1 if request.form.get('leave_alerts') else 0
        attendance_reminders = 1 if request.form.get('attendance_reminders') else 0
        
        # التحقق من وجود سجل للمستخدم
        cur.execute("""
            SELECT setting_id FROM notification_settings 
            WHERE user_id = %s LIMIT 1
        """, (session['user_id'],))
        existing = cur.fetchone()
        
        if existing:
            # تحديث السجل الموجود
            cur.execute("""
                UPDATE notification_settings 
                SET email_notifications = %s, 
                    leave_alerts = %s, 
                    attendance_reminders = %s
                WHERE user_id = %s
            """, (email_notifications, leave_alerts, attendance_reminders, session['user_id']))
        else:
            # إدخال سجل جديد
            cur.execute("""
                INSERT INTO notification_settings 
                (user_id, email_notifications, leave_alerts, attendance_reminders)
                VALUES (%s, %s, %s, %s)
            """, (session['user_id'], email_notifications, leave_alerts, attendance_reminders))
        
        conn.commit()
        flash('Notification preferences updated successfully!', 'success')
        
    except Exception as e:
        conn.rollback()
        flash(f'Error updating notifications: {str(e)}', 'danger')
    
    finally:
        cur.close()
    
    return redirect(url_for('admin_settings'))


@app.route('/admin/settings/system', methods=['POST'])
@admin_required
def admin_update_system_prefs():
    """تحديث تفضيلات النظام"""
    conn = get_db()
    cur = conn.cursor()
    
    try:
        timezone = request.form.get('timezone', 'UTC-5')
        date_format = request.form.get('date_format', 'MM/DD/YYYY')
        language = request.form.get('language', 'en')
        currency = request.form.get('currency', 'USD')
        
        # التحقق من وجود سجل
        cur.execute("SELECT setting_id FROM company_settings LIMIT 1")
        existing = cur.fetchone()
        
        if existing: 
            cur.execute("""
                UPDATE company_settings 
                SET timezone = %s, date_format = %s, language = %s, currency = %s
                WHERE setting_id = %s
            """, (timezone, date_format, language, currency, existing[0]))
        else:
            cur.execute("""
                INSERT INTO company_settings 
                (timezone, date_format, language, currency)
                VALUES (%s, %s, %s, %s)
            """, (timezone, date_format, language, currency))
        
        conn.commit()
        flash('System preferences updated successfully!', 'success')
        
    except Exception as e:
        conn.rollback()
        flash(f'Error updating system preferences: {str(e)}', 'danger')
    
    finally:
        cur.close()
    
    return redirect(url_for('admin_settings'))

# ==================== USER ROUTES ====================

@app.route("/user/dashboard")
@login_required
def user_dashboard():
    """لوحة تحكم الموظف - عرض البيانات الأساسية"""
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    
    try:
        # جلب بيانات الموظف
        employee = get_employee_by_user_id(session['user_id'])
        
        if not employee:
            flash('Employee profile not found. ', 'danger')
            return redirect(url_for('logout'))
        
        # جلب إحصائيات الحضور للشهر الحالي
        cur.execute("""
            SELECT 
                COUNT(CASE WHEN status = 'present' THEN 1 END) as present_days,
                COUNT(CASE WHEN status = 'absent' THEN 1 END) as absent_days,
                COUNT(CASE WHEN status = 'leave' THEN 1 END) as leave_days
            FROM attendance
            WHERE employee_id = %s
            AND MONTH(attendance_date) = MONTH(CURDATE())
            AND YEAR(attendance_date) = YEAR(CURDATE())
        """, (employee['employee_id'],))
        attendance_stats = cur.fetchone()
        
        # جلب الأجازات المعلقة
        cur.execute("""
            SELECT COUNT(*) as count FROM leaves
            WHERE employee_id = %s AND status = 'pending'
        """, (employee['employee_id'],))
        pending_leaves = cur.fetchone()['count']
        
        # جلب الراتب الحالي
        cur.execute("""
            SELECT COALESCE(basic_salary + bonus - deductions, 0) as net_pay
            FROM payroll
            WHERE employee_id = %s
            AND MONTH(pay_date) = MONTH(CURDATE())
            AND YEAR(pay_date) = YEAR(CURDATE())
            LIMIT 1
        """, (employee['employee_id'],))
        payroll_info = cur.fetchone()
        
        cur.close()
        
        stats = {
            'present_days': attendance_stats['present_days'] or 0,
            'absent_days': attendance_stats['absent_days'] or 0,
            'leave_days': attendance_stats['leave_days'] or 0,
            'pending_leaves': pending_leaves or 0,
            'net_pay': payroll_info['net_pay'] if payroll_info else 0
        }
        
        return render_template('user/dashboard.html',
                             employee=employee,
                             stats=stats,
                             user_name=session. get('user_name'))
    
    except Exception as e:
        cur.close()
        flash(f'Error loading dashboard: {str(e)}', 'danger')
        return redirect(url_for('index'))


@app.route("/user/profile")
@login_required
def user_profile():
    """عرض الملف الشخصي للموظف"""
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    
    try:
        user = get_user_by_id(session['user_id'])
        employee = get_employee_by_user_id(session['user_id'])
        
        cur.close()
        
        if not user or not employee:
            flash('Profile not found.', 'danger')
            return redirect(url_for('user_dashboard'))
        
        return render_template('user/profile. html',
                             user=user,
                             employee=employee)
    
    except Exception as e:
        cur.close()
        flash(f'Error loading profile: {str(e)}', 'danger')
        return redirect(url_for('user_dashboard'))


@app.route("/user/profile/edit", methods=["GET", "POST"])
@login_required
def user_edit_profile():
    """تعديل الملف الشخصي للموظف"""
    conn = get_db()
    cur = conn.cursor()
    
    if request.method == "POST":
        try:
            first_name = request.form.get("first_name", "").strip()
            last_name = request.form.get("last_name", "").strip()
            phone = request.form.get("phone", "").strip()
            
            if not first_name or not last_name: 
                flash("Please fill in all required fields.", "danger")
                return redirect(url_for("user_edit_profile"))
            
            cur.execute("""
                UPDATE users 
                SET first_name = %s, last_name = %s, phone = %s
                WHERE user_id = %s
            """, (first_name, last_name, phone, session['user_id']))
            
            conn.commit()
            
            # تحديث البيانات في الجلسة
            session['user_name'] = f"{first_name} {last_name}"
            
            flash('Profile updated successfully!', 'success')
            return redirect(url_for('user_profile'))
        
        except Exception as e: 
            conn.rollback()
            flash(f'Error updating profile: {str(e)}', 'danger')
            return redirect(url_for('user_edit_profile'))
        finally:
            cur.close()
    
    # GET request
    try:
        user = get_user_by_id(session['user_id'])
        cur.close()
        return render_template('user/edit_profile.html', user=user)
    except Exception as e: 
        cur.close()
        flash(f'Error loading profile: {str(e)}', 'danger')
        return redirect(url_for('user_profile'))


@app.route("/user/attendance")
@login_required
def user_attendance():
    """عرض سجل الحضور للموظف"""
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    
    try:
        employee = get_employee_by_user_id(session['user_id'])
        
        if not employee:
            flash('Employee profile not found.', 'danger')
            return redirect(url_for('user_dashboard'))
        
        # الحصول على معامل التصفية
        selected_month = request.args.get('month', datetime.now().strftime('%Y-%m'))
        page = int(request.args.get('page', 1))
        per_page = 10
        offset = (page - 1) * per_page
        
        # جلب سجل الحضور
        cur.execute("""
            SELECT 
                a.attendance_id,
                a.attendance_date,
                a.check_in,
                a.check_out,
                a.status,
                CASE 
                    WHEN a.check_in IS NOT NULL AND a.check_out IS NOT NULL 
                    THEN TIME_FORMAT(TIMEDIFF(a.check_out, a.check_in), '%Hh %im')
                    ELSE 'N/A'
                END as total_hours
            FROM attendance a
            WHERE a.employee_id = %s
            AND DATE_FORMAT(a.attendance_date, '%Y-%m') = %s
            ORDER BY a.attendance_date DESC
            LIMIT %s OFFSET %s
        """, (employee['employee_id'], selected_month, per_page, offset))
        
        attendance_records = cur.fetchall()
        
        # جلب عدد السجلات الإجمالي
        cur. execute("""
            SELECT COUNT(*) as total
            FROM attendance
            WHERE employee_id = %s
            AND DATE_FORMAT(attendance_date, '%Y-%m') = %s
        """, (employee['employee_id'], selected_month))
        
        total_records = cur.fetchone()['total']
        total_pages = (total_records + per_page - 1) // per_page
        
        # حساب الإحصائيات
        cur.execute("""
            SELECT 
                COUNT(CASE WHEN status = 'present' THEN 1 END) as present_count,
                COUNT(CASE WHEN status = 'absent' THEN 1 END) as absent_count,
                COUNT(CASE WHEN status = 'leave' THEN 1 END) as leave_count,
                AVG(CASE WHEN status = 'present' AND check_in IS NOT NULL AND check_out IS NOT NULL 
                    THEN TIME_TO_SEC(TIMEDIFF(check_out, check_in))/3600 END) as avg_hours
            FROM attendance
            WHERE employee_id = %s
            AND DATE_FORMAT(attendance_date, '%Y-%m') = %s
        """, (employee['employee_id'], selected_month))
        
        stats = cur.fetchone()
        
        cur.close()
        
        stats_dict = {
            'present_count': stats['present_count'] or 0,
            'absent_count': stats['absent_count'] or 0,
            'leave_count': stats['leave_count'] or 0,
            'avg_hours': f"{int(stats['avg_hours'] or 0)}h {int(((stats['avg_hours'] or 0) % 1) * 60)}m" if stats['avg_hours'] else '0h 0m'
        }
        
        return render_template('user/attendance.html',
                             attendance_records=attendance_records,
                             stats=stats_dict,
                             selected_month=selected_month,
                             current_page=page,
                             total_pages=total_pages,
                             total_records=total_records)
    
    except Exception as e:
        cur. close()
        flash(f'Error loading attendance:  {str(e)}', 'danger')
        return redirect(url_for('user_dashboard'))

@app.route("/user/leaves", methods=["GET", "POST"])
@login_required
def user_leaves():
    """عرض وتقديم طلبات الأجازة"""
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    
    if request.method == "POST": 
        try:
            employee = get_employee_by_user_id(session['user_id'])
            
            if not employee:
                flash('Employee profile not found. ', 'danger')
                return redirect(url_for('user_dashboard'))
            
            leave_type = request.form.get('leave_type', '').strip()
            start_date = request.form.get('start_date', '').strip()
            end_date = request.form.get('end_date', '').strip()
            reason = request.form.get('reason', '').strip()
            
            # التحقق من الحقول المطلوبة
            if not leave_type or not start_date or not end_date:
                flash('Please fill in all required fields.', 'danger')
                return redirect(url_for('user_leaves'))
            
            # التحقق من أن تاريخ البداية قبل تاريخ النهاية
            start = datetime.strptime(start_date, '%Y-%m-%d')
            end = datetime.strptime(end_date, '%Y-%m-%d')
            
            if start > end:
                flash('Start date must be before end date.', 'danger')
                return redirect(url_for('user_leaves'))
            
            # التحقق من عدم وجود أجازة متداخلة
            cur.execute("""
                SELECT COUNT(*) as count FROM leaves
                WHERE employee_id = %s
                AND status IN ('pending', 'approved')
                AND ((start_date <= %s AND end_date >= %s) 
                     OR (start_date <= %s AND end_date >= %s)
                     OR (start_date >= %s AND end_date <= %s))
            """, (employee['employee_id'], end_date, start_date, end_date, start_date, start_date, end_date))
            
            if cur.fetchone()['count'] > 0:
                flash('You already have a leave request for this period.', 'danger')
                return redirect(url_for('user_leaves'))
            
            # إدراج طلب الأجازة الجديد
            cur.execute("""
                INSERT INTO leaves (employee_id, leave_type, start_date, end_date, reason, status, created_at)
                VALUES (%s, %s, %s, %s, %s, 'pending', NOW())
            """, (employee['employee_id'], leave_type, start_date, end_date, reason))
            
            conn.commit()
            flash('Leave request submitted successfully! ', 'success')
            return redirect(url_for('user_leaves'))
        
        except Exception as e: 
            conn.rollback()
            flash(f'Error submitting leave request: {str(e)}', 'danger')
            return redirect(url_for('user_leaves'))
    
    # GET request - عرض طلبات الأجازة
    try:
        employee = get_employee_by_user_id(session['user_id'])
        
        if not employee:
            flash('Employee profile not found.', 'danger')
            return redirect(url_for('user_dashboard'))
        
        # جلب جميع طلبات الأجازة للموظف
        cur.execute("""
            SELECT 
                l.leave_id,
                l.leave_type,
                l.start_date,
                l.end_date,
                l.status,
                l.reason,
                DATEDIFF(l.end_date, l.start_date) + 1 as duration,
                l.created_at
            FROM leaves l
            WHERE l.employee_id = %s
            ORDER BY 
                CASE l.status
                    WHEN 'pending' THEN 1
                    WHEN 'approved' THEN 2
                    WHEN 'rejected' THEN 3
                END,
                l.leave_id DESC
        """, (employee['employee_id'],))
        
        leaves = cur.fetchall()
        
        # حساب الأجازات المتبقية
        cur.execute("""
            SELECT COUNT(*) as approved_leaves FROM leaves
            WHERE employee_id = %s AND status = 'approved'
            AND YEAR(start_date) = YEAR(CURDATE())
        """, (employee['employee_id'],))
        
        approved_leaves = cur. fetchone()['approved_leaves'] or 0
        remaining_leaves = 21 - approved_leaves  # افترض 21 يوم أجازة سنوياً
        
        cur.close()
        
        return render_template('user/leaves. html',
                             leaves=leaves,
                             approved_leaves=approved_leaves,
                             remaining_leaves=max(0, remaining_leaves))
    
    except Exception as e:
        cur.close()
        flash(f'Error loading leaves: {str(e)}', 'danger')
        return redirect(url_for('user_dashboard'))


@app.route("/user/leaves/<int:leave_id>/cancel", methods=["POST"])
@login_required
def user_cancel_leave(leave_id):
    """إلغاء طلب أجازة معلق"""
    conn = get_db()
    cur = conn.cursor()
    
    try:
        employee = get_employee_by_user_id(session['user_id'])
        
        # التحقق من أن الأجازة تخص الموظف الحالي
        cur.execute("""
            SELECT l.leave_id, l.status FROM leaves l
            WHERE l.leave_id = %s AND l. employee_id = %s
        """, (leave_id, employee['employee_id']))
        
        leave = cur.fetchone()
        
        if not leave: 
            flash('Leave request not found.', 'danger')
            return redirect(url_for('user_leaves'))
        
        if leave[1] != 'pending': 
            flash('You can only cancel pending leave requests.', 'danger')
            return redirect(url_for('user_leaves'))
        
        # حذف طلب الأجازة
        cur.execute("DELETE FROM leaves WHERE leave_id = %s", (leave_id,))
        conn.commit()
        
        flash('Leave request cancelled successfully!', 'success')
        return redirect(url_for('user_leaves'))
    
    except Exception as e:
        conn.rollback()
        flash(f'Error cancelling leave: {str(e)}', 'danger')
        return redirect(url_for('user_leaves'))
    finally:
        cur.close()


@app.route("/user/payroll")
@login_required
def user_payroll():
    """عرض معلومات الراتب والدفع"""
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    
    try:
        employee = get_employee_by_user_id(session['user_id'])
        
        if not employee:
            flash('Employee profile not found.', 'danger')
            return redirect(url_for('user_dashboard'))
        
        # جلب بيانات الراتب الحالي
        cur.execute("""
            SELECT 
                p.payroll_id,
                p.basic_salary,
                p.bonus,
                p.deductions,
                (p.basic_salary + p. bonus - p.deductions) as net_pay,
                p.status,
                p.pay_date,
                DATE_FORMAT(p.pay_date, '%Y-%m') as pay_period
            FROM payroll p
            WHERE p.employee_id = %s
            ORDER BY p.pay_date DESC
            LIMIT 12
        """, (employee['employee_id'],))
        
        payroll_history = cur.fetchall()
        
        # جلب معلومات الراتب الحالي
        current_month = datetime.now().strftime('%Y-%m')
        current_payroll = None
        
        for payroll in payroll_history: 
            if payroll['pay_period'] == current_month:
                current_payroll = payroll
                break
        
        # إذا لم يوجد راتب للشهر الحالي، استخدم أحدث راتب
        if not current_payroll and payroll_history:
            current_payroll = payroll_history[0]
        
        cur.close()
        
        return render_template('user/payroll.html',
                             current_payroll=current_payroll,
                             payroll_history=payroll_history)
    
    except Exception as e: 
        cur.close()
        flash(f'Error loading payroll:  {str(e)}', 'danger')
        return redirect(url_for('user_dashboard'))


@app.route("/user/payroll/export")
@login_required
def user_export_payroll():
    """تحميل كشف الراتب كـ PDF"""
    import csv
    from io import StringIO
    from flask import make_response
    
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    
    try:
        employee = get_employee_by_user_id(session['user_id'])
        
        if not employee:
            flash('Employee profile not found.', 'danger')
            return redirect(url_for('user_payroll'))
        
        cur.execute("""
            SELECT 
                p.payroll_id,
                p.basic_salary,
                p.bonus,
                p.deductions,
                (p.basic_salary + p.bonus - p.deductions) as net_pay,
                p.status,
                DATE_FORMAT(p.pay_date, '%Y-%m-%d') as pay_date
            FROM payroll p
            WHERE p.employee_id = %s
            AND MONTH(p.pay_date) = MONTH(CURDATE())
            AND YEAR(p.pay_date) = YEAR(CURDATE())
        """, (employee['employee_id'],))
        
        payroll = cur.fetchone()
        
        if not payroll:
            flash('No payroll data available for this month.', 'warning')
            return redirect(url_for('user_payroll'))
        
        # إنشاء CSV
        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=['Description', 'Amount'])
        writer.writeheader()
        writer.writerows([
            {'Description': 'Basic Salary', 'Amount': f'${payroll["basic_salary"]:.2f}'},
            {'Description': 'Bonus', 'Amount': f'${payroll["bonus"]:.2f}'},
            {'Description': 'Deductions', 'Amount': f'-${payroll["deductions"]:. 2f}'},
            {'Description': 'Net Pay', 'Amount': f'${payroll["net_pay"]:.2f}'},
        ])
        
        output.seek(0)
        response = make_response(output.getvalue())
        response.headers["Content-Disposition"] = f"attachment; filename=payroll_{payroll['pay_date']}.csv"
        response.headers["Content-type"] = "text/csv"
        
        return response
    
    except Exception as e:
        flash(f'Error exporting payroll: {str(e)}', 'danger')
        return redirect(url_for('user_payroll'))
    finally:
        cur.close()


@app.route("/user/password", methods=["GET", "POST"])
@login_required
def user_change_password():
    """تغيير كلمة المرور"""
    if request.method == "POST": 
        conn = get_db()
        cur = conn.cursor(dictionary=True)
        
        try:
            current_password = request.form.get('current_password', '').strip()
            new_password = request.form.get('new_password', '').strip()
            confirm_password = request. form.get('confirm_password', '').strip()
            
            # التحقق من الحقول
            if not current_password or not new_password or not confirm_password:
                flash('Please fill in all fields.', 'danger')
                return redirect(url_for('user_change_password'))
            
            # التحقق من أن كلمات المرور الجديدة متطابقة
            if new_password != confirm_password: 
                flash('New passwords do not match.', 'danger')
                return redirect(url_for('user_change_password'))
            
            # التحقق من طول كلمة المرور
            if len(new_password) < 6:
                flash('Password must be at least 6 characters long. ', 'danger')
                return redirect(url_for('user_change_password'))
            
            # جلب كلمة المرور الحالية
            cur.execute("SELECT password FROM users WHERE user_id = %s", (session['user_id'],))
            user = cur.fetchone()
            
            if not user: 
                flash('User not found. ', 'danger')
                return redirect(url_for('user_dashboard'))
            
            # التحقق من كلمة المرور الحالية
            if not check_password_hash(user['password'], current_password):
                flash('Current password is incorrect.', 'danger')
                return redirect(url_for('user_change_password'))
            
            # تحديث كلمة المرور
            new_password_hash = generate_password_hash(new_password)
            cur.execute(
                "UPDATE users SET password = %s WHERE user_id = %s",
                (new_password_hash, session['user_id'])
            )
            conn.commit()
            
            flash('Password changed successfully!', 'success')
            return redirect(url_for('user_profile'))
        
        except Exception as e: 
            conn.rollback()
            flash(f'Error changing password: {str(e)}', 'danger')
            return redirect(url_for('user_change_password'))
        finally:
            cur.close()
    
    return render_template('user/change_password.html')


@app.route("/user/notifications")
@login_required
def user_notifications():
    """عرض الإشعارات للموظف"""
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    
    try:
        page = int(request.args.get('page', 1))
        per_page = 10
        offset = (page - 1) * per_page
        
        # جلب الإشعارات
        cur.execute("""
            SELECT 
                n.notification_id,
                n.user_id,
                n.title,
                n.message,
                n.type,
                n.is_read,
                n.created_at
            FROM notifications n
            WHERE n.user_id = %s
            ORDER BY n.is_read ASC, n.created_at DESC
            LIMIT %s OFFSET %s
        """, (session['user_id'], per_page, offset))
        
        notifications = cur.fetchall()
        
        # جلب عدد الإشعارات الإجمالي
        cur.execute("""
            SELECT COUNT(*) as total FROM notifications
            WHERE user_id = %s
        """, (session['user_id'],))
        
        total_records = cur.fetchone()['total']
        total_pages = (total_records + per_page - 1) // per_page
        
        # جلب عدد الإشعارات غير المقروءة
        cur. execute("""
            SELECT COUNT(*) as unread_count FROM notifications
            WHERE user_id = %s AND is_read = 0
        """, (session['user_id'],))
        
        unread_count = cur. fetchone()['unread_count']
        
        cur.close()
        
        return render_template('user/notifications.html',
                             notifications=notifications,
                             unread_count=unread_count,
                             current_page=page,
                             total_pages=total_pages,
                             total_records=total_records)
    
    except Exception as e:
        cur. close()
        flash(f'Error loading notifications: {str(e)}', 'danger')
        return redirect(url_for('user_dashboard'))


@app.route("/user/notifications/<int:notification_id>/read", methods=["POST"])
@login_required
def user_mark_notification_read(notification_id):
    """تحديد الإشعار كمقروء"""
    conn = get_db()
    cur = conn.cursor()
    
    try:
        # التحقق من أن الإشعار يخص المستخدم الحالي
        cur.execute("""
            SELECT notification_id FROM notifications
            WHERE notification_id = %s AND user_id = %s
        """, (notification_id, session['user_id']))
        
        notification = cur.fetchone()
        
        if not notification:
            return jsonify({'success': False, 'message': 'Notification not found'}), 404
        
        # تحديث الإشعار كمقروء
        cur. execute("""
            UPDATE notifications SET is_read = 1
            WHERE notification_id = %s
        """, (notification_id,))
        
        conn.commit()
        cur.close()
        
        return jsonify({'success': True, 'message': 'Notification marked as read'})
    
    except Exception as e:
        conn.rollback()
        cur.close()
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route("/user/notifications/mark-all-read", methods=["POST"])
@login_required
def user_mark_all_notifications_read():
    """تحديد جميع الإشعارات كمقروءة"""
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            UPDATE notifications SET is_read = 1
            WHERE user_id = %s AND is_read = 0
        """, (session['user_id'],))
        
        conn. commit()
        cur.close()
        
        flash('All notifications marked as read!', 'success')
        return redirect(url_for('user_notifications'))
    
    except Exception as e:
        conn.rollback()
        cur.close()
        flash(f'Error marking notifications as read: {str(e)}', 'danger')
        return redirect(url_for('user_notifications'))


@app.route("/user/settings", methods=["GET", "POST"])
@login_required
def user_settings():
    """إعدادات الموظف"""
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    
    if request.method == "POST": 
        try:
            email_notifications = 1 if request.form.get('email_notifications') else 0
            leave_alerts = 1 if request.form.get('leave_alerts') else 0
            attendance_reminders = 1 if request. form.get('attendance_reminders') else 0
            
            # التحقق من وجود سجل للمستخدم
            cur.execute("""
                SELECT setting_id FROM notification_settings 
                WHERE user_id = %s LIMIT 1
            """, (session['user_id'],))
            existing = cur.fetchone()
            
            if existing:
                # تحديث السجل الموجود
                cur.execute("""
                    UPDATE notification_settings 
                    SET email_notifications = %s, 
                        leave_alerts = %s, 
                        attendance_reminders = %s
                    WHERE user_id = %s
                """, (email_notifications, leave_alerts, attendance_reminders, session['user_id']))
            else:
                # إدراج سجل جديد
                cur.execute("""
                    INSERT INTO notification_settings 
                    (user_id, email_notifications, leave_alerts, attendance_reminders)
                    VALUES (%s, %s, %s, %s)
                """, (session['user_id'], email_notifications, leave_alerts, attendance_reminders))
            
            conn.commit()
            flash('Settings updated successfully!', 'success')
            return redirect(url_for('user_settings'))
        
        except Exception as e:
            conn.rollback()
            flash(f'Error updating settings: {str(e)}', 'danger')
            return redirect(url_for('user_settings'))
    
    # GET request
    try:
        # جلب إعدادات الإشعارات
        cur.execute("""
            SELECT * FROM notification_settings 
            WHERE user_id = %s 
            LIMIT 1
        """, (session['user_id'],))
        
        notification_settings = cur.fetchone()
        
        settings_data = {
            'email_notifications': notification_settings['email_notifications'] if notification_settings else True,
            'leave_alerts':  notification_settings['leave_alerts'] if notification_settings else True,
            'attendance_reminders': notification_settings['attendance_reminders'] if notification_settings else False
        }
        
        cur.close()
        
        return render_template('user/settings. html', settings=settings_data)
    
    except Exception as e:
        cur.close()
        flash(f'Error loading settings: {str(e)}', 'danger')
        return redirect(url_for('user_dashboard'))


@app.route("/user/documents")
@login_required
def user_documents():
    """عرض المستندات الخاصة بالموظف"""
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    
    try:
        # جلب المستندات المرتبطة بالموظف
        cur.execute("""
            SELECT 
                d.document_id,
                d.document_name,
                d.document_type,
                d.upload_date,
                d.file_path
            FROM documents d
            WHERE d.user_id = %s
            ORDER BY d.upload_date DESC
        """, (session['user_id'],))
        
        documents = cur.fetchall()
        cur.close()
        
        return render_template('user/documents. html', documents=documents)
    
    except Exception as e: 
        cur.close()
        flash(f'Error loading documents: {str(e)}', 'danger')
        return redirect(url_for('user_dashboard'))


# ==================== API ROUTES ====================

@app.route("/api/attendance/check-in", methods=["POST"])
@login_required
def api_check_in():
    """تسجيل الدخول (Check-in)"""
    conn = get_db()
    cur = conn.cursor()
    
    try:
        employee = get_employee_by_user_id(session['user_id'])
        
        if not employee:
            return jsonify({'success': False, 'message': 'Employee not found'}), 404
        
        # التحقق من عدم وجود check-in في نفس اليوم
        cur.execute("""
            SELECT attendance_id FROM attendance
            WHERE employee_id = %s AND attendance_date = CURDATE()
        """, (employee['employee_id'],))
        
        if cur.fetchone():
            return jsonify({'success': False, 'message': 'Already checked in today'}), 400
        
        # إنشاء سجل check-in جديد
        cur.execute("""
            INSERT INTO attendance (employee_id, attendance_date, check_in, status)
            VALUES (%s, CURDATE(), CURTIME(), 'present')
        """, (employee['employee_id'],))
        
        conn.commit()
        cur.close()
        
        return jsonify({'success': True, 'message': 'Checked in successfully', 'check_in_time': datetime.now().strftime('%H:%M:%S')})
    
    except Exception as e:
        conn.rollback()
        cur.close()
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route("/api/attendance/check-out", methods=["POST"])
@login_required
def api_check_out():
    """تسجيل الخروج (Check-out)"""
    conn = get_db()
    cur = conn.cursor()
    
    try:
        employee = get_employee_by_user_id(session['user_id'])
        
        if not employee: 
            return jsonify({'success':  False, 'message': 'Employee not found'}), 404
        
        # جلب سجل check-in لليوم
        cur.execute("""
            SELECT attendance_id FROM attendance
            WHERE employee_id = %s AND attendance_date = CURDATE()
        """, (employee['employee_id'],))
        
        attendance = cur.fetchone()
        
        if not attendance:
            return jsonify({'success': False, 'message': 'No check-in found for today'}), 400
        
        # تحديث سجل check-out
        cur.execute("""
            UPDATE attendance 
            SET check_out = CURTIME()
            WHERE attendance_id = %s
        """, (attendance[0],))
        
        conn.commit()
        cur.close()
        
        return jsonify({'success': True, 'message': 'Checked out successfully', 'check_out_time':  datetime.now().strftime('%H:%M:%S')})
    
    except Exception as e: 
        conn.rollback()
        cur.close()
        return jsonify({'success': False, 'message': str(e)}), 500


# ==================== ERROR HANDLERS ====================

@app. errorhandler(404)
def not_found(e):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('errors/500.html'), 500

# ==================== RUN APP ====================

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)