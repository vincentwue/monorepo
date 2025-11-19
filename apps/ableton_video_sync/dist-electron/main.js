import { ipcMain, BrowserWindow, shell, dialog, app } from "electron";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { existsSync, readFileSync, mkdirSync, writeFileSync, readdirSync, statSync } from "node:fs";
const __dirname = path.dirname(fileURLToPath(import.meta.url));
process.env.APP_ROOT = path.join(__dirname, "..");
const VITE_DEV_SERVER_URL = process.env["VITE_DEV_SERVER_URL"];
const MAIN_DIST = path.join(process.env.APP_ROOT, "dist-electron");
const RENDERER_DIST = path.join(process.env.APP_ROOT, "dist");
process.env.VITE_PUBLIC = VITE_DEV_SERVER_URL ? path.join(process.env.APP_ROOT, "public") : RENDERER_DIST;
let win;
const SETTINGS_FILE_NAME = "settings.json";
let cachedSettings = null;
const resolveSettingsRoot = () => {
  if (app.isPackaged) {
    return path.dirname(app.getPath("exe"));
  }
  return process.env.APP_ROOT ?? app.getAppPath();
};
const getSettingsPath = () => path.join(resolveSettingsRoot(), SETTINGS_FILE_NAME);
const loadSettingsFromDisk = () => {
  const settingsPath = getSettingsPath();
  try {
    if (!existsSync(settingsPath)) {
      return {};
    }
    const raw = readFileSync(settingsPath, "utf-8");
    return raw ? JSON.parse(raw) : {};
  } catch (error) {
    console.error("[settings] Failed to read settings file", error);
    return {};
  }
};
const getSettings = () => {
  if (!cachedSettings) {
    cachedSettings = loadSettingsFromDisk();
  }
  return cachedSettings;
};
const persistSettings = (next) => {
  const settingsPath = getSettingsPath();
  cachedSettings = next;
  try {
    mkdirSync(path.dirname(settingsPath), { recursive: true });
    writeFileSync(settingsPath, JSON.stringify(next, null, 2), "utf-8");
  } catch (error) {
    console.error("[settings] Failed to save settings file", error);
  }
  return cachedSettings;
};
const updateSettings = (partial) => {
  const nextSettings = {
    ...getSettings(),
    ...partial
  };
  if (nextSettings.activeProjectPath && !existsSync(nextSettings.activeProjectPath)) {
    nextSettings.activeProjectPath = null;
  }
  return persistSettings(nextSettings);
};
const broadcastSettings = () => {
  const current = getSettings();
  BrowserWindow.getAllWindows().forEach((window) => {
    window.webContents.send("settings:updated", current);
  });
  return current;
};
const CORE_PROJECT_DIRS = ["ableton", "footage", "generated"];
const VIDEO_EXTENSIONS = [".mp4", ".mov", ".mxf"];
const AUDIO_EXTENSIONS = [".wav", ".mp3", ".aiff", ".flac"];
const IMAGE_EXTENSIONS = [".png", ".jpg", ".jpeg", ".bmp"];
const sanitizeProjectName = (name) => name.replace(/[<>:"/\\|?*]/g, " ").replace(/\s+/g, " ").trim();
const ensureDirectory = (dirPath) => {
  if (!existsSync(dirPath)) {
    mkdirSync(dirPath, { recursive: true });
  }
};
const safeReadDir = (dirPath) => {
  try {
    return readdirSync(dirPath, { withFileTypes: true });
  } catch {
    return [];
  }
};
const isReadableDirectory = (dirPath) => {
  try {
    return statSync(dirPath).isDirectory();
  } catch {
    return false;
  }
};
const directoryHasChildren = (dirPath) => safeReadDir(dirPath).some((entry) => entry.isDirectory());
const listRootDirectories = () => {
  if (process.platform === "win32") {
    const drives = [];
    for (let charCode = 65; charCode <= 90; charCode += 1) {
      const letter = String.fromCharCode(charCode);
      const drivePath = `${letter}:\\`;
      if (!isReadableDirectory(drivePath)) {
        continue;
      }
      drives.push({
        path: drivePath,
        name: `${letter}:\\`,
        hasChildren: directoryHasChildren(drivePath)
      });
    }
    return drives;
  }
  const rootPath = path.parse(process.cwd()).root || "/";
  const roots = [];
  if (isReadableDirectory(rootPath)) {
    roots.push({
      path: rootPath,
      name: rootPath,
      hasChildren: directoryHasChildren(rootPath)
    });
  }
  if (process.platform === "darwin") {
    const volumesPath = "/Volumes";
    if (isReadableDirectory(volumesPath)) {
      roots.push({
        path: volumesPath,
        name: volumesPath,
        hasChildren: directoryHasChildren(volumesPath)
      });
    }
  }
  return roots;
};
const listDirectoryEntries = (dirPath) => {
  if (!dirPath) {
    return listRootDirectories();
  }
  const normalizedPath = path.resolve(dirPath);
  if (!isReadableDirectory(normalizedPath)) {
    return [];
  }
  return safeReadDir(normalizedPath).filter((entry) => entry.isDirectory()).map((entry) => {
    const entryPath = path.join(normalizedPath, entry.name);
    return {
      path: entryPath,
      name: entry.name,
      hasChildren: directoryHasChildren(entryPath)
    };
  }).sort((a, b) => a.name.localeCompare(b.name, void 0, { sensitivity: "base" }));
};
const countFilesRecursive = (dirPath, extensions) => {
  const dirents = safeReadDir(dirPath);
  return dirents.reduce((acc, entry) => {
    const entryPath = path.join(dirPath, entry.name);
    if (entry.isDirectory()) {
      return acc + countFilesRecursive(entryPath, extensions);
    }
    if (entry.isFile() && extensions.some((ext) => entry.name.toLowerCase().endsWith(ext))) {
      return acc + 1;
    }
    return acc;
  }, 0);
};
const findAbletonSet = (projectPath) => {
  const abletonPath = path.join(projectPath, "ableton");
  const entries = safeReadDir(abletonPath);
  for (const entry of entries) {
    const entryPath = path.join(abletonPath, entry.name);
    if (entry.isDirectory()) {
      const innerEntries = safeReadDir(entryPath);
      for (const nestedEntry of innerEntries) {
        if (nestedEntry.isFile() && nestedEntry.name.toLowerCase().endsWith(".als")) {
          return path.join(entryPath, nestedEntry.name);
        }
      }
    } else if (entry.isFile() && entry.name.toLowerCase().endsWith(".als")) {
      return entryPath;
    }
  }
  return null;
};
const readProjectStats = (projectPath) => ({
  abletonFile: findAbletonSet(projectPath),
  videoClips: countFilesRecursive(path.join(projectPath, "footage", "videos"), VIDEO_EXTENSIONS),
  audioClips: countFilesRecursive(path.join(projectPath, "footage", "music"), AUDIO_EXTENSIONS),
  imageFiles: countFilesRecursive(path.join(projectPath, "footage", "images"), IMAGE_EXTENSIONS)
});
const describeProject = (projectPath) => {
  const stats = readProjectStats(projectPath);
  const { activeProjectPath } = getSettings();
  const missing = CORE_PROJECT_DIRS.filter((dirName) => !existsSync(path.join(projectPath, dirName)));
  let status = "ready";
  if (missing.length) {
    status = "incomplete";
  } else if (!stats.abletonFile) {
    status = "needsAbleton";
  } else if (stats.videoClips === 0) {
    status = "needsFootage";
  }
  let createdAt;
  let updatedAt;
  try {
    const meta = statSync(projectPath);
    createdAt = meta.birthtimeMs;
    updatedAt = meta.mtimeMs;
  } catch {
  }
  const isActive = !!activeProjectPath && path.resolve(activeProjectPath) === path.resolve(projectPath);
  return {
    name: path.basename(projectPath),
    path: projectPath,
    status,
    missing,
    stats,
    createdAt,
    updatedAt,
    isActive
  };
};
const ensureProjectsRoot = () => {
  const settings = getSettings();
  if (!settings.mainFolder) {
    throw new Error("Set a main folder before managing projects.");
  }
  return settings.mainFolder;
};
const listProjects = () => {
  const projectsRoot = getSettings().mainFolder;
  if (!projectsRoot || !existsSync(projectsRoot)) {
    return [];
  }
  return safeReadDir(projectsRoot).filter((entry) => entry.isDirectory()).map((entry) => describeProject(path.join(projectsRoot, entry.name))).sort((a, b) => (b.updatedAt ?? 0) - (a.updatedAt ?? 0));
};
const ensureProjectStructure = (projectRoot, projectName) => {
  const abletonFolderName = `${projectName} ableton Project`;
  const directories = [
    "",
    "ableton",
    path.join("ableton", abletonFolderName),
    path.join("ableton", abletonFolderName, "Ableton Project Info"),
    path.join("ableton", abletonFolderName, "Samples"),
    path.join("ableton", abletonFolderName, "Samples", "Recorded"),
    "footage",
    path.join("footage", "images"),
    path.join("footage", "music"),
    path.join("footage", "videos"),
    path.join("footage", "videos", "lumix"),
    path.join("footage", "videos", "phone_marco"),
    path.join("footage", "videos", "phone_vincent"),
    "generated"
  ];
  directories.forEach((relativeDir) => {
    const target = path.join(projectRoot, relativeDir);
    ensureDirectory(target);
  });
  const recordingsFile = path.join(projectRoot, "footage", "recordings.json");
  if (!existsSync(recordingsFile)) {
    writeFileSync(recordingsFile, "[]", "utf-8");
  }
  const abletonSet = path.join(projectRoot, "ableton", abletonFolderName, `${projectName} ableton.als`);
  if (!existsSync(abletonSet)) {
    writeFileSync(abletonSet, "", "utf-8");
  }
};
const createProject = (rawName) => {
  if (typeof rawName !== "string") {
    throw new Error("Project name must be a string.");
  }
  const projectName = sanitizeProjectName(rawName);
  if (!projectName) {
    throw new Error("Please enter a project name.");
  }
  const projectsRoot = ensureProjectsRoot();
  ensureDirectory(projectsRoot);
  const projectRoot = path.join(projectsRoot, projectName);
  if (existsSync(projectRoot)) {
    throw new Error(`A project named "${projectName}" already exists.`);
  }
  ensureProjectStructure(projectRoot, projectName);
  return describeProject(projectRoot);
};
const setActiveProject = (projectPath) => {
  if (!projectPath) {
    const updated2 = updateSettings({ activeProjectPath: null });
    broadcastSettings();
    return updated2;
  }
  const resolved = path.resolve(projectPath);
  if (!existsSync(resolved)) {
    throw new Error(`Project folder "${projectPath}" does not exist.`);
  }
  const { mainFolder } = getSettings();
  if (!mainFolder) {
    throw new Error("Set the main Ableton folder before choosing an active project.");
  }
  const normalizedMain = path.resolve(mainFolder);
  if (!resolved.startsWith(normalizedMain)) {
    throw new Error("Active project must live inside the main Ableton folder.");
  }
  const updated = updateSettings({ activeProjectPath: resolved });
  broadcastSettings();
  return updated;
};
const promptForMainFolder = async (parent) => {
  const result = await dialog.showOpenDialog(parent ?? void 0, {
    title: "Choose your Ableton main folder",
    message: "Pick the folder that should be used as the main Ableton directory.",
    buttonLabel: "Use Folder",
    properties: ["openDirectory", "createDirectory"]
  });
  if (result.canceled || result.filePaths.length === 0) {
    return void 0;
  }
  return result.filePaths[0];
};
const ensureMainFolder = async (window) => {
  let settings = getSettings();
  while (!settings.mainFolder) {
    const folder = await promptForMainFolder(window);
    if (!folder) {
      const { response } = await dialog.showMessageBox(window, {
        type: "warning",
        title: "Main folder required",
        message: "Ableton Video Sync needs a main folder to continue.",
        detail: "Choose a folder to keep using the app or quit if you want to exit.",
        buttons: ["Choose Folder", "Quit App"],
        defaultId: 0,
        cancelId: 1,
        noLink: true
      });
      if (response === 1) {
        app.quit();
        return;
      }
      continue;
    }
    settings = updateSettings({ mainFolder: folder });
    broadcastSettings();
  }
};
ipcMain.handle("settings:get", () => getSettings());
ipcMain.handle("settings:choose-main-folder", async (event) => {
  const requestingWindow = BrowserWindow.fromWebContents(event.sender);
  const folder = await promptForMainFolder(requestingWindow);
  if (!folder) {
    return getSettings();
  }
  const updated = updateSettings({ mainFolder: folder });
  broadcastSettings();
  return updated;
});
ipcMain.handle("projects:list", () => {
  try {
    return listProjects();
  } catch (error) {
    console.error("[projects] Failed to list projects", error);
    throw error;
  }
});
ipcMain.handle("projects:create", (_event, projectName) => {
  try {
    const created = createProject(projectName);
    return created;
  } catch (error) {
    console.error("[projects] Failed to create project", error);
    throw error;
  }
});
ipcMain.handle("projects:set-active", (_event, projectPath) => {
  try {
    return setActiveProject(projectPath);
  } catch (error) {
    console.error("[projects] Failed to set active project", error);
    throw error;
  }
});
ipcMain.handle("projects:open-folder", async (_event, folderPath) => {
  if (!folderPath) {
    return { success: false, error: "Missing folder path." };
  }
  try {
    const result = await shell.openPath(folderPath);
    if (result) {
      return { success: false, error: result };
    }
    return { success: true };
  } catch (error) {
    console.error("[projects] Failed to open folder", error);
    return { success: false, error: error instanceof Error ? error.message : String(error) };
  }
});
ipcMain.handle("files:open", async (_event, filePath) => {
  if (!filePath) {
    return { success: false, error: "Missing file path." };
  }
  try {
    const result = await shell.openPath(filePath);
    if (result) {
      return { success: false, error: result };
    }
    return { success: true };
  } catch (error) {
    console.error("[files] Failed to open file", error);
    return { success: false, error: error instanceof Error ? error.message : String(error) };
  }
});
ipcMain.handle("dialog:choose-directory", async (_event, input) => {
  const result = await dialog.showOpenDialog({
    title: input?.title ?? "Select a folder",
    defaultPath: input?.defaultPath,
    properties: ["openDirectory", "createDirectory"]
  });
  if (result.canceled || result.filePaths.length === 0) {
    return { canceled: true, path: null };
  }
  return { canceled: false, path: result.filePaths[0] };
});
ipcMain.handle("filesystem:list-directories", (_event, input) => {
  const rawPath = input?.path ?? null;
  const parentPath = rawPath ? path.resolve(rawPath) : null;
  try {
    return {
      parent: parentPath,
      entries: listDirectoryEntries(parentPath)
    };
  } catch (error) {
    console.error("[filesystem] Failed to list directories", error);
    return {
      parent: parentPath,
      entries: [],
      error: error instanceof Error ? error.message : String(error)
    };
  }
});
function createWindow() {
  win = new BrowserWindow({
    icon: path.join(process.env.VITE_PUBLIC, "electron-vite.svg"),
    webPreferences: {
      preload: path.join(__dirname, "preload.mjs")
    }
  });
  win.webContents.on("did-finish-load", () => {
    win?.webContents.send("main-process-message", (/* @__PURE__ */ new Date()).toLocaleString());
    win?.webContents.send("settings:updated", getSettings());
  });
  win.webContents.once("did-finish-load", () => {
    if (!win) {
      return;
    }
    ensureMainFolder(win).catch((error) => {
      console.error("[settings] Failed to ensure main folder", error);
    });
  });
  if (VITE_DEV_SERVER_URL) {
    win.loadURL(VITE_DEV_SERVER_URL);
  } else {
    win.loadFile(path.join(RENDERER_DIST, "index.html"));
  }
}
app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
    win = null;
  }
});
app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});
app.whenReady().then(createWindow);
export {
  MAIN_DIST,
  RENDERER_DIST,
  VITE_DEV_SERVER_URL
};
