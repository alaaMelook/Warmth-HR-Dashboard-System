import os
from flask import Flask, render_template, request, redirect, url_for, flash, g, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
from mysql.connector import Error
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "dev-secret-key-change-in-production")

# DB config
DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "127.0.0.1"),
    "user": os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", ""),
    "database": os.environ.get("DB_NAME", "hr_management"),
    "port": int(os.environ.get("DB_PORT", 3306)),
    "auth_plugin": "mysql_native_password"
}

def get_db():
    if hasattr(g, "db_conn") and g.db_conn.is_connected():
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
            flash('Please login first.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Decorator للتأكد إن المستخدم admin
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login first.', 'danger')
            return redirect(url_for('login'))
        if session.get('role_id') != 2:  # 2 = admin
            flash('Access denied. Admin only.', 'danger')
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

@app.route("/")
def index():
    if 'user_id' in session:
        if session.get('role_id') == 2:  # admin
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('user_dashboard'))
    return render_template("base.html", title="Home")

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

        stored_pw = user.get("password", "")
        try:
            valid = check_password_hash(stored_pw, password)
        except Exception:
            valid = False

        if valid:
            session['user_id'] = user['user_id']
            session['user_name'] = f"{user['first_name']} {user['last_name']}"
            session['email'] = user['email']
            session['role_id'] = user['role_id']
            
            flash(f"Welcome back, {user.get('first_name')}!", "success")
            
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
        password = request.form.get("password", "").strip()

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
        flash("Registration successful. You can now log in.", "success")
        return redirect(url_for("login"))

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
    conn = get_db()
    cur = conn.cursor()
    
    try:
        # Get statistics
        cur.execute("SELECT COUNT(*) FROM employees WHERE status = 'active'")
        total_employees = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM attendance WHERE attendance_date = CURDATE() AND status = 'present'")
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
        
        cur.close()
        
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
        status = request.form.get("status", "active")
        
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
        employee = cur.fetchone()
        
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
        flash(f"Error loading employee: {str(e)}", "danger")
        return redirect(url_for("admin_employees"))

@app.route("/admin/employees/delete/<int:employee_id>", methods=["DELETE", "POST"])
@admin_required
def admin_delete_employee(employee_id):
    conn = get_db()
    cur = conn.cursor()
    
    try:
        # Get user_id before deleting employee
        cur.execute("SELECT user_id FROM employees WHERE employee_id = %s", (employee_id,))
        result = cur.fetchone()
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
            return jsonify({"success": True, "message": "Employee deleted successfully"})
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
    return render_template("admin/attendance.html")

@app.route("/admin/leaves")
@admin_required
def admin_leaves():
    return render_template("admin/leaves.html")

@app.route("/admin/payroll")
@admin_required
def admin_payroll():
    return render_template("admin/payroll.html")

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
        cur.execute("""
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
        
        return render_template('admin/settings.html',
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
        
        conn.commit()
        flash('Company information updated successfully!', 'success')
        
    except Exception as e:
        conn.rollback()
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
    return f"<h1>Welcome {session.get('user_name')}!</h1><p>User Dashboard (Coming Soon)</p>"

# ==================== RUN APP ====================

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)