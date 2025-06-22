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
  Switch
} from 'react-native';
import { useRouter } from 'expo-router';
import AsyncStorage from '@react-native-async-storage/async-storage';
import * as Location from 'expo-location';

interface LocationData {
  latitude: number;
  longitude: number;
}

// 🔧 TESTING CONFIGURATION - Change this to your backend IP
const BACKEND_URL = 'http://192.168.0.104:5000'; // Replace with your computer's IP address
const TESTING_MODE = true; // Set to false for production

const HAITI_AREAS = [
  'CITE_SOLEIL',
  'DELMAS', 
  'TABARRE',
  'MARTISSANT',
  'CARREFOUR',
  'PETIONVILLE',
  'CROIX_DES_BOUQUETS',
  'PORT_AU_PRINCE'
];

export default function Index() {
  const router = useRouter();
  const [isFirstTime, setIsFirstTime] = useState(true);
  const [loading, setLoading] = useState(true);
  
  // Registration form state
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [selectedArea, setSelectedArea] = useState('');
  const [useLocation, setUseLocation] = useState(false);
  const [location, setLocation] = useState<LocationData | null>(null);
  const [registering, setRegistering] = useState(false);
  
  // OTP verification state
  const [showOTP, setShowOTP] = useState(false);
  const [otp, setOtp] = useState('');
  const [verifying, setVerifying] = useState(false);

  useEffect(() => {
    checkExistingUser();
  }, []);

  const checkExistingUser = async () => {
    try {
      const userData = await AsyncStorage.getItem('user_data');
      if (userData) {
        const user = JSON.parse(userData);
        if (user.verified) {
          setIsFirstTime(false);
        }
      }
    } catch (error) {
      console.log('Error checking user data:', error);
    } finally {
      setLoading(false);
    }
  };

  const requestLocation = async () => {
    try {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') {
        Alert.alert(
          'Permission Denied',
          'Location permission is needed for accurate area detection.'
        );
        return;
      }

      const locationResult = await Location.getCurrentPositionAsync({
        accuracy: Location.Accuracy.Balanced,
      });
      
      setLocation({
        latitude: locationResult.coords.latitude,
        longitude: locationResult.coords.longitude
      });
      
      Alert.alert('Success', 'Location captured successfully!');
    } catch (error) {
      Alert.alert('Error', 'Could not get location. Please select area manually.');
    }
  };

  const validateForm = () => {
    if (!name.trim()) {
      Alert.alert('Error', 'Please enter your full name');
      return false;
    }
    
    if (!phone.trim()) {
      Alert.alert('Error', 'Please enter your phone number');
      return false;
    }
    
    // More flexible phone validation for international testing
    const phoneRegex = /^(\+\d{1,3})?\d{8,15}$/;
    if (!phoneRegex.test(phone.replace(/[\s\-\(\)]/g, ''))) {
      Alert.alert('Error', 'Please enter a valid phone number (8-15 digits, optional country code)');
      return false;
    }
    
    if (!selectedArea) {
      Alert.alert('Error', 'Please select your area');
      return false;
    }
    
    return true;
  };

  const handleRegister = async () => {
    if (!validateForm()) return;
    
    setRegistering(true);
    
    try {
      // More flexible phone formatting - keep original format if it has country code, otherwise add + prefix
      let formattedPhone = phone.trim();
      if (!formattedPhone.startsWith('+')) {
        // If no country code, you can set your default country code here for testing
        // For India testing, you might want +91, but let's keep it flexible
        formattedPhone = `+${formattedPhone}`;
      }
      
      const registrationData = {
        name: name.trim(),
        phone: formattedPhone,
        area: selectedArea,
        latitude: location?.latitude || null,
        longitude: location?.longitude || null
      };

      const response = await fetch(`${BACKEND_URL}/register`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(registrationData),
      });

      const result = await response.json();

      if (result.success) {
        // Store user data locally
        await AsyncStorage.setItem('user_data', JSON.stringify({
          ...registrationData,
          verified: false
        }));
        
        setShowOTP(true);
        Alert.alert(
          'OTP Sent', 
          result.debug_otp ? 
            `Verification code sent! Debug OTP: ${result.debug_otp}` : 
            'Verification code sent to your phone!'
        );
      } else {
        Alert.alert('Registration Failed', result.error || 'Please try again');
      }
    } catch (error) {
      Alert.alert('Network Error', 'Please check your internet connection');
      console.error('Registration error:', error);
    } finally {
      setRegistering(false);
    }
  };

  const handleVerifyOTP = async () => {
    if (!otp.trim()) {
      Alert.alert('Error', 'Please enter the verification code');
      return;
    }
    
    setVerifying(true);
    
    try {
      const userData = await AsyncStorage.getItem('user_data');
      if (!userData) {
        Alert.alert('Error', 'User data not found. Please register again.');
        return;
      }
      
      const user = JSON.parse(userData);
      
      const response = await fetch(`${BACKEND_URL}/verify`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          phone: user.phone,
          otp: otp.trim()
        }),
      });

      const result = await response.json();

      if (result.verified) {
        // Update local storage
        const updatedUser = { ...user, verified: true };
        await AsyncStorage.setItem('user_data', JSON.stringify(updatedUser));
        
        Alert.alert(
          'Success!', 
          'Your account has been verified. You will now receive health and safety alerts.',
          [{ text: 'OK', onPress: () => setIsFirstTime(false) }]
        );
        setShowOTP(false);
      } else {
        Alert.alert('Verification Failed', result.error || 'Invalid code. Please try again.');
      }
    } catch (error) {
      Alert.alert('Network Error', 'Please check your internet connection');
      console.error('Verification error:', error);
    } finally {
      setVerifying(false);
    }
  };

  const navigateToUpdates = () => {
    router.push('/update-details');
  };

  const navigateToHistory = () => {
    router.push('/sms-history');
  };

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#3498db" />
        <Text style={styles.loadingText}>Loading...</Text>
      </View>
    );
  }

  if (!isFirstTime) {
    // Returning user screen
    return (
      <ScrollView style={styles.container}>
        <View style={styles.header}>
          <Text style={styles.title}>🏥 ALATEM</Text>
          <Text style={styles.subtitle}>Sistèm Alèt Sante ak Sekirite</Text>
          <Text style={styles.welcomeBack}>Welcome back!</Text>
        </View>

        <View style={styles.card}>
          <Text style={styles.cardTitle}>✅ You're Protected</Text>
          <Text style={styles.protectedText}>
            You will receive SMS alerts about health outbreaks and safety issues in your area.
            No need to keep this app installed - alerts work via SMS!
          </Text>
        </View>

        <View style={styles.buttonContainer}>
          <TouchableOpacity style={styles.primaryButton} onPress={navigateToUpdates}>
            <Text style={styles.buttonText}>📝 Update Details</Text>
          </TouchableOpacity>

          <TouchableOpacity style={styles.secondaryButton} onPress={navigateToHistory}>
            <Text style={styles.buttonText}>📱 View SMS History</Text>
          </TouchableOpacity>
        </View>

        <View style={styles.infoCard}>
          <Text style={styles.infoTitle}>🔄 How It Works</Text>
          <Text style={styles.infoText}>
            • You're registered once, protected forever{'\n'}
            • SMS alerts work on any phone{'\n'}
            • No internet required to receive alerts{'\n'}
            • You can delete this app after registration
          </Text>
        </View>
      </ScrollView>
    );
  }

  if (showOTP) {
    // OTP verification screen
    return (
      <ScrollView style={styles.container}>
        <View style={styles.header}>
          <Text style={styles.title}>🔐 Verify Phone</Text>
          <Text style={styles.subtitle}>Enter the code sent to your phone</Text>
        </View>

        <View style={styles.form}>
          <TextInput
            style={styles.otpInput}
            placeholder="Enter 6-digit code"
            value={otp}
            onChangeText={setOtp}
            keyboardType="numeric"
            maxLength={6}
            autoFocus
          />

          <TouchableOpacity 
            style={[styles.primaryButton, verifying && styles.disabledButton]} 
            onPress={handleVerifyOTP}
            disabled={verifying}
          >
            {verifying ? (
              <ActivityIndicator color="white" />
            ) : (
              <Text style={styles.buttonText}>✅ Verify & Complete</Text>
            )}
          </TouchableOpacity>

          <TouchableOpacity 
            style={styles.linkButton}
            onPress={() => setShowOTP(false)}
          >
            <Text style={styles.linkText}>← Back to Registration</Text>
          </TouchableOpacity>
        </View>
      </ScrollView>
    );
  }

  // First-time registration screen
  return (
    <ScrollView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>🏥 ALATEM</Text>
        <Text style={styles.subtitle}>Register Once, Protected Forever</Text>
        <Text style={styles.description}>
          Get SMS alerts about health outbreaks and safety issues (Testing Mode - Any Country)
        </Text>
      </View>

      <View style={styles.form}>
        <Text style={styles.label}>Full Name</Text>
        <TextInput
          style={styles.input}
          placeholder="Enter your full name"
          value={name}
          onChangeText={setName}
          autoCapitalize="words"
        />

        <Text style={styles.label}>Phone Number</Text>
        <TextInput
          style={styles.input}
          placeholder="+91 XXXXX XXXXX (or your country code)"
          value={phone}
          onChangeText={setPhone}
          keyboardType="phone-pad"
        />

        <Text style={styles.label}>Area</Text>
        <View style={styles.areaContainer}>
          {HAITI_AREAS.map((area) => (
            <TouchableOpacity
              key={area}
              style={[
                styles.areaButton,
                selectedArea === area && styles.selectedArea
              ]}
              onPress={() => setSelectedArea(area)}
            >
              <Text style={[
                styles.areaText,
                selectedArea === area && styles.selectedAreaText
              ]}>
                {area.replace(/_/g, ' ')}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        <View style={styles.locationContainer}>
          <View style={styles.locationToggle}>
            <Text style={styles.label}>Use Current Location</Text>
            <Switch
              value={useLocation}
              onValueChange={setUseLocation}
              trackColor={{ false: '#767577', true: '#3498db' }}
              thumbColor={useLocation ? '#fff' : '#f4f3f4'}
            />
          </View>
          
          {useLocation && (
            <TouchableOpacity 
              style={styles.locationButton}
              onPress={requestLocation}
            >
              <Text style={styles.locationButtonText}>
                📍 {location ? 'Location Captured ✅' : 'Get My Location'}
              </Text>
            </TouchableOpacity>
          )}
        </View>

        <TouchableOpacity 
          style={[styles.primaryButton, registering && styles.disabledButton]} 
          onPress={handleRegister}
          disabled={registering}
        >
          {registering ? (
            <ActivityIndicator color="white" />
          ) : (
            <Text style={styles.buttonText}>📱 Register for Alerts</Text>
          )}
        </TouchableOpacity>
      </View>

      <View style={styles.infoCard}>
        <Text style={styles.infoTitle}>ℹ️ Testing Mode</Text>
        <Text style={styles.infoText}>
          • Registration works with any phone number{'\n'}
          • Area selection is manual (for testing){'\n'}
          • SMS alerts work without internet{'\n'}
          • You can delete this app after registration{'\n'}
          • Backend may show debug OTP for testing
        </Text>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f8f9fa',
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#f8f9fa',
  },
  loadingText: {
    marginTop: 10,
    fontSize: 16,
    color: '#666',
  },
  header: {
    backgroundColor: '#3498db',
    padding: 30,
    alignItems: 'center',
  },
  title: {
    fontSize: 32,
    fontWeight: 'bold',
    color: 'white',
    marginBottom: 5,
  },
  subtitle: {
    fontSize: 16,
    color: 'rgba(255,255,255,0.9)',
    textAlign: 'center',
    marginBottom: 10,
  },
  description: {
    fontSize: 14,
    color: 'rgba(255,255,255,0.8)',
    textAlign: 'center',
  },
  welcomeBack: {
    fontSize: 18,
    color: 'white',
    fontWeight: '600',
  },
  form: {
    padding: 20,
  },
  label: {
    fontSize: 16,
    fontWeight: '600',
    color: '#2c3e50',
    marginBottom: 8,
    marginTop: 15,
  },
  input: {
    borderWidth: 2,
    borderColor: '#ddd',
    borderRadius: 10,
    padding: 15,
    fontSize: 16,
    backgroundColor: 'white',
  },
  otpInput: {
    borderWidth: 2,
    borderColor: '#ddd',
    borderRadius: 10,
    padding: 20,
    fontSize: 24,
    backgroundColor: 'white',
    textAlign: 'center',
    letterSpacing: 5,
    marginBottom: 20,
  },
  areaContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
  areaButton: {
    borderWidth: 2,
    borderColor: '#ddd',
    borderRadius: 10,
    padding: 12,
    backgroundColor: 'white',
  },
  selectedArea: {
    borderColor: '#3498db',
    backgroundColor: '#3498db',
  },
  areaText: {
    fontSize: 14,
    color: '#666',
    textAlign: 'center',
  },
  selectedAreaText: {
    color: 'white',
    fontWeight: '600',
  },
  locationContainer: {
    marginTop: 20,
  },
  locationToggle: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 15,
  },
  locationButton: {
    borderWidth: 2,
    borderColor: '#27ae60',
    borderRadius: 10,
    padding: 15,
    backgroundColor: 'white',
    alignItems: 'center',
  },
  locationButtonText: {
    color: '#27ae60',
    fontWeight: '600',
    fontSize: 16,
  },
  primaryButton: {
    backgroundColor: '#3498db',
    padding: 18,
    borderRadius: 10,
    alignItems: 'center',
    marginTop: 25,
  },
  secondaryButton: {
    backgroundColor: '#95a5a6',
    padding: 18,
    borderRadius: 10,
    alignItems: 'center',
    marginTop: 10,
  },
  disabledButton: {
    backgroundColor: '#bdc3c7',
  },
  buttonText: {
    color: 'white',
    fontSize: 16,
    fontWeight: '600',
  },
  linkButton: {
    padding: 15,
    alignItems: 'center',
  },
  linkText: {
    color: '#3498db',
    fontSize: 16,
  },
  buttonContainer: {
    padding: 20,
  },
  card: {
    margin: 20,
    padding: 20,
    backgroundColor: 'white',
    borderRadius: 15,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  cardTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#27ae60',
    marginBottom: 10,
  },
  protectedText: {
    fontSize: 16,
    color: '#666',
    lineHeight: 24,
  },
  infoCard: {
    margin: 20,
    padding: 20,
    backgroundColor: '#e8f4fd',
    borderRadius: 15,
    borderLeftWidth: 4,
    borderLeftColor: '#3498db',
  },
  infoTitle: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#2c3e50',
    marginBottom: 10,
  },
  infoText: {
    fontSize: 14,
    color: '#666',
    lineHeight: 22,
  },
});