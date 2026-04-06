import os
import csv
from io import StringIO
from flask import Flask, render_template, redirect, url_for, request, flash, send_file, Response
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Report, Attendance
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev-secret-key-12345'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Routes ---

@app.route('/')
def index():
    recent_reports = Report.query.order_by(Report.date_reported.desc()).limit(5).all()
    return render_template('index.html', reports=recent_reports)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        if user:
            flash('Email already exists.', 'error')
            return redirect(url_for('signup'))
        
        new_user = User(
            username=username,
            email=email,
            password=generate_password_hash(password, method='scrypt')
        )
        db.session.add(new_user)
        db.session.commit()
        
        flash('Account created! Please log in.', 'success')
        return redirect(url_for('login'))
        
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Login failed. Check your email and password.', 'error')
            
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/reports', methods=['GET', 'POST'])
@login_required
def reports():
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        location = request.form.get('location')
        severity = request.form.get('severity')
        disaster_type = request.form.get('disaster_type')
        
        new_report = Report(
            title=title,
            description=description,
            location=location,
            severity=severity,
            disaster_type=disaster_type,
            user_id=current_user.id
        )
        db.session.add(new_report)
        db.session.commit()
        flash('Report submitted successfully!', 'success')
        return redirect(url_for('reports'))
        
    all_reports = Report.query.order_by(Report.date_reported.desc()).all()
    return render_template('reports.html', reports=all_reports)

@app.route('/attendance', methods=['GET', 'POST'])
@login_required
def attendance():
    if request.method == 'POST':
        status = request.form.get('status')
        
        # Check if record already exists
        att_record = Attendance.query.filter_by(user_id=current_user.id).first()
        if att_record:
            att_record.status = status
            att_record.last_updated = datetime.utcnow()
        else:
            new_att = Attendance(user_id=current_user.id, status=status)
            db.session.add(new_att)
        
        db.session.commit()
        flash('Attendance status updated!', 'success')
        return redirect(url_for('attendance'))
        
    all_attendance = Attendance.query.all()
    return render_template('attendance.html', attendance_list=all_attendance)

@app.route('/download/reports')
@login_required
def download_reports():
    reports = Report.query.all()
    
    def generate():
        data = StringIO()
        writer = csv.writer(data)
        writer.writerow(['ID', 'Title', 'Type', 'Location', 'Severity', 'Date Reported'])
        yield data.getvalue()
        data.truncate(0)
        data.seek(0)
        
        for r in reports:
            writer.writerow([r.id, r.title, r.disaster_type, r.location, r.severity, r.date_reported])
            yield data.getvalue()
            data.truncate(0)
            data.seek(0)

    response = Response(generate(), mimetype='text/csv')
    response.headers.set('Content-Disposition', 'attachment', filename='disaster_reports.csv')
    return response

# --- Database Initialization ---
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)
