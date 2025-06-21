# app.py - Main Flask application
from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from twilio.rest import Client
import sqlite3
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

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///alatem.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Twilio configuration
twilio_client = Client(os.getenv('TWILIO_SID'), os.getenv('TWILIO_TOKEN'))
TWILIO_PHONE = os.getenv('TWILIO_PHONE')

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), unique=True, nullable=False)
    area = db.Column(db.String(50), nullable=False)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    verified = db.Column(db.Boolean, default=False)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class HealthReport(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    condition = db.Column(db.String(50), nullable=False)
    cases = db.Column(db.Integer, nullable=False)
    area = db.Column(db.String(50), nullable=False)
    reported_by = db.Column(db.String(100))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class CrimeReport(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    crime_type = db.Column(db.String(50), nullable=False)
    area = db.Column(db.String(50), nullable=False)
    severity = db.Column(db.String(20))
    reported_by = db.Column(db.String(100))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class SentAlert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    alert_type = db.Column(db.String(50), nullable=False)
    area = db.Column(db.String(50), nullable=False)
    message = db.Column(db.Text, nullable=False)
    recipients_count = db.Column(db.Integer)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# Initialize ML models
health_predictor = None
crime_predictor = None

def load_ml_models():
    """Load trained ML models"""
    global health_predictor, crime_predictor
    try:
        health_predictor = HealthOutbreakPredictor()
        if os.path.exists('outbreak_classifier.pkl'):
            health_predictor.outbreak_classifier = joblib.load('outbreak_classifier.pkl')
            health_predictor.cases_regressor = joblib.load('cases_regressor.pkl')
            health_predictor.label_encoders = joblib.load('label_encoders.pkl')
            health_predictor.scaler = joblib.load('scaler.pkl')
            health_predictor.is_trained = True
            print("Health models loaded successfully!")
        
        crime_predictor = CrimePredictor()
        if os.path.exists('crime_classifier.pkl'):
            crime_predictor.crime_classifier = joblib.load('crime_classifier.pkl')
            crime_predictor.is_trained = True
            print("Crime model loaded successfully!")
            
    except Exception as e:
        print(f"Error loading models: {e}")

# OTP storage (use Redis in production)
otp_store = {}

@app.route('/register', methods=['POST'])
def register_user():
    """Register new user and send OTP"""
    try:
        data = request.json
        name = data.get('name')
        phone = data.get('phone')
        area = data.get('area')
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        
        # Generate OTP
        otp = np.random.randint(100000, 999999)
        
        # Store user (unverified)
        existing_user = User.query.filter_by(phone=phone).first()
        if existing_user:
            existing_user.name = name
            existing_user.area = area
            existing_user.latitude = latitude
            existing_user.longitude = longitude
            existing_user.verified = False
        else:
            user = User(name=name, phone=phone, area=area, 
                       latitude=latitude, longitude=longitude)
            db.session.add(user)
        
        db.session.commit()
        
        # Send OTP SMS
        message = f"Kòd verifikasyon Alatem: {otp}. Pa pataje kòd sa a ak pèsonn."
        twilio_client.messages.create(
            body=message,
            from_=TWILIO_PHONE,
            to=phone
        )
        
        # Store OTP
        otp_store[phone] = {
            'otp': otp,
            'expires': datetime.now() + timedelta(minutes=5)
        }
        
        return jsonify({'success': True, 'message': 'OTP sent successfully'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/verify', methods=['POST'])
def verify_otp():
    """Verify OTP and activate user"""
    try:
        data = request.json
        phone = data.get('phone')
        otp = data.get('otp')
        
        stored_otp = otp_store.get(phone)
        
        if (stored_otp and 
            str(stored_otp['otp']) == str(otp) and 
            datetime.now() < stored_otp['expires']):
            
            # Verify user
            user = User.query.filter_by(phone=phone).first()
            if user:
                user.verified = True
                db.session.commit()
                
                # Send welcome message
                welcome_msg = f"Byenveni nan Alatem, {user.name}! Ou ap resevwa alèt sante ak sekirite nan {user.area}."
                twilio_client.messages.create(
                    body=welcome_msg,
                    from_=TWILIO_PHONE,
                    to=phone
                )
                
                # Clean up OTP
                del otp_store[phone]
                
                return jsonify({'verified': True, 'message': 'User verified successfully'})
        
        return jsonify({'verified': False, 'error': 'Invalid or expired OTP'})
        
    except Exception as e:
        return jsonify({'verified': False, 'error': str(e)}), 400

@app.route('/health-report', methods=['POST'])
def submit_health_report():
    """Submit health report and trigger outbreak detection"""
    try:
        data = request.json
        condition = data.get('condition')
        cases = data.get('cases')
        area = data.get('area')
        reported_by = data.get('reported_by', 'Anonymous')
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        
        # Store health report
        report = HealthReport(
            condition=condition,
            cases=cases,
            area=area,
            reported_by=reported_by,
            latitude=latitude,
            longitude=longitude
        )
        db.session.add(report)
        db.session.commit()
        
        # Check for outbreaks
        check_outbreak_and_alert(area, condition)
        
        return jsonify({'success': True, 'message': 'Health report submitted'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/crime-report', methods=['POST'])
def submit_crime_report():
    """Submit crime report"""
    try:
        data = request.json
        crime_type = data.get('crime_type')
        area = data.get('area')
        severity = data.get('severity', 'medium')
        reported_by = data.get('reported_by', 'Anonymous')
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        
        # Store crime report
        report = CrimeReport(
            crime_type=crime_type,
            area=area,
            severity=severity,
            reported_by=reported_by,
            latitude=latitude,
            longitude=longitude
        )
        db.session.add(report)
        db.session.commit()
        
        # Check for crime pattern alerts
        check_crime_patterns_and_alert(area, crime_type)
        
        return jsonify({'success': True, 'message': 'Crime report submitted'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/predictions/<area>')
def get_predictions(area):
    """Get ML predictions for an area"""
    try:
        predictions = {}
        
        # Health predictions
        if health_predictor and health_predictor.is_trained:
            # Get historical data for the area
            historical_health = get_historical_health_data(area)
            
            for condition in ['cholera', 'malnutrition', 'fever', 'diarrhea']:
                health_pred = health_predictor.predict_outbreak_risk(
                    area, condition, historical_health, days_ahead=7
                )
                predictions[f'{condition}_prediction'] = health_pred
        
        # Crime predictions would go here
        
        return jsonify({
            'area': area,
            'predictions': predictions,
            'generated_at': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 400

def get_historical_health_data(area):
    """Get historical health data for ML prediction"""
    thirty_days_ago = datetime.now() - timedelta(days=30)
    
    reports = HealthReport.query.filter(
        HealthReport.area == area,
        HealthReport.timestamp >= thirty_days_ago
    ).all()
    
    recent_cases_7d = sum([r.cases for r in reports if r.timestamp >= datetime.now() - timedelta(days=7)])
    recent_cases_14d = sum([r.cases for r in reports if r.timestamp >= datetime.now() - timedelta(days=14)])
    avg_cases_7d = recent_cases_7d / 7 if recent_cases_7d > 0 else 0
    
    return {
        'recent_cases_7d': recent_cases_7d,
        'recent_cases_14d': recent_cases_14d,
        'avg_cases_7d': avg_cases_7d
    }

def check_outbreak_and_alert(area, condition):
    """Check for outbreak and send alerts"""
    # Get cases in last 24 hours
    yesterday = datetime.now() - timedelta(days=1)
    recent_reports = HealthReport.query.filter(
        HealthReport.area == area,
        HealthReport.condition == condition,
        HealthReport.timestamp >= yesterday
    ).all()
    
    total_cases = sum([r.cases for r in recent_reports])
    
    # Outbreak thresholds
    thresholds = {
        'cholera': 10,
        'malnutrition': 15,
        'fever': 20,
        'diarrhea': 12
    }
    
    if total_cases >= thresholds.get(condition, 10):
        send_health_alert(area, condition, total_cases)

def check_crime_patterns_and_alert(area, crime_type):
    """Check crime patterns and send safety alerts"""
    # Get recent crimes in area
    recent_crimes = CrimeReport.query.filter(
        CrimeReport.area == area,
        CrimeReport.timestamp >= datetime.now() - timedelta(days=1)
    ).count()
    
    if recent_crimes >= 3:  # Multiple crimes in one day
        send_safety_alert(area, crime_type)

def send_health_alert(area, condition, cases):
    """Send health alert to all users in area"""
    users = User.query.filter_by(area=area, verified=True, active=True).all()
    
    # Create alert message in Haitian Creole
    messages = {
        'cholera': f"🚨 ALÈT SANTE: {cases} ka cholera nan {area}. Bwè dlo pwòp, lave men nou. Ale kay doktè si nou gen simptòm. Rele 911 pou èd.",
        'malnutrition': f"⚠️ ALÈT SANTE: {cases} ka malnitrisyon nan {area}. Chèche manje ak vitamin. Mennen timoun yo kay doktè.",
        'fever': f"🌡️ ALÈT SANTE: {cases} ka lafyèv nan {area}. Rete lakay si nou malad. Bwè dlo anpil. Ale kay doktè si lafyèv la kontinye.",
        'diarrhea': f"💧 ALÈT SANTE: {cases} ka dyare nan {area}. Bwè dlo pwòp, lave men nou. Evite manje ki pa kwit byen."
    }
    
    message = messages.get(condition, f"🚨 ALÈT SANTE: {cases} ka {condition} nan {area}")
    
    sent_count = 0
    for user in users:
        try:
            twilio_client.messages.create(
                body=message,
                from_=TWILIO_PHONE,
                to=user.phone
            )
            sent_count += 1
            time.sleep(0.1)  # Rate limiting
        except Exception as e:
            print(f"Failed to send to {user.phone}: {e}")
    
    # Log alert
    alert = SentAlert(
        alert_type='health_outbreak',
        area=area,
        message=message,
        recipients_count=sent_count
    )
    db.session.add(alert)
    db.session.commit()
    
    print(f"Health alert sent to {sent_count} users in {area}")

def send_safety_alert(area, crime_type):
    """Send safety alert to users in area"""
    users = User.query.filter_by(area=area, verified=True, active=True).all()
    
    safety_messages = {
        'kidnapping': f"🚨 SEKIRITE: Kidnapping nan {area}. Pa mache pou kont nou. Evite kote yo ki izole. Rele 114 pou polis.",
        'armed_robbery': f"⚠️ SEKIRITE: Volè ak zam nan {area}. Pa montre objè ki gen valè. Mache nan gwoup. Evite lannwit.",
        'gang_shooting': f"🔫 DANJE: Bandi k ap tire nan {area}. Rete lakay. Pa soti. Kontak fanmi nou yo.",
        'street_violence': f"⚠️ SEKIRITE: Vyolans nan lari nan {area}. Evite kote yo ki gen anpil moun. Ale nan sekirite."
    }
    
    message = safety_messages.get(crime_type, f"⚠️ SEKIRITE: Danje nan {area}. Fè atansyon.")
    
    sent_count = 0
    for user in users:
        try:
            twilio_client.messages.create(
                body=message,
                from_=TWILIO_PHONE,
                to=user.phone
            )
            sent_count += 1
            time.sleep(0.1)
        except Exception as e:
            print(f"Failed to send to {user.phone}: {e}")
    
    # Log alert
    alert = SentAlert(
        alert_type='safety_alert',
        area=area,
        message=message,
        recipients_count=sent_count
    )
    db.session.add(alert)
    db.session.commit()

# Health worker interface
@app.route('/health-worker')
def health_worker_interface():
    """Simple web interface for health workers"""
    html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Alatem - Health Worker Interface</title>
        <meta charset="utf-8">
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            .form-group { margin: 15px 0; }
            label { display: block; margin-bottom: 5px; font-weight: bold; }
            select, input, textarea { width: 300px; padding: 8px; }
            button { background: #007bff; color: white; padding: 10px 20px; border: none; cursor: pointer; }
            button:hover { background: #0056b3; }
            .predictions { background: #f8f9fa; padding: 20px; margin: 20px 0; border-radius: 5px; }
        </style>
    </head>
    <body>
        <h1>🏥 Alatem - Health Worker Interface</h1>
        
        <h2>Report Health Case</h2>
        <form id="healthForm">
            <div class="form-group">
                <label>Health Condition:</label>
                <select name="condition" required>
                    <option value="">Select condition...</option>
                    <option value="cholera">Cholera</option>
                    <option value="malnutrition">Malnutrition/Malnitrisyon</option>
                    <option value="fever">Fever/Lafyèv</option>
                    <option value="diarrhea">Diarrhea/Dyare</option>
                    <option value="respiratory">Respiratory Issues</option>
                </select>
            </div>
            
            <div class="form-group">
                <label>Number of Cases:</label>
                <input name="cases" type="number" min="1" required>
            </div>
            
            <div class="form-group">
                <label>Area:</label>
                <select name="area" required>
                    <option value="">Select area...</option>
                    <option value="CITE_SOLEIL">Cite Soleil</option>
                    <option value="DELMAS">Delmas</option>
                    <option value="TABARRE">Tabarre</option>
                    <option value="MARTISSANT">Martissant</option>
                    <option value="CARREFOUR">Carrefour</option>
                    <option value="PETIONVILLE">Petionville</option>
                    <option value="PORT_AU_PRINCE">Port-au-Prince</option>
                </select>
            </div>
            
            <div class="form-group">
                <label>Reported by:</label>
                <input name="reported_by" type="text" placeholder="Your name" required>
            </div>
            
            <button type="submit">Submit Health Report</button>
        </form>
        
        <h2>Report Crime/Security Issue</h2>
        <form id="crimeForm">
            <div class="form-group">
                <label>Crime Type:</label>
                <select name="crime_type" required>
                    <option value="">Select crime type...</option>
                    <option value="kidnapping">Kidnapping</option>
                    <option value="armed_robbery">Armed Robbery</option>
                    <option value="gang_shooting">Gang Shooting</option>
                    <option value="street_violence">Street Violence</option>
                    <option value="home_invasion">Home Invasion</option>
                </select>
            </div>
            
            <div class="form-group">
                <label>Area:</label>
                <select name="area" required>
                    <option value="">Select area...</option>
                    <option value="CITE_SOLEIL">Cite Soleil</option>
                    <option value="DELMAS">Delmas</option>
                    <option value="TABARRE">Tabarre</option>
                    <option value="MARTISSANT">Martissant</option>
                    <option value="CARREFOUR">Carrefour</option>
                    <option value="PETIONVILLE">Petionville</option>
                    <option value="PORT_AU_PRINCE">Port-au-Prince</option>
                </select>
            </div>
            
            <div class="form-group">
                <label>Severity:</label>
                <select name="severity" required>
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                </select>
            </div>
            
            <div class="form-group">
                <label>Reported by:</label>
                <input name="reported_by" type="text" placeholder="Your name" required>
            </div>
            
            <button type="submit">Submit Crime Report</button>
        </form>
        
        <div class="predictions">
            <h2>📊 ML Predictions</h2>
            <p>Select an area to see outbreak predictions:</p>
            <select id="predictionArea">
                <option value="">Select area...</option>
                <option value="CITE_SOLEIL">Cite Soleil</option>
                <option value="DELMAS">Delmas</option>
                <option value="TABARRE">Tabarre</option>
                <option value="MARTISSANT">Martissant</option>
            </select>
            <button onclick="getPredictions()">Get Predictions</button>
            <div id="predictionResults"></div>
        </div>
        
        <script>
            document.getElementById('healthForm').onsubmit = async function(e) {
                e.preventDefault();
                const formData = new FormData(e.target);
                const data = Object.fromEntries(formData);
                
                try {
                    const response = await fetch('/health-report', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify(data)
                    });
                    const result = await response.json();
                    alert(result.success ? 'Health report submitted successfully!' : 'Error: ' + result.error);
                    if (result.success) e.target.reset();
                } catch (error) {
                    alert('Error submitting report: ' + error);
                }
            };
            
            document.getElementById('crimeForm').onsubmit = async function(e) {
                e.preventDefault();
                const formData = new FormData(e.target);
                const data = Object.fromEntries(formData);
                
                try {
                    const response = await fetch('/crime-report', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify(data)
                    });
                    const result = await response.json();
                    alert(result.success ? 'Crime report submitted successfully!' : 'Error: ' + result.error);
                    if (result.success) e.target.reset();
                } catch (error) {
                    alert('Error submitting report: ' + error);
                }
            };
            
            async function getPredictions() {
                const area = document.getElementById('predictionArea').value;
                if (!area) {
                    alert('Please select an area');
                    return;
                }
                
                try {
                    const response = await fetch(`/predictions/${area}`);
                    const data = await response.json();
                    
                    let html = `<h3>Predictions for ${area}</h3>`;
                    if (data.predictions) {
                        for (const [condition, predictions] of Object.entries(data.predictions)) {
                            if (predictions && predictions.length > 0) {
                                html += `<h4>${condition.replace('_prediction', '').toUpperCase()}</h4>`;
                                predictions.forEach(pred => {
                                    html += `<p><strong>${pred.date}</strong>: ${pred.risk_level} risk (${Math.round(pred.outbreak_probability * 100)}%) - ${pred.predicted_cases} cases</p>`;
                                });
                            }
                        }
                    }
                    
                    document.getElementById('predictionResults').innerHTML = html;
                } catch (error) {
                    alert('Error getting predictions: ' + error);
                }
            }
        </script>
    </body>
    </html>
    '''
    return html

# Automated tasks
def run_daily_predictions():
    """Run daily ML predictions and send proactive alerts"""
    if not health_predictor or not health_predictor.is_trained:
        return
    
    areas = ['CITE_SOLEIL', 'DELMAS', 'TABARRE', 'MARTISSANT', 'CARREFOUR']
    conditions = ['cholera', 'malnutrition', 'fever']
    
    for area in areas:
        historical_data = get_historical_health_data(area)
        
        for condition in conditions:
            predictions = health_predictor.predict_outbreak_risk(
                area, condition, historical_data, days_ahead=3
            )
            
            if predictions:
                # Check for high-risk predictions
                high_risk_days = [p for p in predictions if p['risk_level'] == 'HIGH']
                
                if high_risk_days:
                    send_prediction_alert(area, condition, high_risk_days)

def send_prediction_alert(area, condition, predictions):
    """Send predictive alert to users"""
    users = User.query.filter_by(area=area, verified=True, active=True).all()
    
    risk_dates = [p['date'] for p in predictions]
    message = f"📈 ALÈT PREDIKSYON: Risk segondè pou {condition} nan {area} nan {len(risk_dates)} jou kap vini an. Pwoteje fanmi nou ak pratik ijyèn."
    
    for user in users[:50]:  # Limit to prevent spam
        try:
            twilio_client.messages.create(
                body=message,
                from_=TWILIO_PHONE,
                to=user.phone
            )
            time.sleep(0.2)
        except:
            pass

# Initialize app
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        load_ml_models()
    
    # Schedule daily predictions
    schedule.every().day.at("08:00").do(run_daily_predictions)
    
    def run_scheduler():
        while True:
            schedule.run_pending()
            time.sleep(60)
    
    scheduler_thread = threading.Thread(target=run_scheduler)
    scheduler_thread.daemon = True
    scheduler_thread.start()
    
    app.run(debug=True, host='0.0.0.0', port=5000)