import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    # Flask Configuration
    SECRET_KEY = os.getenv('SECRET_KEY', 'alatem-secret-key-change-in-production')
    
    # Database Configuration
    MONGODB_URI = os.getenv('MONGODB_URI')
    DATA_DIR = 'data'
    
    # Twilio Configuration
    TWILIO_SID = os.getenv('TWILIO_SID')
    TWILIO_TOKEN = os.getenv('TWILIO_TOKEN')
    TWILIO_PHONE = os.getenv('TWILIO_PHONE')
    
    # ML Configuration
    ML_MODELS_DIR = 'ml_models'
    DATASET_DIR = 'dataset'
    
    # App Configuration
    DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'
    HOST = os.getenv('HOST', '0.0.0.0')
    PORT = int(os.getenv('PORT', 5000))
    
    # Feature Flags
    USE_REAL_SMS = os.getenv('USE_REAL_SMS', 'False').lower() == 'true'
    CREATE_DEMO_DATA = os.getenv('CREATE_DEMO_DATA', 'False').lower() == 'true'
    
    # Haiti Areas Configuration
    HAITI_AREAS = [
        'CITE_SOLEIL',
        'DELMAS', 
        'TABARRE',
        'MARTISSANT',
        'CARREFOUR',
        'PETIONVILLE',
        'CROIX_DES_BOUQUETS',
        'PORT_AU_PRINCE'
    ]
    
    # Health Conditions
    HEALTH_CONDITIONS = [
        'cholera',
        'malnutrition', 
        'fever',
        'diarrhea',
        'respiratory'
    ]
    
    # Crime Types
    CRIME_TYPES = [
        'kidnapping',
        'armed_robbery',
        'gang_shooting',
        'street_violence',
        'home_invasion'
    ]
    
    @classmethod
    def validate_config(cls):
        """Validate required configuration"""
        errors = []
        
        if cls.USE_REAL_SMS and not all([cls.TWILIO_SID, cls.TWILIO_TOKEN, cls.TWILIO_PHONE]):
            errors.append("Twilio credentials required when USE_REAL_SMS=True")
        
        return errors