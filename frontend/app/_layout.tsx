import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";

export default function RootLayout() {
  return (
    <>
      <StatusBar style="light" />
      <Stack
        screenOptions={{
          headerShown: false, // We're handling headers in each screen
          gestureEnabled: true,
          animation: 'slide_from_right',
        }}
      >
        <Stack.Screen 
          name="index" 
          options={{
            title: "Alatem",
          }} 
        />
        <Stack.Screen 
          name="update-details" 
          options={{
            title: "Update Details",
          }} 
        />
        <Stack.Screen 
          name="sms-history" 
          options={{
            title: "SMS History",
          }} 
        />
      </Stack>
    </>
  );
}