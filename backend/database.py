import json
import os
from datetime import datetime, timedelta
from config import Config

# Conditional MongoDB import
try:
    from pymongo import MongoClient
    from pymongo.errors import ConnectionFailure
    MONGODB_AVAILABLE = True
except ImportError:
    MONGODB_AVAILABLE = False

class DatabaseManager:
    def __init__(self):
        self.use_mongodb = MONGODB_AVAILABLE and Config.MONGODB_URI
        self._setup_database()
    
    def _setup_database(self):
        """Setup database connection"""
        if self.use_mongodb:
            self._setup_mongodb()
        else:
            self._setup_json_storage()
    
    def _setup_mongodb(self):
        """Setup MongoDB connection"""
        try:
            self.client = MongoClient(Config.MONGODB_URI)
            self.db = self.client.alatem
            
            # Test connection
            self.client.admin.command('ping')
            print("✅ MongoDB Atlas connected successfully!")
            
            # Collections
            self.users = self.db.users
            self.staff_users = self.db.staff_users
            self.health_reports = self.db.health_reports
            self.crime_reports = self.db.crime_reports
            self.sent_alerts = self.db.sent_alerts
            self.predictions = self.db.predictions
            
            # Create indexes
            self._create_indexes()
            
        except Exception as e:
            print(f"❌ MongoDB connection failed: {e}")
            print("📁 Falling back to JSON files")
            self.use_mongodb = False
            self._setup_json_storage()
    
    def _create_indexes(self):
        """Create database indexes for better performance"""
        try:
            self.users.create_index("phone", unique=True, background=True)
            self.staff_users.create_index("username", unique=True, background=True)
            self.predictions.create_index([("area", 1), ("date", -1)], background=True)
            self.sent_alerts.create_index([("area", 1), ("timestamp", -1)], background=True)
            print("✅ Database indexes created")
        except Exception as e:
            print(f"⚠️ Index creation error: {e}")
    
    def _setup_json_storage(self):
        """Setup JSON file storage"""
        os.makedirs(Config.DATA_DIR, exist_ok=True)
        self.files = {
            'users': os.path.join(Config.DATA_DIR, 'users.json'),
            'staff_users': os.path.join(Config.DATA_DIR, 'staff_users.json'),
            'health_reports': os.path.join(Config.DATA_DIR, 'health_reports.json'),
            'crime_reports': os.path.join(Config.DATA_DIR, 'crime_reports.json'),
            'sent_alerts': os.path.join(Config.DATA_DIR, 'sent_alerts.json'),
            'predictions': os.path.join(Config.DATA_DIR, 'predictions.json')
        }
        print("📁 JSON file storage initialized")
    
    # User Management Methods
    def save_user(self, user_data):
        """Save or update user"""
        if self.use_mongodb:
            return self.users.replace_one(
                {"phone": user_data["phone"]}, 
                user_data, 
                upsert=True
            )
        else:
            users = self._load_json('users')
            existing_index = next(
                (i for i, u in enumerate(users) if u.get('phone') == user_data['phone']), 
                None
            )
            if existing_index is not None:
                users[existing_index] = user_data
            else:
                users.append(user_data)
            return self._save_json('users', users)
    
    def find_user_by_phone(self, phone):
        """Find user by phone number"""
        if self.use_mongodb:
            return self.users.find_one({"phone": phone})
        else:
            users = self._load_json('users')
            return next((u for u in users if u.get('phone') == phone), None)
    
    def update_user_verified(self, phone):
        """Mark user as verified"""
        if self.use_mongodb:
            return self.users.update_one(
                {"phone": phone}, 
                {"$set": {"verified": True, "verified_at": datetime.utcnow()}}
            )
        else:
            users = self._load_json('users')
            user_index = next(
                (i for i, u in enumerate(users) if u.get('phone') == phone), 
                None
            )
            if user_index is not None:
                users[user_index]['verified'] = True
                users[user_index]['verified_at'] = datetime.utcnow().isoformat()
                return self._save_json('users', users)
            return False
    
    def get_users_by_area(self, area, verified_only=True):
        """Get all users in a specific area"""
        if self.use_mongodb:
            query = {"area": area, "active": True}
            if verified_only:
                query["verified"] = True
            return list(self.users.find(query))
        else:
            users = self._load_json('users')
            return [u for u in users if (
                u.get('area') == area and
                u.get('active', True) and
                (not verified_only or u.get('verified', False))
            )]
    
    def get_area_stats(self):
        """Get user count statistics by area"""
        if self.use_mongodb:
            pipeline = [
                {"$match": {"verified": True, "active": True}},
                {"$group": {"_id": "$area", "user_count": {"$sum": 1}}},
                {"$sort": {"_id": 1}}
            ]
            return list(self.users.aggregate(pipeline))
        else:
            users = self._load_json('users')
            verified_users = [u for u in users if u.get('verified', False) and u.get('active', True)]
            area_counts = {}
            for user in verified_users:
                area = user.get('area')
                if area:
                    area_counts[area] = area_counts.get(area, 0) + 1
            return [{'_id': area, 'user_count': count} for area, count in sorted(area_counts.items())]
    
    # Staff User Management
    def save_staff_user(self, staff_data):
        """Save staff user"""
        if self.use_mongodb:
            return self.staff_users.insert_one(staff_data)
        else:
            staff_users = self._load_json('staff_users')
            staff_users.append(staff_data)
            return self._save_json('staff_users', staff_users)
    
    def find_staff_user(self, username):
        """Find staff user by username"""
        if self.use_mongodb:
            return self.staff_users.find_one({"username": username, "is_active": True})
        else:
            staff_users = self._load_json('staff_users')
            return next(
                (u for u in staff_users if u.get('username') == username and u.get('is_active')), 
                None
            )
    
    def update_staff_login(self, user_id, login_time):
        """Update staff user last login"""
        if self.use_mongodb:
            from bson.objectid import ObjectId
            return self.staff_users.update_one(
                {"_id": ObjectId(user_id)}, 
                {"$set": {"last_login": login_time}}
            )
        else:
            staff_users = self._load_json('staff_users')
            user_index = next(
                (i for i, u in enumerate(staff_users) if u.get('id') == user_id), 
                None
            )
            if user_index is not None:
                staff_users[user_index]['last_login'] = login_time.isoformat()
                return self._save_json('staff_users', staff_users)
    
    # Reports Management
    def save_health_report(self, report_data):
        """Save health report"""
        if self.use_mongodb:
            return self.health_reports.insert_one(report_data)
        else:
            reports = self._load_json('health_reports')
            reports.append(report_data)
            return self._save_json('health_reports', reports)
    
    def save_crime_report(self, report_data):
        """Save crime report"""
        if self.use_mongodb:
            return self.crime_reports.insert_one(report_data)
        else:
            reports = self._load_json('crime_reports')
            reports.append(report_data)
            return self._save_json('crime_reports', reports)
    
    def get_recent_health_reports(self, area, condition, since_date):
        """Get recent health reports for ML predictions"""
        if self.use_mongodb:
            return list(self.health_reports.find({
                "area": area,
                "condition": condition,
                "timestamp": {"$gte": since_date}
            }))
        else:
            reports = self._load_json('health_reports')
            result = []
            for report in reports:
                if (report.get('area') == area and 
                    report.get('condition') == condition):
                    try:
                        report_time = datetime.fromisoformat(report['timestamp'].replace('Z', '+00:00'))
                        if report_time >= since_date:
                            result.append(report)
                    except (ValueError, KeyError):
                        continue
            return result
    
    def get_recent_crime_reports(self, area, since_date):
        """Get recent crime report count"""
        if self.use_mongodb:
            return self.crime_reports.count_documents({
                "area": area,
                "timestamp": {"$gte": since_date}
            })
        else:
            reports = self._load_json('crime_reports')
            count = 0
            for report in reports:
                if report.get('area') == area:
                    try:
                        report_time = datetime.fromisoformat(report['timestamp'].replace('Z', '+00:00'))
                        if report_time >= since_date:
                            count += 1
                    except (ValueError, KeyError):
                        continue
            return count
    
    # Alert Management
    def save_alert(self, alert_data):
        """Save sent alert"""
        if self.use_mongodb:
            return self.sent_alerts.insert_one(alert_data)
        else:
            alerts = self._load_json('sent_alerts')
            alerts.append(alert_data)
            return self._save_json('sent_alerts', alerts)
    
    def get_alerts_history(self, area, limit=50, alert_type=None):
        """Get alert history for an area"""
        if self.use_mongodb:
            query = {"area": area}
            if alert_type:
                query["alert_type"] = alert_type
            
            alerts = list(self.sent_alerts.find(
                query,
                sort=[("timestamp", -1)],
                limit=limit
            ))
            
            # Convert ObjectId to string
            for alert in alerts:
                if '_id' in alert:
                    alert['_id'] = str(alert['_id'])
            return alerts
        else:
            all_alerts = self._load_json('sent_alerts')
            area_alerts = [
                alert for alert in all_alerts 
                if alert.get('area') == area and 
                (not alert_type or alert.get('alert_type') == alert_type)
            ]
            area_alerts.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            return area_alerts[:limit]
    
    def get_recent_alerts(self, hours=24, area=None):
        """Get recent alerts"""
        since_date = datetime.utcnow() - timedelta(hours=hours)
        
        if self.use_mongodb:
            query = {"timestamp": {"$gte": since_date}}
            if area:
                query["area"] = area
            
            alerts = list(self.sent_alerts.find(
                query,
                sort=[("timestamp", -1)]
            ))
            
            for alert in alerts:
                if '_id' in alert:
                    alert['_id'] = str(alert['_id'])
            return alerts
        else:
            all_alerts = self._load_json('sent_alerts')
            recent_alerts = []
            for alert in all_alerts:
                try:
                    alert_time = datetime.fromisoformat(alert['timestamp'].replace('Z', '+00:00'))
                    if alert_time >= since_date:
                        if not area or alert.get('area') == area:
                            recent_alerts.append(alert)
                except (ValueError, KeyError):
                    continue
            recent_alerts.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            return recent_alerts
    
    # Prediction Management
    def save_prediction(self, prediction_data):
        """Save ML prediction"""
        if self.use_mongodb:
            return self.predictions.replace_one(
                {
                    "area": prediction_data["area"], 
                    "date": prediction_data["date"], 
                    "type": prediction_data["type"],
                    "condition": prediction_data.get("condition")
                },
                prediction_data,
                upsert=True
            )
        else:
            predictions = self._load_json('predictions')
            # Remove existing prediction for same area/date/type/condition
            predictions = [p for p in predictions if not (
                p.get('area') == prediction_data['area'] and 
                p.get('date') == prediction_data['date'] and
                p.get('type') == prediction_data['type'] and
                p.get('condition') == prediction_data.get('condition')
            )]
            predictions.append(prediction_data)
            return self._save_json('predictions', predictions)
    
    def get_latest_predictions(self, area=None, limit=20):
        """Get latest ML predictions"""
        if self.use_mongodb:
            query = {}
            if area:
                query["area"] = area
            
            predictions = list(self.predictions.find(query).sort("timestamp", -1).limit(limit))
            for pred in predictions:
                if '_id' in pred:
                    pred['_id'] = str(pred['_id'])
            return predictions
        else:
            predictions = self._load_json('predictions')
            if area:
                predictions = [p for p in predictions if p.get('area') == area]
            predictions.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            return predictions[:limit]
    
    # Statistics
    def get_stats(self):
        """Get system statistics"""
        if self.use_mongodb:
            yesterday = datetime.utcnow() - timedelta(days=1)
            return {
                'users': {
                    'total': self.users.count_documents({}),
                    'verified': self.users.count_documents({"verified": True}),
                    'active': self.users.count_documents({"active": True})
                },
                'staff': {
                    'total': self.staff_users.count_documents({}),
                    'active': self.staff_users.count_documents({"is_active": True})
                },
                'reports': {
                    'health_reports': self.health_reports.count_documents({}),
                    'crime_reports': self.crime_reports.count_documents({}),
                    'alerts_sent': self.sent_alerts.count_documents({}),
                    'predictions': self.predictions.count_documents({})
                },
                'recent_activity': {
                    'health_reports_24h': self.health_reports.count_documents({
                        "timestamp": {"$gte": yesterday}
                    }),
                    'crime_reports_24h': self.crime_reports.count_documents({
                        "timestamp": {"$gte": yesterday}
                    }),
                    'alerts_sent_24h': self.sent_alerts.count_documents({
                        "timestamp": {"$gte": yesterday}
                    }),
                    'predictions_24h': self.predictions.count_documents({
                        "timestamp": {"$gte": yesterday}
                    })
                }
            }
        else:
            users = self._load_json('users')
            staff_users = self._load_json('staff_users')
            health_reports = self._load_json('health_reports')
            crime_reports = self._load_json('crime_reports')
            sent_alerts = self._load_json('sent_alerts')
            predictions = self._load_json('predictions')
            
            yesterday = datetime.utcnow() - timedelta(days=1)
            
            def count_recent(items, date_field='timestamp'):
                count = 0
                for item in items:
                    try:
                        item_time = datetime.fromisoformat(item[date_field].replace('Z', '+00:00'))
                        if item_time >= yesterday:
                            count += 1
                    except (ValueError, KeyError):
                        continue
                return count
            
            return {
                'users': {
                    'total': len(users),
                    'verified': len([u for u in users if u.get('verified', False)]),
                    'active': len([u for u in users if u.get('active', True)])
                },
                'staff': {
                    'total': len(staff_users),
                    'active': len([u for u in staff_users if u.get('is_active', True)])
                },
                'reports': {
                    'health_reports': len(health_reports),
                    'crime_reports': len(crime_reports),
                    'alerts_sent': len(sent_alerts),
                    'predictions': len(predictions)
                },
                'recent_activity': {
                    'health_reports_24h': count_recent(health_reports),
                    'crime_reports_24h': count_recent(crime_reports),
                    'alerts_sent_24h': count_recent(sent_alerts),
                    'predictions_24h': count_recent(predictions)
                }
            }
    
    # JSON file helpers
    def _load_json(self, file_key):
        """Load data from JSON file"""
        filename = self.files[file_key]
        if os.path.exists(filename):
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return []
        return []
    
    def _save_json(self, file_key, data):
        """Save data to JSON file"""
        filename = self.files[file_key]
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, default=str)
            return True
        except Exception as e:
            print(f"Error saving to {filename}: {e}")
            return False