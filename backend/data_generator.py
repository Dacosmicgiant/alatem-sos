# data_generator.py - Create realistic synthetic dataset
import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta
import random

# Haiti geographic areas with real population estimates
HAITI_AREAS = {
    'CITE_SOLEIL': {'population': 300000, 'risk_factor': 0.9, 'coordinates': [18.5944, -72.3074]},
    'DELMAS': {'population': 500000, 'risk_factor': 0.6, 'coordinates': [18.5483, -72.3074]},
    'TABARRE': {'population': 250000, 'risk_factor': 0.4, 'coordinates': [18.5736, -72.2928]},
    'MARTISSANT': {'population': 200000, 'risk_factor': 0.8, 'coordinates': [18.5089, -72.3444]},
    'CARREFOUR': {'population': 450000, 'risk_factor': 0.7, 'coordinates': [18.5413, -72.3979]},
    'PETIONVILLE': {'population': 350000, 'risk_factor': 0.3, 'coordinates': [18.5125, -72.2853]},
    'CROIX_DES_BOUQUETS': {'population': 180000, 'risk_factor': 0.5, 'coordinates': [18.5792, -72.2261]},
    'PORT_AU_PRINCE': {'population': 1200000, 'risk_factor': 0.8, 'coordinates': [18.5944, -72.3074]}
}

HEALTH_CONDITIONS = {
    'cholera': {'base_rate': 0.02, 'seasonal_factor': 2.0, 'outbreak_threshold': 15},
    'malnutrition': {'base_rate': 0.05, 'seasonal_factor': 1.5, 'outbreak_threshold': 25},
    'fever': {'base_rate': 0.08, 'seasonal_factor': 1.3, 'outbreak_threshold': 40},
    'diarrhea': {'base_rate': 0.06, 'seasonal_factor': 1.8, 'outbreak_threshold': 30},
    'respiratory': {'base_rate': 0.04, 'seasonal_factor': 1.4, 'outbreak_threshold': 20}
}

CRIME_TYPES = {
    'kidnapping': {'base_rate': 0.001, 'gang_factor': 5.0, 'time_pattern': 'evening'},
    'armed_robbery': {'base_rate': 0.003, 'gang_factor': 3.0, 'time_pattern': 'night'},
    'home_invasion': {'base_rate': 0.002, 'gang_factor': 2.5, 'time_pattern': 'night'},
    'street_violence': {'base_rate': 0.004, 'gang_factor': 4.0, 'time_pattern': 'day'},
    'gang_shooting': {'base_rate': 0.0005, 'gang_factor': 10.0, 'time_pattern': 'random'}
}

def generate_health_data(days=365):
    """Generate realistic health outbreak data for Haiti"""
    data = []
    start_date = datetime.now() - timedelta(days=days)
    
    for day in range(days):
        current_date = start_date + timedelta(days=day)
        
        # Simulate seasonal patterns (rainy season increases waterborne diseases)
        month = current_date.month
        rainy_season_factor = 1.5 if month in [4, 5, 6, 7, 8, 9] else 1.0
        
        for area_name, area_info in HAITI_AREAS.items():
            population = area_info['population']
            risk_factor = area_info['risk_factor']
            
            for condition, condition_info in HEALTH_CONDITIONS.items():
                base_rate = condition_info['base_rate']
                seasonal_factor = condition_info['seasonal_factor']
                
                # Calculate expected cases with multiple factors
                expected_rate = (base_rate * 
                               risk_factor * 
                               (seasonal_factor if month in [4,5,6,7,8,9] else 1.0) *
                               rainy_season_factor)
                
                # Add random outbreak events (5% chance per day per area)
                outbreak_multiplier = 1.0
                if random.random() < 0.05 * risk_factor:
                    outbreak_multiplier = random.uniform(2.0, 5.0)
                
                # Generate cases with Poisson distribution
                expected_cases = int(population * expected_rate * outbreak_multiplier / 1000)
                actual_cases = max(0, np.random.poisson(expected_cases))
                
                if actual_cases > 0:  # Only record non-zero cases
                    data.append({
                        'date': current_date.strftime('%Y-%m-%d'),
                        'area': area_name,
                        'condition': condition,
                        'cases': actual_cases,
                        'population': population,
                        'risk_factor': risk_factor,
                        'latitude': area_info['coordinates'][0],
                        'longitude': area_info['coordinates'][1],
                        'is_outbreak': actual_cases >= condition_info['outbreak_threshold'],
                        'month': month,
                        'day_of_week': current_date.weekday(),
                        'rainfall': random.uniform(0, 50) if month in [4,5,6,7,8,9] else random.uniform(0, 10)
                    })
    
    return pd.DataFrame(data)

def generate_crime_data(days=365):
    """Generate realistic crime data for Haiti"""
    data = []
    start_date = datetime.now() - timedelta(days=days)
    
    # Gang control intensity by area (affects crime rates)
    gang_control = {
        'CITE_SOLEIL': 0.9,
        'MARTISSANT': 0.8,
        'CARREFOUR': 0.7,
        'PORT_AU_PRINCE': 0.8,
        'DELMAS': 0.5,
        'TABARRE': 0.3,
        'PETIONVILLE': 0.2,
        'CROIX_DES_BOUQUETS': 0.4
    }
    
    for day in range(days):
        current_date = start_date + timedelta(days=day)
        
        for area_name, area_info in HAITI_AREAS.items():
            population = area_info['population']
            gang_intensity = gang_control.get(area_name, 0.5)
            
            for crime_type, crime_info in CRIME_TYPES.items():
                base_rate = crime_info['base_rate']
                gang_factor = crime_info['gang_factor']
                
                # Calculate crime probability
                crime_rate = base_rate * (1 + gang_intensity * gang_factor)
                expected_incidents = int(population * crime_rate / 1000)
                actual_incidents = np.random.poisson(expected_incidents)
                
                if actual_incidents > 0:
                    for incident in range(actual_incidents):
                        # Generate time based on crime pattern
                        if crime_info['time_pattern'] == 'night':
                            hour = random.randint(22, 23) if random.random() < 0.5 else random.randint(0, 5)
                        elif crime_info['time_pattern'] == 'evening':
                            hour = random.randint(18, 22)
                        elif crime_info['time_pattern'] == 'day':
                            hour = random.randint(8, 17)
                        else:  # random
                            hour = random.randint(0, 23)
                        
                        data.append({
                            'date': current_date.strftime('%Y-%m-%d'),
                            'time': f"{hour:02d}:{random.randint(0,59):02d}",
                            'area': area_name,
                            'crime_type': crime_type,
                            'gang_control_level': gang_intensity,
                            'population': population,
                            'latitude': area_info['coordinates'][0] + random.uniform(-0.01, 0.01),
                            'longitude': area_info['coordinates'][1] + random.uniform(-0.01, 0.01),
                            'severity': random.choice(['low', 'medium', 'high']),
                            'day_of_week': current_date.weekday(),
                            'month': current_date.month
                        })
    
    return pd.DataFrame(data)

if __name__ == "__main__":
    print("Generating synthetic dataset for Haiti...")
    
    # Generate datasets
    health_df = generate_health_data(days=730)  # 2 years of data
    crime_df = generate_crime_data(days=730)
    
    # Save datasets
    health_df.to_csv('dataset/haiti_health_data.csv', index=False)
    crime_df.to_csv('dataset/haiti_crime_data.csv', index=False)
    
    print(f"Generated {len(health_df)} health records")
    print(f"Generated {len(crime_df)} crime records")
    
    # Display sample data
    print("\nSample Health Data:")
    print(health_df.head())
    print("\nSample Crime Data:")
    print(crime_df.head())
    
    # Save area information
    with open('dataset/haiti_areas.json', 'w') as f:
        json.dump(HAITI_AREAS, f, indent=2)
    
    print("\nDataset generation complete!")