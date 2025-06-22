from datetime import datetime
from flask import session

class AlertService:
    def __init__(self, db_manager, sms_service, auth_service):
        self.db = db_manager
        self.sms = sms_service
        self.auth = auth_service
    
    def broadcast_health_alert(self, area, condition, cases=None):
        """Broadcast health alert to users in specific area"""
        try:
            # Get verified users in the area
            users = self.db.get_users_by_area(area, verified_only=True)
            
            if not users:
                return False, f"No verified users found in {area}", 0
            
            # Generate message
            message = self.sms.get_health_alert_message(area, condition, cases)
            
            # Send SMS to all users
            sent_count, failed_count = self.sms.send_bulk_sms(users, message)
            
            # Log the alert
            alert_data = self._create_alert_record(
                alert_type="health_outbreak",
                area=area,
                message=message,
                recipients_count=sent_count,
                condition=condition,
                cases=cases
            )
            
            self.db.save_alert(alert_data)
            
            return True, f"Health alert sent to {sent_count} users", sent_count
            
        except Exception as e:
            return False, f"Error broadcasting health alert: {str(e)}", 0
    
    def broadcast_safety_alert(self, area, crime_type):
        """Broadcast safety alert to users in specific area"""
        try:
            # Get verified users in the area
            users = self.db.get_users_by_area(area, verified_only=True)
            
            if not users:
                return False, f"No verified users found in {area}", 0
            
            # Generate message
            message = self.sms.get_safety_alert_message(area, crime_type)
            
            # Send SMS to all users
            sent_count, failed_count = self.sms.send_bulk_sms(users, message)
            
            # Log the alert
            alert_data = self._create_alert_record(
                alert_type="safety_alert",
                area=area,
                message=message,
                recipients_count=sent_count,
                crime_type=crime_type
            )
            
            self.db.save_alert(alert_data)
            
            return True, f"Safety alert sent to {sent_count} users", sent_count
            
        except Exception as e:
            return False, f"Error broadcasting safety alert: {str(e)}", 0
    
    def broadcast_custom_alert(self, area, message):
        """Broadcast custom message to users in specific area"""
        try:
            # Get verified users in the area
            users = self.db.get_users_by_area(area, verified_only=True)
            
            if not users:
                return False, f"No verified users found in {area}", 0
            
            # Send SMS to all users
            sent_count, failed_count = self.sms.send_bulk_sms(users, message)
            
            # Log the alert
            alert_data = self._create_alert_record(
                alert_type="custom_alert",
                area=area,
                message=message,
                recipients_count=sent_count
            )
            
            self.db.save_alert(alert_data)
            
            return True, f"Custom alert sent to {sent_count} users", sent_count
            
        except Exception as e:
            return False, f"Error broadcasting custom alert: {str(e)}", 0
    
    def send_ml_triggered_alert(self, area, condition, predicted_cases, probability):
        """Send alert triggered by ML prediction"""
        try:
            # Get verified users in the area
            users = self.db.get_users_by_area(area, verified_only=True)
            
            if not users:
                return False, f"No verified users found in {area}", 0
            
            # Generate message with ML context
            base_message = self.sms.get_health_alert_message(area, condition, predicted_cases)
            ml_message = f"🤖 PREDIKSYON: {base_message} (Probability: {probability:.1%})"
            
            # Send SMS to all users
            sent_count, failed_count = self.sms.send_bulk_sms(users, ml_message)
            
            # Log the alert with ML flag
            alert_data = self._create_alert_record(
                alert_type="health_outbreak",
                area=area,
                message=ml_message,
                recipients_count=sent_count,
                condition=condition,
                cases=predicted_cases,
                is_ml_triggered=True,
                ml_probability=probability
            )
            
            self.db.save_alert(alert_data)
            
            return True, f"ML-triggered alert sent to {sent_count} users", sent_count
            
        except Exception as e:
            return False, f"Error sending ML alert: {str(e)}", 0
    
    def get_alert_history(self, area, limit=50, alert_type=None):
        """Get alert history for an area"""
        try:
            alerts = self.db.get_alerts_history(area, limit, alert_type)
            return True, alerts
        except Exception as e:
            return False, f"Error getting alert history: {str(e)}"
    
    def get_recent_alerts(self, hours=24, area=None):
        """Get recent alerts"""
        try:
            alerts = self.db.get_recent_alerts(hours, area)
            return True, alerts
        except Exception as e:
            return False, f"Error getting recent alerts: {str(e)}"
    
    def get_alert_stats(self):
        """Get alert statistics"""
        try:
            stats = self.db.get_stats()
            return True, stats
        except Exception as e:
            return False, f"Error getting alert stats: {str(e)}"
    
    def _create_alert_record(self, alert_type, area, message, recipients_count, **kwargs):
        """Create alert record for database"""
        current_user = self.auth.get_current_user()
        
        alert_data = {
            "id": self.auth.generate_id(),
            "alert_type": alert_type,
            "area": area,
            "message": message,
            "recipients_count": recipients_count,
            "timestamp": datetime.utcnow().isoformat() if not self.db.use_mongodb else datetime.utcnow(),
            "triggered_by": current_user.get('username', 'system'),
            "staff_user_id": current_user.get('user_id'),
            "is_ml_triggered": kwargs.get('is_ml_triggered', False)
        }
        
        # Add optional fields
        if 'condition' in kwargs:
            alert_data['condition'] = kwargs['condition']
        if 'cases' in kwargs:
            alert_data['cases'] = kwargs['cases']
        if 'crime_type' in kwargs:
            alert_data['crime_type'] = kwargs['crime_type']
        if 'ml_probability' in kwargs:
            alert_data['ml_probability'] = kwargs['ml_probability']
        
        return alert_data
    
    def validate_alert_data(self, alert_type, area, **kwargs):
        """Validate alert data before sending"""
        errors = []
        
        # Validate area
        from config import Config
        if area not in Config.HAITI_AREAS:
            errors.append(f"Invalid area: {area}")
        
        # Validate alert type specific data
        if alert_type == "health_outbreak":
            condition = kwargs.get('condition')
            if not condition or condition not in Config.HEALTH_CONDITIONS:
                errors.append(f"Invalid health condition: {condition}")
        
        elif alert_type == "safety_alert":
            crime_type = kwargs.get('crime_type')
            if not crime_type or crime_type not in Config.CRIME_TYPES:
                errors.append(f"Invalid crime type: {crime_type}")
        
        elif alert_type == "custom_alert":
            message = kwargs.get('message', '').strip()
            if not message:
                errors.append("Custom message cannot be empty")
            elif len(message) > 160:
                errors.append("Message too long (160 character limit)")
        
        return len(errors) == 0, errors