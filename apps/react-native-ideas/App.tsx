import { useMemo, useState } from 'react';
import { StatusBar } from 'expo-status-bar';
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

const DEMO_USER = {
  email: 'demo@ideas.app',
  password: 'letmein',
  name: 'Idea Explorer',
};

const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export default function App() {
  const [email, setEmail] = useState(DEMO_USER.email);
  const [password, setPassword] = useState(DEMO_USER.password);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [user, setUser] = useState<typeof DEMO_USER | null>(null);

  const helperText = useMemo(
    () => `Try ${DEMO_USER.email} / ${DEMO_USER.password}`,
    [],
  );

  const handleLogin = async () => {
    if (isLoading) {
      return;
    }

    setError(null);

    if (!email.trim() || !password.trim()) {
      setError('Please provide both email and password.');
      return;
    }

    setIsLoading(true);
    await wait(800);

    const normalizedEmail = email.trim().toLowerCase();
    if (
      normalizedEmail === DEMO_USER.email &&
      password.trim() === DEMO_USER.password
    ) {
      setUser(DEMO_USER);
    } else {
      setError('Invalid credentials. Please try again.');
      setUser(null);
    }
    setIsLoading(false);
  };

  const handleLogout = () => {
    setUser(null);
    setPassword('');
  };

  const renderLogin = () => (
    <View style={styles.card}>
      <Text style={styles.heading}>Sign in to Ideas</Text>
      <Text style={styles.subtitle}>Sketch, capture and revisit ideas.</Text>

      <View style={styles.formGroup}>
        <Text style={styles.label}>Email</Text>
        <TextInput
          autoCapitalize="none"
          autoComplete="email"
          autoCorrect={false}
          keyboardType="email-address"
          placeholder="you@domain.com"
          placeholderTextColor="#98a2b3"
          style={styles.input}
          value={email}
          onChangeText={setEmail}
        />
      </View>

      <View style={styles.formGroup}>
        <Text style={styles.label}>Password</Text>
        <TextInput
          autoCapitalize="none"
          placeholder="********"
          placeholderTextColor="#98a2b3"
          secureTextEntry
          style={styles.input}
          value={password}
          onChangeText={setPassword}
        />
      </View>

      <Pressable
        accessibilityRole="button"
        disabled={isLoading}
        onPress={handleLogin}
        style={({ pressed }) => [
          styles.button,
          pressed && styles.buttonPressed,
          isLoading && styles.buttonDisabled,
        ]}
      >
        {isLoading ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.buttonLabel}>Sign In</Text>
        )}
      </Pressable>

      {error ? (
        <Text style={styles.errorText}>{error}</Text>
      ) : (
        <Text style={styles.helperText}>{helperText}</Text>
      )}
    </View>
  );

  const renderWelcome = () => (
    <View style={styles.card}>
      <Text style={styles.heading}>Welcome back!</Text>
      <Text style={styles.subtitle}>{user?.name}</Text>
      <Text style={styles.bodyCopy}>
        You're authenticated and ready to continue jotting down the next big
        idea.
      </Text>
      <View style={styles.metaContainer}>
        <Text style={styles.metaTitle}>Signed in as</Text>
        <Text style={styles.metaValue}>{user?.email}</Text>
      </View>
      <Pressable
        accessibilityRole="button"
        onPress={handleLogout}
        style={({ pressed }) => [
          styles.button,
          styles.secondaryButton,
          pressed && styles.secondaryPressed,
        ]}
      >
        <Text style={[styles.buttonLabel, styles.secondaryButtonLabel]}>
          Log out
        </Text>
      </Pressable>
    </View>
  );

  return (
    <View style={styles.container}>
      <StatusBar style="dark" />
      {user ? renderWelcome() : renderLogin()}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f3f3f5',
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 24,
  },
  card: {
    width: '100%',
    maxWidth: 420,
    backgroundColor: '#ffffff',
    borderRadius: 16,
    padding: 24,
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 10 },
    shadowOpacity: 0.1,
    shadowRadius: 20,
    elevation: 6,
  },
  heading: {
    fontSize: 24,
    fontWeight: '600',
    color: '#1d2939',
  },
  subtitle: {
    fontSize: 16,
    color: '#475467',
    marginTop: 4,
    marginBottom: 24,
  },
  formGroup: {
    marginBottom: 16,
  },
  label: {
    fontSize: 14,
    fontWeight: '500',
    marginBottom: 6,
    color: '#475467',
  },
  input: {
    borderWidth: 1,
    borderColor: '#d0d5dd',
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 16,
    color: '#101828',
    backgroundColor: '#f8fafc',
  },
  button: {
    backgroundColor: '#7f56d9',
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: 'center',
    marginTop: 8,
  },
  buttonPressed: {
    opacity: 0.85,
  },
  buttonDisabled: {
    opacity: 0.6,
  },
  buttonLabel: {
    fontSize: 16,
    fontWeight: '600',
    color: '#fff',
  },
  helperText: {
    marginTop: 16,
    color: '#475467',
    textAlign: 'center',
    fontSize: 14,
  },
  errorText: {
    marginTop: 16,
    color: '#d92d20',
    textAlign: 'center',
    fontSize: 14,
  },
  bodyCopy: {
    fontSize: 16,
    color: '#475467',
    marginBottom: 24,
  },
  metaContainer: {
    backgroundColor: '#f8f3ff',
    padding: 16,
    borderRadius: 12,
    marginBottom: 24,
  },
  metaTitle: {
    fontSize: 12,
    color: '#6941c6',
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 0.8,
  },
  metaValue: {
    fontSize: 16,
    color: '#101828',
    marginTop: 6,
  },
  secondaryButton: {
    backgroundColor: '#efe9fc',
  },
  secondaryPressed: {
    opacity: 0.6,
  },
  secondaryButtonLabel: {
    color: '#7f56d9',
  },
});
