import { useState } from 'react';
import { ActivityIndicator, Linking, Pressable, Text, TextInput, View } from 'react-native';
import type { UseKratosAuthResult } from '../auth/useKratosAuth';
import { globalStyles } from '../styles/theme';

interface AuthScreenProps {
  auth: UseKratosAuthResult;
}

export const AuthScreen = ({ auth }: AuthScreenProps) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const submit = () => {
    void auth.signIn({ identifier: email, password });
  };

  const openPortal = (path: string) => {
    if (!auth.environment.authUiBaseUrl) return;
    const target = `${auth.environment.authUiBaseUrl}${path}`;
    Linking.openURL(target).catch((err) => {
      console.warn('Failed to open auth portal', err);
    });
  };

  return (
    <View style={globalStyles.card}>
      <Text style={globalStyles.heading}>Sign in with Kratos</Text>
      <Text style={globalStyles.subtitle}>Use your Ory identity credentials.</Text>

      <View style={globalStyles.formGroup}>
        <Text style={globalStyles.label}>Email</Text>
        <TextInput
          autoCapitalize="none"
          autoComplete="email"
          autoCorrect={false}
          keyboardType="email-address"
          placeholder="you@example.com"
          placeholderTextColor="#98a2b3"
          style={globalStyles.input}
          value={email}
          onChangeText={(value) => {
            setEmail(value);
            if (auth.error) auth.clearError();
          }}
        />
      </View>

      <View style={globalStyles.formGroup}>
        <Text style={globalStyles.label}>Password</Text>
        <TextInput
          autoCapitalize="none"
          placeholder="********"
          placeholderTextColor="#98a2b3"
          secureTextEntry
          style={globalStyles.input}
          value={password}
          onChangeText={(value) => {
            setPassword(value);
            if (auth.error) auth.clearError();
          }}
        />
      </View>

      <Pressable
        accessibilityRole="button"
        disabled={!auth.environment.ready || auth.isBusy}
        onPress={submit}
        style={({ pressed }) => [
          globalStyles.primaryButton,
          pressed && globalStyles.primaryButtonPressed,
          (!auth.environment.ready || auth.isBusy) && globalStyles.primaryButtonDisabled,
        ]}
      >
        {auth.isBusy ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={globalStyles.primaryButtonLabel}>Sign In</Text>
        )}
      </Pressable>

      {auth.statusMessage && (
        <View style={globalStyles.noticeBox}>
          <Text style={globalStyles.noticeText}>{auth.statusMessage}</Text>
        </View>
      )}

      {auth.environment.errorMessage && (
        <Text style={globalStyles.errorText}>{auth.environment.errorMessage}</Text>
      )}
      {auth.error && <Text style={globalStyles.errorText}>{auth.error}</Text>}
      {!auth.error && !auth.environment.errorMessage && (
        <Text style={globalStyles.helperText}>{auth.environment.helperText}</Text>
      )}

      {auth.environment.authUiBaseUrl ? (
        <View style={globalStyles.linksRow}>
          <Pressable
            accessibilityRole="link"
            onPress={() => openPortal('/register')}
            style={globalStyles.textButton}
          >
            <Text style={globalStyles.textButtonLabel}>Register in browser</Text>
          </Pressable>
          <Pressable
            accessibilityRole="link"
            onPress={() => openPortal('/recovery')}
            style={globalStyles.textButton}
          >
            <Text style={globalStyles.textButtonLabel}>Forgot password</Text>
          </Pressable>
        </View>
      ) : null}
    </View>
  );
};
