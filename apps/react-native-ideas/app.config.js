const fs = require('node:fs');
const path = require('node:path');

const baseConfig = require('./app.json');

const loadEnvFile = (filePath) => {
  if (!fs.existsSync(filePath)) {
    return {};
  }

  return fs
    .readFileSync(filePath, 'utf8')
    .split(/\r?\n/)
    .reduce((acc, rawLine) => {
      const line = rawLine.trim();
      if (!line || line.startsWith('#')) {
        return acc;
      }
      const separatorIndex = line.indexOf('=');
      if (separatorIndex === -1) {
        return acc;
      }

      const key = line.slice(0, separatorIndex).trim();
      const value = line.slice(separatorIndex + 1).trim().replace(/^['"]|['"]$/g, '');
      if (!key) {
        return acc;
      }

      acc[key] = value;
      return acc;
    }, {});
};

const sanitizeUrl = (value) => {
  if (!value || typeof value !== 'string') {
    return '';
  }
  return value.replace(/\/$/, '');
};

const resolveExtra = () => {
  const repoRoot = path.resolve(__dirname, '..', '..');
  const envFromRoot = loadEnvFile(path.join(repoRoot, '.env'));
  const envFromApp = loadEnvFile(path.join(__dirname, '.env'));

  const env = {
    ...envFromRoot,
    ...envFromApp,
    ...process.env,
  };

  return {
    oryPublicUrl: sanitizeUrl(
      env.EXPO_PUBLIC_KRATOS_PUBLIC_URL ||
        env.EXPO_PUBLIC_ORY_PUBLIC_API_URL ||
        env.VITE_ORY_PUBLIC_API_URL ||
        env.KRATOS_PUBLIC_URL ||
        env.ORY_BROWSER_URL ||
        env.VITE_ORY_BROWSER_URL ||
        '',
    ),
    authUiBaseUrl: sanitizeUrl(
      env.EXPO_PUBLIC_AUTH_UI_BASE_URL || env.VITE_AUTH_UI_BASE_URL || env.AUTH_UI_BASE_URL || '',
    ),
    appBaseUrl: sanitizeUrl(
      env.EXPO_PUBLIC_APP_BASE_URL || env.VITE_APP_BASE_URL || env.APP_BASE_URL || '',
    ),
  };
};

module.exports = () => {
  const extra = resolveExtra();

  if (extra.oryPublicUrl && !process.env.EXPO_PUBLIC_KRATOS_PUBLIC_URL) {
    process.env.EXPO_PUBLIC_KRATOS_PUBLIC_URL = extra.oryPublicUrl;
  }
  if (extra.authUiBaseUrl && !process.env.EXPO_PUBLIC_AUTH_UI_BASE_URL) {
    process.env.EXPO_PUBLIC_AUTH_UI_BASE_URL = extra.authUiBaseUrl;
  }
  if (extra.appBaseUrl && !process.env.EXPO_PUBLIC_APP_BASE_URL) {
    process.env.EXPO_PUBLIC_APP_BASE_URL = extra.appBaseUrl;
  }

  return {
    ...baseConfig,
    expo: {
      ...baseConfig.expo,
      extra: {
        ...baseConfig.expo?.extra,
        ...extra,
      },
    },
  };
};
