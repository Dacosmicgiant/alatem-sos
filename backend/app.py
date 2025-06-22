# app.py - Enhanced with ML Predictions & Smart Alerts
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

# Add CORS support for frontend
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

@app.route('/test')
def test_connection():
    """Test endpoint for frontend to verify backend connectivity"""
    return jsonify({
        'status': 'success',
        'message': 'Backend is running!',
        'version': '5.0 - ML Enhanced',
        'timestamp': datetime.utcnow().isoformat(),
        'features': {
            'database': USE_MONGODB,
            'ml_models': health_predictor is not None and health_predictor.is_trained,
            'sms_service': twilio_client is not None,
            'demo_data': True
        }
    })

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
        predictions_collection = db.predictions  # New collection for ML predictions
        
        # Create indexes
        users_collection.create_index("phone", unique=True, background=True)
        staff_users_collection.create_index("username", unique=True, background=True)
        predictions_collection.create_index([("area", 1), ("date", -1)], background=True)
        
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
    PREDICTIONS_FILE = os.path.join(DATA_DIR, 'predictions.json')

# Database abstraction layer (keeping existing methods, adding prediction methods)
class DatabaseManager:
    def __init__(self):
        self.use_mongodb = USE_MONGODB
    
    # [Previous methods remain the same...]
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
    
    # NEW: Prediction storage methods
    def save_prediction(self, prediction_data):
        if self.use_mongodb:
            return predictions_collection.replace_one(
                {"area": prediction_data["area"], "date": prediction_data["date"], "type": prediction_data["type"]},
                prediction_data,
                upsert=True
            )
        else:
            predictions = self.load_json_data(PREDICTIONS_FILE)
            # Remove existing prediction for same area/date/type
            predictions = [p for p in predictions if not (
                p.get('area') == prediction_data['area'] and 
                p.get('date') == prediction_data['date'] and
                p.get('type') == prediction_data['type']
            )]
            predictions.append(prediction_data)
            return self.save_json_data(PREDICTIONS_FILE, predictions)
    
    def get_latest_predictions(self, area=None, limit=10):
        if self.use_mongodb:
            query = {}
            if area:
                query["area"] = area
            return list(predictions_collection.find(query).sort("timestamp", -1).limit(limit))
        else:
            predictions = self.load_json_data(PREDICTIONS_FILE)
            if area:
                predictions = [p for p in predictions if p.get('area') == area]
            predictions.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            return predictions[:limit]
    
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
                    'alerts_sent': sent_alerts_collection.count_documents({}),
                    'predictions': predictions_collection.count_documents({})
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
                    }),
                    'predictions_24h': predictions_collection.count_documents({
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
            predictions = self.load_json_data(PREDICTIONS_FILE)
            
            yesterday = datetime.now() - timedelta(days=1)
            recent_health = len([r for r in health_reports if 
                               datetime.fromisoformat(r['timestamp'].replace('Z', '+00:00')) >= yesterday])
            recent_crime = len([r for r in crime_reports if 
                              datetime.fromisoformat(r['timestamp'].replace('Z', '+00:00')) >= yesterday])
            recent_alerts = len([r for r in sent_alerts if 
                               datetime.fromisoformat(r['timestamp'].replace('Z', '+00:00')) >= yesterday])
            recent_predictions = len([r for r in predictions if 
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
                    'alerts_sent': len(sent_alerts),
                    'predictions': len(predictions)
                },
                'recent_activity': {
                    'health_reports_24h': recent_health,
                    'crime_reports_24h': recent_crime,
                    'alerts_sent_24h': recent_alerts,
                    'predictions_24h': recent_predictions
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

# ML models - Enhanced initialization
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

def create_demo_alert_history():
    """Create demo alert history for testing"""
    try:
        # Check if we already have alerts
        if USE_MONGODB:
            existing_count = sent_alerts_collection.count_documents({})
        else:
            existing_alerts = db_manager.load_json_data(SENT_ALERTS_FILE)
            existing_count = len(existing_alerts)
        
        if existing_count > 0:
            return  # Already have data
        
        areas = ['CITE_SOLEIL', 'DELMAS', 'TABARRE', 'MARTISSANT', 'CARREFOUR', 'PETIONVILLE']
        conditions = ['cholera', 'fever', 'diarrhea', 'malnutrition', 'respiratory']
        crime_types = ['kidnapping', 'armed_robbery', 'gang_shooting', 'street_violence']
        
        demo_alerts = []
        
        # Create alerts for the past 30 days
        for days_ago in range(30):
            alert_date = datetime.utcnow() - timedelta(days=days_ago)
            
            # 1-3 alerts per day
            for _ in range(np.random.randint(1, 4)):
                area = np.random.choice(areas)
                alert_type = np.random.choice(['health_outbreak', 'safety_alert', 'custom_alert'], p=[0.6, 0.3, 0.1])
                
                if alert_type == 'health_outbreak':
                    condition = np.random.choice(conditions)
                    cases = np.random.randint(5, 50)
                    
                    messages = {
                        'cholera': f"🚨 ALÈT SANTE: {cases} ka cholera nan {area}. Bwè dlo pwòp, lave men nou.",
                        'fever': f"🌡️ ALÈT SANTE: {cases} ka lafyèv nan {area}. Rete lakay si nou malad.",
                        'diarrhea': f"💧 ALÈT SANTE: {cases} ka dyare nan {area}. Bwè dlo pwòp.",
                        'malnutrition': f"⚠️ ALÈT SANTE: {cases} ka malnitrisyon nan {area}. Chèche manje ak vitamin.",
                        'respiratory': f"🫁 ALÈT SANTE: {cases} ka pwoblèm respiratwa nan {area}. Rete lakay."
                    }
                    
                    alert_data = {
                        "id": generate_id(),
                        "alert_type": "health_outbreak",
                        "area": area,
                        "condition": condition,
                        "cases": cases,
                        "message": messages.get(condition, f"ALÈT SANTE: {condition} nan {area}"),
                        "recipients_count": np.random.randint(50, 200),
                        "timestamp": alert_date.isoformat() if not USE_MONGODB else alert_date,
                        "triggered_by": np.random.choice(['admin', 'health_worker', 'ml_system'], p=[0.5, 0.3, 0.2]),
                        "staff_user_id": "demo_user_id",
                        "is_ml_triggered": np.random.choice([True, False], p=[0.2, 0.8])
                    }
                    
                elif alert_type == 'safety_alert':
                    crime_type = np.random.choice(crime_types)
                    
                    safety_messages = {
                        'kidnapping': f"🚨 SEKIRITE: Kidnapping nan {area}. Pa mache pou kont nou.",
                        'armed_robbery': f"⚠️ SEKIRITE: Volè ak zam nan {area}. Pa montre objè ki gen valè.",
                        'gang_shooting': f"🔫 DANJE: Bandi k ap tire nan {area}. Rete lakay.",
                        'street_violence': f"⚠️ SEKIRITE: Vyolans nan lari nan {area}. Fè atansyon."
                    }
                    
                    alert_data = {
                        "id": generate_id(),
                        "alert_type": "safety_alert",
                        "area": area,
                        "crime_type": crime_type,
                        "message": safety_messages.get(crime_type, f"SEKIRITE: {crime_type} nan {area}"),
                        "recipients_count": np.random.randint(50, 200),
                        "timestamp": alert_date.isoformat() if not USE_MONGODB else alert_date,
                        "triggered_by": np.random.choice(['admin', 'health_worker'], p=[0.6, 0.4]),
                        "staff_user_id": "demo_user_id"
                    }
                    
                else:  # custom_alert
                    custom_messages = [
                        f"ℹ️ ENFÒMASYON: Vaksinasyon gratis nan {area} jodi a 9h-4h.",
                        f"📢 AVIS: Distribisyon dlo pwòp nan {area} depi 8h.",
                        f"🏥 ENFÒMASYON: Klinik mobil nan {area} pou konsèy sante.",
                        f"📚 AVIS: Sesyon edikasyon sante nan {area} nan 2h."
                    ]
                    
                    alert_data = {
                        "id": generate_id(),
                        "alert_type": "custom_alert",
                        "area": area,
                        "message": np.random.choice(custom_messages),
                        "recipients_count": np.random.randint(50, 200),
                        "timestamp": alert_date.isoformat() if not USE_MONGODB else alert_date,
                        "triggered_by": np.random.choice(['admin', 'health_worker'], p=[0.7, 0.3]),
                        "staff_user_id": "demo_user_id"
                    }
                
                demo_alerts.append(alert_data)
        
        # Save demo alerts
        for alert in demo_alerts:
            db_manager.save_alert(alert)
        
        print(f"✅ Created {len(demo_alerts)} demo alerts for testing")
        
    except Exception as e:
        print(f"⚠️ Error creating demo alerts: {e}")

def create_demo_predictions():
    """Create demo prediction history for testing"""
    try:
        # Check if we already have predictions
        if USE_MONGODB:
            existing_count = predictions_collection.count_documents({})
        else:
            existing_predictions = db_manager.load_json_data(PREDICTIONS_FILE)
            existing_count = len(existing_predictions)
        
        if existing_count > 5:  # Allow some existing predictions
            return
        
        areas = ['CITE_SOLEIL', 'DELMAS', 'TABARRE', 'MARTISSANT']
        conditions = ['cholera', 'fever', 'diarrhea', 'malnutrition']
        
        # Create predictions for the past 7 days
        for days_ago in range(7):
            pred_date = datetime.utcnow() - timedelta(days=days_ago)
            
            for area in areas:
                for condition in conditions:
                    # Generate realistic predictions
                    predictions = []
                    for day_ahead in range(1, 8):  # 7-day forecast
                        future_date = pred_date + timedelta(days=day_ahead)
                        probability = np.random.uniform(0.1, 0.9)
                        predicted_cases = int(np.random.exponential(10))
                        
                        risk_level = 'HIGH' if probability > 0.7 else 'MEDIUM' if probability > 0.4 else 'LOW'
                        
                        predictions.append({
                            'date': future_date.strftime('%Y-%m-%d'),
                            'outbreak_probability': probability,
                            'predicted_cases': predicted_cases,
                            'risk_level': risk_level
                        })
                    
                    prediction_data = {
                        "id": generate_id(),
                        "area": area,
                        "condition": condition,
                        "type": "health",
                        "date": pred_date.strftime('%Y-%m-%d'),
                        "predictions": predictions,
                        "timestamp": pred_date.isoformat() if not USE_MONGODB else pred_date,
                        "generated_by": np.random.choice(['ml_system', 'admin'], p=[0.8, 0.2])
                    }
                    
                    db_manager.save_prediction(prediction_data)
        
        print(f"✅ Created demo predictions for testing")
        
    except Exception as e:
        print(f"⚠️ Error creating demo predictions: {e}")

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

# NEW: ML Prediction Functions
def get_historical_health_data(area, condition):
    """Get historical data for ML predictions"""
    since_date = datetime.now() - timedelta(days=30)
    recent_reports = db_manager.get_recent_health_reports(area, condition, since_date)
    
    if recent_reports:
        total_cases_7d = sum(r.get('cases', 0) for r in recent_reports[-7:])
        total_cases_14d = sum(r.get('cases', 0) for r in recent_reports[-14:])
        avg_cases_7d = total_cases_7d / 7 if recent_reports else 0
        
        return {
            'recent_cases_7d': total_cases_7d,
            'recent_cases_14d': total_cases_14d,
            'avg_cases_7d': avg_cases_7d
        }
    else:
        return {
            'recent_cases_7d': 0,
            'recent_cases_14d': 0,
            'avg_cases_7d': 0
        }

def run_predictions_for_all_areas():
    """Run ML predictions for all areas and conditions"""
    if not health_predictor or not health_predictor.is_trained:
        print("⚠️ Health predictor not available")
        return
    
    areas = ['CITE_SOLEIL', 'DELMAS', 'TABARRE', 'MARTISSANT', 'CARREFOUR', 'PETIONVILLE', 'CROIX_DES_BOUQUETS', 'PORT_AU_PRINCE']
    conditions = ['cholera', 'malnutrition', 'fever', 'diarrhea', 'respiratory']
    
    high_risk_predictions = []
    
    for area in areas:
        for condition in conditions:
            try:
                historical_data = get_historical_health_data(area, condition)
                predictions = health_predictor.predict_outbreak_risk(area, condition, historical_data, days_ahead=7)
                
                if predictions:
                    # Save prediction to database
                    prediction_data = {
                        "id": generate_id(),
                        "area": area,
                        "condition": condition,
                        "type": "health",
                        "date": datetime.now().strftime('%Y-%m-%d'),
                        "predictions": predictions,
                        "timestamp": datetime.utcnow().isoformat() if not USE_MONGODB else datetime.utcnow(),
                        "generated_by": "ml_system"
                    }
                    db_manager.save_prediction(prediction_data)
                    
                    # Check for high risk predictions
                    for pred in predictions:
                        if pred['risk_level'] == 'HIGH':
                            high_risk_predictions.append({
                                'area': area,
                                'condition': condition,
                                'date': pred['date'],
                                'probability': pred['outbreak_probability'],
                                'predicted_cases': pred['predicted_cases']
                            })
                            
            except Exception as e:
                print(f"Error predicting for {area} - {condition}: {e}")
    
    # Auto-trigger alerts for high-risk predictions
    for pred in high_risk_predictions:
        users = db_manager.get_users_by_area(pred['area'], verified_only=True)
        if users and len(users) > 0:
            sent_count = send_health_alert_to_users(
                users, pred['area'], pred['condition'], pred['predicted_cases']
            )
            print(f"🤖 AUTO-ALERT: Sent {pred['condition']} alert to {sent_count} users in {pred['area']} (ML predicted)")

# Routes
@app.route('/debug/routes')
def list_routes():
    """Debug endpoint to list all available routes"""
    routes = []
    for rule in app.url_map.iter_rules():
        if rule.endpoint != 'static':
            routes.append({
                'endpoint': rule.endpoint,
                'methods': list(rule.methods),
                'rule': str(rule),
                'description': app.view_functions[rule.endpoint].__doc__ or 'No description'
            })
    
    routes.sort(key=lambda x: x['rule'])
    
    return jsonify({
        'success': True,
        'total_routes': len(routes),
        'routes': routes,
        'categories': {
            'authentication': [r for r in routes if 'login' in r['rule'] or 'logout' in r['rule']],
            'user_management': [r for r in routes if 'register' in r['rule'] or 'verify' in r['rule']],
            'alerts': [r for r in routes if 'alert' in r['rule'] or 'broadcast' in r['rule']],
            'predictions': [r for r in routes if 'prediction' in r['rule']],
            'history': [r for r in routes if 'history' in r['rule'] or 'stats' in r['rule']],
            'system': [r for r in routes if 'debug' in r['rule'] or 'test' in r['rule'] or 'health' in r['rule']]
        }
    })

@app.route('/')
def home():
    stats = db_manager.get_stats()
    return jsonify({
        'app': 'Alatem Health Alert System',
        'version': '5.0 - ML Enhanced with Complete History Support',
        'database': 'MongoDB Atlas' if USE_MONGODB else 'JSON Files (Development)',
        'status': {
            'database': 'connected',
            'mongodb': USE_MONGODB,
            'verified_users': stats['users']['verified'],
            'staff_users': stats['staff']['active'],
            'sms_service': twilio_client is not None,
            'ml_models': health_predictor is not None and health_predictor.is_trained,
            'predictions_generated': stats['reports'].get('predictions', 0),
            'total_alerts_sent': stats['reports']['alerts_sent']
        },
        'api_endpoints': {
            'alerts_history': '/alerts/history?area=AREA_NAME',
            'predictions': '/predictions/latest',
            'system_health': '/system/health',
            'test_connection': '/test',
            'debug_routes': '/debug/routes'
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
        .ml-status { background: #e8f4fd; border-left: 4px solid #3498db; padding: 10px; margin-bottom: 20px; border-radius: 4px; font-size: 12px; }
    </style>
</head>
<body>
    <div class="login-container">
        <div class="status">
            ☁️ <strong>Database:</strong> {{ "MongoDB Atlas (Production Ready)" if use_mongodb else "JSON Files (Development)" }}
        </div>
        <div class="ml-status">
            🤖 <strong>ML Models:</strong> {{ "✅ Loaded & Active" if ml_active else "⚠️ Not Available" }}
        </div>
        <div class="logo">
            <h1>🏥 Alatem</h1>
            <p>Health Worker Portal v5.0</p>
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
        ''', error=request.args.get('error'), use_mongodb=USE_MONGODB, ml_active=health_predictor is not None and health_predictor.is_trained)
    
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

# NEW: ML Prediction Endpoints
@app.route('/predictions/generate', methods=['POST'])
@login_required
def generate_predictions():
    """Manually trigger ML predictions"""
    try:
        data = request.json or {}
        area = data.get('area')
        
        if area:
            # Generate predictions for specific area
            conditions = ['cholera', 'malnutrition', 'fever', 'diarrhea', 'respiratory']
            results = []
            
            for condition in conditions:
                historical_data = get_historical_health_data(area, condition)
                predictions = health_predictor.predict_outbreak_risk(area, condition, historical_data, days_ahead=7)
                
                if predictions:
                    prediction_data = {
                        "id": generate_id(),
                        "area": area,
                        "condition": condition,
                        "type": "health",
                        "date": datetime.now().strftime('%Y-%m-%d'),
                        "predictions": predictions,
                        "timestamp": datetime.utcnow().isoformat() if not USE_MONGODB else datetime.utcnow(),
                        "generated_by": session.get('staff_username', 'system')
                    }
                    db_manager.save_prediction(prediction_data)
                    results.append(prediction_data)
            
            return jsonify({
                'success': True,
                'message': f'Generated predictions for {area}',
                'predictions': results
            })
        else:
            # Generate for all areas
            run_predictions_for_all_areas()
            return jsonify({
                'success': True,
                'message': 'Generated predictions for all areas'
            })
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

# NEW: Prediction History Routes
@app.route('/predictions/history')
def get_predictions_history():
    """Get prediction history for analysis"""
    try:
        area = request.args.get('area')
        condition = request.args.get('condition')
        limit = int(request.args.get('limit', 50))
        days = int(request.args.get('days', 30))
        
        since_date = datetime.utcnow() - timedelta(days=days)
        
        if USE_MONGODB:
            query = {"timestamp": {"$gte": since_date}}
            if area:
                query["area"] = area
            if condition:
                query["condition"] = condition
                
            predictions = list(predictions_collection.find(
                query,
                sort=[("timestamp", -1)],
                limit=limit
            ))
            
            # Convert ObjectId to string
            for pred in predictions:
                if '_id' in pred:
                    pred['_id'] = str(pred['_id'])
                    
        else:
            all_predictions = db_manager.load_json_data(PREDICTIONS_FILE)
            
            filtered_predictions = []
            for pred in all_predictions:
                try:
                    pred_time = datetime.fromisoformat(pred['timestamp'].replace('Z', '+00:00'))
                    if pred_time >= since_date:
                        if (not area or pred.get('area') == area) and \
                           (not condition or pred.get('condition') == condition):
                            filtered_predictions.append(pred)
                except (ValueError, KeyError):
                    continue
            
            # Sort by timestamp (newest first)
            filtered_predictions.sort(
                key=lambda x: x.get('timestamp', ''),
                reverse=True
            )
            
            predictions = filtered_predictions[:limit]
        
        return jsonify({
            'success': True,
            'predictions': predictions,
            'count': len(predictions),
            'filters': {
                'area': area,
                'condition': condition,
                'days': days
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/predictions/accuracy')
def get_prediction_accuracy():
    """Get prediction accuracy metrics"""
    try:
        # This would compare predictions vs actual reported cases
        # For now, return sample accuracy data
        
        accuracy_data = {
            'overall_accuracy': 78.5,
            'by_condition': {
                'cholera': {'accuracy': 82.1, 'predictions': 45, 'correct': 37},
                'fever': {'accuracy': 75.3, 'predictions': 38, 'correct': 29},
                'diarrhea': {'accuracy': 80.0, 'predictions': 25, 'correct': 20},
                'malnutrition': {'accuracy': 71.4, 'predictions': 21, 'correct': 15},
                'respiratory': {'accuracy': 77.8, 'predictions': 18, 'correct': 14}
            },
            'by_area': {
                'CITE_SOLEIL': {'accuracy': 85.2, 'predictions': 27, 'correct': 23},
                'DELMAS': {'accuracy': 73.9, 'predictions': 23, 'correct': 17},
                'MARTISSANT': {'accuracy': 81.3, 'predictions': 16, 'correct': 13},
                'CARREFOUR': {'accuracy': 75.0, 'predictions': 20, 'correct': 15}
            },
            'last_updated': datetime.utcnow().isoformat()
        }
        
        return jsonify({
            'success': True,
            'accuracy': accuracy_data
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/system/health')
def system_health():
    """Get system health status"""
    try:
        health_status = {
            'database': {
                'status': 'connected',
                'type': 'MongoDB Atlas' if USE_MONGODB else 'JSON Files',
                'last_check': datetime.utcnow().isoformat()
            },
            'ml_models': {
                'health_predictor': health_predictor is not None and health_predictor.is_trained,
                'crime_predictor': crime_predictor is not None and crime_predictor.is_trained,
                'last_prediction': 'Available' if health_predictor and health_predictor.is_trained else 'Not Available'
            },
            'sms_service': {
                'status': 'connected' if twilio_client else 'disabled',
                'provider': 'Twilio' if twilio_client else 'Mock SMS'
            },
            'recent_activity': {
                'alerts_24h': 0,  # Would get real data
                'predictions_24h': 0,  # Would get real data
                'registrations_24h': 0  # Would get real data
            }
        }
        
        # Get real activity data
        try:
            stats = db_manager.get_stats()
            health_status['recent_activity'] = stats.get('recent_activity', {})
        except:
            pass
        
        return jsonify({
            'success': True,
            'health': health_status,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    """Get latest ML predictions"""
    try:
        area = request.args.get('area')
        limit = int(request.args.get('limit', 20))
        
        predictions = db_manager.get_latest_predictions(area, limit)
        
        return jsonify({
            'success': True,
            'predictions': predictions,
            'count': len(predictions)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 400

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
    
@app.route('/alerts/history')
def get_alerts_history():
    """Get alert history for a specific area"""
    try:
        area = request.args.get('area')
        limit = int(request.args.get('limit', 50))
        alert_type = request.args.get('type')  # Optional filter by alert type
        
        if not area:
            return jsonify({'error': 'Area parameter required'}), 400
        
        if USE_MONGODB:
            query = {"area": area}
            if alert_type:
                query["alert_type"] = alert_type
            
            alerts = list(sent_alerts_collection.find(
                query,
                sort=[("timestamp", -1)],
                limit=limit
            ))
            
            # Convert ObjectId to string for JSON serialization
            for alert in alerts:
                if '_id' in alert:
                    alert['_id'] = str(alert['_id'])
                    
        else:
            all_alerts = db_manager.load_json_data(SENT_ALERTS_FILE)
            
            # Filter by area and optionally by type
            area_alerts = [
                alert for alert in all_alerts 
                if alert.get('area') == area and 
                (not alert_type or alert.get('alert_type') == alert_type)
            ]
            
            # Sort by timestamp (newest first)
            area_alerts.sort(
                key=lambda x: x.get('timestamp', ''), 
                reverse=True
            )
            
            # Limit results
            alerts = area_alerts[:limit]
        
        return jsonify({
            'success': True,
            'alerts': alerts,
            'count': len(alerts),
            'area': area,
            'type_filter': alert_type
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/alerts/stats')
def get_alerts_stats():
    """Get alert statistics by area and type"""
    try:
        if USE_MONGODB:
            # MongoDB aggregation
            pipeline = [
                {
                    "$group": {
                        "_id": {
                            "area": "$area",
                            "alert_type": "$alert_type"
                        },
                        "count": {"$sum": 1},
                        "latest": {"$max": "$timestamp"},
                        "total_recipients": {"$sum": "$recipients_count"}
                    }
                },
                {
                    "$group": {
                        "_id": "$_id.area",
                        "types": {
                            "$push": {
                                "type": "$_id.alert_type",
                                "count": "$count",
                                "latest": "$latest",
                                "total_recipients": "$total_recipients"
                            }
                        },
                        "total_alerts": {"$sum": "$count"},
                        "total_recipients": {"$sum": "$total_recipients"}
                    }
                },
                {"$sort": {"_id": 1}}
            ]
            
            stats = list(sent_alerts_collection.aggregate(pipeline))
            
        else:
            # JSON file aggregation
            all_alerts = db_manager.load_json_data(SENT_ALERTS_FILE)
            
            # Group by area and type
            area_stats = {}
            for alert in all_alerts:
                area = alert.get('area')
                alert_type = alert.get('alert_type', 'unknown')
                timestamp = alert.get('timestamp')
                recipients = alert.get('recipients_count', 0)
                
                if area not in area_stats:
                    area_stats[area] = {'total_alerts': 0, 'total_recipients': 0, 'types': {}}
                
                if alert_type not in area_stats[area]['types']:
                    area_stats[area]['types'][alert_type] = {
                        'count': 0,
                        'latest': timestamp,
                        'total_recipients': 0
                    }
                
                area_stats[area]['types'][alert_type]['count'] += 1
                area_stats[area]['types'][alert_type]['total_recipients'] += recipients
                area_stats[area]['total_alerts'] += 1
                area_stats[area]['total_recipients'] += recipients
                
                # Update latest timestamp if newer
                if timestamp and (
                    not area_stats[area]['types'][alert_type]['latest'] or
                    timestamp > area_stats[area]['types'][alert_type]['latest']
                ):
                    area_stats[area]['types'][alert_type]['latest'] = timestamp
            
            # Convert to expected format
            stats = []
            for area, data in area_stats.items():
                types_list = [
                    {
                        'type': alert_type,
                        'count': type_data['count'],
                        'latest': type_data['latest'],
                        'total_recipients': type_data['total_recipients']
                    }
                    for alert_type, type_data in data['types'].items()
                ]
                
                stats.append({
                    '_id': area,
                    'total_alerts': data['total_alerts'],
                    'total_recipients': data['total_recipients'],
                    'types': types_list
                })
        
        return jsonify({
            'success': True,
            'stats': stats
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/alerts/recent')
def get_recent_alerts():
    """Get recent alerts across all areas (last 24 hours)"""
    try:
        hours = int(request.args.get('hours', 24))
        area = request.args.get('area')  # Optional area filter
        since_date = datetime.utcnow() - timedelta(hours=hours)
        
        if USE_MONGODB:
            query = {"timestamp": {"$gte": since_date}}
            if area:
                query["area"] = area
                
            recent_alerts = list(sent_alerts_collection.find(
                query,
                sort=[("timestamp", -1)]
            ))
            
            # Convert ObjectId to string for JSON serialization
            for alert in recent_alerts:
                if '_id' in alert:
                    alert['_id'] = str(alert['_id'])
                    
        else:
            all_alerts = db_manager.load_json_data(SENT_ALERTS_FILE)
            
            recent_alerts = []
            for alert in all_alerts:
                try:
                    alert_time = datetime.fromisoformat(
                        alert['timestamp'].replace('Z', '+00:00')
                    )
                    if alert_time >= since_date:
                        if not area or alert.get('area') == area:
                            recent_alerts.append(alert)
                except (ValueError, KeyError):
                    continue
            
            # Sort by timestamp (newest first)
            recent_alerts.sort(
                key=lambda x: x.get('timestamp', ''),
                reverse=True
            )
        
        return jsonify({
            'success': True,
            'alerts': recent_alerts,
            'count': len(recent_alerts),
            'period_hours': hours,
            'area_filter': area
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/alerts/summary')
def get_alerts_summary():
    """Get summary of all alerts for dashboard"""
    try:
        # Get overall statistics
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday = today - timedelta(days=1)
        week_ago = today - timedelta(days=7)
        
        if USE_MONGODB:
            total_alerts = sent_alerts_collection.count_documents({})
            today_alerts = sent_alerts_collection.count_documents({
                "timestamp": {"$gte": today}
            })
            week_alerts = sent_alerts_collection.count_documents({
                "timestamp": {"$gte": week_ago}
            })
            
            # Get alert type breakdown
            type_pipeline = [
                {"$group": {"_id": "$alert_type", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}}
            ]
            alert_types = list(sent_alerts_collection.aggregate(type_pipeline))
            
        else:
            all_alerts = db_manager.load_json_data(SENT_ALERTS_FILE)
            
            total_alerts = len(all_alerts)
            today_alerts = 0
            week_alerts = 0
            type_counts = {}
            
            for alert in all_alerts:
                try:
                    alert_time = datetime.fromisoformat(alert['timestamp'].replace('Z', '+00:00'))
                    if alert_time >= today:
                        today_alerts += 1
                    if alert_time >= week_ago:
                        week_alerts += 1
                    
                    alert_type = alert.get('alert_type', 'unknown')
                    type_counts[alert_type] = type_counts.get(alert_type, 0) + 1
                        
                except (ValueError, KeyError):
                    continue
            
            alert_types = [{'_id': k, 'count': v} for k, v in sorted(type_counts.items(), key=lambda x: x[1], reverse=True)]
        
        return jsonify({
            'success': True,
            'summary': {
                'total_alerts': total_alerts,
                'today_alerts': today_alerts,
                'week_alerts': week_alerts,
                'alert_types': alert_types
            }
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
        "condition": condition,
        "cases": cases,
        "message": message,
        "recipients_count": sent_count,
        "timestamp": datetime.utcnow().isoformat() if not USE_MONGODB else datetime.utcnow(),
        "triggered_by": session.get('staff_username', 'system'),
        "staff_user_id": session.get('staff_user_id'),
        "is_ml_triggered": session.get('staff_username') == 'ml_system'
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
        "crime_type": crime_type,
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
    <title>Alatem - ML Enhanced Dashboard</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center; }
        .header h1 { margin: 0; }
        .logout-btn { background: rgba(255,255,255,0.2); color: white; border: 1px solid rgba(255,255,255,0.3); padding: 8px 16px; border-radius: 5px; text-decoration: none; font-size: 14px; }
        .container { max-width: 1400px; margin: 0 auto; }
        .card { background: white; padding: 25px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); margin-bottom: 20px; }
        .ml-section { background: linear-gradient(135deg, #e8f4fd 0%, #f0f8ff 100%); border: 2px solid #3498db; border-radius: 8px; padding: 20px; margin-bottom: 20px; }
        .broadcast-section { background: #fff3cd; border: 1px solid #ffeaa7; border-radius: 8px; padding: 20px; }
        .predictions-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 15px; margin: 15px 0; }
        .prediction-card { background: white; padding: 15px; border-radius: 8px; border-left: 4px solid #3498db; }
        .risk-high { border-left-color: #e74c3c; background: #fff5f5; }
        .risk-medium { border-left-color: #f39c12; background: #fffdf5; }
        .risk-low { border-left-color: #27ae60; background: #f8fff8; }
        .broadcast-controls { display: flex; gap: 10px; flex-wrap: wrap; margin: 15px 0; }
        button { background: #3498db; color: white; padding: 12px 24px; border: none; border-radius: 6px; cursor: pointer; font-size: 16px; font-weight: 600; transition: background 0.3s; margin-right: 10px; margin-bottom: 10px; }
        button:hover { background: #2980b9; }
        button.danger { background: #e74c3c; }
        button.warning { background: #f39c12; }
        button.success { background: #27ae60; }
        select { width: 100%; padding: 12px; border: 2px solid #ddd; border-radius: 6px; font-size: 14px; box-sizing: border-box; margin-bottom: 15px; }
        textarea { width: 100%; padding: 12px; border: 2px solid #ddd; border-radius: 6px; font-size: 14px; box-sizing: border-box; }
        .area-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; margin: 15px 0; }
        .area-card { background: white; padding: 15px; border-radius: 8px; text-align: center; border: 1px solid #ddd; }
        .area-card h4 { margin: 0 0 10px 0; color: #2c3e50; }
        .area-card .count { font-size: 24px; font-weight: bold; color: #3498db; }
        .success { color: #27ae60; font-weight: 600; padding: 15px; margin: 15px 0; border-radius: 6px; background: #eafaf1; }
        .error { color: #e74c3c; font-weight: 600; padding: 15px; margin: 15px 0; border-radius: 6px; background: #ffeaea; }
        .loading { text-align: center; padding: 20px; color: #666; }
        .tabs { display: flex; background: #ecf0f1; border-radius: 6px; margin-bottom: 20px; }
        .tab { flex: 1; padding: 12px 20px; text-align: center; cursor: pointer; border: none; background: transparent; font-weight: 600; }
        .tab.active { background: #3498db; color: white; border-radius: 6px; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .ml-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 15px 0; }
        .ml-stat { background: white; padding: 15px; border-radius: 8px; text-align: center; border: 1px solid #ddd; }
        .ml-stat .number { font-size: 28px; font-weight: bold; color: #3498db; }
        .ml-stat .label { font-size: 12px; color: #666; text-transform: uppercase; }
        .prediction-details { font-size: 12px; color: #666; margin-top: 10px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div>
                <h1>🤖 Alatem - ML Enhanced Dashboard v5.0</h1>
                <div>{{ "MongoDB Atlas (Production)" if use_mongodb else "JSON Files (Development)" }} • ML Models Active</div>
            </div>
            <a href="/logout" class="logout-btn">Logout</a>
        </div>
        
        <div class="tabs">
            <button class="tab active" onclick="showTab('predictions')">🔮 ML Predictions</button>
            <button class="tab" onclick="showTab('alerts')">📡 Manual Alerts</button>
            <button class="tab" onclick="showTab('stats')">📊 System Stats</button>
        </div>
        
        <!-- ML Predictions Tab -->
        <div id="predictions" class="tab-content active">
            <div class="ml-section">
                <h3>🤖 Machine Learning Outbreak Predictions</h3>
                <p>AI-powered predictions for health outbreaks in the next 7 days based on historical data, seasonality, and risk factors.</p>
                
                <div class="broadcast-controls">
                    <button class="success" onclick="generatePredictions()">🔮 Generate New Predictions</button>
                    <button onclick="loadPredictions()">📊 Refresh Predictions</button>
                    <button class="warning" onclick="generatePredictions('all')">🌍 Generate for All Areas</button>
                </div>
                
                <label for="prediction-area">Focus Area (optional):</label>
                <select id="prediction-area">
                    <option value="">All Areas</option>
                    <option value="CITE_SOLEIL">Cite Soleil</option>
                    <option value="DELMAS">Delmas</option>
                    <option value="TABARRE">Tabarre</option>
                    <option value="MARTISSANT">Martissant</option>
                    <option value="CARREFOUR">Carrefour</option>
                    <option value="PETIONVILLE">Petionville</option>
                </select>
                
                <div id="mlStats" class="ml-stats">
                    <div class="ml-stat">
                        <div class="number" id="totalPredictions">0</div>
                        <div class="label">Total Predictions</div>
                    </div>
                    <div class="ml-stat">
                        <div class="number" id="highRiskPredictions">0</div>
                        <div class="label">High Risk Alerts</div>
                    </div>
                    <div class="ml-stat">
                        <div class="number" id="autoAlertsSent">0</div>
                        <div class="label">Auto Alerts Sent</div>
                    </div>
                </div>
                
                <div id="predictionsContainer">
                    <div class="loading">🔮 Loading ML predictions...</div>
                </div>
            </div>
        </div>
        
        <!-- Manual Alerts Tab -->
        <div id="alerts" class="tab-content">
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
        
        <!-- System Stats Tab -->
        <div id="stats" class="tab-content">
            <div class="card">
                <h3>📊 System Statistics</h3>
                <div id="systemStats">
                    <div class="loading">📊 Loading system statistics...</div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        let currentTab = 'predictions';
        
        function showTab(tabName) {
            // Hide all tabs
            document.querySelectorAll('.tab-content').forEach(content => {
                content.classList.remove('active');
            });
            document.querySelectorAll('.tab').forEach(tab => {
                tab.classList.remove('active');
            });
            
            // Show selected tab
            document.getElementById(tabName).classList.add('active');
            event.target.classList.add('active');
            currentTab = tabName;
            
            // Load data for active tab
            if (tabName === 'predictions') {
                loadPredictions();
            } else if (tabName === 'alerts') {
                loadAreaStats();
            } else if (tabName === 'stats') {
                loadSystemStats();
            }
        }
        
        function showMessage(message, type = 'success') {
            const alert = document.createElement('div');
            alert.className = type;
            alert.textContent = message;
            const container = document.querySelector('.container');
            container.insertBefore(alert, container.children[1]);
            setTimeout(() => alert.remove(), 5000);
        }
        
        async function generatePredictions(scope = 'area') {
            try {
                const area = scope === 'all' ? null : document.getElementById('prediction-area').value;
                const response = await fetch('/predictions/generate', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ area: area })
                });
                const result = await response.json();
                
                if (result.success) {
                    showMessage(`✅ ${result.message}`);
                    loadPredictions();
                } else {
                    showMessage('❌ Error: ' + result.error, 'error');
                }
            } catch (error) {
                showMessage('❌ Error generating predictions: ' + error, 'error');
            }
        }
        
        async function loadPredictions() {
            try {
                const response = await fetch('/predictions/latest');
                const data = await response.json();
                
                if (data.success) {
                    displayPredictions(data.predictions);
                    updateMLStats(data.predictions);
                } else {
                    document.getElementById('predictionsContainer').innerHTML = '<div class="error">Error loading predictions</div>';
                }
            } catch (error) {
                document.getElementById('predictionsContainer').innerHTML = '<div class="error">Error loading predictions: ' + error + '</div>';
            }
        }
        
        function displayPredictions(predictions) {
            const container = document.getElementById('predictionsContainer');
            
            if (predictions.length === 0) {
                container.innerHTML = '<div class="loading">No predictions available. Click "Generate New Predictions" to create ML forecasts.</div>';
                return;
            }
            
            let html = '<div class="predictions-grid">';
            
            predictions.forEach(pred => {
                if (pred.predictions && pred.predictions.length > 0) {
                    const highestRisk = pred.predictions.reduce((max, p) => p.outbreak_probability > max.outbreak_probability ? p : max);
                    const riskClass = highestRisk.risk_level.toLowerCase();
                    
                    html += `<div class="prediction-card risk-${riskClass}">
                        <h4>${pred.area.replace(/_/g, ' ')} - ${pred.condition.toUpperCase()}</h4>
                        <div style="font-size: 18px; font-weight: bold; color: ${riskClass === 'high' ? '#e74c3c' : riskClass === 'medium' ? '#f39c12' : '#27ae60'}">
                            ${highestRisk.risk_level} RISK
                        </div>
                        <div>Probability: ${(highestRisk.outbreak_probability * 100).toFixed(1)}%</div>
                        <div>Predicted Cases: ${highestRisk.predicted_cases}</div>
                        <div>Date: ${highestRisk.date}</div>
                        <div class="prediction-details">
                            Generated: ${new Date(pred.timestamp).toLocaleString()}<br>
                            By: ${pred.generated_by}
                        </div>
                    </div>`;
                }
            });
            
            html += '</div>';
            container.innerHTML = html;
        }
        
        function updateMLStats(predictions) {
            const total = predictions.length;
            const highRisk = predictions.filter(p => 
                p.predictions && p.predictions.some(pred => pred.risk_level === 'HIGH')
            ).length;
            
            document.getElementById('totalPredictions').textContent = total;
            document.getElementById('highRiskPredictions').textContent = highRisk;
            // Auto alerts count would come from backend
            document.getElementById('autoAlertsSent').textContent = '12'; // Placeholder
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
        
        async function loadSystemStats() {
            try {
                const response = await fetch('/stats');
                const data = await response.json();
                
                let html = `
                    <div class="ml-stats">
                        <div class="ml-stat">
                            <div class="number">${data.users.verified}</div>
                            <div class="label">Verified Users</div>
                        </div>
                        <div class="ml-stat">
                            <div class="number">${data.reports.alerts_sent}</div>
                            <div class="label">Total Alerts Sent</div>
                        </div>
                        <div class="ml-stat">
                            <div class="number">${data.reports.predictions || 0}</div>
                            <div class="label">ML Predictions</div>
                        </div>
                        <div class="ml-stat">
                            <div class="number">${data.recent_activity.alerts_sent_24h}</div>
                            <div class="label">Alerts (24h)</div>
                        </div>
                        <div class="ml-stat">
                            <div class="number">${data.recent_activity.predictions_24h || 0}</div>
                            <div class="label">Predictions (24h)</div>
                        </div>
                        <div class="ml-stat">
                            <div class="number">${data.database}</div>
                            <div class="label">Database</div>
                        </div>
                    </div>
                `;
                
                document.getElementById('systemStats').innerHTML = html;
            } catch (error) {
                document.getElementById('systemStats').innerHTML = '<div class="error">Error loading stats: ' + error + '</div>';
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
        
        // Auto-load data on page load
        document.addEventListener('DOMContentLoaded', function() {
            loadPredictions();
        });
        
        // Auto-refresh predictions every 5 minutes
        setInterval(() => {
            if (currentTab === 'predictions') {
                loadPredictions();
            }
        }, 300000);
    </script>
</body>
</html>
    ''', use_mongodb=USE_MONGODB)

@app.route('/stats')
def get_stats():
    try:
        stats = db_manager.get_stats()
        stats['database'] = 'MongoDB Atlas' if USE_MONGODB else 'JSON Files'
        stats['ml_active'] = health_predictor is not None and health_predictor.is_trained
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
            
            # Run initial predictions on startup
            print("🔮 Generating initial ML predictions...")
            run_predictions_for_all_areas()
            
        else:
            print("⚠️ Health model files not found. Run 'python ml_models.py' to train models first.")
            
    except Exception as e:
        print(f"❌ Error loading models: {e}")

# NEW: Automated ML prediction scheduler
def schedule_predictions():
    """Schedule automatic ML predictions"""
    def run_scheduled_predictions():
        print("🕐 Running scheduled ML predictions...")
        run_predictions_for_all_areas()
    
    # Run predictions every 6 hours
    schedule.every(6).hours.do(run_scheduled_predictions)
    
    while True:
        schedule.run_pending()
        time.sleep(3600)  # Check every hour

def start_prediction_scheduler():
    """Start the prediction scheduler in a background thread"""
    if health_predictor and health_predictor.is_trained:
        scheduler_thread = threading.Thread(target=schedule_predictions, daemon=True)
        scheduler_thread.start()
        print("✅ ML prediction scheduler started (runs every 6 hours)")

if __name__ == '__main__':
    print(f"🚀 Starting Alatem Health Alert System v5.0...")
    print(f"📊 Database: {'MongoDB Atlas' if USE_MONGODB else 'JSON Files'}")
    
    ensure_directories()
    create_default_admin()
    create_demo_users()
    create_demo_alert_history()  # Create demo alerts for testing
    create_demo_predictions()    # Create demo predictions for testing
    load_ml_models()
    start_prediction_scheduler()
    
    print("\n" + "="*70)
    print("🤖 ALATEM HEALTH ALERT SYSTEM v5.0 - ML ENHANCED")
    print("="*70)
    print("🔐 Staff Login: http://localhost:5000/login")
    print("📱 ML Dashboard: http://localhost:5000/health-worker")
    print("🔗 API: http://localhost:5000/")
    print("📊 Stats: http://localhost:5000/stats")
    print("🔮 Predictions API: http://localhost:5000/predictions/latest")
    print("📱 SMS History API: http://localhost:5000/alerts/history?area=DELMAS")
    print("📈 Alert Stats API: http://localhost:5000/alerts/stats")
    print("🏥 System Health API: http://localhost:5000/system/health")
    print("="*70)
    print(f"💾 Database: {'MongoDB Atlas (Production)' if USE_MONGODB else 'JSON Files (Development)'}")
    print(f"🤖 ML Models: {'✅ Active' if health_predictor and health_predictor.is_trained else '⚠️ Not Available'}")
    print("🔑 Login: admin / admin123")
    print("📱 Demo Data: Alert history and predictions created for testing")
    print("="*70)
    
    app.run(debug=True, host='0.0.0.0', port=5000)