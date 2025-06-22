import hashlib
import uuid
import random
from datetime import datetime, timedelta
from functools import wraps
from flask import session, jsonify

class AuthService:
    def __init__(self, db_manager):
        self.db = db_manager
        self.otp_store = {}  # In production, use Redis or database
    
    def generate_id(self):
        """Generate unique ID"""
        return str(uuid.uuid4())
    
    def hash_password(self, password):
        """Hash password using SHA256"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def verify_password(self, password, password_hash):
        """Verify password against hash"""
        return hashlib.sha256(password.encode()).hexdigest() == password_hash
    
    def generate_otp(self):
        """Generate 6-digit OTP"""
        return random.randint(100000, 999999)
    
    def store_otp(self, phone, otp, expires_minutes=5):
        """Store OTP with expiration"""
        self.otp_store[phone] = {
            'otp': otp,
            'expires': datetime.now() + timedelta(minutes=expires_minutes),
            'attempts': 0
        }
    
    def verify_otp(self, phone, otp):
        """Verify OTP"""
        stored_otp = self.otp_store.get(phone)
        
        if not stored_otp:
            return False, "No OTP found for this phone number"
        
        if datetime.now() > stored_otp['expires']:
            del self.otp_store[phone]
            return False, "OTP has expired"
        
        if stored_otp['attempts'] >= 3:
            del self.otp_store[phone]
            return False, "Too many failed attempts"
        
        if str(stored_otp['otp']) != str(otp):
            stored_otp['attempts'] += 1
            return False, "Invalid OTP"
        
        # OTP verified successfully
        del self.otp_store[phone]
        return True, "OTP verified successfully"
    
    def create_user(self, name, phone, area, latitude=None, longitude=None):
        """Create new user (unverified)"""
        user_data = {
            "id": self.generate_id(),
            "name": name.strip(),
            "phone": phone.strip(),
            "area": area,
            "latitude": latitude,
            "longitude": longitude,
            "verified": False,
            "active": True,
            "created_at": datetime.utcnow().isoformat(),
            "verified_at": None
        }
        
        try:
            self.db.save_user(user_data)
            return True, user_data
        except Exception as e:
            return False, str(e)
    
    def verify_user(self, phone):
        """Mark user as verified"""
        try:
            result = self.db.update_user_verified(phone)
            return result is not False
        except Exception as e:
            print(f"Error verifying user: {e}")
            return False
    
    def create_staff_user(self, username, password, full_name, role="health_worker", organization="Alatem"):
        """Create staff user"""
        if self.db.find_staff_user(username):
            return False, "Username already exists"
        
        staff_data = {
            "id": self.generate_id(),
            "username": username,
            "password_hash": self.hash_password(password),
            "full_name": full_name,
            "role": role,
            "organization": organization,
            "is_active": True,
            "created_at": datetime.utcnow().isoformat(),
            "last_login": None
        }
        
        try:
            self.db.save_staff_user(staff_data)
            return True, staff_data
        except Exception as e:
            return False, str(e)
    
    def authenticate_staff(self, username, password):
        """Authenticate staff user"""
        user = self.db.find_staff_user(username)
        
        if not user:
            return False, None, "User not found"
        
        if not self.verify_password(password, user['password_hash']):
            return False, None, "Invalid password"
        
        return True, user, "Authentication successful"
    
    def create_session(self, user):
        """Create user session"""
        if self.db.use_mongodb:
            session['staff_user_id'] = str(user['_id'])
            self.db.update_staff_login(user['_id'], datetime.utcnow())
        else:
            session['staff_user_id'] = user['id']
            self.db.update_staff_login(user['id'], datetime.utcnow())
        
        session['staff_username'] = user['username']
        session['staff_role'] = user['role']
        session['staff_full_name'] = user['full_name']
    
    def clear_session(self):
        """Clear user session"""
        session.clear()
    
    def get_current_user(self):
        """Get current logged-in user info"""
        return {
            'user_id': session.get('staff_user_id'),
            'username': session.get('staff_username'),
            'role': session.get('staff_role'),
            'full_name': session.get('staff_full_name')
        }
    
    def is_authenticated(self):
        """Check if user is authenticated"""
        return 'staff_user_id' in session
    
    def login_required(self, f):
        """Decorator for routes that require authentication"""
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not self.is_authenticated():
                return jsonify({'error': 'Authentication required'}), 401
            return f(*args, **kwargs)
        return decorated_function
    
    def create_default_admin(self):
        """Create default admin user if none exists"""
        admin = self.db.find_staff_user('admin')
        if not admin:
            success, result = self.create_staff_user(
                username='admin',
                password='admin123',
                full_name='System Administrator',
                role='admin',
                organization='Alatem System'
            )
            if success:
                print("✅ Default admin user created (username: admin, password: admin123)")
            else:
                print(f"❌ Failed to create admin user: {result}")
    
    def validate_phone_number(self, phone):
        """Validate phone number format"""
        # Remove spaces, dashes, parentheses
        clean_phone = phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
        
        # Check if it's a valid international format
        if clean_phone.startswith('+'):
            # International format: +CountryCode followed by 8-15 digits
            if len(clean_phone) >= 10 and len(clean_phone) <= 16 and clean_phone[1:].isdigit():
                return True, clean_phone
        
        # Check if it's just digits (add + prefix)
        if clean_phone.isdigit() and len(clean_phone) >= 8 and len(clean_phone) <= 15:
            return True, f"+{clean_phone}"
        
        return False, "Invalid phone number format"
    
    def cleanup_expired_otps(self):
        """Clean up expired OTPs (call periodically)"""
        current_time = datetime.now()
        expired_phones = [
            phone for phone, data in self.otp_store.items() 
            if current_time > data['expires']
        ]
        
        for phone in expired_phones:
            del self.otp_store[phone]
        
        if expired_phones:
            print(f"🧹 Cleaned up {len(expired_phones)} expired OTPs")