import { StatusBar } from 'expo-status-bar';
import { ActivityIndicator, Text, View } from 'react-native';
import { useKratosAuth } from './src/auth/useKratosAuth';
import { AuthScreen } from './src/screens/AuthScreen';
import { HomeScreen } from './src/screens/HomeScreen';
import { globalStyles } from './src/styles/theme';

export default function App() {
  const auth = useKratosAuth();

  return (
    <View style={globalStyles.container}>
      <StatusBar style="dark" />
      {auth.bootstrapping ? (
        <BootScreen />
      ) : auth.session ? (
        <HomeScreen
          session={auth.session}
          statusMessage={auth.statusMessage}
          helperText={auth.environment.helperText}
          authUiBaseUrl={auth.environment.authUiBaseUrl}
          onLogout={auth.signOut}
          isBusy={auth.isBusy}
        />
      ) : (
        <AuthScreen auth={auth} />
      )}
    </View>
  );
}

const BootScreen = () => (
  <View style={globalStyles.card}>
    <Text style={globalStyles.heading}>Connecting to Kratos</Text>
    <Text style={globalStyles.subtitle}>Checking for an existing session...</Text>
    <ActivityIndicator style={{ marginTop: 12 }} color="#7f56d9" />
  </View>
);
