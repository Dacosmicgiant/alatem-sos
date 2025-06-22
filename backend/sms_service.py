import time
from datetime import datetime
from config import Config

# Conditional Twilio import
try:
    from twilio.rest import Client as TwilioClient
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False

class SMSService:
    def __init__(self):
        self.client = None
        self.phone_number = None
        self.setup_twilio()
    
    def setup_twilio(self):
        """Initialize Twilio client"""
        if not TWILIO_AVAILABLE:
            print("⚠️ Twilio SDK not available")
            return
        
        if not Config.USE_REAL_SMS:
            print("📱 SMS service in mock mode (USE_REAL_SMS=False)")
            return
        
        if not all([Config.TWILIO_SID, Config.TWILIO_TOKEN, Config.TWILIO_PHONE]):
            print("⚠️ Twilio credentials incomplete")
            return
        
        try:
            self.client = TwilioClient(Config.TWILIO_SID, Config.TWILIO_TOKEN)
            self.phone_number = Config.TWILIO_PHONE
            print("✅ Twilio SMS service initialized")
        except Exception as e:
            print(f"❌ Twilio initialization failed: {e}")
    
    def send_sms(self, phone, message):
        """Send SMS message"""
        try:
            if self.client and self.phone_number:
                # Send real SMS
                message_obj = self.client.messages.create(
                    body=message,
                    from_=self.phone_number,
                    to=phone
                )
                print(f"✅ SMS sent to {phone}: {message[:50]}...")
                return True
            else:
                # Mock SMS (for development/testing)
                print(f"📱 MOCK SMS to {phone}: {message}")
                return True
                
        except Exception as e:
            print(f"❌ Failed to send SMS to {phone}: {e}")
            return False
    
    def send_bulk_sms(self, recipients, message, delay=0.1):
        """Send SMS to multiple recipients with rate limiting"""
        sent_count = 0
        failed_count = 0
        
        for recipient in recipients:
            phone = recipient.get('phone') if isinstance(recipient, dict) else recipient
            
            if self.send_sms(phone, message):
                sent_count += 1
            else:
                failed_count += 1
            
            # Rate limiting to avoid overwhelming Twilio
            if delay > 0:
                time.sleep(delay)
        
        print(f"📊 Bulk SMS completed: {sent_count} sent, {failed_count} failed")
        return sent_count, failed_count
    
    def generate_otp_message(self, otp, app_name="Alatem"):
        """Generate OTP verification message in Haitian Creole"""
        return f"Kòd verifikasyon {app_name}: {otp}. Pa pataje kòd sa a ak pèsonn."
    
    def generate_welcome_message(self, name, area):
        """Generate welcome message after verification"""
        return f"Byenveni nan Alatem, {name}! Ou ap resevwa alèt sante ak sekirite nan {area}."
    
    def get_health_alert_message(self, area, condition, cases=None):
        """Generate health alert message in Haitian Creole"""
        messages = {
            'cholera': f"🚨 ALÈT SANTE: {cases if cases else 'Ka'} cholera nan {area}. Bwè dlo pwòp, lave men nou. Ale kay doktè si nou gen simptòm.",
            'malnutrition': f"⚠️ ALÈT SANTE: {cases if cases else 'Ka'} malnitrisyon nan {area}. Chèche manje ak vitamin. Mennen timoun yo kay doktè.",
            'fever': f"🌡️ ALÈT SANTE: {cases if cases else 'Ka'} lafyèv nan {area}. Rete lakay si nou malad. Bwè dlo anpil.",
            'diarrhea': f"💧 ALÈT SANTE: {cases if cases else 'Ka'} dyare nan {area}. Bwè dlo pwòp, lave men nou.",
            'respiratory': f"🫁 ALÈT SANTE: {cases if cases else 'Ka'} pwoblèm respiratwa nan {area}. Rete lakay, evite foul moun."
        }
        return messages.get(condition, f"🚨 ALÈT SANTE: {condition} nan {area}")
    
    def get_safety_alert_message(self, area, crime_type):
        """Generate safety alert message in Haitian Creole"""
        messages = {
            'kidnapping': f"🚨 SEKIRITE: Kidnapping nan {area}. Pa mache pou kont nou. Evite kote yo ki izole.",
            'armed_robbery': f"⚠️ SEKIRITE: Volè ak zam nan {area}. Pa montre objè ki gen valè. Mache nan gwoup.",
            'gang_shooting': f"🔫 DANJE: Bandi k ap tire nan {area}. Rete lakay. Pa soti.",
            'street_violence': f"⚠️ SEKIRITE: Vyolans nan lari nan {area}. Evite kote yo ki gen anpil moun.",
            'home_invasion': f"🏠 SEKIRITE: Anvazyòn lakay nan {area}. Asire pòt ak fenèt yo."
        }
        return messages.get(crime_type, f"⚠️ SEKIRITE: Danje nan {area}. Fè atansyon.")
    
    def is_available(self):
        """Check if SMS service is available"""
        return self.client is not None or not Config.USE_REAL_SMS