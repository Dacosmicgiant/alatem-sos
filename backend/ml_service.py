# D:\VEDANT\projects\mobile\alatem\backend\ml_service.py

import os
import joblib
from datetime import datetime, timedelta
import random

# Assuming ml_models.py exists and contains these classes/functions
from ml_models import HealthOutbreakPredictor, CrimePredictor, train_all_models, check_model_files

class MLService:
    def __init__(self, db_manager, alert_service):
        self.db_manager = db_manager
        self.alert_service = alert_service
        self.health_predictor = None
        self.crime_predictor = None
        self.models_loaded = False
        self._load_models() # Attempt to load models on initialization

    def _load_models(self):
        """Attempts to load trained ML models from disk."""
        print("MLService: Attempting to load models...")
        try:
            # You would typically have a path to your trained models
            # For example: model_path_health = os.path.join(Config.ML_MODELS_DIR, 'health_model.pkl')
            # For this example, let's assume check_model_files just verifies existence
            
            # This is a simplification; in a real app, you'd load actual Joblib models
            if check_model_files(): # This function (from ml_models) should verify if models exist
                self.health_predictor = HealthOutbreakPredictor() # Initialize your predictor classes
                self.crime_predictor = CrimePredictor()
                self.models_loaded = True
                print("MLService: ML models loaded successfully.")
            else:
                print("MLService: ML models not found. Please train them first (e.g., run ml_models.py).")
                self.models_loaded = False
        except Exception as e:
            self.models_loaded = False
            print(f"MLService: Error loading models: {e}")
            # Consider logging the full traceback in a production environment

    def is_available(self):
        """Checks if ML models are loaded and ready for use."""
        return self.models_loaded

    def get_system_health(self):
        """Returns health status of the ML service."""
        return {
            'status': 'active' if self.is_available() else 'inactive',
            'models_loaded': self.models_loaded,
            'last_prediction_run': self.db_manager.get_last_prediction_timestamp(), # Assuming this method exists
            'message': 'ML models ready' if self.models_loaded else 'ML models not trained/loaded'
        }

    def generate_predictions_for_area(self, area, days_ahead=7):
        """
        Generates and stores predictions for a specific area.
        In a real scenario, this would fetch historical data for the area
        and use the trained models.
        """
        if not self.is_available():
            print(f"MLService: Cannot generate predictions, models not available for area {area}.")
            return []

        print(f"MLService: Generating predictions for area: {area}...")
        predictions = []
        for i in range(days_ahead):
            pred_date = (datetime.now() + timedelta(days=i)).isoformat()
            
            # Mock historical data for demonstration. Replace with actual data retrieval.
            sample_historical_health = {
                'recent_cases_7d': random.randint(0, 10),
                'recent_cases_14d': random.randint(0, 20),
                'avg_cases_7d': random.uniform(0.5, 3.0)
            }

            # Use your actual predictor methods
            health_preds = self.health_predictor.predict_outbreak_risk(
                area, 'cholera', sample_historical_health, days_ahead=1 # Predict one day at a time
            )
            crime_preds = self.crime_predictor.predict_crime_risk(
                area, days_ahead=1 # Predict one day at a time
            )

            # Assuming the predictor returns a list of daily predictions, take the first
            health_risk = health_preds[0]['risk_level'] if health_preds else 'low'
            crime_risk = crime_preds[0]['risk_level'] if crime_preds else 'low'

            prediction_data = {
                'area': area,
                'date': pred_date,
                'health_risk': health_risk,
                'crime_risk': crime_risk,
                'generated_at': datetime.utcnow().isoformat()
            }
            predictions.append(prediction_data)
            self.db_manager.save_prediction(prediction_data) # Save to database

        print(f"MLService: Generated {len(predictions)} predictions for {area}.")
        return predictions

    def generate_predictions_for_all_areas(self, days_ahead=7):
        """Generates and stores predictions for all configured areas."""
        all_predictions = []
        for area in Config.HAITI_AREAS: # Assuming Config.HAITI_AREAS is defined
            area_preds = self.generate_predictions_for_area(area, days_ahead)
            all_predictions.extend(area_preds)
        
        # Update last prediction timestamp in DB/config
        self.db_manager.update_last_prediction_timestamp() # Assuming this method exists
        print("MLService: Generated predictions for all areas.")
        return all_predictions

    def get_latest_predictions(self, area=None, limit=20):
        """Retrieves the latest predictions from the database."""
        # This will fetch from your database based on the area and limit
        # You'll need to implement get_predictions in your DatabaseManager
        return self.db_manager.get_predictions(area=area, limit=limit)

    def get_prediction_accuracy(self):
        """
        Retrieves prediction accuracy metrics.
        This would typically involve comparing past predictions with actual outcomes
        and calculating metrics like accuracy, precision, recall, etc.
        For now, this is a placeholder.
        """
        # In a real system, you'd fetch accuracy data from a storage or calculate it
        # based on historical data vs. historical predictions.
        return {
            'health_model': {
                'accuracy': 0.85, # Placeholder
                'last_evaluated': '2025-06-01T10:00:00Z',
                'description': 'Accuracy for health outbreak predictions (e.g., cholera, fever).'
            },
            'crime_model': {
                'accuracy': 0.78, # Placeholder
                'last_evaluated': '2025-06-01T10:00:00Z',
                'description': 'Accuracy for crime risk predictions (e.g., kidnapping, gang violence).'
            },
            'note': 'These are mock accuracy metrics. Implement real evaluation in production.'
        }

    # You might also want a method to trigger model retraining
    def retrain_models(self):
        """Triggers the retraining process for all ML models."""
        print("MLService: Initiating model retraining...")
        try:
            train_all_models() # Call the function from ml_models.py to retrain
            self._load_models() # Reload models after retraining
            print("MLService: Models successfully retrained and reloaded.")
            return True, "Models retrained and reloaded successfully."
        except Exception as e:
            print(f"MLService: Error during model retraining: {e}")
            self.models_loaded = False # Mark as not loaded if retraining fails
            return False, f"Model retraining failed: {e}"

# You might want to remove or comment out the testing functions
# (test_latest_ml_versions, test_alatem_ml, main) from this file
# if this file is meant to be a service module and not a standalone test runner.
# The original test functions should probably be in a separate `tests/` directory.

# Example of how your ml_models.py might look (simplified placeholders)
# ml_models.py:
# import joblib
# import os
# import numpy as np
# import pandas as pd
# from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
# from sklearn.datasets import make_classification, make_regression
# from sklearn.model_selection import train_test_split
# from config import Config # Assuming Config has ML_MODELS_DIR

# class HealthOutbreakPredictor:
#     def __init__(self):
#         # Load your trained model here
#         # For demonstration:
#         self.model = None # Replace with actual loaded model
#         # try:
#         #     self.model = joblib.load(os.path.join(Config.ML_MODELS_DIR, 'health_model.pkl'))
#         # except FileNotFoundError:
#         #     print("Health model not found. Please train it.")

#     def predict_outbreak_risk(self, area, disease, historical_data, days_ahead=1):
#         # This is a mock prediction
#         risk_levels = ['low', 'medium', 'high']
#         outbreak_probabilities = [0.1, 0.4, 0.8]
#         return [{
#             'date': (datetime.now() + timedelta(days=i)).isoformat(),
#             'risk_level': random.choices(risk_levels, weights=[0.6, 0.3, 0.1])[0],
#             'outbreak_probability': random.uniform(0.05, 0.95)
#         } for i in range(days_ahead)]

# class CrimePredictor:
#     def __init__(self):
#         self.model = None # Replace with actual loaded model
#         # try:
#         #     self.model = joblib.load(os.path.join(Config.ML_MODELS_DIR, 'crime_model.pkl'))
#         # except FileNotFoundError:
#         #     print("Crime model not found. Please train it.")

#     def predict_crime_risk(self, area, days_ahead=1):
#         # This is a mock prediction
#         risk_levels = ['low', 'moderate', 'severe']
#         return [{
#             'date': (datetime.now() + timedelta(days=i)).isoformat(),
#             'risk_level': random.choices(risk_levels, weights=[0.5, 0.3, 0.2])[0],
#             'crime_probability': random.uniform(0.1, 0.8)
#         } for i in range(days_ahead)]

# def train_all_models():
#     print("Training all models (placeholder)...")
#     # Implement actual model training here
#     # Example:
#     # X, y = make_classification(n_samples=1000, n_features=10, n_classes=2, random_state=42)
#     # X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
#     # health_model = RandomForestClassifier(random_state=42)
#     # health_model.fit(X_train, y_train)
#     # joblib.dump(health_model, os.path.join(Config.ML_MODELS_DIR, 'health_model.pkl'))
#     print("Models training complete (mock).")

# def check_model_files():
#     # In a real scenario, check if actual model files exist
#     # return os.path.exists(os.path.join(Config.ML_MODELS_DIR, 'health_model.pkl')) and \
#     #        os.path.exists(os.path.join(Config.ML_MODELS_DIR, 'crime_model.pkl'))
#     return True # Mock for demonstration