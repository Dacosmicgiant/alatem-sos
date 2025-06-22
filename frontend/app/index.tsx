import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  Alert,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
  StatusBar,
  Dimensions,
} from 'react-native';
import * as Location from 'expo-location';

const { width, height } = Dimensions.get('window');

const HAITI_AREAS = [
  'CITE_SOLEIL',
  'DELMAS',
  'TABARRE',
  'MARTISSANT',
  'CARREFOUR',
  'PETIONVILLE',
  'PORT_AU_PRINCE',
  'CROIX_DES_BOUQUETS',
];

const API_BASE = 'http://192.168.0.104:5000'; // Replace with your backend URL

interface UserInfo {
  name: string;
  phone: string;
  area: string;
  latitude: number | null;
  longitude: number | null;
}

export default function AlatemApp() {
  const [currentStep, setCurrentStep] = useState<'welcome' | 'register' | 'verify' | 'success'>('welcome');
  const [loading, setLoading] = useState(false);
  const [locationLoading, setLocationLoading] = useState(false);
  const [userInfo, setUserInfo] = useState<UserInfo>({
    name: '',
    phone: '',
    area: '',
    latitude: null,
    longitude: null,
  });
  const [otp, setOtp] = useState('');
  const [debugOtp, setDebugOtp] = useState<string | null>(null);

  // Get user's location
  const getLocation = async (): Promise<void> => {
    try {
      setLocationLoading(true);
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') {
        Alert.alert('Permission Denied', 'Location access is needed for precise alerts.');
        return;
      }

      const location = await Location.getCurrentPositionAsync({});
      setUserInfo((prev) => ({
        ...prev,
        latitude: location.coords.latitude,
        longitude: location.coords.longitude,
      }));
    } catch (error) {
      console.log('Location error:', error);
      Alert.alert('Error', 'Failed to get location. Please try again.');
    } finally {
      setLocationLoading(false);
    }
  };

  // Register user
  const handleRegister = async (): Promise<void> => {
    if (!userInfo.name || !userInfo.phone || !userInfo.area) {
      Alert.alert('Error', 'Please fill in all required fields');
      return;
    }

    if (!userInfo.phone.startsWith('+')) {
      Alert.alert('Error', 'Phone number must include country code (e.g., +509...)');
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/register`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(userInfo),
      });

      const data = await response.json();

      if (data.success) {
        setDebugOtp(data.debug_otp);
        setCurrentStep('verify');
        Alert.alert(
          'Success',
          data.debug_otp ? `OTP sent! Debug OTP: ${data.debug_otp}` : 'OTP sent to your phone number'
        );
      } else {
        Alert.alert('Error', data.error || 'Registration failed');
      }
    } catch (error) {
      Alert.alert('Error', 'Network error. Please check your connection.');
      console.error('Registration error:', error);
    } finally {
      setLoading(false);
    }
  };

  // Verify OTP
  const handleVerifyOTP = async (): Promise<void> => {
    if (!otp || otp.length !== 6) {
      Alert.alert('Error', 'Please enter a valid 6-digit OTP');
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/verify`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          phone: userInfo.phone,
          otp,
        }),
      });

      const data = await response.json();

      if (data.verified) {
        setCurrentStep('success');
        Alert.alert('Success!', 'Your phone number is verified. You will now receive alerts.');
      } else {
        Alert.alert('Error', data.error || 'Invalid OTP');
      }
    } catch (error) {
      Alert.alert('Error', 'Network error. Please try again.');
      console.error('Verification error:', error);
    } finally {
      setLoading(false);
    }
  };

  // Update user details
  const handleUpdateDetails = (): void => {
    setCurrentStep('register');
  };

  // Area picker component
  const AreaPicker = () => (
    <View style={styles.areaContainer}>
      <Text style={styles.label}>Select Your Area *</Text>
      <Text style={styles.sublabel}>Choose your area for location-specific alerts</Text>
      <ScrollView style={styles.areaScroll} showsVerticalScrollIndicator={false}>
        {HAITI_AREAS.map((area) => (
          <TouchableOpacity
            key={area}
            style={[styles.areaOption, userInfo.area === area && styles.areaOptionSelected]}
            onPress={() => setUserInfo((prev) => ({ ...prev, area }))}
          >
            <Text style={[styles.areaText, userInfo.area === area && styles.areaTextSelected]}>
              {area.replace(/_/g, ' ')}
            </Text>
          </TouchableOpacity>
        ))}
      </ScrollView>
    </View>
  );

  // Welcome Screen
  const WelcomeScreen = () => (
    <ScrollView style={styles.container} contentContainerStyle={styles.centerContent}>
      <View style={styles.logoContainer}>
        <Text style={styles.logo}>🏥</Text>
        <Text style={styles.appTitle}>Alatem</Text>
        <Text style={styles.tagline}>Health & Safety Alert System for Haiti</Text>
      </View>

      <View style={styles.featuresContainer}>
        <View style={styles.feature}>
          <Text style={styles.featureIcon}>🚨</Text>
          <Text style={styles.featureTitle}>Health Alerts</Text>
          <Text style={styles.featureDescription}>
            Get notified about cholera, fever, and other health risks
          </Text>
        </View>

        <View style={styles.feature}>
          <Text style={styles.featureIcon}>🔒</Text>
          <Text style={styles.featureTitle}>Safety Warnings</Text>
          <Text style={styles.featureDescription}>
            Receive alerts about kidnapping, violence, and other dangers
          </Text>
        </View>

        <View style={styles.feature}>
          <Text style={styles.featureIcon}>📱</Text>
          <Text style={styles.featureTitle}>SMS Protection</Text>
          <Text style={styles.featureDescription}>
            Works via SMS - no internet needed. Delete app after registering!
          </Text>
        </View>
      </View>

      <TouchableOpacity style={styles.primaryButton} onPress={() => setCurrentStep('register')}>
        <Text style={styles.primaryButtonText}>Get Started</Text>
      </TouchableOpacity>

      <TouchableOpacity style={styles.secondaryButton} onPress={handleUpdateDetails}>
        <Text style={styles.secondaryButtonText}>Update My Details</Text>
      </TouchableOpacity>
    </ScrollView>
  );

  // Registration Screen
  const RegisterScreen = () => {
    useEffect(() => {
      getLocation();
    }, []);

    return (
      <ScrollView style={styles.container} contentContainerStyle={styles.formContainer}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => setCurrentStep('welcome')}>
            <Text style={styles.backButton}>← Back</Text>
          </TouchableOpacity>
          <Text style={styles.headerTitle}>Register for Alerts</Text>
        </View>

        <View style={styles.progressBar}>
          <View style={[styles.progressStep, styles.progressStepActive]} />
          <View style={styles.progressStep} />
          <View style={styles.progressStep} />
        </View>

        <Text style={styles.stepTitle}>Personal Information</Text>
        <Text style={styles.stepDescription}>
          Enter your details to receive health and safety alerts
        </Text>

        <View style={styles.inputGroup}>
          <Text style={styles.label}>Full Name *</Text>
          <TextInput
            style={styles.input}
            value={userInfo.name}
            onChangeText={(text) => setUserInfo((prev) => ({ ...prev, name: text }))}
            placeholder="Jean Baptiste"
            placeholderTextColor="#999"
          />
        </View>

        <View style={styles.inputGroup}>
          <Text style={styles.label}>Phone Number *</Text>
          <Text style={styles.sublabel}>Include country code (e.g., +509 for Haiti)</Text>
          <TextInput
            style={styles.input}
            value={userInfo.phone}
            onChangeText={(text) => setUserInfo((prev) => ({ ...prev, phone: text }))}
            placeholder="+509 1234 5678"
            placeholderTextColor="#999"
            keyboardType="phone-pad"
          />
        </View>

        <AreaPicker />

        <TouchableOpacity
          style={[styles.locationButton, locationLoading && styles.buttonDisabled]}
          onPress={getLocation}
          disabled={locationLoading}
        >
          {locationLoading ? (
            <ActivityIndicator color="#27ae60" />
          ) : (
            <>
              <Text style={styles.locationButtonText}>📍 Get My Location</Text>
              <Text style={styles.locationSubtext}>Optional - enhances alert accuracy</Text>
            </>
          )}
        </TouchableOpacity>

        {userInfo.latitude !== null && userInfo.longitude !== null && (
          <Text style={styles.locationText}>
            ✅ Location: {userInfo.latitude.toFixed(4)}, {userInfo.longitude.toFixed(4)}
          </Text>
        )}

        <TouchableOpacity
          style={[styles.primaryButton, loading && styles.buttonDisabled]}
          onPress={handleRegister}
          disabled={loading}
        >
          {loading ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text style={styles.primaryButtonText}>Send Verification Code</Text>
          )}
        </TouchableOpacity>
      </ScrollView>
    );
  };

  // OTP Verification Screen
  const VerifyScreen = () => (
    <ScrollView style={styles.container} contentContainerStyle={styles.centerContent}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => setCurrentStep('register')}>
          <Text style={styles.backButton}>← Back</Text>
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Verify Phone</Text>
      </View>

      <View style={styles.progressBar}>
        <View style={[styles.progressStep, styles.progressStepComplete]} />
        <View style={[styles.progressStep, styles.progressStepActive]} />
        <View style={styles.progressStep} />
      </View>

      <View style={styles.verifyContainer}>
        <Text style={styles.verifyIcon}>📱</Text>
        <Text style={styles.stepTitle}>Enter Verification Code</Text>
        <Text style={styles.stepDescription}>We sent a 6-digit code to {userInfo.phone}</Text>

        {debugOtp && (
          <View style={styles.debugContainer}>
            <Text style={styles.debugText}>Debug OTP: {debugOtp}</Text>
          </View>
        )}

        <TextInput
          style={styles.otpInput}
          value={otp}
          onChangeText={setOtp}
          placeholder="000000"
          placeholderTextColor="#999"
          keyboardType="numeric"
          maxLength={6}
          textAlign="center"
        />

        <TouchableOpacity
          style={[styles.primaryButton, loading && styles.buttonDisabled]}
          onPress={handleVerifyOTP}
          disabled={loading}
        >
          {loading ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text style={styles.primaryButtonText}>Verify & Complete</Text>
          )}
        </TouchableOpacity>

        <TouchableOpacity style={styles.resendButton} onPress={handleRegister}>
          <Text style={styles.resendButtonText}>Resend Code</Text>
        </TouchableOpacity>
      </View>
    </ScrollView>
  );

  // Success Screen
  const SuccessScreen = () => (
    <ScrollView style={styles.container} contentContainerStyle={styles.centerContent}>
      <View style={styles.progressBar}>
        <View style={[styles.progressStep, styles.progressStepComplete]} />
        <View style={[styles.progressStep, styles.progressStepComplete]} />
        <View style={[styles.progressStep, styles.progressStepComplete]} />
      </View>

      <View style={styles.successContainer}>
        <Text style={styles.successIcon}>✅</Text>
        <Text style={styles.successTitle}>Registration Complete!</Text>
        <Text style={styles.successMessage}>
          You are now registered for alerts in {userInfo.area.replace(/_/g, ' ')}.
        </Text>

        <View style={styles.importantInfo}>
          <Text style={styles.importantTitle}>🎉 You're Protected Forever!</Text>
          <Text style={styles.importantText}>
            • Receive SMS alerts even if you delete this app{'\n'}
            • No internet needed for alerts{'\n'}
            • Covers health outbreaks and security warnings{'\n'}
            • Free service - no charges for alerts
          </Text>
        </View>

        <View style={styles.exampleAlert}>
          <Text style={styles.exampleTitle}>Example Alert:</Text>
          <Text style={styles.exampleText}>
            "🚨 ALÈT SANTE: Ka cholera nan {userInfo.area.replace(/_/g, ' ')}. Bwè dlo pwòp, lave men nou. Ale kay doktè si nou gen simptòm."
          </Text>
        </View>

        <TouchableOpacity style={styles.primaryButton} onPress={() => setCurrentStep('welcome')}>
          <Text style={styles.primaryButtonText}>Done - You Can Delete This App!</Text>
        </TouchableOpacity>

        <TouchableOpacity style={styles.secondaryButton} onPress={() => setCurrentStep('register')}>
          <Text style={styles.secondaryButtonText}>Update My Details</Text>
        </TouchableOpacity>
      </View>
    </ScrollView>
  );

  // Main render
  return (
    <View style={styles.appContainer}>
      <StatusBar barStyle="light-content" backgroundColor="#667eea" />
      {currentStep === 'welcome' && <WelcomeScreen />}
      {currentStep === 'register' && <RegisterScreen />}
      {currentStep === 'verify' && <VerifyScreen />}
      {currentStep === 'success' && <SuccessScreen />}
    </View>
  );
}

const styles = StyleSheet.create({
  appContainer: {
    flex: 1,
    backgroundColor: '#f8f9fa',
  },
  container: {
    flex: 1,
    paddingTop: 50,
  },
  centerContent: {
    paddingHorizontal: 20,
    paddingBottom: 40,
  },
  formContainer: {
    paddingHorizontal: 20,
    paddingBottom: 40,
  },

  // Header
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 30,
  },
  backButton: {
    fontSize: 16,
    color: '#667eea',
    fontWeight: '600',
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#2c3e50',
    marginLeft: 20,
  },

  // Progress Bar
  progressBar: {
    flexDirection: 'row',
    justifyContent: 'center',
    marginBottom: 30,
    paddingHorizontal: 40,
  },
  progressStep: {
    flex: 1,
    height: 4,
    backgroundColor: '#e1e5e9',
    marginHorizontal: 2,
    borderRadius: 2,
  },
  progressStepActive: {
    backgroundColor: '#667eea',
  },
  progressStepComplete: {
    backgroundColor: '#27ae60',
  },

  // Logo & Branding
  logoContainer: {
    alignItems: 'center',
    marginBottom: 40,
    marginTop: 20,
  },
  logo: {
    fontSize: 80,
    marginBottom: 10,
  },
  appTitle: {
    fontSize: 32,
    fontWeight: 'bold',
    color: '#2c3e50',
    marginBottom: 8,
  },
  tagline: {
    fontSize: 16,
    color: '#7f8c8d',
    textAlign: 'center',
    lineHeight: 22,
  },

  // Features
  featuresContainer: {
    marginBottom: 40,
  },
  feature: {
    backgroundColor: '#fff',
    padding: 20,
    borderRadius: 12,
    marginBottom: 15,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  featureIcon: {
    fontSize: 24,
    marginBottom: 8,
  },
  featureTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#2c3e50',
    marginBottom: 5,
  },
  featureDescription: {
    fontSize: 14,
    color: '#7f8c8d',
    lineHeight: 20,
  },

  // Form Elements
  stepTitle: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#2c3e50',
    marginBottom: 8,
    textAlign: 'center',
  },
  stepDescription: {
    fontSize: 16,
    color: '#7f8c8d',
    textAlign: 'center',
    marginBottom: 30,
    lineHeight: 22,
  },
  inputGroup: {
    marginBottom: 20,
  },
  label: {
    fontSize: 16,
    fontWeight: '600',
    color: '#2c3e50',
    marginBottom: 5,
  },
  sublabel: {
    fontSize: 12,
    color: '#7f8c8d',
    marginBottom: 8,
  },
  input: {
    borderWidth: 2,
    borderColor: '#e1e5e9',
    borderRadius: 12,
    padding: 16,
    fontSize: 16,
    backgroundColor: '#fff',
    color: '#2c3e50',
  },

  // Area Picker
  areaContainer: {
    marginBottom: 20,
  },
  areaScroll: {
    maxHeight: 200,
    backgroundColor: '#fff',
    borderRadius: 12,
    borderWidth: 2,
    borderColor: '#e1e5e9',
  },
  areaOption: {
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#f1f2f6',
  },
  areaOptionSelected: {
    backgroundColor: '#667eea',
  },
  areaText: {
    fontSize: 16,
    color: '#2c3e50',
  },
  areaTextSelected: {
    color: '#fff',
    fontWeight: '600',
  },

  // Location
  locationButton: {
    backgroundColor: '#fff',
    borderWidth: 2,
    borderColor: '#27ae60',
    borderRadius: 12,
    padding: 16,
    alignItems: 'center',
    marginBottom: 10,
  },
  locationButtonText: {
    fontSize: 16,
    color: '#27ae60',
    fontWeight: '600',
  },
  locationSubtext: {
    fontSize: 12,
    color: '#7f8c8d',
    marginTop: 4,
  },
  locationText: {
    fontSize: 12,
    color: '#27ae60',
    textAlign: 'center',
    marginBottom: 20,
  },

  // Buttons
  primaryButton: {
    backgroundColor: '#667eea',
    borderRadius: 12,
    padding: 18,
    alignItems: 'center',
    marginBottom: 15,
    shadowColor: '#667eea',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 5,
  },
  primaryButtonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: 'bold',
  },
  secondaryButton: {
    backgroundColor: 'transparent',
    borderWidth: 2,
    borderColor: '#667eea',
    borderRadius: 12,
    padding: 18,
    alignItems: 'center',
    marginBottom: 15,
  },
  secondaryButtonText: {
    color: '#667eea',
    fontSize: 16,
    fontWeight: '600',
  },
  buttonDisabled: {
    opacity: 0.6,
  },

  // OTP Verification
  verifyContainer: {
    alignItems: 'center',
    paddingHorizontal: 20,
  },
  verifyIcon: {
    fontSize: 60,
    marginBottom: 20,
  },
  otpInput: {
    borderWidth: 2,
    borderColor: '#667eea',
    borderRadius: 12,
    padding: 20,
    fontSize: 24,
    fontWeight: 'bold',
    color: '#2c3e50',
    backgroundColor: '#fff',
    width: 200,
    marginBottom: 30,
    letterSpacing: 8,
  },
  debugContainer: {
    backgroundColor: '#fff3cd',
    padding: 10,
    borderRadius: 8,
    marginBottom: 20,
  },
  debugText: {
    color: '#856404',
    fontWeight: '600',
    textAlign: 'center',
  },
  resendButton: {
    padding: 10,
  },
  resendButtonText: {
    color: '#667eea',
    fontSize: 14,
    textDecorationLine: 'underline',
  },

  // Success Screen
  successContainer: {
    alignItems: 'center',
    paddingHorizontal: 20,
  },
  successIcon: {
    fontSize: 80,
    marginBottom: 20,
  },
  successTitle: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#27ae60',
    marginBottom: 15,
    textAlign: 'center',
  },
  successMessage: {
    fontSize: 16,
    color: '#2c3e50',
    textAlign: 'center',
    marginBottom: 30,
    lineHeight: 22,
  },
  importantInfo: {
    backgroundColor: '#e8f5e8',
    padding: 20,
    borderRadius: 12,
    marginBottom: 20,
    width: '100%',
  },
  importantTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#27ae60',
    marginBottom: 10,
    textAlign: 'center',
  },
  importantText: {
    fontSize: 14,
    color: '#2c3e50',
    lineHeight: 20,
  },
  exampleAlert: {
    backgroundColor: '#fff3cd',
    padding: 15,
    borderRadius: 8,
    marginBottom: 30,
    width: '100%',
  },
  exampleTitle: {
    fontSize: 14,
    fontWeight: 'bold',
    color: '#856404',
    marginBottom: 5,
  },
  exampleText: {
    fontSize: 12,
    color: '#856404',
    fontStyle: 'italic',
  },
});