import { StyleSheet } from 'react-native';

export const globalStyles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f3f3f5',
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 24,
  },
  card: {
    width: '100%',
    maxWidth: 440,
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
  primaryButton: {
    backgroundColor: '#7f56d9',
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: 'center',
    marginTop: 8,
  },
  primaryButtonPressed: {
    opacity: 0.85,
  },
  primaryButtonDisabled: {
    opacity: 0.6,
  },
  primaryButtonLabel: {
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
  noticeBox: {
    backgroundColor: '#efe9fc',
    borderRadius: 10,
    padding: 12,
    marginTop: 16,
    borderWidth: 1,
    borderColor: '#d6bbfb',
  },
  noticeText: {
    color: '#53389e',
    fontSize: 14,
  },
  textButton: {
    paddingVertical: 6,
    paddingHorizontal: 12,
  },
  textButtonLabel: {
    color: '#7f56d9',
    fontSize: 14,
    fontWeight: '500',
  },
  linksRow: {
    marginTop: 16,
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  metaContainer: {
    backgroundColor: '#f8f3ff',
    padding: 16,
    borderRadius: 12,
    marginBottom: 24,
    marginTop: 8,
  },
  metaRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 10,
  },
  metaLabel: {
    fontSize: 12,
    color: '#6941c6',
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 0.8,
  },
  metaValue: {
    fontSize: 16,
    color: '#101828',
  },
  secondaryButton: {
    backgroundColor: '#efe9fc',
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: 'center',
    marginTop: 8,
  },
  secondaryPressed: {
    opacity: 0.6,
  },
  secondaryButtonLabel: {
    color: '#7f56d9',
  },
  bodyCopy: {
    fontSize: 16,
    color: '#475467',
    marginBottom: 24,
  },
});
