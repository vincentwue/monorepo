import { app, BrowserWindow, dialog, ipcMain, shell } from 'electron'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import { existsSync, mkdirSync, readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

// The built directory structure
//
// ├─┬─┬ dist
// │ │ └── index.html
// │ │
// │ ├─┬ dist-electron
// │ │ ├── main.js
// │ │ └── preload.mjs
// │
process.env.APP_ROOT = path.join(__dirname, '..')

// 🚧 Use ['ENV_NAME'] avoid vite:define plugin - Vite@2.x
export const VITE_DEV_SERVER_URL = process.env['VITE_DEV_SERVER_URL']
export const MAIN_DIST = path.join(process.env.APP_ROOT, 'dist-electron')
export const RENDERER_DIST = path.join(process.env.APP_ROOT, 'dist')

process.env.VITE_PUBLIC = VITE_DEV_SERVER_URL ? path.join(process.env.APP_ROOT, 'public') : RENDERER_DIST

let win: BrowserWindow | null

type AppSettings = {
  mainFolder?: string
  activeProjectPath?: string | null
}

const SETTINGS_FILE_NAME = 'settings.json'
let cachedSettings: AppSettings | null = null

const resolveSettingsRoot = () => {
  if (app.isPackaged) {
    return path.dirname(app.getPath('exe'))
  }

  return process.env.APP_ROOT ?? app.getAppPath()
}

const getSettingsPath = () => path.join(resolveSettingsRoot(), SETTINGS_FILE_NAME)

const loadSettingsFromDisk = (): AppSettings => {
  const settingsPath = getSettingsPath()

  try {
    if (!existsSync(settingsPath)) {
      return {}
    }

    const raw = readFileSync(settingsPath, 'utf-8')
    return raw ? JSON.parse(raw) : {}
  } catch (error) {
    console.error('[settings] Failed to read settings file', error)
    return {}
  }
}

const getSettings = (): AppSettings => {
  if (!cachedSettings) {
    cachedSettings = loadSettingsFromDisk()
  }

  return cachedSettings
}

const persistSettings = (next: AppSettings) => {
  const settingsPath = getSettingsPath()
  cachedSettings = next

  try {
    mkdirSync(path.dirname(settingsPath), { recursive: true })
    writeFileSync(settingsPath, JSON.stringify(next, null, 2), 'utf-8')
  } catch (error) {
    console.error('[settings] Failed to save settings file', error)
  }

  return cachedSettings
}

const updateSettings = (partial: Partial<AppSettings>) => {
  const nextSettings: AppSettings = {
    ...getSettings(),
    ...partial,
  }

  if (nextSettings.activeProjectPath && !existsSync(nextSettings.activeProjectPath)) {
    nextSettings.activeProjectPath = null
  }

  return persistSettings(nextSettings)
}

const broadcastSettings = () => {
  const current = getSettings()
  BrowserWindow.getAllWindows().forEach((window) => {
    window.webContents.send('settings:updated', current)
  })
  return current
}

type ProjectStatus = 'ready' | 'needsAbleton' | 'needsFootage' | 'incomplete'

type ProjectStats = {
  abletonFile: string | null
  videoClips: number
  audioClips: number
  imageFiles: number
}

type ProjectSummary = {
  name: string
  path: string
  status: ProjectStatus
  missing?: string[]
  stats: ProjectStats
  createdAt?: number
  updatedAt?: number
  isActive?: boolean
}

type DirectoryEntry = {
  path: string
  name: string
  hasChildren: boolean
}

const CORE_PROJECT_DIRS = ['ableton', 'footage', 'generated']
const VIDEO_EXTENSIONS = ['.mp4', '.mov', '.mxf']
const AUDIO_EXTENSIONS = ['.wav', '.mp3', '.aiff', '.flac']
const IMAGE_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.bmp']

const sanitizeProjectName = (name: string) =>
  name
    .replace(/[<>:"/\\|?*]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()

const ensureDirectory = (dirPath: string) => {
  if (!existsSync(dirPath)) {
    mkdirSync(dirPath, { recursive: true })
  }
}

const safeReadDir = (dirPath: string) => {
  try {
    return readdirSync(dirPath, { withFileTypes: true })
  } catch {
    return []
  }
}

const isReadableDirectory = (dirPath: string) => {
  try {
    return statSync(dirPath).isDirectory()
  } catch {
    return false
  }
}

const directoryHasChildren = (dirPath: string) =>
  safeReadDir(dirPath).some((entry) => entry.isDirectory())

const listRootDirectories = (): DirectoryEntry[] => {
  if (process.platform === 'win32') {
    const drives: DirectoryEntry[] = []

    for (let charCode = 65; charCode <= 90; charCode += 1) {
      const letter = String.fromCharCode(charCode)
      const drivePath = `${letter}:\\`

      if (!isReadableDirectory(drivePath)) {
        continue
      }

      drives.push({
        path: drivePath,
        name: `${letter}:\\`,
        hasChildren: directoryHasChildren(drivePath),
      })
    }

    return drives
  }

  const rootPath = path.parse(process.cwd()).root || '/'
  const roots: DirectoryEntry[] = []

  if (isReadableDirectory(rootPath)) {
    roots.push({
      path: rootPath,
      name: rootPath,
      hasChildren: directoryHasChildren(rootPath),
    })
  }

  if (process.platform === 'darwin') {
    const volumesPath = '/Volumes'
    if (isReadableDirectory(volumesPath)) {
      roots.push({
        path: volumesPath,
        name: volumesPath,
        hasChildren: directoryHasChildren(volumesPath),
      })
    }
  }

  return roots
}

const listDirectoryEntries = (dirPath?: string | null): DirectoryEntry[] => {
  if (!dirPath) {
    return listRootDirectories()
  }

  const normalizedPath = path.resolve(dirPath)

  if (!isReadableDirectory(normalizedPath)) {
    return []
  }

  return safeReadDir(normalizedPath)
    .filter((entry) => entry.isDirectory())
    .map((entry) => {
      const entryPath = path.join(normalizedPath, entry.name)
      return {
        path: entryPath,
        name: entry.name,
        hasChildren: directoryHasChildren(entryPath),
      }
    })
    .sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: 'base' }))
}

const countFilesRecursive = (dirPath: string, extensions: string[]) => {
  const dirents = safeReadDir(dirPath)

  return dirents.reduce((acc, entry) => {
    const entryPath = path.join(dirPath, entry.name)

    if (entry.isDirectory()) {
      return acc + countFilesRecursive(entryPath, extensions)
    }

    if (entry.isFile() && extensions.some((ext) => entry.name.toLowerCase().endsWith(ext))) {
      return acc + 1
    }

    return acc
  }, 0)
}

const findAbletonSet = (projectPath: string) => {
  const abletonPath = path.join(projectPath, 'ableton')
  const entries = safeReadDir(abletonPath)

  for (const entry of entries) {
    const entryPath = path.join(abletonPath, entry.name)

    if (entry.isDirectory()) {
      const innerEntries = safeReadDir(entryPath)

      for (const nestedEntry of innerEntries) {
        if (nestedEntry.isFile() && nestedEntry.name.toLowerCase().endsWith('.als')) {
          return path.join(entryPath, nestedEntry.name)
        }
      }
    } else if (entry.isFile() && entry.name.toLowerCase().endsWith('.als')) {
      return entryPath
    }
  }

  return null
}

const readProjectStats = (projectPath: string): ProjectStats => ({
  abletonFile: findAbletonSet(projectPath),
  videoClips: countFilesRecursive(path.join(projectPath, 'footage', 'videos'), VIDEO_EXTENSIONS),
  audioClips: countFilesRecursive(path.join(projectPath, 'footage', 'music'), AUDIO_EXTENSIONS),
  imageFiles: countFilesRecursive(path.join(projectPath, 'footage', 'images'), IMAGE_EXTENSIONS),
})

const describeProject = (projectPath: string): ProjectSummary => {
  const stats = readProjectStats(projectPath)
  const { activeProjectPath } = getSettings()
  const missing = CORE_PROJECT_DIRS.filter((dirName) => !existsSync(path.join(projectPath, dirName)))
  let status: ProjectStatus = 'ready'

  if (missing.length) {
    status = 'incomplete'
  } else if (!stats.abletonFile) {
    status = 'needsAbleton'
  } else if (stats.videoClips === 0) {
    status = 'needsFootage'
  }

  let createdAt: number | undefined
  let updatedAt: number | undefined

  try {
    const meta = statSync(projectPath)
    createdAt = meta.birthtimeMs
    updatedAt = meta.mtimeMs
  } catch {
    // ignore stat errors
  }

  const isActive =
    !!activeProjectPath && path.resolve(activeProjectPath) === path.resolve(projectPath)

  return {
    name: path.basename(projectPath),
    path: projectPath,
    status,
    missing,
    stats,
    createdAt,
    updatedAt,
    isActive,
  }
}

const ensureProjectsRoot = () => {
  const settings = getSettings()

  if (!settings.mainFolder) {
    throw new Error('Set a main folder before managing projects.')
  }

  return settings.mainFolder
}

const listProjects = (): ProjectSummary[] => {
  const projectsRoot = getSettings().mainFolder

  if (!projectsRoot || !existsSync(projectsRoot)) {
    return []
  }

  return safeReadDir(projectsRoot)
    .filter((entry) => entry.isDirectory())
    .map((entry) => describeProject(path.join(projectsRoot, entry.name)))
    .sort((a, b) => (b.updatedAt ?? 0) - (a.updatedAt ?? 0))
}

const ensureProjectStructure = (projectRoot: string, projectName: string) => {
  const abletonFolderName = `${projectName} ableton Project`
  const directories = [
    '',
    'ableton',
    path.join('ableton', abletonFolderName),
    path.join('ableton', abletonFolderName, 'Ableton Project Info'),
    path.join('ableton', abletonFolderName, 'Samples'),
    path.join('ableton', abletonFolderName, 'Samples', 'Recorded'),
    'footage',
    path.join('footage', 'images'),
    path.join('footage', 'music'),
    path.join('footage', 'videos'),
    path.join('footage', 'videos', 'lumix'),
    path.join('footage', 'videos', 'phone_marco'),
    path.join('footage', 'videos', 'phone_vincent'),
    'generated',
  ]

  directories.forEach((relativeDir) => {
    const target = path.join(projectRoot, relativeDir)
    ensureDirectory(target)
  })

  const recordingsFile = path.join(projectRoot, 'footage', 'recordings.json')
  if (!existsSync(recordingsFile)) {
    writeFileSync(recordingsFile, '[]', 'utf-8')
  }

  const abletonSet = path.join(projectRoot, 'ableton', abletonFolderName, `${projectName} ableton.als`)
  if (!existsSync(abletonSet)) {
    writeFileSync(abletonSet, '', 'utf-8')
  }
}

const createProject = (rawName: unknown) => {
  if (typeof rawName !== 'string') {
    throw new Error('Project name must be a string.')
  }

  const projectName = sanitizeProjectName(rawName)

  if (!projectName) {
    throw new Error('Please enter a project name.')
  }

  const projectsRoot = ensureProjectsRoot()
  ensureDirectory(projectsRoot)

  const projectRoot = path.join(projectsRoot, projectName)

  if (existsSync(projectRoot)) {
    throw new Error(`A project named "${projectName}" already exists.`)
  }

  ensureProjectStructure(projectRoot, projectName)
  return describeProject(projectRoot)
}

const setActiveProject = (projectPath?: string | null) => {
  if (!projectPath) {
    const updated = updateSettings({ activeProjectPath: null })
    broadcastSettings()
    return updated
  }

  const resolved = path.resolve(projectPath)

  if (!existsSync(resolved)) {
    throw new Error(`Project folder "${projectPath}" does not exist.`)
  }

  const { mainFolder } = getSettings()
  if (!mainFolder) {
    throw new Error('Set the main Ableton folder before choosing an active project.')
  }
  const normalizedMain = path.resolve(mainFolder)
  if (!resolved.startsWith(normalizedMain)) {
    throw new Error('Active project must live inside the main Ableton folder.')
  }

  const updated = updateSettings({ activeProjectPath: resolved })
  broadcastSettings()
  return updated
}

const promptForMainFolder = async (parent?: BrowserWindow | null) => {
  const result = await dialog.showOpenDialog(parent ?? undefined, {
    title: 'Choose your Ableton main folder',
    message: 'Pick the folder that should be used as the main Ableton directory.',
    buttonLabel: 'Use Folder',
    properties: ['openDirectory', 'createDirectory'],
  })

  if (result.canceled || result.filePaths.length === 0) {
    return undefined
  }

  return result.filePaths[0]
}

const ensureMainFolder = async (window: BrowserWindow) => {
  let settings = getSettings()

  while (!settings.mainFolder) {
    const folder = await promptForMainFolder(window)

    if (!folder) {
      const { response } = await dialog.showMessageBox(window, {
        type: 'warning',
        title: 'Main folder required',
        message: 'Ableton Video Sync needs a main folder to continue.',
        detail: 'Choose a folder to keep using the app or quit if you want to exit.',
        buttons: ['Choose Folder', 'Quit App'],
        defaultId: 0,
        cancelId: 1,
        noLink: true,
      })

      if (response === 1) {
        app.quit()
        return
      }

      continue
    }

    settings = updateSettings({ mainFolder: folder })
    broadcastSettings()
  }
}

ipcMain.handle('settings:get', () => getSettings())

ipcMain.handle('settings:choose-main-folder', async (event) => {
  const requestingWindow = BrowserWindow.fromWebContents(event.sender)
  const folder = await promptForMainFolder(requestingWindow)

  if (!folder) {
    return getSettings()
  }

  const updated = updateSettings({ mainFolder: folder })
  broadcastSettings()
  return updated
})

ipcMain.handle('projects:list', () => {
  try {
    return listProjects()
  } catch (error) {
    console.error('[projects] Failed to list projects', error)
    throw error
  }
})

ipcMain.handle('projects:create', (_event, projectName: unknown) => {
  try {
    const created = createProject(projectName)
    return created
  } catch (error) {
    console.error('[projects] Failed to create project', error)
    throw error
  }
})

ipcMain.handle('projects:set-active', (_event, projectPath?: string | null) => {
  try {
    return setActiveProject(projectPath)
  } catch (error) {
    console.error('[projects] Failed to set active project', error)
    throw error
  }
})

ipcMain.handle('projects:open-folder', async (_event, folderPath: string) => {
  if (!folderPath) {
    return { success: false, error: 'Missing folder path.' }
  }

  try {
    const result = await shell.openPath(folderPath)

    if (result) {
      return { success: false, error: result }
    }

    return { success: true }
  } catch (error) {
    console.error('[projects] Failed to open folder', error)
    return { success: false, error: error instanceof Error ? error.message : String(error) }
  }
})

ipcMain.handle('files:open', async (_event, filePath: string) => {
  if (!filePath) {
    return { success: false, error: 'Missing file path.' }
  }
  try {
    const result = await shell.openPath(filePath)
    if (result) {
      return { success: false, error: result }
    }
    return { success: true }
  } catch (error) {
    console.error('[files] Failed to open file', error)
    return { success: false, error: error instanceof Error ? error.message : String(error) }
  }
})

ipcMain.handle('dialog:choose-directory', async (_event, input?: { title?: string; defaultPath?: string }) => {
  const result = await dialog.showOpenDialog({
    title: input?.title ?? 'Select a folder',
    defaultPath: input?.defaultPath,
    properties: ['openDirectory', 'createDirectory'],
  })

  if (result.canceled || result.filePaths.length === 0) {
    return { canceled: true, path: null }
  }

  return { canceled: false, path: result.filePaths[0] }
})

ipcMain.handle('filesystem:list-directories', (_event, input?: { path?: string | null }) => {
  const rawPath = input?.path ?? null
  const parentPath = rawPath ? path.resolve(rawPath) : null

  try {
    return {
      parent: parentPath,
      entries: listDirectoryEntries(parentPath),
    }
  } catch (error) {
    console.error('[filesystem] Failed to list directories', error)
    return {
      parent: parentPath,
      entries: [],
      error: error instanceof Error ? error.message : String(error),
    }
  }
})

function createWindow() {
  win = new BrowserWindow({
    icon: path.join(process.env.VITE_PUBLIC, 'electron-vite.svg'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.mjs'),
    },
  })

  // Test active push message to Renderer-process.
  win.webContents.on('did-finish-load', () => {
    win?.webContents.send('main-process-message', (new Date).toLocaleString())
    win?.webContents.send('settings:updated', getSettings())
  })

  win.webContents.once('did-finish-load', () => {
    if (!win) {
      return
    }

    ensureMainFolder(win).catch((error) => {
      console.error('[settings] Failed to ensure main folder', error)
    })
  })

  if (VITE_DEV_SERVER_URL) {
    win.loadURL(VITE_DEV_SERVER_URL)
  } else {
    // win.loadFile('dist/index.html')
    win.loadFile(path.join(RENDERER_DIST, 'index.html'))
  }
}

// Quit when all windows are closed, except on macOS. There, it's common
// for applications and their menu bar to stay active until the user quits
// explicitly with Cmd + Q.
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
    win = null
  }
})

app.on('activate', () => {
  // On OS X it's common to re-create a window in the app when the
  // dock icon is clicked and there are no other windows open.
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow()
  }
})

app.whenReady().then(createWindow)
