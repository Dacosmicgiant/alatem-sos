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

export default function UpdateDetails() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState(false);
  
  // Form state
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [selectedArea, setSelectedArea] = useState('');
  const [useLocation, setUseLocation] = useState(false);
  const [location, setLocation] = useState<LocationData | null>(null);
  const [isActive, setIsActive] = useState(true);

  useEffect(() => {
    loadUserData();
  }, []);

  const loadUserData = async () => {
    try {
      const userData = await AsyncStorage.getItem('user_data');
      if (userData) {
        const user = JSON.parse(userData);
        setName(user.name || '');
        setPhone(user.phone || '');
        setSelectedArea(user.area || '');
        setIsActive(user.active !== false);
        
        if (user.latitude && user.longitude) {
          setLocation({
            latitude: user.latitude,
            longitude: user.longitude
          });
          setUseLocation(true);
        }
      } else {
        Alert.alert('No User Data', 'Please register first.');
        router.push('/');
      }
    } catch (error) {
      console.log('Error loading user data:', error);
      Alert.alert('Error', 'Could not load user data.');
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
      
      Alert.alert('Success', 'Location updated successfully!');
    } catch (error) {
      Alert.alert('Error', 'Could not get location. Please check GPS settings.');
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

  const handleUpdate = async () => {
    if (!validateForm()) return;
    
    setUpdating(true);
    
    try {
      // More flexible phone formatting - keep original format if it has country code
      let formattedPhone = phone.trim();
      if (!formattedPhone.startsWith('+')) {
        formattedPhone = `+${formattedPhone}`;
      }
      
      const updatedData = {
        name: name.trim(),
        phone: formattedPhone,
        area: selectedArea,
        latitude: useLocation ? location?.latitude || null : null,
        longitude: useLocation ? location?.longitude || null : null,
        active: isActive,
        verified: true,
        updated_at: new Date().toISOString()
      };

      await AsyncStorage.setItem('user_data', JSON.stringify(updatedData));
      
      Alert.alert(
        'Success!', 
        'Your details have been updated successfully.',
        [{ text: 'OK', onPress: () => router.push('/') }]
      );
      
    } catch (error) {
      Alert.alert('Error', 'Failed to update details. Please try again.');
      console.error('Update error:', error);
    } finally {
      setUpdating(false);
    }
  };

  const handleDeactivate = () => {
    Alert.alert(
      'Deactivate Alerts',
      'Are you sure you want to stop receiving health and safety alerts? You can reactivate anytime.',
      [
        { text: 'Cancel', style: 'cancel' },
        { 
          text: 'Deactivate', 
          style: 'destructive',
          onPress: () => setIsActive(false)
        }
      ]
    );
  };

  const handleReactivate = () => {
    setIsActive(true);
    Alert.alert('Reactivated', 'You will now receive alerts again.');
  };

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#3498db" />
        <Text style={styles.loadingText}>Loading your details...</Text>
      </View>
    );
  }

  return (
    <ScrollView style={styles.container}>
      <View style={styles.header}>
        <TouchableOpacity 
          style={styles.backButton}
          onPress={() => router.push('/')}
        >
          <Text style={styles.backButtonText}>← Back</Text>
        </TouchableOpacity>
        <Text style={styles.title}>📝 Update Details</Text>
        <Text style={styles.subtitle}>Modify your alert preferences</Text>
      </View>

      <View style={styles.form}>
        <View style={[styles.statusCard, isActive ? styles.activeCard : styles.inactiveCard]}>
          <Text style={styles.statusTitle}>
            {isActive ? '✅ Alerts Active' : '⏸️ Alerts Paused'}
          </Text>
          <Text style={styles.statusText}>
            {isActive 
              ? 'You are receiving health and safety alerts'
              : 'You are not receiving alerts'
            }
          </Text>
          <TouchableOpacity 
            style={[styles.statusButton, isActive ? styles.deactivateButton : styles.activateButton]}
            onPress={isActive ? handleDeactivate : handleReactivate}
          >
            <Text style={styles.statusButtonText}>
              {isActive ? 'Pause Alerts' : 'Resume Alerts'}
            </Text>
          </TouchableOpacity>
        </View>

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
            <Text style={styles.label}>Share Location</Text>
            <Switch
              value={useLocation}
              onValueChange={setUseLocation}
              trackColor={{ false: '#767577', true: '#3498db' }}
              thumbColor={useLocation ? '#fff' : '#f4f3f4'}
            />
          </View>
          
          {useLocation && (
            <>
              <TouchableOpacity 
                style={styles.locationButton}
                onPress={requestLocation}
              >
                <Text style={styles.locationButtonText}>
                  📍 {location ? 'Update Location' : 'Get Current Location'}
                </Text>
              </TouchableOpacity>
              
              {location && (
                <View style={styles.locationInfo}>
                  <Text style={styles.locationInfoText}>
                    Current: {location.latitude.toFixed(4)}, {location.longitude.toFixed(4)}
                  </Text>
                </View>
              )}
            </>
          )}
        </View>

        <TouchableOpacity 
          style={[styles.primaryButton, updating && styles.disabledButton]} 
          onPress={handleUpdate}
          disabled={updating}
        >
          {updating ? (
            <ActivityIndicator color="white" />
          ) : (
            <Text style={styles.buttonText}>💾 Save Changes</Text>
          )}
        </TouchableOpacity>
      </View>

      <View style={styles.infoCard}>
        <Text style={styles.infoTitle}>ℹ️ Note</Text>
        <Text style={styles.infoText}>
          • Changes take effect immediately{'\n'}
          • Phone number changes may require re-verification{'\n'}
          • Pausing alerts can be undone anytime{'\n'}
          • Location sharing improves alert accuracy
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
    paddingTop: 50,
  },
  backButton: {
    alignSelf: 'flex-start',
    marginBottom: 15,
  },
  backButtonText: {
    color: 'white',
    fontSize: 16,
    fontWeight: '600',
  },
  title: {
    fontSize: 28,
    fontWeight: 'bold',
    color: 'white',
    marginBottom: 5,
  },
  subtitle: {
    fontSize: 16,
    color: 'rgba(255,255,255,0.9)',
  },
  form: {
    padding: 20,
  },
  statusCard: {
    padding: 20,
    borderRadius: 15,
    marginBottom: 20,
    borderWidth: 2,
  },
  activeCard: {
    backgroundColor: '#e8f5e8',
    borderColor: '#27ae60',
  },
  inactiveCard: {
    backgroundColor: '#fff3cd',
    borderColor: '#f39c12',
  },
  statusTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    marginBottom: 5,
  },
  statusText: {
    fontSize: 14,
    color: '#666',
    marginBottom: 15,
  },
  statusButton: {
    padding: 12,
    borderRadius: 8,
    alignItems: 'center',
  },
  activateButton: {
    backgroundColor: '#27ae60',
  },
  deactivateButton: {
    backgroundColor: '#f39c12',
  },
  statusButtonText: {
    color: 'white',
    fontWeight: '600',
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
    marginBottom: 10,
  },
  locationButtonText: {
    color: '#27ae60',
    fontWeight: '600',
    fontSize: 16,
  },
  locationInfo: {
    backgroundColor: '#f8f9fa',
    padding: 10,
    borderRadius: 5,
    alignItems: 'center',
  },
  locationInfoText: {
    fontSize: 12,
    color: '#666',
  },
  primaryButton: {
    backgroundColor: '#3498db',
    padding: 18,
    borderRadius: 10,
    alignItems: 'center',
    marginTop: 25,
  },
  disabledButton: {
    backgroundColor: '#bdc3c7',
  },
  buttonText: {
    color: 'white',
    fontSize: 16,
    fontWeight: '600',
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