from flask import Flask, request, jsonify
from flask_mysqldb import MySQL
from flask_bcrypt import Bcrypt
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity

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
    data = request.json
    first_name = data['first_name']
    last_name = data['last_name']
    email = data['email']
    password = data['password']

    hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

    cursor = mysql.connection.cursor()
    try:
        cursor.execute("INSERT INTO users (first_name, last_name, email, password) VALUES (%s,%s,%s,%s)",
                       (first_name, last_name, email, hashed_password))
        mysql.connection.commit()
        return jsonify({"message": "User registered successfully!"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# --------------------
# Login
# --------------------
@app.route('/login', methods=['POST'])
def login():
    data = request.json
    email = data['email']
    password = data['password']

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
    # Check if admin
    cursor.execute("SELECT role_id FROM users WHERE user_id=%s", (current_user,))
    role = cursor.fetchone()[0]
    if role != 2:
        return jsonify({"error": "Access denied"}), 403

    data = request.json
    user_id = data['user_id']
    department_id = data.get('department_id')
    job_title_id = data.get('job_title_id')

    cursor.execute("INSERT INTO employees (user_id, department_id, job_title_id, hire_date) VALUES (%s,%s,%s,CURDATE())",
                   (user_id, department_id, job_title_id))
    mysql.connection.commit()
    return jsonify({"message": "Employee added successfully"}), 201

# --------------------
# Attendance
# --------------------
@app.route('/attendance', methods=['POST'])
@jwt_required()
def attendance():
    current_user = get_jwt_identity()
    data = request.json
    employee_id = data['employee_id']
    check_in = data.get('check_in')
    check_out = data.get('check_out')
    status = data.get('status', 'present')

    cursor = mysql.connection.cursor()
    cursor.execute("INSERT INTO attendance (employee_id, attendance_date, check_in, check_out, status) VALUES (%s,CURDATE(),%s,%s,%s)",
                   (employee_id, check_in, check_out, status))
    mysql.connection.commit()
    return jsonify({"message": "Attendance recorded"}), 201

# --------------------
# Request Leave
# --------------------
@app.route('/leave', methods=['POST'])
@jwt_required()
def request_leave():
    current_user = get_jwt_identity()
    data = request.json
    employee_id = data['employee_id']
    leave_type = data['leave_type']
    start_date = data['start_date']
    end_date = data['end_date']

    cursor = mysql.connection.cursor()
    cursor.execute("INSERT INTO leaves (employee_id, leave_type, start_date, end_date) VALUES (%s,%s,%s,%s)",
                   (employee_id, leave_type, start_date, end_date))
    mysql.connection.commit()
    return jsonify({"message": "Leave requested"}), 201

# --------------------
# Run Flask App
# --------------------
if __name__ == "__main__":
    app.run(debug=True)
