import os
import csv
from io import StringIO
from flask import Flask, render_template, redirect, url_for, request, flash, send_file, Response, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Report, Attendance, ChatMessage, TrainingEvent
from datetime import datetime
import google.generativeai as genai

# --- Gemini Configuration ---
genai.configure(api_key="AIzaSyBU9wswRSU3DuN0zZAXWjLEPNZM5hw9wlU")

# System instruction to restrict the AI scope
SYSTEM_INSTRUCTION = """
You are the SAFESTEP Assistant, an AI expert in disaster management and the features of our platform. 
Your task is to help users with disaster-related questions (e.g., 'What to do in a flood?') and platform-related queries (e.g., 'How to report an incident?').

STRICT RULES:
1. ONLY answer questions related to disasters, emergency management, safety tips, or the SAFESTEP platform features.
2. If a user asks something unrelated (e.g., general knowledge, jokes, translations, programming, celebs), politely decline and tell them you are only specialized in SAFESTEP and Disaster Management.
3. Keep your answers professional, concise, and helpful.
"""

model = genai.GenerativeModel(
    model_name="gemini-2.5-flash",
    system_instruction=SYSTEM_INSTRUCTION
)

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
def reports():
    if request.method == 'POST':
        if not current_user.is_authenticated:
            flash('Please log in to submit a report.', 'error')
            return redirect(url_for('login'))
        
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
def attendance():
    if request.method == 'POST':
        if not current_user.is_authenticated:
            flash('Please log in to update your status.', 'error')
            return redirect(url_for('login'))
        
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

@app.route('/training', methods=['GET', 'POST'])
def training():
    if request.method == 'POST':
        if not current_user.is_authenticated:
            flash('Please log in to add a training event.', 'error')
            return redirect(url_for('login'))
        
        title = request.form.get('title')
        description = request.form.get('description')
        location = request.form.get('location')
        event_type = request.form.get('event_type')
        status = request.form.get('status')
        start_date_str = request.form.get('start_date')
        end_date_str = request.form.get('end_date')
        participants = request.form.get('participants', 0, type=int)
        
        start_date = datetime.strptime(start_date_str, '%Y-%m-%dT%H:%M') if start_date_str else datetime.utcnow()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%dT%H:%M') if end_date_str else None
        
        new_event = TrainingEvent(
            title=title,
            description=description,
            location=location,
            event_type=event_type,
            status=status,
            start_date=start_date,
            end_date=end_date,
            participants=participants,
            user_id=current_user.id
        )
        db.session.add(new_event)
        db.session.commit()
        flash('Training event added successfully!', 'success')
        return redirect(url_for('training'))
    
    completed = TrainingEvent.query.filter_by(status='completed').order_by(TrainingEvent.start_date.desc()).all()
    ongoing = TrainingEvent.query.filter_by(status='ongoing').order_by(TrainingEvent.start_date.desc()).all()
    upcoming = TrainingEvent.query.filter_by(status='upcoming').order_by(TrainingEvent.start_date.asc()).all()
    
    return render_template('training.html', completed=completed, ongoing=ongoing, upcoming=upcoming)

@app.route('/download/reports')
def download_reports():
    if not current_user.is_authenticated:
        flash('Unauthorized. Please log in to download reports.', 'error')
        return redirect(url_for('login'))
    
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

@app.route('/chat', methods=['POST'])
def chat():
    user_message = request.json.get('message')
    if not user_message:
        return {"error": "No message provided"}, 400

    chat_session_history = []
    
    if current_user.is_authenticated:
        # Save user message to DB
        new_user_msg = ChatMessage(user_id=current_user.id, role='user', content=user_message)
        db.session.add(new_user_msg)
        
        # Fetch conversation history for this user
        history = ChatMessage.query.filter_by(user_id=current_user.id).order_by(ChatMessage.timestamp.asc()).all()
        for msg in history:
            chat_session_history.append({"role": msg.role, "parts": [msg.content]})
    else:
        # Guest logic using Flask session
        if 'chat_history' not in session:
            session['chat_history'] = []
        
        session['chat_history'].append({"role": "user", "parts": [user_message]})
        chat_session_history = session['chat_history']

    try:
        # Start a chat session with history
        chat_session = model.start_chat(history=chat_session_history[:-1]) 
        response = chat_session.send_message(user_message)
        bot_response = response.text
        
        if current_user.is_authenticated:
            # Save bot response to DB
            new_bot_msg = ChatMessage(user_id=current_user.id, role='model', content=bot_response)
            db.session.add(new_bot_msg)
            db.session.commit()
        else:
            # Save bot response to session
            session['chat_history'].append({"role": "model", "parts": [bot_response]})
            session.modified = True 
        
        return {"response": bot_response}
    except Exception as e:
        if current_user.is_authenticated:
            db.session.rollback()
        return {"error": str(e)}, 500

@app.route('/chat/history', methods=['GET'])
def chat_history():
    if current_user.is_authenticated:
        messages = ChatMessage.query.filter_by(user_id=current_user.id).order_by(ChatMessage.timestamp.asc()).all()
        return {"history": [{"role": m.role, "content": m.content} for m in messages]}
    else:
        # Format session history for frontend
        guest_history = session.get('chat_history', [])
        formatted_history = []
        for msg in guest_history:
            formatted_history.append({
                "role": msg['role'],
                "content": msg['parts'][0]
            })
        return {"history": formatted_history}

@app.route('/chat/clear', methods=['POST'])
def clear_chat():
    if current_user.is_authenticated:
        try:
            ChatMessage.query.filter_by(user_id=current_user.id).delete()
            db.session.commit()
            return {"success": True}
        except Exception as e:
            db.session.rollback()
            return {"error": str(e)}, 500
    else:
        session.pop('chat_history', None)
        return {"success": True}
    try:
        ChatMessage.query.filter_by(user_id=current_user.id).delete()
        db.session.commit()
        return {"success": True}
    except Exception as e:
        db.session.rollback()
        return {"error": str(e)}, 500

# --- Database Initialization ---
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)
