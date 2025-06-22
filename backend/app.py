from flask import Flask, request, jsonify, render_template_string, redirect, url_for
import os
from datetime import datetime

# Import our modular components
from config import Config
from database import DatabaseManager
from sms_service import SMSService
from auth import AuthService
from alert_service import AlertService
from ml_service import MLService

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = Config.SECRET_KEY

# Add CORS support
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

# Initialize services
db_manager = DatabaseManager()
sms_service = SMSService()
auth_service = AuthService(db_manager)
alert_service = AlertService(db_manager, sms_service, auth_service)
ml_service = MLService(db_manager, alert_service)

# Ensure required directories exist
def ensure_directories():
    for directory in [Config.ML_MODELS_DIR, Config.DATASET_DIR, Config.DATA_DIR]:
        os.makedirs(directory, exist_ok=True)

# ======================
# API ROUTES
# ======================

@app.route('/')
def home():
    """System status and API information"""
    stats = db_manager.get_stats()
    return jsonify({
        'app': 'Alatem Health Alert System',
        'version': '6.0 - Modular Architecture',
        'database': 'MongoDB Atlas' if db_manager.use_mongodb else 'JSON Files (Development)',
        'status': {
            'database': 'connected',
            'mongodb': db_manager.use_mongodb,
            'verified_users': stats['users']['verified'],
            'staff_users': stats['staff']['active'],
            'sms_service': sms_service.is_available(),
            'ml_models': ml_service.is_available(),
            'total_alerts_sent': stats['reports']['alerts_sent']
        },
        'api_endpoints': {
            'user_registration': '/register',
            'otp_verification': '/verify',
            'alerts_history': '/alerts/history?area=AREA_NAME',
            'predictions': '/predictions/latest',
            'system_health': '/system/health',
            'staff_login': '/login'
        }
    })

@app.route('/test')
def test_connection():
    """Test endpoint for frontend connectivity"""
    return jsonify({
        'status': 'success',
        'message': 'Backend is running!',
        'version': '6.0 - Modular Architecture',
        'timestamp': datetime.utcnow().isoformat(),
        'features': {
            'database': db_manager.use_mongodb,
            'ml_models': ml_service.is_available(),
            'sms_service': sms_service.is_available(),
            'real_users_only': True
        }
    })

# ======================
# USER REGISTRATION ROUTES
# ======================

@app.route('/register', methods=['POST'])
def register_user():
    """Register new user with OTP verification"""
    try:
        data = request.json
        name = data.get('name', '').strip()
        phone = data.get('phone', '').strip()
        area = data.get('area', '').strip()
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        
        # Validate required fields
        if not all([name, phone, area]):
            return jsonify({
                'success': False, 
                'error': 'Name, phone, and area are required'
            }), 400
        
        # Validate phone number
        valid_phone, formatted_phone = auth_service.validate_phone_number(phone)
        if not valid_phone:
            return jsonify({
                'success': False,
                'error': formatted_phone  # Error message
            }), 400
        
        # Validate area
        if area not in Config.HAITI_AREAS:
            return jsonify({
                'success': False,
                'error': f'Invalid area. Must be one of: {", ".join(Config.HAITI_AREAS)}'
            }), 400
        
        # Check if user already exists
        existing_user = db_manager.find_user_by_phone(formatted_phone)
        if existing_user and existing_user.get('verified'):
            return jsonify({
                'success': False,
                'error': 'User already registered and verified'
            }), 400
        
        # Create or update user
        success, result = auth_service.create_user(
            name=name,
            phone=formatted_phone,
            area=area,
            latitude=latitude,
            longitude=longitude
        )
        
        if not success:
            return jsonify({'success': False, 'error': result}), 400
        
        # Generate and send OTP
        otp = auth_service.generate_otp()
        auth_service.store_otp(formatted_phone, otp)
        
        # Send OTP via SMS
        otp_message = sms_service.generate_otp_message(otp)
        sms_sent = sms_service.send_sms(formatted_phone, otp_message)
        
        response_data = {
            'success': True,
            'message': 'OTP sent successfully' if sms_sent else 'User registered, OTP generated'
        }
        
        # Include debug OTP only in development mode
        if not Config.USE_REAL_SMS:
            response_data['debug_otp'] = otp
        
        return jsonify(response_data)
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/verify', methods=['POST'])
def verify_otp():
    """Verify OTP and activate user"""
    try:
        data = request.json
        phone = data.get('phone', '').strip()
        otp = data.get('otp', '').strip()
        
        if not phone or not otp:
            return jsonify({
                'verified': False,
                'error': 'Phone and OTP are required'
            }), 400
        
        # Validate phone format
        valid_phone, formatted_phone = auth_service.validate_phone_number(phone)
        if not valid_phone:
            return jsonify({
                'verified': False,
                'error': 'Invalid phone number format'
            }), 400
        
        # Verify OTP
        otp_valid, message = auth_service.verify_otp(formatted_phone, otp)
        
        if not otp_valid:
            return jsonify({
                'verified': False,
                'error': message
            }), 400
        
        # Mark user as verified
        if not auth_service.verify_user(formatted_phone):
            return jsonify({
                'verified': False,
                'error': 'Failed to verify user'
            }), 500
        
        # Get user details for welcome message
        user = db_manager.find_user_by_phone(formatted_phone)
        if user:
            welcome_message = sms_service.generate_welcome_message(
                user['name'], 
                user['area']
            )
            sms_service.send_sms(formatted_phone, welcome_message)
        
        return jsonify({
            'verified': True,
            'message': 'User verified successfully'
        })
        
    except Exception as e:
        return jsonify({'verified': False, 'error': str(e)}), 500

# ======================
# STAFF AUTHENTICATION ROUTES
# ======================

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Staff login page and authentication"""
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
            <p>Health Worker Portal v6.0</p>
            <small>Real Users Only - No Demo Data</small>
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
            <strong>Default Credentials:</strong><br>
            Username: <strong>admin</strong><br>
            Password: <strong>admin123</strong>
        </div>
    </div>
</body>
</html>
        ''', 
        error=request.args.get('error'), 
        use_mongodb=db_manager.use_mongodb,
        ml_active=ml_service.is_available()
        )
    
    # Handle POST - Login authentication
    username = request.form['username']
    password = request.form['password']
    
    success, user, message = auth_service.authenticate_staff(username, password)
    
    if success:
        auth_service.create_session(user)
        return redirect(url_for('health_worker_interface'))
    else:
        return redirect(url_for('login', error=message))

@app.route('/logout')
def logout():
    """Staff logout"""
    auth_service.clear_session()
    return redirect(url_for('login'))

# ======================
# ALERT MANAGEMENT ROUTES
# ======================

@app.route('/broadcast/areas')
@auth_service.login_required
def get_broadcast_areas():
    """Get areas with user counts for broadcasting"""
    try:
        areas_data = db_manager.get_area_stats()
        areas = [{'area': area['_id'], 'user_count': area['user_count']} for area in areas_data]
        return jsonify({'success': True, 'areas': areas})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/broadcast', methods=['POST'])
@auth_service.login_required
def broadcast_alert():
    """Broadcast alert to users"""
    try:
        data = request.json
        alert_type = data.get('alert_type')
        area = data.get('area')
        
        # Validate alert data
        valid, errors = alert_service.validate_alert_data(alert_type, area, **data)
        if not valid:
            return jsonify({
                'success': False,
                'error': '; '.join(errors)
            }), 400
        
        # Broadcast based on alert type
        if alert_type == 'health':
            success, message, sent_count = alert_service.broadcast_health_alert(
                area, data.get('condition'), data.get('cases')
            )
        elif alert_type == 'safety':
            success, message, sent_count = alert_service.broadcast_safety_alert(
                area, data.get('crime_type')
            )
        elif alert_type == 'custom':
            success, message, sent_count = alert_service.broadcast_custom_alert(
                area, data.get('message')
            )
        else:
            return jsonify({
                'success': False,
                'error': 'Invalid alert type'
            }), 400
        
        if success:
            return jsonify({
                'success': True,
                'message': message,
                'recipients_count': sent_count
            })
        else:
            return jsonify({
                'success': False,
                'error': message
            }), 500
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/alerts/history')
def get_alerts_history():
    """Get alert history for a specific area"""
    try:
        area = request.args.get('area')
        limit = int(request.args.get('limit', 50))
        alert_type = request.args.get('type')
        
        if not area:
            return jsonify({'success': False, 'error': 'Area parameter required'}), 400
        
        success, result = alert_service.get_alert_history(area, limit, alert_type)
        
        if success:
            return jsonify({
                'success': True,
                'alerts': result,
                'count': len(result),
                'area': area,
                'type_filter': alert_type
            })
        else:
            return jsonify({'success': False, 'error': result}), 500
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/alerts/recent')
def get_recent_alerts():
    """Get recent alerts across all areas"""
    try:
        hours = int(request.args.get('hours', 24))
        area = request.args.get('area')
        
        success, result = alert_service.get_recent_alerts(hours, area)
        
        if success:
            return jsonify({
                'success': True,
                'alerts': result,
                'count': len(result),
                'period_hours': hours,
                'area_filter': area
            })
        else:
            return jsonify({'success': False, 'error': result}), 500
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ======================
# ML PREDICTION ROUTES
# ======================

@app.route('/predictions/generate', methods=['POST'])
@auth_service.login_required
def generate_predictions():
    """Manually trigger ML predictions"""
    try:
        if not ml_service.is_available():
            return jsonify({
                'success': False,
                'error': 'ML service not available'
            }), 503
        
        data = request.json or {}
        area = data.get('area')
        
        if area:
            results = ml_service.generate_predictions_for_area(area)
            return jsonify({
                'success': True,
                'message': f'Generated predictions for {area}',
                'predictions': results,
                'count': len(results)
            })
        else:
            results = ml_service.generate_predictions_for_all_areas()
            return jsonify({
                'success': True,
                'message': 'Generated predictions for all areas',
                'count': len(results)
            })
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/predictions/latest')
def get_latest_predictions():
    """Get latest ML predictions"""
    try:
        area = request.args.get('area')
        limit = int(request.args.get('limit', 20))
        
        predictions = ml_service.get_latest_predictions(area, limit)
        
        return jsonify({
            'success': True,
            'predictions': predictions,
            'count': len(predictions)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/predictions/accuracy')
def get_prediction_accuracy():
    """Get prediction accuracy metrics"""
    try:
        accuracy_data = ml_service.get_prediction_accuracy()
        return jsonify({
            'success': True,
            'accuracy': accuracy_data
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ======================
# SYSTEM MONITORING ROUTES
# ======================

@app.route('/system/health')
def system_health():
    """Get comprehensive system health status"""
    try:
        stats = db_manager.get_stats()
        
        health_status = {
            'database': {
                'status': 'connected',
                'type': 'MongoDB Atlas' if db_manager.use_mongodb else 'JSON Files',
                'last_check': datetime.utcnow().isoformat()
            },
            'ml_models': ml_service.get_system_health(),
            'sms_service': {
                'status': 'connected' if sms_service.is_available() else 'disabled',
                'provider': 'Twilio' if Config.USE_REAL_SMS else 'Mock SMS'
            },
            'users': {
                'total': stats['users']['total'],
                'verified': stats['users']['verified'],
                'active': stats['users']['active']
            },
            'recent_activity': stats.get('recent_activity', {}),
            'features': {
                'real_users_only': True,
                'demo_data_disabled': True,
                'modular_architecture': True
            }
        }
        
        return jsonify({
            'success': True,
            'health': health_status,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/stats')
def get_stats():
    """Get system statistics"""
    try:
        stats = db_manager.get_stats()
        stats['database'] = 'MongoDB Atlas' if db_manager.use_mongodb else 'JSON Files'
        stats['ml_active'] = ml_service.is_available()
        stats['sms_active'] = sms_service.is_available()
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ======================
# STAFF DASHBOARD
# ======================

@app.route('/health-worker')
@auth_service.login_required
def health_worker_interface():
    """Health worker dashboard interface"""
    current_user = auth_service.get_current_user()
    
    return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>Alatem - Real Users Dashboard</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center; }
        .header h1 { margin: 0; }
        .logout-btn { background: rgba(255,255,255,0.2); color: white; border: 1px solid rgba(255,255,255,0.3); padding: 8px 16px; border-radius: 5px; text-decoration: none; font-size: 14px; }
        .container { max-width: 1400px; margin: 0 auto; }
        .card { background: white; padding: 25px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); margin-bottom: 20px; }
        .warning-banner { background: #fff3cd; border: 2px solid #ffc107; border-radius: 8px; padding: 15px; margin-bottom: 20px; }
        .warning-banner h3 { margin: 0 0 10px 0; color: #856404; }
        .warning-banner p { margin: 0; color: #856404; }
        .ml-section { background: linear-gradient(135deg, #e8f4fd 0%, #f0f8ff 100%); border: 2px solid #3498db; border-radius: 8px; padding: 20px; margin-bottom: 20px; }
        .broadcast-section { background: #fff3cd; border: 1px solid #ffeaa7; border-radius: 8px; padding: 20px; }
        .predictions-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 15px; margin: 15px 0; }
        .prediction-card { background: white; padding: 15px; border-radius: 8px; border-left: 4px solid #3498db; }
        .risk-high { border-left-color: #e74c3c; background: #fff5f5; }
        .risk-medium { border-left-color: #f39c12; background: #fffdf5; }
        .risk-low { border-left-color: #27ae60; background: #f8fff8; }
        button { background: #3498db; color: white; padding: 12px 24px; border: none; border-radius: 6px; cursor: pointer; font-size: 16px; font-weight: 600; transition: background 0.3s; margin-right: 10px; margin-bottom: 10px; }
        button:hover { background: #2980b9; }
        button.danger { background: #e74c3c; }
        button.warning { background: #f39c12; }
        button.success { background: #27ae60; }
        select, textarea { width: 100%; padding: 12px; border: 2px solid #ddd; border-radius: 6px; font-size: 14px; box-sizing: border-box; margin-bottom: 15px; }
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
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 15px 0; }
        .stat-card { background: white; padding: 15px; border-radius: 8px; text-align: center; border: 1px solid #ddd; }
        .stat-card .number { font-size: 28px; font-weight: bold; color: #3498db; }
        .stat-card .label { font-size: 12px; color: #666; text-transform: uppercase; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div>
                <h1>🏥 Alatem Dashboard v6.0</h1>
                <div>Real Users Only • No Demo Data • Modular Architecture</div>
                <small>Welcome, {{ full_name }}</small>
            </div>
            <a href="/logout" class="logout-btn">Logout</a>
        </div>
        
        <div class="warning-banner">
            <h3>⚠️ Real Users Only Mode</h3>
            <p>This system now only works with actual user registrations. No demo or mock data is created. Users must register through the mobile app and verify their phone numbers with real OTP codes.</p>
        </div>
        
        <div class="tabs">
            <button class="tab active" onclick="showTab('overview')">📊 Overview</button>
            <button class="tab" onclick="showTab('predictions')">🔮 ML Predictions</button>
            <button class="tab" onclick="showTab('alerts')">📡 Send Alerts</button>
        </div>
        
        <!-- Overview Tab -->
        <div id="overview" class="tab-content active">
            <div class="card">
                <h3>📊 System Overview</h3>
                <div id="systemStats">
                    <div class="loading">📊 Loading system statistics...</div>
                </div>
            </div>
        </div>
        
        <!-- ML Predictions Tab -->
        <div id="predictions" class="tab-content">
            <div class="ml-section">
                <h3>🤖 Machine Learning Predictions</h3>
                <p>AI-powered outbreak predictions based on real user registrations and health data.</p>
                
                <button class="success" onclick="generatePredictions()">🔮 Generate Predictions</button>
                <button onclick="loadPredictions()">📊 Refresh Predictions</button>
                
                <div id="predictionsContainer">
                    <div class="loading">🔮 Loading ML predictions...</div>
                </div>
            </div>
        </div>
        
        <!-- Manual Alerts Tab -->
        <div id="alerts" class="tab-content">
            <div class="card">
                <div class="broadcast-section">
                    <h3>📡 Alert Broadcasting</h3>
                    <p>Send alerts to verified users in specific areas.</p>
                    
                    <div id="areaStats">
                        <button onclick="loadAreaStats()">Load User Statistics by Area</button>
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
                        <option value="CROIX_DES_BOUQUETS">Croix des Bouquets</option>
                        <option value="PORT_AU_PRINCE">Port-au-Prince</option>
                    </select>
                    
                    <div style="display: flex; gap: 10px; flex-wrap: wrap; margin: 15px 0;">
                        <h4>Quick Health Alerts:</h4>
                        <button class="danger" onclick="broadcastHealthAlert('cholera')">🚨 Cholera Alert</button>
                        <button class="warning" onclick="broadcastHealthAlert('fever')">🌡️ Fever Alert</button>
                        <button class="warning" onclick="broadcastHealthAlert('diarrhea')">💧 Diarrhea Alert</button>
                        <button class="warning" onclick="broadcastHealthAlert('malnutrition')">⚠️ Malnutrition Alert</button>
                    </div>
                    
                    <div style="display: flex; gap: 10px; flex-wrap: wrap; margin: 15px 0;">
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
    </div>
    
    <script>
        let currentTab = 'overview';
        
        function showTab(tabName) {
            document.querySelectorAll('.tab-content').forEach(content => {
                content.classList.remove('active');
            });
            document.querySelectorAll('.tab').forEach(tab => {
                tab.classList.remove('active');
            });
            
            document.getElementById(tabName).classList.add('active');
            event.target.classList.add('active');
            currentTab = tabName;
            
            if (tabName === 'overview') {
                loadSystemStats();
            } else if (tabName === 'predictions') {
                loadPredictions();
            } else if (tabName === 'alerts') {
                loadAreaStats();
            }
        }
        
        function showMessage(message, type = 'success') {
            const alert = document.createElement('div');
            alert.className = type;
            alert.textContent = message;
            const container = document.querySelector('.container');
            container.insertBefore(alert, container.children[2]);
            setTimeout(() => alert.remove(), 5000);
        }
        
        async function loadSystemStats() {
            try {
                const response = await fetch('/stats');
                const data = await response.json();
                
                let html = `
                    <div class="stats-grid">
                        <div class="stat-card">
                            <div class="number">${data.users.total}</div>
                            <div class="label">Total Users</div>
                        </div>
                        <div class="stat-card">
                            <div class="number">${data.users.verified}</div>
                            <div class="label">Verified Users</div>
                        </div>
                        <div class="stat-card">
                            <div class="number">${data.reports.alerts_sent}</div>
                            <div class="label">Alerts Sent</div>
                        </div>
                        <div class="stat-card">
                            <div class="number">${data.reports.predictions || 0}</div>
                            <div class="label">ML Predictions</div>
                        </div>
                        <div class="stat-card">
                            <div class="number">${data.recent_activity.alerts_sent_24h}</div>
                            <div class="label">Alerts (24h)</div>
                        </div>
                        <div class="stat-card">
                            <div class="number">${data.ml_active ? 'Active' : 'Disabled'}</div>
                            <div class="label">ML Models</div>
                        </div>
                    </div>
                `;
                
                if (data.users.verified === 0) {
                    html += `
                        <div class="warning-banner" style="margin-top: 20px;">
                            <h3>🚀 Getting Started</h3>
                            <p>No verified users yet. Have users register through the mobile app to start receiving alerts. Each user must complete phone verification before they can receive SMS alerts.</p>
                        </div>
                    `;
                }
                
                document.getElementById('systemStats').innerHTML = html;
            } catch (error) {
                document.getElementById('systemStats').innerHTML = '<div class="error">Error loading stats: ' + error + '</div>';
            }
        }
        
        async function loadPredictions() {
            try {
                const response = await fetch('/predictions/latest');
                const data = await response.json();
                
                if (data.success) {
                    displayPredictions(data.predictions);
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
                container.innerHTML = '<div class="loading">No predictions available. Click "Generate Predictions" to create ML forecasts.</div>';
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
                        <small>Generated: ${new Date(pred.timestamp).toLocaleString()}</small>
                    </div>`;
                }
            });
            
            html += '</div>';
            container.innerHTML = html;
        }
        
        async function generatePredictions() {
            try {
                const response = await fetch('/predictions/generate', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({})
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
        
        async function loadAreaStats() {
            try {
                const response = await fetch('/broadcast/areas');
                const data = await response.json();
                
                let html = '<div class="area-stats">';
                if (data.areas && data.areas.length > 0) {
                    data.areas.forEach(area => {
                        html += `<div class="area-card">
                            <h4>${area.area.replace(/_/g, ' ')}</h4>
                            <div class="count">${area.user_count}</div>
                            <small>verified users</small>
                        </div>`;
                    });
                } else {
                    html += '<div class="warning-banner"><h3>📱 No Verified Users</h3><p>Users must register through the mobile app and verify their phone numbers before they can receive alerts.</p></div>';
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
            
            if (!confirm(`Send ${condition} alert to all verified users in ${area}?`)) return;
            
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
            
            if (!confirm(`Send ${crimeType} alert to all verified users in ${area}?`)) return;
            
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
            
            if (!confirm(`Send custom message to all verified users in ${area}?\\n\\nMessage: "${message}"`)) return;
            
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
            loadSystemStats();
        });
    </script>
</body>
</html>
    ''',
    full_name=current_user.get('full_name', 'User'),
    use_mongodb=db_manager.use_mongodb,
    ml_active=ml_service.is_available()
    )

# ======================
# STARTUP INITIALIZATION
# ======================

def initialize_app():
    """Initialize application on startup"""
    print(f"🚀 Starting Alatem Health Alert System v6.0...")
    print(f"📊 Database: {'MongoDB Atlas' if db_manager.use_mongodb else 'JSON Files'}")
    
    # Validate configuration
    config_errors = Config.validate_config()
    if config_errors:
        print("⚠️ Configuration warnings:")
        for error in config_errors:
            print(f"   - {error}")
    
    # Ensure directories exist
    ensure_directories()
    
    # Create default admin user
    auth_service.create_default_admin()
    
    # Start ML prediction scheduler if available
    if ml_service.is_available():
        ml_service.start_prediction_scheduler()
    
    print("\n" + "="*70)
    print("🏥 ALATEM HEALTH ALERT SYSTEM v6.0 - REAL USERS ONLY")
    print("="*70)
    print("🔐 Staff Login: http://localhost:5000/login")
    print("📱 Dashboard: http://localhost:5000/health-worker")
    print("🔗 API: http://localhost:5000/")
    print("📊 Stats: http://localhost:5000/stats")
    print("🏥 System Health: http://localhost:5000/system/health")
    print("📱 SMS History API: http://localhost:5000/alerts/history?area=DELMAS")
    print("="*70)
    print(f"💾 Database: {'MongoDB Atlas (Production)' if db_manager.use_mongodb else 'JSON Files (Development)'}")
    print(f"📱 SMS Service: {'Twilio (Live)' if Config.USE_REAL_SMS else 'Mock SMS (Development)'}")
    print(f"🤖 ML Models: {'✅ Active' if ml_service.is_available() else '⚠️ Not Available'}")
    print("🚫 Demo Data: DISABLED - Real users only")
    print("🔑 Default Login: admin / admin123")
    print("="*70)

if __name__ == '__main__':
    initialize_app()
    app.run(
        debug=Config.DEBUG,
        host=Config.HOST,
        port=Config.PORT
    )