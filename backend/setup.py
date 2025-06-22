#!/usr/bin/env python3
"""
Alatem Backend Setup Script
Helps initialize the system for first-time use
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def print_banner():
    """Print welcome banner"""
    print("=" * 60)
    print("🏥 ALATEM HEALTH ALERT SYSTEM - SETUP v6.0")
    print("=" * 60)
    print("This script will help you set up the Alatem backend.")
    print()

def check_python_version():
    """Check if Python version is adequate"""
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 or higher is required")
        print(f"   Current version: {sys.version}")
        return False
    print(f"✅ Python version: {sys.version.split()[0]}")
    return True

def check_pip():
    """Check if pip is available"""
    try:
        subprocess.run([sys.executable, "-m", "pip", "--version"], 
                      capture_output=True, check=True)
        print("✅ pip is available")
        return True
    except subprocess.CalledProcessError:
        print("❌ pip is not available")
        return False

def install_dependencies():
    """Install Python dependencies"""
    print("\n📦 Installing dependencies...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
                      check=True)
        print("✅ Dependencies installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
        return False

def setup_environment():
    """Setup environment file"""
    env_example = Path(".env.example")
    env_file = Path(".env")
    
    if env_file.exists():
        print("✅ .env file already exists")
        return True
    
    if env_example.exists():
        print("\n🔧 Setting up environment configuration...")
        shutil.copy(env_example, env_file)
        print("✅ Created .env file from template")
        print("📝 Please edit .env file with your configuration")
        return True
    else:
        print("⚠️ .env.example not found, creating basic .env file...")
        basic_env = """# Alatem Backend Configuration
SECRET_KEY=dev-secret-key-change-in-production
DEBUG=True
USE_REAL_SMS=False
CREATE_DEMO_DATA=False
"""
        with open(env_file, 'w') as f:
            f.write(basic_env)
        print("✅ Created basic .env file")
        return True

def create_directories():
    """Create necessary directories"""
    print("\n📁 Creating directories...")
    directories = ['data', 'ml_models', 'dataset', 'logs']
    
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
        print(f"✅ Created {directory}/ directory")

def check_optional_services():
    """Check status of optional services"""
    print("\n🔍 Checking optional services...")
    
    # Check if MongoDB URI is configured
    try:
        from dotenv import load_dotenv
        load_dotenv()
        mongodb_uri = os.getenv('MONGODB_URI')
        if mongodb_uri:
            print("✅ MongoDB URI configured")
        else:
            print("⚠️ MongoDB URI not configured (will use JSON files)")
    except ImportError:
        print("⚠️ python-dotenv not available")
    
    # Check Twilio configuration
    twilio_sid = os.getenv('TWILIO_SID')
    twilio_token = os.getenv('TWILIO_TOKEN')
    if twilio_sid and twilio_token:
        print("✅ Twilio SMS configured")
    else:
        print("⚠️ Twilio SMS not configured (will use mock SMS)")

def generate_ml_data():
    """Offer to generate ML training data"""
    print("\n🤖 Machine Learning Setup")
    
    # Check if datasets exist
    health_data = Path("dataset/haiti_health_data.csv")
    crime_data = Path("dataset/haiti_crime_data.csv")
    
    if health_data.exists() and crime_data.exists():
        print("✅ ML datasets already exist")
        
        # Check if models are trained
        model_files = [
            "ml_models/outbreak_classifier.pkl",
            "ml_models/cases_regressor.pkl",
            "ml_models/label_encoders.pkl",
            "ml_models/scaler.pkl",
            "ml_models/feature_cols.pkl"
        ]
        
        if all(Path(f).exists() for f in model_files):
            print("✅ ML models already trained")
        else:
            print("📊 ML models not found")
            train = input("Do you want to train ML models now? (y/N): ").lower()
            if train == 'y':
                train_ml_models()
    else:
        print("📊 ML datasets not found")
        generate = input("Do you want to generate synthetic training data? (y/N): ").lower()
        if generate == 'y':
            generate_synthetic_data()
            train = input("Do you want to train ML models now? (y/N): ").lower()
            if train == 'y':
                train_ml_models()

def generate_synthetic_data():
    """Generate synthetic training data"""
    print("🎲 Generating synthetic datasets...")
    try:
        subprocess.run([sys.executable, "data_generator.py"], check=True)
        print("✅ Synthetic datasets generated")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to generate datasets: {e}")
    except FileNotFoundError:
        print("❌ data_generator.py not found")

def train_ml_models():
    """Train ML models"""
    print("🧠 Training ML models...")
    try:
        subprocess.run([sys.executable, "ml_models.py"], check=True)
        print("✅ ML models trained successfully")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to train models: {e}")
    except FileNotFoundError:
        print("❌ ml_models.py not found")

def test_installation():
    """Test the installation"""
    print("\n🧪 Testing installation...")
    
    try:
        # Try importing main modules
        from config import Config
        from database import DatabaseManager
        from sms_service import SMSService
        from auth import AuthService
        print("✅ All modules can be imported")
        
        # Test configuration
        Config.validate_config()
        print("✅ Configuration is valid")
        
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        return False

def show_next_steps():
    """Show next steps for the user"""
    print("\n🎯 SETUP COMPLETE!")
    print("=" * 60)
    print("Next steps:")
    print()
    print("1. 📝 Edit .env file with your configuration:")
    print("   - Set SECRET_KEY for production")
    print("   - Configure MongoDB URI (optional)")
    print("   - Configure Twilio for real SMS (optional)")
    print()
    print("2. 🚀 Start the backend server:")
    print("   python app.py")
    print()
    print("3. 📱 Setup the mobile app to register users")
    print()
    print("4. 🔐 Access staff dashboard:")
    print("   http://localhost:5000/login")
    print("   Default: admin / admin123")
    print()
    print("5. 📊 Monitor system health:")
    print("   http://localhost:5000/system/health")
    print()
    print("=" * 60)
    print("📚 For detailed documentation, see README.md")
    print("🆘 For support, check the troubleshooting section")

def main():
    """Main setup function"""
    print_banner()
    
    # System checks
    if not check_python_version():
        sys.exit(1)
    
    if not check_pip():
        sys.exit(1)
    
    # Installation steps
    print("\n🛠️ Starting setup process...")
    
    steps = [
        ("Installing dependencies", install_dependencies),
        ("Setting up environment", setup_environment),
        ("Creating directories", create_directories),
        ("Checking optional services", check_optional_services),
        ("Testing installation", test_installation)
    ]
    
    for step_name, step_func in steps:
        if not step_func():
            print(f"\n❌ Setup failed at: {step_name}")
            sys.exit(1)
    
    # Optional ML setup
    generate_ml_data()
    
    # Show completion
    show_next_steps()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ Setup interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)