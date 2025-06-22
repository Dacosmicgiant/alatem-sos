import React, { useState, useEffect } from 'react';
import { 
  View, 
  Text, 
  TouchableOpacity, 
  ScrollView, 
  StyleSheet,
  ActivityIndicator,
  RefreshControl,
  Alert
} from 'react-native';
import { useRouter } from 'expo-router';
import AsyncStorage from '@react-native-async-storage/async-storage';

interface AlertMessage {
  id: string;
  alert_type: string;
  area: string;
  message: string;
  timestamp: string;
  recipients_count: number;
  triggered_by: string;
}

export default function SMSHistory() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [alerts, setAlerts] = useState<AlertMessage[]>([]);
  const [userArea, setUserArea] = useState('');
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    loadUserAreaAndAlerts();
  }, []);

  const loadUserAreaAndAlerts = async () => {
    try {
      const userData = await AsyncStorage.getItem('user_data');
      if (userData) {
        const user = JSON.parse(userData);
        setUserArea(user.area || '');
        await fetchAlerts(user.area);
      } else {
        Alert.alert('No User Data', 'Please register first.');
        router.push('/');
      }
    } catch (error) {
      console.log('Error loading user data:', error);
    }
  };

  const fetchAlerts = async (area: string) => {
    if (!area) return;
    
    try {
      // Try to fetch from backend
      const response = await fetch(`http://192.168.1.100:5000/alerts/history?area=${area}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        const data = await response.json();
        setAlerts(data.alerts || []);
        setConnected(true);
      } else {
        throw new Error('Server error');
      }
    } catch (error) {
      console.log('Backend not available, using demo data:', error);
      setConnected(false);
      
      // Load demo data if backend is not available
      const demoAlerts = generateDemoAlerts(area);
      setAlerts(demoAlerts);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const generateDemoAlerts = (area: string): AlertMessage[] => {
    const now = new Date();
    const demoAlerts: AlertMessage[] = [
      {
        id: '1',
        alert_type: 'health_outbreak',
        area: area,
        message: `🚨 ALÈT SANTE: 12 ka cholera nan ${area}. Bwè dlo pwòp, lave men nou. Ale kay doktè si nou gen simptòm.`,
        timestamp: new Date(now.getTime() - 2 * 60 * 60 * 1000).toISOString(), // 2 hours ago
        recipients_count: 156,
        triggered_by: 'health_worker'
      },
      {
        id: '2',
        alert_type: 'safety_alert',
        area: area,
        message: `⚠️ SEKIRITE: Danje nan ${area}. Fè atansyon. Pa mache pou kont nou.`,
        timestamp: new Date(now.getTime() - 24 * 60 * 60 * 1000).toISOString(), // 1 day ago
        recipients_count: 156,
        triggered_by: 'system'
      },
      {
        id: '3',
        alert_type: 'health_outbreak',
        area: area,
        message: `🌡️ ALÈT SANTE: Ka lafyèv nan ${area}. Rete lakay si nou malad. Bwè dlo anpil.`,
        timestamp: new Date(now.getTime() - 3 * 24 * 60 * 60 * 1000).toISOString(), // 3 days ago
        recipients_count: 156,
        triggered_by: 'health_worker'
      },
      {
        id: '4',
        alert_type: 'custom_alert',
        area: area,
        message: `ℹ️ ENFÒMASYON: Vaksinasyon gratis nan ${area} jodi a 9h-4h nan sant sante a.`,
        timestamp: new Date(now.getTime() - 5 * 24 * 60 * 60 * 1000).toISOString(), // 5 days ago
        recipients_count: 156,
        triggered_by: 'health_worker'
      },
      {
        id: '5',
        alert_type: 'safety_alert',
        area: area,
        message: `🚨 SEKIRITE: Kidnapping nan ${area}. Pa mache pou kont nou. Evite kote yo ki izole.`,
        timestamp: new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000).toISOString(), // 1 week ago
        recipients_count: 156,
        triggered_by: 'system'
      }
    ];
    
    return demoAlerts;
  };

  const onRefresh = async () => {
    setRefreshing(true);
    await fetchAlerts(userArea);
  };

  const getAlertIcon = (alertType: string) => {
    switch (alertType) {
      case 'health_outbreak':
        return '🏥';
      case 'safety_alert':
        return '⚠️';
      case 'custom_alert':
        return 'ℹ️';
      default:
        return '📱';
    }
  };

  const getAlertTypeText = (alertType: string) => {
    switch (alertType) {
      case 'health_outbreak':
        return 'Health Alert';
      case 'safety_alert':
        return 'Safety Alert';
      case 'custom_alert':
        return 'Information';
      default:
        return 'Alert';
    }
  };

  const getTimeAgo = (timestamp: string) => {
    const now = new Date();
    const alertTime = new Date(timestamp);
    const diffMs = now.getTime() - alertTime.getTime();
    const diffMins = Math.floor(diffMs / (1000 * 60));
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMins < 60) {
      return `${diffMins} minutes ago`;
    } else if (diffHours < 24) {
      return `${diffHours} hours ago`;
    } else {
      return `${diffDays} days ago`;
    }
  };

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#3498db" />
        <Text style={styles.loadingText}>Loading SMS history...</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <TouchableOpacity 
          style={styles.backButton}
          onPress={() => router.push('/')}
        >
          <Text style={styles.backButtonText}>← Back</Text>
        </TouchableOpacity>
        <Text style={styles.title}>📱 SMS History</Text>
        <Text style={styles.subtitle}>Alerts sent to {userArea.replace(/_/g, ' ')}</Text>
      </View>

      <View style={styles.statusBar}>
        <View style={[styles.connectionStatus, connected ? styles.connected : styles.disconnected]}>
          <Text style={styles.connectionText}>
            {connected ? '🟢 Live Data' : '🔴 Demo Data (Offline)'}
          </Text>
        </View>
        <Text style={styles.alertCount}>
          {alerts.length} alert{alerts.length !== 1 ? 's' : ''}
        </Text>
      </View>

      <ScrollView 
        style={styles.scrollView}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
      >
        {alerts.length === 0 ? (
          <View style={styles.emptyState}>
            <Text style={styles.emptyIcon}>📭</Text>
            <Text style={styles.emptyTitle}>No alerts yet</Text>
            <Text style={styles.emptyText}>
              You haven't received any SMS alerts yet. This is good news - no outbreaks or emergencies in your area!
            </Text>
          </View>
        ) : (
          alerts.map((alert) => (
            <View key={alert.id} style={styles.alertCard}>
              <View style={styles.alertHeader}>
                <View style={styles.alertTypeContainer}>
                  <Text style={styles.alertIcon}>{getAlertIcon(alert.alert_type)}</Text>
                  <Text style={styles.alertType}>{getAlertTypeText(alert.alert_type)}</Text>
                </View>
                <Text style={styles.alertTime}>{getTimeAgo(alert.timestamp)}</Text>
              </View>
              
              <Text style={styles.alertMessage}>{alert.message}</Text>
              
              <View style={styles.alertFooter}>
                <Text style={styles.alertMeta}>
                  Sent to {alert.recipients_count} users • By {alert.triggered_by}
                </Text>
              </View>
            </View>
          ))
        )}
      </ScrollView>

      <View style={styles.infoCard}>
        <Text style={styles.infoTitle}>ℹ️ About SMS History</Text>
        <Text style={styles.infoText}>
          {connected 
            ? 'This shows real alerts sent to your area. Pull down to refresh for the latest alerts.'
            : 'Currently showing demo data. Connect to internet to see real alert history from the server.'
          }
        </Text>
      </View>
    </View>
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
  statusBar: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 15,
    backgroundColor: 'white',
    borderBottomWidth: 1,
    borderBottomColor: '#eee',
  },
  connectionStatus: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 20,
  },
  connected: {
    backgroundColor: '#e8f5e8',
  },
  disconnected: {
    backgroundColor: '#ffeaea',
  },
  connectionText: {
    fontSize: 12,
    fontWeight: '600',
  },
  alertCount: {
    fontSize: 14,
    color: '#666',
    fontWeight: '600',
  },
  scrollView: {
    flex: 1,
  },
  alertCard: {
    backgroundColor: 'white',
    margin: 15,
    marginBottom: 10,
    padding: 20,
    borderRadius: 15,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  alertHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 15,
  },
  alertTypeContainer: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  alertIcon: {
    fontSize: 20,
    marginRight: 8,
  },
  alertType: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#2c3e50',
  },
  alertTime: {
    fontSize: 12,
    color: '#95a5a6',
  },
  alertMessage: {
    fontSize: 16,
    color: '#2c3e50',
    lineHeight: 24,
    marginBottom: 15,
  },
  alertFooter: {
    borderTopWidth: 1,
    borderTopColor: '#ecf0f1',
    paddingTop: 10,
  },
  alertMeta: {
    fontSize: 12,
    color: '#95a5a6',
  },
  emptyState: {
    alignItems: 'center',
    padding: 50,
    marginTop: 50,
  },
  emptyIcon: {
    fontSize: 64,
    marginBottom: 20,
  },
  emptyTitle: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#2c3e50',
    marginBottom: 10,
  },
  emptyText: {
    fontSize: 16,
    color: '#666',
    textAlign: 'center',
    lineHeight: 24,
  },
  infoCard: {
    margin: 15,
    padding: 15,
    backgroundColor: '#e8f4fd',
    borderRadius: 10,
    borderLeftWidth: 4,
    borderLeftColor: '#3498db',
  },
  infoTitle: {
    fontSize: 14,
    fontWeight: 'bold',
    color: '#2c3e50',
    marginBottom: 5,
  },
  infoText: {
    fontSize: 12,
    color: '#666',
    lineHeight: 18,
  },
});