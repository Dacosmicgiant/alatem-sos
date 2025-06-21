# app.py - Production Ready with MongoDB Atlas
from flask import Flask, request, jsonify, render_template_string, session, redirect, url_for
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import joblib
import json
import os
from ml_models import HealthOutbreakPredictor, CrimePredictor
import threading
import schedule
import time
import hashlib
from functools import wraps
import uuid

# Conditional imports - works with or without MongoDB
try:
    from pymongo import MongoClient
    from pymongo.errors import ConnectionFailure
    MONGODB_AVAILABLE = True
    print("✅ MongoDB driver available")
except ImportError:
    MONGODB_AVAILABLE = False
    print("⚠️ MongoDB not available, falling back to JSON files")

try:
    from twilio.rest import Client as TwilioClient
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False
    print("⚠️ Twilio not available, SMS disabled")

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("✅ Environment variables loaded")
except ImportError:
    print("⚠️ python-dotenv not installed")

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'alatem-secret-key-change-in-production')

# Database Configuration
USE_MONGODB = MONGODB_AVAILABLE and os.getenv('MONGODB_URI')
DATA_DIR = 'data'

if USE_MONGODB:
    try:
        client = MongoClient(os.getenv('MONGODB_URI'))
        db = client.alatem
        # Test connection
        client.admin.command('ping')
        print("✅ MongoDB Atlas connected successfully!")
        
        # Collections
        users_collection = db.users
        staff_users_collection = db.staff_users
        health_reports_collection = db.health_reports
        crime_reports_collection = db.crime_reports
        sent_alerts_collection = db.sent_alerts
        
        # Create indexes
        users_collection.create_index("phone", unique=True, background=True)
        staff_users_collection.create_index("username", unique=True, background=True)
        
    except Exception as e:
        print(f"❌ MongoDB connection failed: {e}")
        print("📁 Falling back to JSON files")
        USE_MONGODB = False

# JSON fallback setup
if not USE_MONGODB:
    os.makedirs(DATA_DIR, exist_ok=True)
    USERS_FILE = os.path.join(DATA_DIR, 'users.json')
    STAFF_USERS_FILE = os.path.join(DATA_DIR, 'staff_users.json')
    HEALTH_REPORTS_FILE = os.path.join(DATA_DIR, 'health_reports.json')
    CRIME_REPORTS_FILE = os.path.join(DATA_DIR, 'crime_reports.json')
    SENT_ALERTS_FILE = os.path.join(DATA_DIR, 'sent_alerts.json')

# Database abstraction layer
class DatabaseManager:
    def __init__(self):
        self.use_mongodb = USE_MONGODB
    
    def save_user(self, user_data):
        if self.use_mongodb:
            return users_collection.replace_one(
                {"phone": user_data["phone"]}, 
                user_data, 
                upsert=True
            )
        else:
            users = self.load_json_data(USERS_FILE)
            existing_index = next((i for i, u in enumerate(users) if u.get('phone') == user_data['phone']), None)
            if existing_index is not None:
                users[existing_index] = user_data
            else:
                users.append(user_data)
            return self.save_json_data(USERS_FILE, users)
    
    def find_user_by_phone(self, phone):
        if self.use_mongodb:
            return users_collection.find_one({"phone": phone})
        else:
            users = self.load_json_data(USERS_FILE)
            return next((u for u in users if u.get('phone') == phone), None)
    
    def update_user_verified(self, phone):
        if self.use_mongodb:
            return users_collection.update_one(
                {"phone": phone}, 
                {"$set": {"verified": True}}
            )
        else:
            users = self.load_json_data(USERS_FILE)
            user_index = next((i for i, u in enumerate(users) if u.get('phone') == phone), None)
            if user_index is not None:
                users[user_index]['verified'] = True
                return self.save_json_data(USERS_FILE, users)
            return False
    
    def get_users_by_area(self, area, verified_only=True):
        if self.use_mongodb:
            query = {"area": area, "active": True}
            if verified_only:
                query["verified"] = True
            return list(users_collection.find(query))
        else:
            users = self.load_json_data(USERS_FILE)
            return [u for u in users if (
                u.get('area') == area and
                u.get('active', True) and
                (not verified_only or u.get('verified', False))
            )]
    
    def get_area_stats(self):
        if self.use_mongodb:
            pipeline = [
                {"$match": {"verified": True, "active": True}},
                {"$group": {"_id": "$area", "user_count": {"$sum": 1}}},
                {"$sort": {"_id": 1}}
            ]
            return list(users_collection.aggregate(pipeline))
        else:
            users = self.load_json_data(USERS_FILE)
            verified_users = [u for u in users if u.get('verified', False) and u.get('active', True)]
            area_counts = {}
            for user in verified_users:
                area = user.get('area')
                if area:
                    area_counts[area] = area_counts.get(area, 0) + 1
            return [{'_id': area, 'user_count': count} for area, count in sorted(area_counts.items())]
    
    def save_staff_user(self, staff_data):
        if self.use_mongodb:
            return staff_users_collection.insert_one(staff_data)
        else:
            staff_users = self.load_json_data(STAFF_USERS_FILE)
            staff_users.append(staff_data)
            return self.save_json_data(STAFF_USERS_FILE, staff_users)
    
    def find_staff_user(self, username):
        if self.use_mongodb:
            return staff_users_collection.find_one({"username": username, "is_active": True})
        else:
            staff_users = self.load_json_data(STAFF_USERS_FILE)
            return next((u for u in staff_users if u.get('username') == username and u.get('is_active')), None)
    
    def update_staff_login(self, user_id, login_time):
        if self.use_mongodb:
            from bson.objectid import ObjectId
            return staff_users_collection.update_one(
                {"_id": ObjectId(user_id)}, 
                {"$set": {"last_login": login_time}}
            )
        else:
            staff_users = self.load_json_data(STAFF_USERS_FILE)
            user_index = next((i for i, u in enumerate(staff_users) if u.get('id') == user_id), None)
            if user_index is not None:
                staff_users[user_index]['last_login'] = login_time.isoformat()
                return self.save_json_data(STAFF_USERS_FILE, staff_users)
    
    def save_health_report(self, report_data):
        if self.use_mongodb:
            return health_reports_collection.insert_one(report_data)
        else:
            reports = self.load_json_data(HEALTH_REPORTS_FILE)
            reports.append(report_data)
            return self.save_json_data(HEALTH_REPORTS_FILE, reports)
    
    def save_crime_report(self, report_data):
        if self.use_mongodb:
            return crime_reports_collection.insert_one(report_data)
        else:
            reports = self.load_json_data(CRIME_REPORTS_FILE)
            reports.append(report_data)
            return self.save_json_data(CRIME_REPORTS_FILE, reports)
    
    def save_alert(self, alert_data):
        if self.use_mongodb:
            return sent_alerts_collection.insert_one(alert_data)
        else:
            alerts = self.load_json_data(SENT_ALERTS_FILE)
            alerts.append(alert_data)
            return self.save_json_data(SENT_ALERTS_FILE, alerts)
    
    def get_recent_health_reports(self, area, condition, since_date):
        if self.use_mongodb:
            return list(health_reports_collection.find({
                "area": area,
                "condition": condition,
                "timestamp": {"$gte": since_date}
            }))
        else:
            reports = self.load_json_data(HEALTH_REPORTS_FILE)
            result = []
            for report in reports:
                if (report.get('area') == area and 
                    report.get('condition') == condition):
                    try:
                        report_time = datetime.fromisoformat(report['timestamp'].replace('Z', '+00:00'))
                        if report_time >= since_date:
                            result.append(report)
                    except (ValueError, KeyError):
                        continue
            return result
    
    def get_recent_crime_reports(self, area, since_date):
        if self.use_mongodb:
            return crime_reports_collection.count_documents({
                "area": area,
                "timestamp": {"$gte": since_date}
            })
        else:
            reports = self.load_json_data(CRIME_REPORTS_FILE)
            count = 0
            for report in reports:
                if report.get('area') == area:
                    try:
                        report_time = datetime.fromisoformat(report['timestamp'].replace('Z', '+00:00'))
                        if report_time >= since_date:
                            count += 1
                    except (ValueError, KeyError):
                        continue
            return count
    
    def get_stats(self):
        if self.use_mongodb:
            yesterday = datetime.now() - timedelta(days=1)
            return {
                'users': {
                    'total': users_collection.count_documents({}),
                    'verified': users_collection.count_documents({"verified": True}),
                    'active': users_collection.count_documents({"active": True})
                },
                'staff': {
                    'total': staff_users_collection.count_documents({}),
                    'active': staff_users_collection.count_documents({"is_active": True})
                },
                'reports': {
                    'health_reports': health_reports_collection.count_documents({}),
                    'crime_reports': crime_reports_collection.count_documents({}),
                    'alerts_sent': sent_alerts_collection.count_documents({})
                },
                'recent_activity': {
                    'health_reports_24h': health_reports_collection.count_documents({
                        "timestamp": {"$gte": yesterday}
                    }),
                    'crime_reports_24h': crime_reports_collection.count_documents({
                        "timestamp": {"$gte": yesterday}
                    }),
                    'alerts_sent_24h': sent_alerts_collection.count_documents({
                        "timestamp": {"$gte": yesterday}
                    })
                }
            }
        else:
            users = self.load_json_data(USERS_FILE)
            staff_users = self.load_json_data(STAFF_USERS_FILE)
            health_reports = self.load_json_data(HEALTH_REPORTS_FILE)
            crime_reports = self.load_json_data(CRIME_REPORTS_FILE)
            sent_alerts = self.load_json_data(SENT_ALERTS_FILE)
            
            yesterday = datetime.now() - timedelta(days=1)
            recent_health = len([r for r in health_reports if 
                               datetime.fromisoformat(r['timestamp'].replace('Z', '+00:00')) >= yesterday])
            recent_crime = len([r for r in crime_reports if 
                              datetime.fromisoformat(r['timestamp'].replace('Z', '+00:00')) >= yesterday])
            recent_alerts = len([r for r in sent_alerts if 
                               datetime.fromisoformat(r['timestamp'].replace('Z', '+00:00')) >= yesterday])
            
            return {
                'users': {
                    'total': len(users),
                    'verified': len([u for u in users if u.get('verified', False)]),
                    'active': len([u for u in users if u.get('active', True)])
                },
                'staff': {
                    'total': len(staff_users),
                    'active': len([u for u in staff_users if u.get('is_active', True)])
                },
                'reports': {
                    'health_reports': len(health_reports),
                    'crime_reports': len(crime_reports),
                    'alerts_sent': len(sent_alerts)
                },
                'recent_activity': {
                    'health_reports_24h': recent_health,
                    'crime_reports_24h': recent_crime,
                    'alerts_sent_24h': recent_alerts
                }
            }
    
    # JSON file helpers
    def load_json_data(self, filename):
        if os.path.exists(filename):
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return []
        return []
    
    def save_json_data(self, filename, data):
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, default=str)
            return True
        except Exception as e:
            print(f"Error saving to {filename}: {e}")
            return False

# Initialize database manager
db_manager = DatabaseManager()

# Twilio setup
twilio_client = None
TWILIO_PHONE = None

if TWILIO_AVAILABLE:
    try:
        TWILIO_SID = os.getenv('TWILIO_SID')
        TWILIO_TOKEN = os.getenv('TWILIO_TOKEN')
        TWILIO_PHONE = os.getenv('TWILIO_PHONE')
        
        if TWILIO_SID and TWILIO_TOKEN:
            twilio_client = TwilioClient(TWILIO_SID, TWILIO_TOKEN)
            print("✅ Twilio initialized successfully")
        else:
            print("⚠️ Twilio credentials not found")
    except Exception as e:
        print(f"⚠️ Twilio initialization failed: {e}")

# ML models
health_predictor = None
crime_predictor = None

# Authentication helpers
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password, password_hash):
    return hashlib.sha256(password.encode()).hexdigest() == password_hash

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'staff_user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function

def generate_id():
    return str(uuid.uuid4())

def create_default_admin():
    """Create default admin user if none exists"""
    admin = db_manager.find_staff_user('admin')
    if not admin:
        admin_user = {
            "id": generate_id(),
            "username": "admin",
            "password_hash": hash_password("admin123"),
            "full_name": "System Administrator",
            "role": "admin",
            "organization": "Alatem System",
            "is_active": True,
            "created_at": datetime.utcnow().isoformat() if not USE_MONGODB else datetime.utcnow(),
            "last_login": None
        }
        db_manager.save_staff_user(admin_user)
        print("✅ Default admin user created (username: admin, password: admin123)")

def create_demo_users():
    """Create demo users for testing"""
    demo_users = [
        {"name": "Jean Baptiste", "phone": "+50912345001", "area": "CITE_SOLEIL"},
        {"name": "Marie Claire", "phone": "+50912345002", "area": "CITE_SOLEIL"},
        {"name": "Pierre Louis", "phone": "+50912345003", "area": "DELMAS"},
        {"name": "Anne Marie", "phone": "+50912345004", "area": "DELMAS"},
        {"name": "Joseph Michel", "phone": "+50912345005", "area": "TABARRE"},
        {"name": "Rose Antoinette", "phone": "+50912345006", "area": "MARTISSANT"},
    ]
    
    for demo_user in demo_users:
        existing = db_manager.find_user_by_phone(demo_user['phone'])
        if not existing:
            user_data = {
                "id": generate_id(),
                "name": demo_user['name'],
                "phone": demo_user['phone'],
                "area": demo_user['area'],
                "latitude": None,
                "longitude": None,
                "verified": True,
                "active": True,
                "created_at": datetime.utcnow().isoformat() if not USE_MONGODB else datetime.utcnow()
            }
            db_manager.save_user(user_data)
    
    print(f"✅ Demo users created")

def send_sms(phone, message):
    """Send SMS with proper error handling"""
    if not twilio_client or not TWILIO_PHONE:
        print(f"📱 SMS would be sent to {phone}: {message}")
        return False
    
    try:
        twilio_client.messages.create(
            body=message,
            from_=TWILIO_PHONE,
            to=phone
        )
        return True
    except Exception as e:
        print(f"❌ Failed to send SMS to {phone}: {e}")
        return False

# OTP storage
otp_store = {}

# Routes
@app.route('/')
def home():
    stats = db_manager.get_stats()
    return jsonify({
        'app': 'Alatem Health Alert System',
        'version': '4.0 - Production Ready',
        'database': 'MongoDB Atlas' if USE_MONGODB else 'JSON Files (Development)',
        'status': {
            'database': 'connected',
            'mongodb': USE_MONGODB,
            'verified_users': stats['users']['verified'],
            'staff_users': stats['staff']['active'],
            'sms_service': twilio_client is not None
        }
    })

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>Alatem - Staff Login</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
            margin: 0; padding: 0; 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            height: 100vh; display: flex; align-items: center; justify-content: center;
        }
        .login-container {
            background: white; padding: 40px; border-radius: 15px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.2); width: 100%; max-width: 400px;
        }
        .logo { text-align: center; margin-bottom: 30px; }
        .logo h1 { color: #2c3e50; margin: 0; font-size: 28px; }
        .form-group { margin: 20px 0; }
        label { display: block; margin-bottom: 8px; font-weight: 600; color: #2c3e50; }
        input { width: 100%; padding: 12px; border: 2px solid #ddd; border-radius: 8px; font-size: 16px; box-sizing: border-box; }
        input:focus { border-color: #3498db; outline: none; }
        button { width: 100%; background: #3498db; color: white; padding: 14px; border: none; border-radius: 8px; font-size: 16px; font-weight: 600; cursor: pointer; }
        button:hover { background: #2980b9; }
        .error { color: #e74c3c; font-size: 14px; margin-top: 10px; text-align: center; }
        .status { background: #e8f5e8; border-left: 4px solid #27ae60; padding: 10px; margin-bottom: 20px; border-radius: 4px; font-size: 12px; }
        .demo-credentials { background: #ecf0f1; padding: 15px; border-radius: 8px; margin-top: 20px; font-size: 12px; color: #7f8c8d; }
    </style>
</head>
<body>
    <div class="login-container">
        <div class="status">
            ☁️ <strong>Database:</strong> {{ "MongoDB Atlas (Production Ready)" if use_mongodb else "JSON Files (Development)" }}
        </div>
        <div class="logo">
            <h1>🏥 Alatem</h1>
            <p>Health Worker Portal</p>
        </div>
        <form method="POST">
            <div class="form-group">
                <label for="username">Username:</label>
                <input type="text" name="username" id="username" required>
            </div>
            <div class="form-group">
                <label for="password">Password:</label>
                <input type="password" name="password" id="password" required>
            </div>
            <button type="submit">Login</button>
            {% if error %}
            <div class="error">{{ error }}</div>
            {% endif %}
        </form>
        <div class="demo-credentials">
            <strong>Demo Credentials:</strong><br>
            Username: <strong>admin</strong><br>
            Password: <strong>admin123</strong>
        </div>
    </div>
</body>
</html>
        ''', error=request.args.get('error'), use_mongodb=USE_MONGODB)
    
    # Handle POST
    username = request.form['username']
    password = request.form['password']
    
    user = db_manager.find_staff_user(username)
    
    if user and verify_password(password, user['password_hash']):
        if USE_MONGODB:
            session['staff_user_id'] = str(user['_id'])
            db_manager.update_staff_login(user['_id'], datetime.utcnow())
        else:
            session['staff_user_id'] = user['id']
            db_manager.update_staff_login(user['id'], datetime.utcnow())
        
        session['staff_username'] = user['username']
        session['staff_role'] = user['role']
        
        return redirect(url_for('health_worker_interface'))
    
    return redirect(url_for('login', error='Invalid credentials'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/register', methods=['POST'])
def register_user():
    try:
        data = request.json
        name = data.get('name')
        phone = data.get('phone')
        area = data.get('area')
        
        if not all([name, phone, area]):
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400
        
        otp = np.random.randint(100000, 999999)
        
        user_data = {
            "id": generate_id(),
            "name": name,
            "phone": phone,
            "area": area,
            "latitude": data.get('latitude'),
            "longitude": data.get('longitude'),
            "verified": False,
            "active": True,
            "created_at": datetime.utcnow().isoformat() if not USE_MONGODB else datetime.utcnow()
        }
        
        db_manager.save_user(user_data)
        
        message = f"Kòd verifikasyon Alatem: {otp}. Pa pataje kòd sa a ak pèsonn."
        sms_sent = send_sms(phone, message)
        
        otp_store[phone] = {
            'otp': otp,
            'expires': datetime.now() + timedelta(minutes=5)
        }
        
        return jsonify({
            'success': True,
            'message': 'OTP sent successfully' if sms_sent else 'OTP generated (SMS disabled)',
            'debug_otp': otp if not twilio_client else None
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/verify', methods=['POST'])
def verify_otp():
    try:
        data = request.json
        phone = data.get('phone')
        otp = data.get('otp')
        
        stored_otp = otp_store.get(phone)
        
        if (stored_otp and 
            str(stored_otp['otp']) == str(otp) and 
            datetime.now() < stored_otp['expires']):
            
            db_manager.update_user_verified(phone)
            user = db_manager.find_user_by_phone(phone)
            
            if user:
                welcome_msg = f"Byenveni nan Alatem, {user['name']}! Ou ap resevwa alèt sante ak sekirite nan {user['area']}."
                send_sms(phone, welcome_msg)
                del otp_store[phone]
                return jsonify({'verified': True, 'message': 'User verified successfully'})
        
        return jsonify({'verified': False, 'error': 'Invalid or expired OTP'})
        
    except Exception as e:
        return jsonify({'verified': False, 'error': str(e)}), 400

@app.route('/broadcast/areas')
@login_required
def get_broadcast_areas():
    try:
        areas_data = db_manager.get_area_stats()
        areas = [{'area': area['_id'], 'user_count': area['user_count']} for area in areas_data]
        return jsonify({'areas': areas})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/broadcast', methods=['POST'])
@login_required
def broadcast_alert():
    try:
        data = request.json
        alert_type = data.get('alert_type')
        area = data.get('area')
        message = data.get('message')
        condition = data.get('condition')
        crime_type = data.get('crime_type')
        
        if not all([alert_type, area]):
            return jsonify({'success': False, 'error': 'Alert type and area required'}), 400
        
        users = db_manager.get_users_by_area(area, verified_only=True)
        
        if alert_type == 'health' and condition:
            sent_count = send_health_alert_to_users(users, area, condition, 0)
        elif alert_type == 'safety' and crime_type:
            sent_count = send_safety_alert_to_users(users, area, crime_type)
        elif alert_type == 'custom' and message:
            sent_count = send_custom_alert_to_users(users, area, message)
        else:
            return jsonify({'success': False, 'error': 'Invalid alert configuration'}), 400
        
        return jsonify({
            'success': True,
            'message': f'Alert broadcast to {sent_count} users in {area}',
            'recipients_count': sent_count
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

def send_health_alert_to_users(users, area, condition, cases):
    messages = {
        'cholera': f"🚨 ALÈT SANTE: {cases if cases > 0 else 'Ka'} cholera nan {area}. Bwè dlo pwòp, lave men nou. Ale kay doktè si nou gen simptòm.",
        'malnutrition': f"⚠️ ALÈT SANTE: {cases if cases > 0 else 'Ka'} malnitrisyon nan {area}. Chèche manje ak vitamin. Mennen timoun yo kay doktè.",
        'fever': f"🌡️ ALÈT SANTE: {cases if cases > 0 else 'Ka'} lafyèv nan {area}. Rete lakay si nou malad. Bwè dlo anpil.",
        'diarrhea': f"💧 ALÈT SANTE: {cases if cases > 0 else 'Ka'} dyare nan {area}. Bwè dlo pwòp, lave men nou.",
        'respiratory': f"🫁 ALÈT SANTE: {cases if cases > 0 else 'Ka'} pwoblèm respiratwa nan {area}. Rete lakay, evite foul moun."
    }
    
    message = messages.get(condition, f"🚨 ALÈT SANTE: {condition} nan {area}")
    
    sent_count = 0
    for user in users:
        if send_sms(user['phone'], message):
            sent_count += 1
        time.sleep(0.1)
    
    # Log alert
    alert_data = {
        "id": generate_id(),
        "alert_type": "health_outbreak",
        "area": area,
        "message": message,
        "recipients_count": sent_count,
        "timestamp": datetime.utcnow().isoformat() if not USE_MONGODB else datetime.utcnow(),
        "triggered_by": session.get('staff_username', 'system'),
        "staff_user_id": session.get('staff_user_id')
    }
    
    db_manager.save_alert(alert_data)
    return sent_count

def send_safety_alert_to_users(users, area, crime_type):
    safety_messages = {
        'kidnapping': f"🚨 SEKIRITE: Kidnapping nan {area}. Pa mache pou kont nou. Evite kote yo ki izole.",
        'armed_robbery': f"⚠️ SEKIRITE: Volè ak zam nan {area}. Pa montre objè ki gen valè. Mache nan gwoup.",
        'gang_shooting': f"🔫 DANJE: Bandi k ap tire nan {area}. Rete lakay. Pa soti.",
        'street_violence': f"⚠️ SEKIRITE: Vyolans nan lari nan {area}. Evite kote yo ki gen anpil moun.",
        'home_invasion': f"🏠 SEKIRITE: Anvazyòn lakay nan {area}. Asire pòt ak fenèt yo."
    }
    
    message = safety_messages.get(crime_type, f"⚠️ SEKIRITE: Danje nan {area}. Fè atansyon.")
    
    sent_count = 0
    for user in users:
        if send_sms(user['phone'], message):
            sent_count += 1
        time.sleep(0.1)
    
    alert_data = {
        "id": generate_id(),
        "alert_type": "safety_alert",
        "area": area,
        "message": message,
        "recipients_count": sent_count,
        "timestamp": datetime.utcnow().isoformat() if not USE_MONGODB else datetime.utcnow(),
        "triggered_by": session.get('staff_username', 'system'),
        "staff_user_id": session.get('staff_user_id')
    }
    
    db_manager.save_alert(alert_data)
    return sent_count

def send_custom_alert_to_users(users, area, message):
    sent_count = 0
    for user in users:
        if send_sms(user['phone'], message):
            sent_count += 1
        time.sleep(0.1)
    
    alert_data = {
        "id": generate_id(),
        "alert_type": "custom_alert",
        "area": area,
        "message": message,
        "recipients_count": sent_count,
        "timestamp": datetime.utcnow().isoformat() if not USE_MONGODB else datetime.utcnow(),
        "triggered_by": session.get('staff_username', 'system'),
        "staff_user_id": session.get('staff_user_id')
    }
    
    db_manager.save_alert(alert_data)
    return sent_count

@app.route('/health-worker')
@login_required
def health_worker_interface():
    return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>Alatem - Health Worker Dashboard</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center; }
        .header h1 { margin: 0; }
        .logout-btn { background: rgba(255,255,255,0.2); color: white; border: 1px solid rgba(255,255,255,0.3); padding: 8px 16px; border-radius: 5px; text-decoration: none; font-size: 14px; }
        .container { max-width: 1200px; margin: 0 auto; }
        .card { background: white; padding: 25px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); margin-bottom: 20px; }
        .broadcast-section { background: #fff3cd; border: 1px solid #ffeaa7; border-radius: 8px; padding: 20px; }
        .broadcast-controls { display: flex; gap: 10px; flex-wrap: wrap; margin: 15px 0; }
        button { background: #3498db; color: white; padding: 12px 24px; border: none; border-radius: 6px; cursor: pointer; font-size: 16px; font-weight: 600; transition: background 0.3s; margin-right: 10px; margin-bottom: 10px; }
        button:hover { background: #2980b9; }
        button.danger { background: #e74c3c; }
        button.warning { background: #f39c12; }
        select { width: 100%; padding: 12px; border: 2px solid #ddd; border-radius: 6px; font-size: 14px; box-sizing: border-box; margin-bottom: 15px; }
        textarea { width: 100%; padding: 12px; border: 2px solid #ddd; border-radius: 6px; font-size: 14px; box-sizing: border-box; }
        .area-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; margin: 15px 0; }
        .area-card { background: white; padding: 15px; border-radius: 8px; text-align: center; border: 1px solid #ddd; }
        .area-card h4 { margin: 0 0 10px 0; color: #2c3e50; }
        .area-card .count { font-size: 24px; font-weight: bold; color: #3498db; }
        .success { color: #27ae60; font-weight: 600; padding: 15px; margin: 15px 0; border-radius: 6px; background: #eafaf1; }
        .error { color: #e74c3c; font-weight: 600; padding: 15px; margin: 15px 0; border-radius: 6px; background: #ffeaea; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div>
                <h1>🏥 Alatem - Health Worker Dashboard</h1>
                <div>{{ "MongoDB Atlas (Production)" if use_mongodb else "JSON Files (Development)" }}</div>
            </div>
            <a href="/logout" class="logout-btn">Logout</a>
        </div>
        
        <div class="card">
            <div class="broadcast-section">
                <h3>📡 Manual Alert Broadcasting</h3>
                <p>Send immediate alerts to users in specific areas.</p>
                
                <div id="areaStats">
                    <button onclick="loadAreaStats()">Load Area Statistics</button>
                </div>
                
                <label for="broadcast-area">Target Area:</label>
                <select id="broadcast-area" required>
                    <option value="">Select area...</option>
                    <option value="CITE_SOLEIL">Cite Soleil</option>
                    <option value="DELMAS">Delmas</option>
                    <option value="TABARRE">Tabarre</option>
                    <option value="MARTISSANT">Martissant</option>
                    <option value="CARREFOUR">Carrefour</option>
                    <option value="PETIONVILLE">Petionville</option>
                </select>
                
                <div class="broadcast-controls">
                    <h4>Quick Health Alerts:</h4>
                    <button class="danger" onclick="broadcastHealthAlert('cholera')">🚨 Cholera Alert</button>
                    <button class="warning" onclick="broadcastHealthAlert('fever')">🌡️ Fever Alert</button>
                    <button class="warning" onclick="broadcastHealthAlert('diarrhea')">💧 Diarrhea Alert</button>
                </div>
                
                <div class="broadcast-controls">
                    <h4>Quick Safety Alerts:</h4>
                    <button class="danger" onclick="broadcastSafetyAlert('kidnapping')">🚨 Kidnapping Alert</button>
                    <button class="danger" onclick="broadcastSafetyAlert('gang_shooting')">🔫 Gang Violence Alert</button>
                    <button class="warning" onclick="broadcastSafetyAlert('armed_robbery')">⚠️ Armed Robbery Alert</button>
                </div>
                
                <h4>Custom Message:</h4>
                <textarea id="custom-message" placeholder="Enter custom alert message in Haitian Creole..." rows="3" maxlength="160"></textarea>
                <small>Maximum 160 characters (SMS limit)</small>
                <br><br>
                <button onclick="broadcastCustomMessage()">📢 Send Custom Alert</button>
                
                <div id="broadcastResults"></div>
            </div>
        </div>
    </div>
    
    <script>
        function showMessage(message, type = 'success') {
            const alert = document.createElement('div');
            alert.className = type;
            alert.textContent = message;
            const container = document.querySelector('.container');
            container.insertBefore(alert, container.children[1]);
            setTimeout(() => alert.remove(), 5000);
        }
        
        async function loadAreaStats() {
            try {
                const response = await fetch('/broadcast/areas');
                const data = await response.json();
                
                let html = '<div class="area-stats">';
                if (data.areas && data.areas.length > 0) {
                    data.areas.forEach(area => {
                        html += `<div class="area-card">
                            <h4>${area.area}</h4>
                            <div class="count">${area.user_count}</div>
                            <small>verified users</small>
                        </div>`;
                    });
                } else {
                    html += '<p>No verified users found. Register some users first!</p>';
                }
                html += '</div>';
                
                document.getElementById('areaStats').innerHTML = html;
            } catch (error) {
                showMessage('Error loading area statistics: ' + error, 'error');
            }
        }
        
        async function broadcastHealthAlert(condition) {
            const area = document.getElementById('broadcast-area').value;
            if (!area) {
                showMessage('Please select an area first', 'error');
                return;
            }
            
            if (!confirm(`Send ${condition} alert to all users in ${area}?`)) return;
            
            try {
                const response = await fetch('/broadcast', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        alert_type: 'health',
                        area: area,
                        condition: condition
                    })
                });
                const result = await response.json();
                
                if (result.success) {
                    showMessage(`✅ Health alert sent successfully! ${result.message}`);
                } else {
                    showMessage('❌ Error: ' + result.error, 'error');
                }
            } catch (error) {
                showMessage('❌ Error sending alert: ' + error, 'error');
            }
        }
        
        async function broadcastSafetyAlert(crimeType) {
            const area = document.getElementById('broadcast-area').value;
            if (!area) {
                showMessage('Please select an area first', 'error');
                return;
            }
            
            if (!confirm(`Send ${crimeType} alert to all users in ${area}?`)) return;
            
            try {
                const response = await fetch('/broadcast', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        alert_type: 'safety',
                        area: area,
                        crime_type: crimeType
                    })
                });
                const result = await response.json();
                
                if (result.success) {
                    showMessage(`✅ Safety alert sent successfully! ${result.message}`);
                } else {
                    showMessage('❌ Error: ' + result.error, 'error');
                }
            } catch (error) {
                showMessage('❌ Error sending alert: ' + error, 'error');
            }
        }
        
        async function broadcastCustomMessage() {
            const area = document.getElementById('broadcast-area').value;
            const message = document.getElementById('custom-message').value.trim();
            
            if (!area) {
                showMessage('Please select an area', 'error');
                return;
            }
            
            if (!message) {
                showMessage('Please enter a custom message', 'error');
                return;
            }
            
            if (!confirm(`Send custom message to all users in ${area}?\\n\\nMessage: "${message}"`)) return;
            
            try {
                const response = await fetch('/broadcast', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        alert_type: 'custom',
                        area: area,
                        message: message
                    })
                });
                const result = await response.json();
                
                if (result.success) {
                    showMessage(`✅ Custom alert sent successfully! ${result.message}`);
                    document.getElementById('custom-message').value = '';
                } else {
                    showMessage('❌ Error: ' + result.error, 'error');
                }
            } catch (error) {
                showMessage('❌ Error sending custom alert: ' + error, 'error');
            }
        }
        
        // Auto-load area stats on page load
        document.addEventListener('DOMContentLoaded', function() {
            loadAreaStats();
        });
    </script>
</body>
</html>
    ''', use_mongodb=USE_MONGODB)

@app.route('/stats')
def get_stats():
    try:
        stats = db_manager.get_stats()
        stats['database'] = 'MongoDB Atlas' if USE_MONGODB else 'JSON Files'
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

def ensure_directories():
    directories = ['ml_models', 'dataset', DATA_DIR]
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)

def load_ml_models():
    global health_predictor, crime_predictor
    ensure_directories()
    
    try:
        health_predictor = HealthOutbreakPredictor()
        crime_predictor = CrimePredictor()
        
        # Try to load models if they exist
        model_files = ['outbreak_classifier.pkl', 'cases_regressor.pkl', 'label_encoders.pkl', 'scaler.pkl', 'feature_cols.pkl']
        model_paths = [os.path.join('ml_models', f) for f in model_files]
        
        if all(os.path.exists(path) for path in model_paths):
            health_predictor.outbreak_classifier = joblib.load(model_paths[0])
            health_predictor.cases_regressor = joblib.load(model_paths[1])
            health_predictor.label_encoders = joblib.load(model_paths[2])
            health_predictor.scaler = joblib.load(model_paths[3])
            health_predictor.feature_cols = joblib.load(model_paths[4])
            health_predictor.is_trained = True
            print("✅ Health models loaded successfully!")
        else:
            print("⚠️ Health model files not found. Run 'python ml_models.py' to train models first.")
            
    except Exception as e:
        print(f"❌ Error loading models: {e}")

if __name__ == '__main__':
    print(f"🚀 Starting Alatem Health Alert System...")
    print(f"📊 Database: {'MongoDB Atlas' if USE_MONGODB else 'JSON Files'}")
    
    ensure_directories()
    create_default_admin()
    create_demo_users()
    load_ml_models()
    
    print("\n" + "="*70)
    print("🏥 ALATEM HEALTH ALERT SYSTEM v4.0 - PRODUCTION READY")
    print("="*70)
    print("🔐 Staff Login: http://localhost:5000/login")
    print("📱 Dashboard: http://localhost:5000/health-worker")
    print("🔗 API: http://localhost:5000/")
    print("📊 Stats: http://localhost:5000/stats")
    print("="*70)
    print(f"💾 Database: {'MongoDB Atlas (Production)' if USE_MONGODB else 'JSON Files (Development)'}")
    print("🔑 Login: admin / admin123")
    print("="*70)
    
    app.run(debug=True, host='0.0.0.0', port=5000)