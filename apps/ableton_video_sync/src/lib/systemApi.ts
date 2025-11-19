export function openExternalPath(targetPath: string) {
  return window.ipcRenderer.invoke('projects:open-folder', targetPath)
}

export function openProjectFile(filePath: string) {
  return window.ipcRenderer.invoke('files:open', filePath)
}

export function openProjectFolder(folderPath: string) {
  return window.ipcRenderer.invoke('projects:open-folder', folderPath)
}
