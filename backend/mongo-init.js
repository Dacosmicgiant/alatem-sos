// MongoDB initialization script for Docker
// This script runs when MongoDB container starts for the first time

// Switch to alatem database
db = db.getSiblingDB('alatem');

// Create collections with proper indexes
db.createCollection('users');
db.createCollection('staff_users');
db.createCollection('health_reports');
db.createCollection('crime_reports');
db.createCollection('sent_alerts');
db.createCollection('predictions');

// Create indexes for better performance
print('Creating indexes...');

// Users collection indexes
db.users.createIndex({ "phone": 1 }, { unique: true });
db.users.createIndex({ "area": 1 });
db.users.createIndex({ "verified": 1 });
db.users.createIndex({ "active": 1 });
db.users.createIndex({ "created_at": 1 });

// Staff users collection indexes
db.staff_users.createIndex({ "username": 1 }, { unique: true });
db.staff_users.createIndex({ "is_active": 1 });

// Health reports collection indexes
db.health_reports.createIndex({ "area": 1, "condition": 1 });
db.health_reports.createIndex({ "timestamp": 1 });
db.health_reports.createIndex({ "area": 1, "timestamp": -1 });

// Crime reports collection indexes
db.crime_reports.createIndex({ "area": 1, "crime_type": 1 });
db.crime_reports.createIndex({ "timestamp": 1 });
db.crime_reports.createIndex({ "area": 1, "timestamp": -1 });

// Sent alerts collection indexes
db.sent_alerts.createIndex({ "area": 1, "timestamp": -1 });
db.sent_alerts.createIndex({ "alert_type": 1 });
db.sent_alerts.createIndex({ "timestamp": -1 });
db.sent_alerts.createIndex({ "triggered_by": 1 });

// Predictions collection indexes
db.predictions.createIndex({ "area": 1, "date": -1 });
db.predictions.createIndex({ "area": 1, "condition": 1, "date": -1 });
db.predictions.createIndex({ "timestamp": -1 });
db.predictions.createIndex({ "type": 1 });

print('Database and indexes created successfully!');

// Optional: Create default admin user (will be handled by application)
print('Alatem database initialized. Default admin user will be created by the application.');
print('Login credentials: admin / admin123');