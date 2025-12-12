from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import os

app = Flask(__name__)
app.secret_key = 'your-secret-key-here-change-in-production'

# MySQL Configuration
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'hr_management'

mysql = MySQL(app)

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('يرجى تسجيل الدخول أولاً', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Admin required decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('يرجى تسجيل الدخول أولاً', 'error')
            return redirect(url_for('login'))
        if session.get('role_id') != 2:  # 2 = admin
            flash('ليس لديك صلاحية للوصول لهذه الصفحة', 'error')
            return redirect(url_for('user_dashboard'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    if 'user_id' in session:
        if session.get('role_id') == 2:
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('user_dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        if session.get('role_id') == 2:
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('user_dashboard'))
    
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        cursor = mysql.connection.cursor()
        cursor.execute('SELECT user_id, password, role_id, first_name, last_name FROM users WHERE email = %s', (email,))
        user = cursor.fetchone()
        cursor.close()
        
        if user and check_password_hash(user[1], password):
            session['user_id'] = user[0]
            session['role_id'] = user[2]
            session['user_name'] = f"{user[3]} {user[4]}"
            
            flash('تم تسجيل الدخول بنجاح', 'success')
            
            if user[2] == 2:  # Admin
                return redirect(url_for('admin_dashboard'))
            else:  # User
                return redirect(url_for('user_dashboard'))
        else:
            flash('البريد الإلكتروني أو كلمة المرور غير صحيحة', 'error')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        if session.get('role_id') == 2:
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('user_dashboard'))
    
    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        email = request.form['email']
        phone = request.form['phone']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        if password != confirm_password:
            flash('كلمة المرور غير متطابقة', 'error')
            return render_template('register.html')
        
        cursor = mysql.connection.cursor()
        cursor.execute('SELECT user_id FROM users WHERE email = %s', (email,))
        existing_user = cursor.fetchone()
        
        if existing_user:
            flash('البريد الإلكتروني مستخدم بالفعل', 'error')
            cursor.close()
            return render_template('register.html')
        
        hashed_password = generate_password_hash(password)
        cursor.execute(
            'INSERT INTO users (first_name, last_name, email, phone, password, role_id) VALUES (%s, %s, %s, %s, %s, %s)',
            (first_name, last_name, email, phone, hashed_password, 1)  # 1 = user role
        )
        mysql.connection.commit()
        cursor.close()
        
        flash('تم إنشاء الحساب بنجاح، يرجى تسجيل الدخول', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    cursor = mysql.connection.cursor()
    
    # Get statistics
    cursor.execute('SELECT COUNT(*) FROM employees WHERE status = "active"')
    total_employees = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM attendance WHERE attendance_date = CURDATE() AND status = "present"')
    today_attendance = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM leaves WHERE status = "pending"')
    pending_leaves = cursor.fetchone()[0]
    
    cursor.execute('SELECT SUM(basic_salary + bonus - deductions) FROM payroll WHERE MONTH(pay_date) = MONTH(CURDATE())')
    monthly_payroll = cursor.fetchone()[0] or 0
    
    # Get recent activity
    cursor.execute('''
        SELECT u.first_name, u.last_name, l.leave_type, l.start_date, l.end_date, l.status 
        FROM leaves l 
        JOIN employees e ON l.employee_id = e.employee_id 
        JOIN users u ON e.user_id = u.user_id 
        ORDER BY l.leave_id DESC LIMIT 5
    ''')
    recent_leaves = cursor.fetchall()
    
    cursor.close()
    
    return render_template('admin/dashboard.html',
                         total_employees=total_employees,
                         today_attendance=today_attendance,
                         pending_leaves=pending_leaves,
                         monthly_payroll=monthly_payroll,
                         recent_leaves=recent_leaves)

@app.route('/admin/employees')
@admin_required
def admin_employees():
    cursor = mysql.connection.cursor()
    cursor.execute('''
        SELECT u.user_id, u.first_name, u.last_name, u.email, u.phone, 
               d.department_name, jt.title_name, e.status, e.employee_id
        FROM users u
        LEFT JOIN employees e ON u.user_id = e.user_id
        LEFT JOIN departments d ON e.department_id = d.department_id
        LEFT JOIN job_titles jt ON e.job_title_id = jt.job_title_id
        WHERE u.role_id = 1
    ''')
    employees = cursor.fetchall()
    cursor.close()
    
    return render_template('admin/employees.html', employees=employees)

@app.route('/admin/attendance')
@admin_required
def admin_attendance():
    cursor = mysql.connection.cursor()
    cursor.execute('''
        SELECT u.first_name, u.last_name, d.department_name, 
               a.attendance_date, a.check_in, a.check_out, a.status
        FROM attendance a
        JOIN employees e ON a.employee_id = e.employee_id
        JOIN users u ON e.user_id = u.user_id
        LEFT JOIN departments d ON e.department_id = d.department_id
        WHERE a.attendance_date = CURDATE()
        ORDER BY a.check_in DESC
    ''')
    attendance = cursor.fetchall()
    cursor.close()
    
    return render_template('admin/attendance.html', attendance=attendance)

@app.route('/admin/leaves')
@admin_required
def admin_leaves():
    cursor = mysql.connection.cursor()
    cursor.execute('''
        SELECT l.leave_id, u.first_name, u.last_name, l.leave_type, 
               l.start_date, l.end_date, l.status
        FROM leaves l
        JOIN employees e ON l.employee_id = e.employee_id
        JOIN users u ON e.user_id = u.user_id
        ORDER BY l.leave_id DESC
    ''')
    leaves = cursor.fetchall()
    cursor.close()
    
    return render_template('admin/leaves.html', leaves=leaves)

@app.route('/admin/payroll')
@admin_required
def admin_payroll():
    cursor = mysql.connection.cursor()
    cursor.execute('''
        SELECT u.first_name, u.last_name, jt.title_name, 
               p.basic_salary, p.bonus, p.deductions, 
               (p.basic_salary + p.bonus - p.deductions) as net_pay, 
               p.pay_date
        FROM payroll p
        JOIN employees e ON p.employee_id = e.employee_id
        JOIN users u ON e.user_id = u.user_id
        LEFT JOIN job_titles jt ON e.job_title_id = jt.job_title_id
        ORDER BY p.pay_date DESC
    ''')
    payroll = cursor.fetchall()
    cursor.close()
    
    return render_template('admin/payroll.html', payroll=payroll)

@app.route('/user/dashboard')
@login_required
def user_dashboard():
    cursor = mysql.connection.cursor()
    
    # Get user's employee info
    cursor.execute('SELECT employee_id FROM employees WHERE user_id = %s', (session['user_id'],))
    employee = cursor.fetchone()
    
    if employee:
        employee_id = employee[0]
        
        # Get attendance for current month
        cursor.execute('''
            SELECT COUNT(*) FROM attendance 
            WHERE employee_id = %s AND status = "present" 
            AND MONTH(attendance_date) = MONTH(CURDATE())
        ''', (employee_id,))
        attendance_count = cursor.fetchone()[0]
        
        # Get pending leaves
        cursor.execute('''
            SELECT COUNT(*) FROM leaves 
            WHERE employee_id = %s AND status = "pending"
        ''', (employee_id,))
        pending_leaves = cursor.fetchone()[0]
        
        # Get latest payroll
        cursor.execute('''
            SELECT basic_salary, bonus, deductions, pay_date 
            FROM payroll WHERE employee_id = %s 
            ORDER BY pay_date DESC LIMIT 1
        ''', (employee_id,))
        latest_payroll = cursor.fetchone()
    else:
        attendance_count = 0
        pending_leaves = 0
        latest_payroll = None
    
    cursor.close()
    
    return render_template('user/dashboard.html',
                         attendance_count=attendance_count,
                         pending_leaves=pending_leaves,
                         latest_payroll=latest_payroll)

@app.route('/logout')
def logout():
    session.clear()
    flash('تم تسجيل الخروج بنجاح', 'success')
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)