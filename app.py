import os
import csv
from io import StringIO
from flask import Flask, render_template, redirect, url_for, request, flash, send_file, Response, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Report, Attendance, ChatMessage, TrainingEvent, TrainingAdmission
from datetime import datetime
import google.generativeai as genai
import requests
import xml.etree.ElementTree as ET
import time
import api_config

# Initialize Gemini AI from the external config file to prevent hardcoded leaks
genai.configure(api_key=api_config.GEMINI_API_KEY)

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
app.secret_key = 'super_secret_key_for_development'

# --- Fallback Database Logic ---
# Defaults to your local SQLite file, but upgrades to PostgreSQL if deployed to a cloud server!
database_url = os.environ.get('DATABASE_URL', 'sqlite:///database.db')
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url

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
        
        user_by_email = User.query.filter_by(email=email).first()
        if user_by_email:
            flash('Email already exists.', 'error')
            return redirect(url_for('signup'))
            
        user_by_username = User.query.filter_by(username=username).first()
        if user_by_username:
            flash('Username is already taken. Please choose another one.', 'error')
            return redirect(url_for('signup'))
        
        # Determine role based on email domain
        role = 'government' if email.lower().endswith('@gov.in') else 'citizen'
        
        new_user = User(
            username=username,
            email=email,
            password=generate_password_hash(password, method='scrypt'),
            role=role
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
        if not current_user.is_authenticated or current_user.role != 'government':
            flash('Access denied. Only government officials can manage training events.', 'error')
            return redirect(url_for('training'))
        
        title = request.form.get('title')
        description = request.form.get('description')
        location = request.form.get('location')
        event_type = request.form.get('event_type')
        status = request.form.get('status')
        start_date_str = request.form.get('start_date')
        end_date_str = request.form.get('end_date')
        participants = request.form.get('participants', 0, type=int)
        latitude = request.form.get('latitude', type=float)
        longitude = request.form.get('longitude', type=float)
        
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
            latitude=latitude,
            longitude=longitude,
            user_id=current_user.id
        )
        db.session.add(new_event)
        db.session.commit()
        flash('Training event added successfully!', 'success')
        return redirect(url_for('training'))
    
    # Seed sample data if empty
    if TrainingEvent.query.count() == 0:
        _seed_training_data()
    
    completed = TrainingEvent.query.filter_by(status='completed').order_by(TrainingEvent.start_date.desc()).all()
    ongoing = TrainingEvent.query.filter_by(status='ongoing').order_by(TrainingEvent.start_date.desc()).all()
    upcoming = TrainingEvent.query.filter_by(status='upcoming').order_by(TrainingEvent.start_date.asc()).all()
    
    return render_template('training.html', completed=completed, ongoing=ongoing, upcoming=upcoming)

@app.route('/api/training-events')
def api_training_events():
    events = TrainingEvent.query.all()
    result = []
    for e in events:
        if e.latitude and e.longitude:
            result.append({
                'id': e.id,
                'title': e.title,
                'location': e.location,
                'event_type': e.event_type,
                'status': e.status,
                'start_date': e.start_date.strftime('%b %d, %Y'),
                'participants': e.participants,
                'lat': e.latitude,
                'lng': e.longitude,
                'description': e.description or ''
            })
    return {'events': result}

@app.route('/admissions')
@login_required
def admissions():
    if current_user.role != 'government':
        flash('Access denied. Admissions board is for official use only.', 'error')
        return redirect(url_for('index'))
    
    all_admissions = TrainingAdmission.query.order_by(TrainingAdmission.admitted_at.desc()).all()
    return render_template('admissions.html', admissions=all_admissions)

@app.route('/api/mark-attendance', methods=['POST'])
@login_required
def mark_attendance():
    data = request.get_json()
    qr_data = data.get('qr_data') # Expected format: "CAMP_ID:123"
    
    if not qr_data or not qr_data.startswith('CAMP_ID:'):
        return {'success': False, 'message': 'Invalid QR Code format.'}, 400
    
    try:
        event_id = int(qr_data.split(':')[1])
        event = TrainingEvent.query.get(event_id)
        
        if not event:
            return {'success': False, 'message': 'Training camp not found.'}, 404
            
        # Check if already admitted
        existing = TrainingAdmission.query.filter_by(user_id=current_user.id, training_event_id=event_id).first()
        if existing:
            return {'success': False, 'message': 'You have already been admitted to this camp.'}
            
        new_admission = TrainingAdmission(user_id=current_user.id, training_event_id=event_id)
        db.session.add(new_admission)
        db.session.commit()
        
        return {'success': True, 'message': f'Successfully admitted to {event.title}!'}
        
    except Exception as e:
        return {'success': False, 'message': str(e)}, 500

@app.route('/api/sync/reports', methods=['POST'])
@login_required
def sync_reports_api():
    data = request.get_json()
    new_report = Report(
        title=data.get('title'),
        description=data.get('description'),
        location=data.get('location'),
        severity=data.get('severity'),
        disaster_type=data.get('disaster_type'),
        user_id=current_user.id
    )
    db.session.add(new_report)
    db.session.commit()
    return {'success': True}

@app.route('/api/sync/attendance', methods=['POST'])
@login_required
def sync_attendance_api():
    data = request.get_json()
    status = data.get('status')
    att_record = Attendance.query.filter_by(user_id=current_user.id).first()
    if att_record:
        att_record.status = status
        att_record.last_updated = datetime.utcnow()
    else:
        new_att = Attendance(user_id=current_user.id, status=status)
        db.session.add(new_att)
    db.session.commit()
    db.session.commit()
    return {'success': True}

# Simple in-memory cache to prevent spamming GDACS API
_gdacs_cache = {
    'data': [],
    'last_fetched': 0
}

def fetch_gdacs_india_alerts():
    global _gdacs_cache
    current_time = time.time()
    
    # Cache for 15 minutes (900 seconds)
    if current_time - _gdacs_cache['last_fetched'] < 900 and _gdacs_cache['data']:
        return _gdacs_cache['data']
        
    alerts = []
    try:
        # Fetch GDACS 7-day RSS feed
        response = requests.get('https://www.gdacs.org/xml/rss_7d.xml', timeout=5)
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            for item in root.findall('.//item'):
                title = item.find('title')
                desc = item.find('description')
                pub_date = item.find('pubDate')
                
                title_text = title.text if title is not None else ""
                desc_text = desc.text if desc is not None else ""
                
                # Filter strictly for India
                if 'India' in title_text or 'India' in desc_text:
                    alerts.append({
                        'type': 'gdacs_alert',
                        'title': title_text,
                        'description': desc_text[:120] + '...' if len(desc_text) > 120 else desc_text,
                        'date': pub_date.text if pub_date is not None else "",
                        'severity': 'high' if 'Orange' in desc_text or 'Red' in desc_text else 'medium'
                    })
                    
        _gdacs_cache['data'] = alerts[:5]
        _gdacs_cache['last_fetched'] = current_time
        return _gdacs_cache['data']
    except Exception as e:
        print(f"Error fetching GDACS: {e}")
        return _gdacs_cache['data']

@app.route('/api/notifications')
@login_required
def get_notifications():
    # 1. Fetch GDACS India alerts
    external_alerts = fetch_gdacs_india_alerts()
    
    # 2. Fetch recent Training Camps added
    recent_camps = TrainingEvent.query.order_by(TrainingEvent.id.desc()).limit(5).all()
    
    notifications = []
    
    # Add external alerts
    for alert in external_alerts:
        notifications.append({
            'id': 'ext_' + str(hash(alert['title'])),
            'type': 'ext_alert',
            'title': "⚠️ " + alert['title'],
            'body': alert['description'],
            'time_str': alert['date'],
            'icon': 'fa-triangle-exclamation'
        })
        
    # Add internal camp alerts
    for camp in recent_camps:
        notifications.append({
            'id': f'camp_{camp.id}',
            'type': 'int_camp',
            'title': f"New Camp: {camp.title}",
            'body': f"A new {camp.event_type} drill has been added at {camp.location}. Status: {camp.status.upper()}",
            'time_str': camp.start_date.strftime('%b %d, %Y'),
            'icon': 'fa-campground'
        })
        
    return {'notifications': notifications}

def _seed_training_data():
    """Seeds realistic demo training events with coordinates across India."""
    samples = [
        TrainingEvent(title='Fire Safety Drill', location='Delhi Public School, Dwarka', event_type='Fire Drill',
                      status='completed', start_date=datetime(2026, 3, 15, 10, 0), participants=120,
                      latitude=28.5921, longitude=77.0460, user_id=0),
        TrainingEvent(title='Earthquake Response Training', location='IIT Bombay Campus', event_type='Earthquake Drill',
                      status='completed', start_date=datetime(2026, 3, 20, 9, 0), participants=250,
                      latitude=19.1334, longitude=72.9133, user_id=0),
        TrainingEvent(title='Flood Evacuation Workshop', location='Patna Municipal Corp', event_type='Flood Preparedness',
                      status='completed', start_date=datetime(2026, 3, 25, 11, 0), participants=85,
                      latitude=25.6093, longitude=85.1376, user_id=0),
        TrainingEvent(title='Community First Aid Camp', location='Jaipur City Hospital', event_type='First Aid Training',
                      status='ongoing', start_date=datetime(2026, 4, 5, 8, 0), participants=65,
                      latitude=26.9124, longitude=75.7873, user_id=0),
        TrainingEvent(title='School Evacuation Drill', location='Kendriya Vidyalaya, Chennai', event_type='Evacuation Drill',
                      status='ongoing', start_date=datetime(2026, 4, 4, 10, 30), participants=180,
                      latitude=13.0827, longitude=80.2707, user_id=0),
        TrainingEvent(title='Industrial Fire Response', location='Sector 17 Industrial Area, Chandigarh', event_type='Fire Drill',
                      status='ongoing', start_date=datetime(2026, 4, 6, 14, 0), participants=45,
                      latitude=30.7415, longitude=76.7682, user_id=0),
        TrainingEvent(title='Cyclone Preparedness Drive', location='Visakhapatnam Port Area', event_type='Flood Preparedness',
                      status='upcoming', start_date=datetime(2026, 4, 15, 9, 0), participants=200,
                      latitude=17.6868, longitude=83.2185, user_id=0),
        TrainingEvent(title='Search & Rescue Mock Drill', location='Uttarakhand Mountain Institute', event_type='Search & Rescue',
                      status='upcoming', start_date=datetime(2026, 4, 20, 7, 0), participants=60,
                      latitude=30.0869, longitude=79.3239, user_id=0),
        TrainingEvent(title='Hospital Emergency Protocol', location='AIIMS New Delhi', event_type='First Aid Training',
                      status='upcoming', start_date=datetime(2026, 4, 25, 10, 0), participants=150,
                      latitude=28.5672, longitude=77.2100, user_id=0),
        TrainingEvent(title='Tsunami Alert Workshop', location='Kochi Naval Base', event_type='Flood Preparedness',
                      status='upcoming', start_date=datetime(2026, 5, 1, 9, 0), participants=90,
                      latitude=9.9312, longitude=76.2673, user_id=0),
    ]
    for s in samples:
        db.session.add(s)
    db.session.commit()

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

@app.route('/download/admissions')
@login_required
def download_admissions():
    if current_user.role != 'government':
        flash('Unauthorized. Only government officials can download admission data.', 'error')
        return redirect(url_for('index'))
    
    admissions = TrainingAdmission.query.order_by(TrainingAdmission.admitted_at.desc()).all()
    
    def generate():
        data = StringIO()
        writer = csv.writer(data)
        writer.writerow(['Admission ID', 'Trainee Username', 'Trainee Role', 'Camp Title', 'Camp Location', 'Admitted At (UTC)'])
        yield data.getvalue()
        data.truncate(0)
        data.seek(0)
        
        for a in admissions:
            writer.writerow([
                a.id, 
                a.user.username, 
                a.user.role, 
                a.event.title if a.event else 'Unknown', 
                a.event.location if a.event else 'Unknown', 
                a.admitted_at.strftime('%Y-%m-%d %H:%M:%S')
            ])
            yield data.getvalue()
            data.truncate(0)
            data.seek(0)

    response = Response(generate(), mimetype='text/csv')
    response.headers.set('Content-Disposition', 'attachment', filename='training_admissions.csv')
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
