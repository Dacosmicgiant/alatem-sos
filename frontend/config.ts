// config.ts - Easy configuration for testing
export const CONFIG = {
  // Change this to your backend URL for testing
  API_BASE_URL: 'http://192.168.1.100:5000', // Replace with your IP
  
  // Alternative URLs for different testing scenarios:
  // 'http://localhost:5000'           // Local testing (same machine)
  // 'http://192.168.1.100:5000'      // Network testing (replace with your IP)
  // 'https://your-heroku-app.herokuapp.com'  // Production testing
  
  // Testing settings
  TESTING_MODE: true,
  DEFAULT_COUNTRY_CODE: '+91', // Your country code for testing
  
  // Demo settings
  ENABLE_DEMO_DATA: true,
  SHOW_DEBUG_INFO: true,
};

// API endpoints
export const API_ENDPOINTS = {
  REGISTER: `${CONFIG.API_BASE_URL}/register`,
  VERIFY: `${CONFIG.API_BASE_URL}/verify`,
  ALERTS_HISTORY: `${CONFIG.API_BASE_URL}/alerts/history`,
  STATS: `${CONFIG.API_BASE_URL}/stats`,
};

// Helper function to get the appropriate country code
export const getDefaultCountryCode = () => {
  return CONFIG.DEFAULT_COUNTRY_CODE;
};

// Helper function to format phone numbers for testing
export const formatPhoneForTesting = (phone: string): string => {
  const cleanPhone = phone.trim();
  
  // If already has country code, return as is
  if (cleanPhone.startsWith('+')) {
    return cleanPhone;
  }
  
  // If in testing mode and no country code, add default
  if (CONFIG.TESTING_MODE) {
    return `${CONFIG.DEFAULT_COUNTRY_CODE}${cleanPhone}`;
  }
  
  // Otherwise just add + prefix
  return `+${cleanPhone}`;
};