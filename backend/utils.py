"""
Utility functions for the Alatem backend
"""
import uuid
import re
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

def generate_id() -> str:
    """Generate a unique UUID string"""
    return str(uuid.uuid4())

def validate_phone_number(phone: str) -> Tuple[bool, str]:
    """
    Validate and format phone number for international use
    
    Args:
        phone: Raw phone number string
        
    Returns:
        Tuple of (is_valid, formatted_phone_or_error_message)
    """
    if not phone:
        return False, "Phone number is required"
    
    # Remove common formatting characters
    clean_phone = re.sub(r'[\s\-\(\)\.]+', '', phone.strip())
    
    # Check if it starts with +
    if clean_phone.startswith('+'):
        # International format: +CountryCode followed by 8-15 digits
        if len(clean_phone) >= 10 and len(clean_phone) <= 16 and clean_phone[1:].isdigit():
            return True, clean_phone
        else:
            return False, "Invalid international phone format"
    
    # Check if it's just digits (add + prefix)
    if clean_phone.isdigit():
        if len(clean_phone) >= 8 and len(clean_phone) <= 15:
            return True, f"+{clean_phone}"
        else:
            return False, "Phone number must be 8-15 digits"
    
    return False, "Phone number must contain only digits and optional +"

def validate_area(area: str) -> bool:
    """
    Validate if area is in allowed list
    
    Args:
        area: Area name to validate
        
    Returns:
        True if valid area
    """
    from config import Config
    return area in Config.HAITI_AREAS

def validate_condition(condition: str) -> bool:
    """
    Validate if health condition is in allowed list
    
    Args:
        condition: Health condition to validate
        
    Returns:
        True if valid condition
    """
    from config import Config
    return condition in Config.HEALTH_CONDITIONS

def validate_crime_type(crime_type: str) -> bool:
    """
    Validate if crime type is in allowed list
    
    Args:
        crime_type: Crime type to validate
        
    Returns:
        True if valid crime type
    """
    from config import Config
    return crime_type in Config.CRIME_TYPES

def format_area_name(area: str) -> str:
    """
    Format area name for display (replace underscores with spaces)
    
    Args:
        area: Area name with underscores
        
    Returns:
        Formatted area name
    """
    return area.replace('_', ' ').title()

def calculate_time_ago(timestamp) -> str:
    """
    Calculate human-readable time difference
    
    Args:
        timestamp: datetime object or ISO string
        
    Returns:
        Human-readable time difference
    """
    if isinstance(timestamp, str):
        try:
            timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        except ValueError:
            return "Unknown time"
    
    now = datetime.utcnow()
    if timestamp.tzinfo is not None:
        # Make now timezone aware if timestamp is
        from datetime import timezone
        now = now.replace(tzinfo=timezone.utc)
    
    diff = now - timestamp
    
    if diff.days > 0:
        return f"{diff.days} day{'s' if diff.days != 1 else ''} ago"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    else:
        return "Just now"

def sanitize_sms_message(message: str, max_length: int = 160) -> str:
    """
    Sanitize and truncate SMS message
    
    Args:
        message: Raw message text
        max_length: Maximum allowed length (SMS limit)
        
    Returns:
        Sanitized message
    """
    # Remove excessive whitespace
    sanitized = re.sub(r'\s+', ' ', message.strip())
    
    # Truncate if too long
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length-3] + "..."
    
    return sanitized

def validate_name(name: str) -> Tuple[bool, str]:
    """
    Validate user name
    
    Args:
        name: User's full name
        
    Returns:
        Tuple of (is_valid, error_message_if_invalid)
    """
    if not name or not name.strip():
        return False, "Name is required"
    
    clean_name = name.strip()
    
    if len(clean_name) < 2:
        return False, "Name must be at least 2 characters"
    
    if len(clean_name) > 100:
        return False, "Name must be less than 100 characters"
    
    # Allow letters, spaces, hyphens, apostrophes, and common international characters
    if not re.match(r"^[a-zA-ZÀ-ÿ\s\-\'\.]+$", clean_name):
        return False, "Name contains invalid characters"
    
    return True, clean_name

def parse_coordinates(latitude, longitude) -> Tuple[Optional[float], Optional[float]]:
    """
    Parse and validate GPS coordinates
    
    Args:
        latitude: Latitude value (string, int, or float)
        longitude: Longitude value (string, int, or float)
        
    Returns:
        Tuple of (latitude, longitude) as floats or (None, None) if invalid
    """
    try:
        if latitude is None or longitude is None:
            return None, None
        
        lat = float(latitude)
        lng = float(longitude)
        
        # Validate latitude range
        if lat < -90 or lat > 90:
            return None, None
        
        # Validate longitude range
        if lng < -180 or lng > 180:
            return None, None
        
        return lat, lng
        
    except (ValueError, TypeError):
        return None, None

def is_haiti_coordinates(latitude: float, longitude: float) -> bool:
    """
    Check if coordinates are within Haiti's approximate boundaries
    
    Args:
        latitude: Latitude coordinate
        longitude: Longitude coordinate
        
    Returns:
        True if coordinates are within Haiti
    """
    # Haiti's approximate boundaries
    # North: 20.0°, South: 18.0°, East: -71.6°, West: -74.5°
    return (18.0 <= latitude <= 20.0) and (-74.5 <= longitude <= -71.6)

def create_response(success: bool, data: dict = None, error: str = None, status_code: int = None) -> dict:
    """
    Create standardized API response
    
    Args:
        success: Whether operation was successful
        data: Response data (if successful)
        error: Error message (if failed)
        status_code: HTTP status code
        
    Returns:
        Standardized response dictionary
    """
    response = {
        'success': success,
        'timestamp': datetime.utcnow().isoformat()
    }
    
    if success and data:
        response.update(data)
    elif not success and error:
        response['error'] = error
    
    if status_code:
        response['status_code'] = status_code
    
    return response

def log_activity(activity_type: str, details: dict, user_id: str = None):
    """
    Log system activity (placeholder for future logging system)
    
    Args:
        activity_type: Type of activity (registration, alert, prediction, etc.)
        details: Activity details
        user_id: User who performed the activity
    """
    # In a production system, this would write to a proper logging system
    timestamp = datetime.utcnow().isoformat()
    log_entry = {
        'timestamp': timestamp,
        'activity_type': activity_type,
        'user_id': user_id,
        'details': details
    }
    
    # For now, just print to console
    print(f"[{timestamp}] {activity_type}: {json.dumps(details, default=str)}")

def get_risk_color(risk_level: str) -> str:
    """
    Get color code for risk level display
    
    Args:
        risk_level: Risk level (HIGH, MEDIUM, LOW)
        
    Returns:
        Color code
    """
    colors = {
        'HIGH': '#e74c3c',
        'MEDIUM': '#f39c12', 
        'LOW': '#27ae60'
    }
    return colors.get(risk_level.upper(), '#95a5a6')

def chunk_list(lst: List, chunk_size: int) -> List[List]:
    """
    Split a list into chunks of specified size
    
    Args:
        lst: List to chunk
        chunk_size: Size of each chunk
        
    Returns:
        List of chunks
    """
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]

def clean_dict(data: dict) -> dict:
    """
    Remove None values and empty strings from dictionary
    
    Args:
        data: Dictionary to clean
        
    Returns:
        Cleaned dictionary
    """
    return {k: v for k, v in data.items() if v is not None and v != ""}

def safe_json_loads(json_str: str, default=None):
    """
    Safely parse JSON string with fallback
    
    Args:
        json_str: JSON string to parse
        default: Default value if parsing fails
        
    Returns:
        Parsed data or default value
    """
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return default or {}

def format_phone_display(phone: str) -> str:
    """
    Format phone number for display purposes
    
    Args:
        phone: Phone number string
        
    Returns:
        Formatted phone number
    """
    # Remove + and spaces for processing
    clean = phone.replace('+', '').replace(' ', '').replace('-', '')
    
    # Format based on length
    if len(clean) == 10:  # US format
        return f"({clean[:3]}) {clean[3:6]}-{clean[6:]}"
    elif len(clean) == 11 and clean.startswith('1'):  # US with country code
        return f"+1 ({clean[1:4]}) {clean[4:7]}-{clean[7:]}"
    else:  # International format
        return f"+{clean[:3]} {clean[3:]}"

def validate_password_strength(password: str) -> Tuple[bool, List[str]]:
    """
    Validate password strength
    
    Args:
        password: Password to validate
        
    Returns:
        Tuple of (is_valid, list_of_issues)
    """
    issues = []
    
    if len(password) < 8:
        issues.append("Password must be at least 8 characters long")
    
    if not re.search(r'[A-Z]', password):
        issues.append("Password must contain at least one uppercase letter")
    
    if not re.search(r'[a-z]', password):
        issues.append("Password must contain at least one lowercase letter")
    
    if not re.search(r'\d', password):
        issues.append("Password must contain at least one number")
    
    return len(issues) == 0, issues