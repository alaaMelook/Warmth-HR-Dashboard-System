from flask import Flask
from user import user_bp

app = Flask(__name__)
app.secret_key = "dev-secret-key"

app.register_blueprint(user_bp)

@app.route("/")
def index():
    return "Employee Portal is running ✔"

if __name__ == "__main__":
    app.run(debug=True)