# ml_models.py - Fixed version with proper model saving/loading
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, mean_absolute_error
import joblib
from datetime import datetime, timedelta
import warnings
import os
warnings.filterwarnings('ignore')

class HealthOutbreakPredictor:
    def __init__(self):
        self.outbreak_classifier = RandomForestClassifier(n_estimators=100, random_state=42)
        self.cases_regressor = RandomForestRegressor(n_estimators=100, random_state=42)
        self.label_encoders = {}
        self.scaler = StandardScaler()
        self.feature_cols = []  # Initialize feature_cols
        self.is_trained = False
    
    def prepare_features(self, df):
        """Prepare features for ML model"""
        features_df = df.copy()
        
        # Encode categorical variables
        categorical_cols = ['area', 'condition']
        for col in categorical_cols:
            if col not in self.label_encoders:
                self.label_encoders[col] = LabelEncoder()
                features_df[f'{col}_encoded'] = self.label_encoders[col].fit_transform(features_df[col])
            else:
                features_df[f'{col}_encoded'] = self.label_encoders[col].transform(features_df[col])
        
        # Create time-based features
        features_df['date'] = pd.to_datetime(features_df['date'])
        features_df['day_of_year'] = features_df['date'].dt.dayofyear
        
        # Fix: Use isocalendar().week instead of deprecated .week
        features_df['week_of_year'] = features_df['date'].dt.isocalendar().week
        
        features_df['is_rainy_season'] = features_df['month'].isin([4,5,6,7,8,9]).astype(int)
        
        # Create lag features (previous 7 days) - More robust approach
        features_df = features_df.sort_values(['area_encoded', 'condition_encoded', 'date']).reset_index(drop=True)
        
        # Use a safer approach for lag and rolling features
        lag_rolling_features = []
        
        for (area_enc, condition_enc), group in features_df.groupby(['area_encoded', 'condition_encoded']):
            group = group.sort_values('date').reset_index(drop=True)
            group['cases_lag_7'] = group['cases'].shift(7)
            group['cases_lag_14'] = group['cases'].shift(14)
            group['cases_rolling_7'] = group['cases'].rolling(window=7, min_periods=1).mean()
            lag_rolling_features.append(group)
        
        # Concatenate all groups back together
        features_df = pd.concat(lag_rolling_features, ignore_index=True)
        
        # Fill NaN values
        features_df = features_df.fillna(0)
        
        return features_df
    
    def train(self, health_df):
        """Train the outbreak prediction models"""
        print("Training health outbreak prediction models...")
        
        # Prepare features
        features_df = self.prepare_features(health_df)
        
        # Select feature columns
        feature_cols = [
            'area_encoded', 'condition_encoded', 'population', 'risk_factor',
            'month', 'day_of_week', 'day_of_year', 'week_of_year', 
            'is_rainy_season', 'rainfall', 'cases_lag_7', 'cases_lag_14', 'cases_rolling_7'
        ]
        
        X = features_df[feature_cols]
        y_outbreak = features_df['is_outbreak']
        y_cases = features_df['cases']
        
        # Split data
        X_train, X_test, y_outbreak_train, y_outbreak_test = train_test_split(
            X, y_outbreak, test_size=0.2, random_state=42
        )
        _, _, y_cases_train, y_cases_test = train_test_split(
            X, y_cases, test_size=0.2, random_state=42
        )
        
        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # Train outbreak classifier
        self.outbreak_classifier.fit(X_train_scaled, y_outbreak_train)
        
        # Train cases regressor
        self.cases_regressor.fit(X_train_scaled, y_cases_train)
        
        # Evaluate models
        outbreak_pred = self.outbreak_classifier.predict(X_test_scaled)
        cases_pred = self.cases_regressor.predict(X_test_scaled)
        
        print("Outbreak Classification Report:")
        print(classification_report(y_outbreak_test, outbreak_pred))
        print(f"Cases Prediction MAE: {mean_absolute_error(y_cases_test, cases_pred):.2f}")
        
        # Feature importance
        feature_importance = pd.DataFrame({
            'feature': feature_cols,
            'importance': self.outbreak_classifier.feature_importances_
        }).sort_values('importance', ascending=False)
        print("\nTop 5 Most Important Features:")
        print(feature_importance.head())
        
        self.feature_cols = feature_cols  # Store feature columns
        self.is_trained = True
        
        # Ensure ml_models directory exists
        os.makedirs('ml_models', exist_ok=True)
        
        # Save models and ALL necessary components
        joblib.dump(self.outbreak_classifier, 'ml_models/outbreak_classifier.pkl')
        joblib.dump(self.cases_regressor, 'ml_models/cases_regressor.pkl')
        joblib.dump(self.label_encoders, 'ml_models/label_encoders.pkl')
        joblib.dump(self.scaler, 'ml_models/scaler.pkl')
        
        # IMPORTANT: Save feature_cols separately
        joblib.dump(self.feature_cols, 'ml_models/feature_cols.pkl')
        
        print("✅ Models saved successfully!")
        print("📁 Saved files:")
        print("   - outbreak_classifier.pkl")
        print("   - cases_regressor.pkl") 
        print("   - label_encoders.pkl")
        print("   - scaler.pkl")
        print("   - feature_cols.pkl")  # New file
    
    def predict_outbreak_risk(self, area, condition, historical_data, days_ahead=7):
        """Predict outbreak risk for next 'days_ahead' days"""
        if not self.is_trained:
            print("Model not trained yet!")
            return None
        
        if not hasattr(self, 'feature_cols') or not self.feature_cols:
            print("Error: feature_cols not available. Model may not be properly loaded.")
            return None
        
        predictions = []
        
        for day in range(1, days_ahead + 1):
            # Prepare prediction features
            future_date = datetime.now() + timedelta(days=day)
            
            # Get area information
            import json
            try:
                with open('dataset/haiti_areas.json', 'r') as f:
                    areas_info = json.load(f)
            except FileNotFoundError:
                print("haiti_areas.json not found. Using default values.")
                areas_info = {}
            
            area_info = areas_info.get(area, {'population': 100000, 'risk_factor': 0.5})
            
            # Create feature vector
            try:
                area_encoded = self.label_encoders['area'].transform([area])[0]
                condition_encoded = self.label_encoders['condition'].transform([condition])[0]
            except (KeyError, ValueError):
                print(f"Unknown area '{area}' or condition '{condition}'. Skipping prediction.")
                continue
            
            features = {
                'area_encoded': area_encoded,
                'condition_encoded': condition_encoded,
                'population': area_info.get('population', 100000),
                'risk_factor': area_info.get('risk_factor', 0.5),
                'month': future_date.month,
                'day_of_week': future_date.weekday(),
                'day_of_year': future_date.timetuple().tm_yday,
                'week_of_year': future_date.isocalendar()[1],  # Fixed: use isocalendar()
                'is_rainy_season': 1 if future_date.month in [4,5,6,7,8,9] else 0,
                'rainfall': 25 if future_date.month in [4,5,6,7,8,9] else 5,
                'cases_lag_7': historical_data.get('recent_cases_7d', 0),
                'cases_lag_14': historical_data.get('recent_cases_14d', 0),
                'cases_rolling_7': historical_data.get('avg_cases_7d', 0)
            }
            
            # Create feature array using the stored feature_cols
            X_pred = np.array([[features[col] for col in self.feature_cols]])
            X_pred_scaled = self.scaler.transform(X_pred)
            
            # Make predictions
            outbreak_prob = self.outbreak_classifier.predict_proba(X_pred_scaled)[0][1]
            predicted_cases = max(0, self.cases_regressor.predict(X_pred_scaled)[0])
            
            predictions.append({
                'date': future_date.strftime('%Y-%m-%d'),
                'outbreak_probability': float(outbreak_prob),
                'predicted_cases': int(predicted_cases),
                'risk_level': 'HIGH' if outbreak_prob > 0.7 else 'MEDIUM' if outbreak_prob > 0.4 else 'LOW'
            })
        
        return predictions

class CrimePredictor:
    def __init__(self):
        self.crime_classifier = RandomForestClassifier(n_estimators=100, random_state=42)
        self.label_encoders = {}
        self.scaler = StandardScaler()
        self.feature_cols = []  # Initialize feature_cols
        self.is_trained = False
    
    def prepare_features(self, df):
        """Prepare features for crime prediction"""
        features_df = df.copy()
        
        # Encode categorical variables
        categorical_cols = ['area', 'crime_type', 'severity']
        for col in categorical_cols:
            if col not in self.label_encoders:
                self.label_encoders[col] = LabelEncoder()
                features_df[f'{col}_encoded'] = self.label_encoders[col].fit_transform(features_df[col])
            else:
                features_df[f'{col}_encoded'] = self.label_encoders[col].transform(features_df[col])
        
        # Time features
        features_df['date'] = pd.to_datetime(features_df['date'])
        features_df['time'] = pd.to_datetime(features_df['time'], format='%H:%M', errors='coerce')
        features_df['hour'] = features_df['time'].dt.hour
        features_df['is_weekend'] = features_df['day_of_week'].isin([5, 6]).astype(int)
        features_df['is_night'] = ((features_df['hour'] >= 22) | (features_df['hour'] <= 5)).astype(int)
        
        # Fill NaN values for hour (in case time parsing failed)
        features_df['hour'] = features_df['hour'].fillna(12)  # Default to noon
        
        return features_df
    
    def train(self, crime_df):
        """Train crime prediction model"""
        print("Training crime prediction model...")
        
        # Prepare features
        features_df = self.prepare_features(crime_df)
        
        # Create daily crime counts by area and type
        daily_crimes = features_df.groupby(['date', 'area', 'crime_type']).size().reset_index(name='crime_count')
        daily_crimes['high_crime_day'] = (daily_crimes['crime_count'] >= 2).astype(int)
        
        # Merge with features
        features_df = features_df.merge(daily_crimes[['date', 'area', 'crime_type', 'high_crime_day']], 
                                       on=['date', 'area', 'crime_type'])
        
        feature_cols = [
            'area_encoded', 'crime_type_encoded', 'gang_control_level',
            'population', 'month', 'day_of_week', 'hour', 'is_weekend', 'is_night'
        ]
        
        X = features_df[feature_cols]
        y = features_df['high_crime_day']
        
        # Split and train
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        self.crime_classifier.fit(X_train_scaled, y_train)
        
        # Evaluate
        y_pred = self.crime_classifier.predict(X_test_scaled)
        print("Crime Prediction Classification Report:")
        print(classification_report(y_test, y_pred))
        
        self.feature_cols = feature_cols  # Store feature columns
        self.is_trained = True
        
        # Ensure ml_models directory exists
        os.makedirs('ml_models', exist_ok=True)
        
        # Save model and components
        joblib.dump(self.crime_classifier, 'ml_models/crime_classifier.pkl')
        joblib.dump({
            'crime_encoders': self.label_encoders, 
            'crime_scaler': self.scaler,
            'crime_feature_cols': self.feature_cols  # Add feature_cols to saved components
        }, 'ml_models/crime_model_components.pkl')
        
        print("✅ Crime model saved!")
    
    def predict_crime_risk(self, area, days_ahead=7):
        """Predict crime risk for area"""
        if not self.is_trained:
            return None
        
        predictions = []
        
        for day in range(1, days_ahead + 1):
            future_date = datetime.now() + timedelta(days=day)
            
            # For demo purposes, return a simple risk assessment
            risk_score = np.random.uniform(0.2, 0.8)  # Mock prediction
            
            predictions.append({
                'date': future_date.strftime('%Y-%m-%d'),
                'crime_risk_score': float(risk_score),
                'risk_level': 'HIGH' if risk_score > 0.6 else 'MEDIUM' if risk_score > 0.4 else 'LOW'
            })
        
        return predictions

def train_all_models():
    """Train all ML models"""
    try:
        # Load datasets
        print("Loading datasets...")
        health_df = pd.read_csv('dataset/haiti_health_data.csv')
        crime_df = pd.read_csv('dataset/haiti_crime_data.csv')
        
        print(f"Loaded {len(health_df)} health records and {len(crime_df)} crime records")
        
        # Train health model
        print("\n" + "="*50)
        health_predictor = HealthOutbreakPredictor()
        health_predictor.train(health_df)
        
        # Train crime model
        print("\n" + "="*50)
        crime_predictor = CrimePredictor()
        crime_predictor.train(crime_df)
        
        print("\n" + "="*50)
        print("🎉 All models trained successfully!")
        print("📁 Model files saved in ml_models/:")
        print("   - outbreak_classifier.pkl")
        print("   - cases_regressor.pkl") 
        print("   - label_encoders.pkl")
        print("   - scaler.pkl")
        print("   - feature_cols.pkl")  # New file
        print("   - crime_classifier.pkl")
        print("   - crime_model_components.pkl")
        
        # Test prediction
        print("\n🔮 Testing predictions...")
        sample_historical = {
            'recent_cases_7d': 5,
            'recent_cases_14d': 12,
            'avg_cases_7d': 1.7
        }
        
        test_prediction = health_predictor.predict_outbreak_risk(
            'CITE_SOLEIL', 'cholera', sample_historical, days_ahead=3
        )
        
        if test_prediction:
            print("✅ Sample prediction successful:")
            for pred in test_prediction:
                print(f"   {pred['date']}: {pred['risk_level']} risk ({pred['outbreak_probability']:.2f})")
        
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        print("💡 Make sure to run 'python data_generator.py' first to create the datasets")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    train_all_models()