import { ActivityIndicator, Linking, Pressable, Text, View } from 'react-native';
import type { KratosSession } from '../auth/kratosClient';
import { formatTimestamp } from '../auth/kratosClient';
import { globalStyles } from '../styles/theme';

interface HomeScreenProps {
  session: KratosSession;
  statusMessage: string | null;
  helperText: string;
  authUiBaseUrl: string;
  onLogout: () => Promise<void>;
  isBusy: boolean;
}

const MOCK_IDEAS = [
  {
    id: 'idea-1',
    title: 'Capture thoughts offline',
    detail: 'Queue drafts while disconnected, sync once you are back online.',
  },
  {
    id: 'idea-2',
    title: 'Voice memo brainstorming',
    detail: 'Record 30-second clips and turn them into outline cards automatically.',
  },
  {
    id: 'idea-3',
    title: 'Idea heatmap',
    detail: 'Highlight the ideas with the most reactions inside your workspace.',
  },
];

export const HomeScreen = ({
  session,
  statusMessage,
  helperText,
  authUiBaseUrl,
  onLogout,
  isBusy,
}: HomeScreenProps) => {
  const openPortal = (path: string) => {
    if (!authUiBaseUrl) return;
    const target = `${authUiBaseUrl}${path}`;
    Linking.openURL(target).catch((err) => {
      console.warn('Failed to open auth portal', err);
    });
  };

  const handleLogout = () => {
    void onLogout();
  };

  return (
    <View style={globalStyles.card}>
      <Text style={globalStyles.heading}>You're signed in</Text>
      <Text style={globalStyles.subtitle}>{session.identity?.traits?.email ?? session.id}</Text>

      {statusMessage && (
        <View style={globalStyles.noticeBox}>
          <Text style={globalStyles.noticeText}>{statusMessage}</Text>
        </View>
      )}

      <View style={globalStyles.metaContainer}>
        <SessionMeta label='Session' value={session.id} />
        <SessionMeta label='Authenticated' value={formatTimestamp(session.authenticated_at)} />
        <SessionMeta label='Expires' value={formatTimestamp(session.expires_at)} />
      </View>

      <Text style={globalStyles.bodyCopy}>
        This is the logged-in Ideas workspace. From here you can start building native features such as
        drafts, notifications, or offline storage that rely on the Kratos session you just established.
      </Text>

      <View style={{ gap: 12 }}>
        {MOCK_IDEAS.map((idea) => (
          <View
            key={idea.id}
            style={{
              borderWidth: 1,
              borderColor: '#e5e1f8',
              borderRadius: 12,
              padding: 12,
              backgroundColor: '#f8f4ff',
            }}
          >
            <Text style={{ fontSize: 16, fontWeight: '600', color: '#53389e' }}>{idea.title}</Text>
            <Text style={{ color: '#475467', marginTop: 4 }}>{idea.detail}</Text>
          </View>
        ))}
      </View>

      <Pressable
        accessibilityRole="button"
        onPress={handleLogout}
        style={({ pressed }) => [
          globalStyles.secondaryButton,
          pressed && globalStyles.secondaryPressed,
        ]}
      >
        {isBusy ? (
          <ActivityIndicator color='#7f56d9' />
        ) : (
          <Text style={[globalStyles.primaryButtonLabel, globalStyles.secondaryButtonLabel]}>
            Log out
          </Text>
        )}
      </Pressable>

      {authUiBaseUrl ? (
        <Pressable
          accessibilityRole="link"
          onPress={() => openPortal('/')}
          style={globalStyles.textButton}
        >
          <Text style={globalStyles.textButtonLabel}>Open web portal</Text>
        </Pressable>
      ) : null}

      <Text style={globalStyles.helperText}>{helperText}</Text>
    </View>
  );
};

const SessionMeta = ({ label, value }: { label: string; value?: string }) => (
  <View style={globalStyles.metaRow}>
    <Text style={globalStyles.metaLabel}>{label}</Text>
    <Text style={globalStyles.metaValue}>{value ?? 'N/A'}</Text>
  </View>
);
