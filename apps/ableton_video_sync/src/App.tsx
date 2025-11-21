import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react'
import { AbletonConnectionPanel } from './ableton/AbletonConnectionPanel'
import { AlignFootagePanel } from './align/AlignFootagePanel'
import './App.css'
import { CueSpeakerPanel } from './ingest/CueSpeakerPanel'
import { DevicesPanel } from './ingest/DevicesPanel'
import { IngestDetail } from './ingest/IngestDetail'
import { PostprocessPanel } from './postprocess/PostprocessPanel'
import { PrimaryCuePanel } from './postprocess/PrimaryCuePanel'
import { RecordPanel } from './record/RecordPanel'
import { VideoGeneratorPanel } from './video/VideoGeneratorPanel'

type AppSettings = {
  mainFolder?: string
  activeProjectPath?: string | null
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

const DEFAULT_FOLDER_MESSAGE = 'Select the folder Ableton Video Sync should use.'
const STATUS_LABELS: Record<ProjectStatus, string> = {
  ready: 'Ready to sync',
  needsAbleton: 'Add Ableton set',
  needsFootage: 'Needs footage',
  incomplete: 'Setup required',
}

const TABS = [
  { id: 'devices', label: 'Devices' },
  { id: 'cueSpeaker', label: 'Cue speaker' },
  { id: 'projects', label: 'Projects' },
  { id: 'abletonConnection', label: 'Ableton connection' },
  { id: 'record', label: 'Record' },
  { id: 'ingest', label: 'Ingest' },
  { id: 'postprocess', label: 'Postprocess footage' },
  { id: 'align', label: 'Align footage' },
  { id: 'videoGen', label: 'Video generator' },
  { id: 'footage', label: 'Footage' },
  { id: 'renders', label: 'Renders' },
]

function App() {
  const [mainFolder, setMainFolder] = useState<string | null>(null)
  const [loadingSettings, setLoadingSettings] = useState(true)
  const [isChoosing, setIsChoosing] = useState(false)
  const [activeProjectPath, setActiveProjectPath] = useState<string | null>(null)
  const [projects, setProjects] = useState<ProjectSummary[]>([])
  const [projectsLoading, setProjectsLoading] = useState(false)
  const [projectsError, setProjectsError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<string>('projects')
  const [newProjectName, setNewProjectName] = useState('')
  const [creatingProject, setCreatingProject] = useState(false)
  const [bannerMessage, setBannerMessage] = useState<string | null>(null)

  const fetchProjects = useCallback(async () => {
    setProjectsLoading(true)
    try {
      const response: ProjectSummary[] = await window.ipcRenderer.invoke('projects:list')
      setProjects(response ?? [])
      setProjectsError(null)
    } catch (error) {
      console.error(error)
      setProjectsError(error instanceof Error ? error.message : 'Failed to load projects.')
    } finally {
      setProjectsLoading(false)
    }
  }, [])

  useEffect(() => {
    let mounted = true

    window.ipcRenderer.invoke('settings:get').then((settings: AppSettings) => {
      if (!mounted) {
        return
      }

      setMainFolder(settings?.mainFolder ?? null)
      setActiveProjectPath(settings?.activeProjectPath ?? null)
      setLoadingSettings(false)
      fetchProjects()
    })

    const handleSettingsUpdated = (_event: unknown, settings: AppSettings) => {
      setMainFolder(settings?.mainFolder ?? null)
      setActiveProjectPath(settings?.activeProjectPath ?? null)
      setLoadingSettings(false)
      fetchProjects()
    }

    window.ipcRenderer.on('settings:updated', handleSettingsUpdated)

    return () => {
      mounted = false
      window.ipcRenderer.off('settings:updated', handleSettingsUpdated)
    }
  }, [fetchProjects])

  const chooseMainFolder = async () => {
    setIsChoosing(true)
    try {
      const settings: AppSettings = await window.ipcRenderer.invoke('settings:choose-main-folder')
      setMainFolder(settings?.mainFolder ?? null)
      setActiveProjectPath(settings?.activeProjectPath ?? null)
    } finally {
      setIsChoosing(false)
      setLoadingSettings(false)
      fetchProjects()
    }
  }

  const handleSetActiveProject = async (projectPath: string) => {
    try {
      await window.ipcRenderer.invoke('projects:set-active', projectPath)
      setBannerMessage(`Active project set to ${projectPath}`)
      setActiveProjectPath(projectPath)
      fetchProjects()
    } catch (error) {
      console.error(error)
      setBannerMessage(error instanceof Error ? error.message : 'Failed to set active project.')
    }
  }

  const activeProject = useMemo(
    () => projects.find((p) => p.path === activeProjectPath) ?? null,
    [projects, activeProjectPath],
  )


  const handleCreateProject = async (event: FormEvent) => {
    event.preventDefault()
    setBannerMessage(null)

    if (!newProjectName.trim()) {
      setBannerMessage('Give your project a name first.')
      return
    }

    if (!mainFolder) {
      setBannerMessage('Set a main folder before creating projects.')
      return
    }

    setCreatingProject(true)

    try {
      await window.ipcRenderer.invoke('projects:create', newProjectName.trim())
      setNewProjectName('')
      setBannerMessage('Project created successfully.')
      fetchProjects()
    } catch (error) {
      console.error(error)
      setBannerMessage(error instanceof Error ? error.message : 'Failed to create project.')
    } finally {
      setCreatingProject(false)
    }
  }

  const openProjectFolder = async (folderPath: string) => {
    if (!folderPath) {
      return
    }

    const result = await window.ipcRenderer.invoke('projects:open-folder', folderPath)

    if (result?.error) {
      setBannerMessage(result.error)
    }
  }

  const folderText = useMemo(() => {
    if (loadingSettings) {
      return 'Checking settings...'
    }

    return mainFolder ?? DEFAULT_FOLDER_MESSAGE
  }, [loadingSettings, mainFolder])

  const projectsEmptyState =
    !projectsLoading && projects.length === 0 ? (
      <p className="empty-state">
        {mainFolder
          ? 'No projects yet. Create one to start syncing Ableton and footage.'
          : 'Pick a workspace folder to start managing projects.'}
      </p>
    ) : null

  return (
    <div className="app-shell">
      <header className="top-bar">
        <div className="top-bar__details">
          <div className="top-bar__title-row">
            <p className="product-name">Ableton Video Sync</p>

            {activeProject ? (
              <div className="active-project">
                <span className="active-project__separator">·</span>
                <span className="active-project__name">{activeProject.name}</span>
                <span className="active-project__path">{activeProject.path}</span>
              </div>
            ) : (
              <span className="active-project__none">No active project</span>
            )}
          </div>

          <p className="folder-status" title={mainFolder ?? undefined}>
            {folderText}
          </p>
        </div>

        <button
          className="settings-button"
          type="button"
          onClick={chooseMainFolder}
          disabled={isChoosing}
          aria-label="Open folder settings"
        >
          <svg
            className="settings-icon"
            viewBox="0 0 24 24"
            aria-hidden="true"
            focusable="false"
          >
            <path
              fill="currentColor"
              d="M11.983 1.079a.67.67 0 0 1 .632.445l.863 2.49c.266.014.52.05.769.104l2.423-1.19a.676.676 0 0 1 .83.223l1.447 2.102a.69.69 0 0 1-.09.894l-1.948 1.597c.085.243.152.495.2.756l2.365.973c.27.11.44.374.44.666v2.567a.69.69 0 0 1-.44.666l-2.365.973a6.566 6.566 0 0 1-.2.756l1.948 1.597a.69.69 0 0 1 .09.894l-1.447 2.102a.676.676 0 0 1-.83.223l-2.423-1.19a6.06 6.06 0 0 1-.769.104l-.863 2.49a.662.662 0 0 1-.632.445h-1.966a.662.662 0 0 1-.632-.445l-.863-2.49a6.06 6.06 0 0 1-.769-.104l-2.423 1.19a.676.676 0 0 1-.83-.223l-1.447-2.102a.69.69 0 0 1 .09-.894l1.948-1.597a6.566 6.566 0 0 1-.2-.756l-2.365-.973a.69.69 0 0 1-.44-.666v-2.567c0-.292.17-.556.44-.666l2.365-.973a6.566 6.566 0 0 1 .2-.756L4.207 6.147a.69.69 0 0 1-.09-.894l1.447-2.102a.676.676 0 0 1 .83-.223l2.423 1.19c.248-.054.503-.09.769-.104l.863-2.49a.662.662 0 0 1 .632-.445zm.017 7.171a3.75 3.75 0 1 0 0 7.5 3.75 3.75 0 0 0 0-7.5z"
            />
          </svg>
          <span>{isChoosing ? 'Opening...' : 'Main folder'}</span>
        </button>
      </header>

      <main className="content">
        <div className="tabs">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              className={`tab-button ${activeTab === tab.id ? 'tab-button--active' : ''}`}
              onClick={() => setActiveTab(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {activeTab === 'projects' ? (
          <section className="projects-panel">
            <div className="panel-header">
              <div>
                <h2>Projects</h2>
                <p>Set up new Ableton video sync workspaces and jump back into existing ones.</p>
              </div>
              <button
                className="ghost-button"
                type="button"
                onClick={fetchProjects}
                disabled={projectsLoading}
              >
                {projectsLoading ? 'Refreshing...' : 'Refresh'}
              </button>
            </div>

            <form className="project-creator" onSubmit={handleCreateProject}>
              <div className="project-creator__copy">
                <p>New project</p>
                <span>Create the default Ableton, footage, and generated folders in one click.</span>
              </div>
              <div className="project-creator__fields">
                <input
                  type="text"
                  placeholder="Wish You Were Here"
                  value={newProjectName}
                  onChange={(event) => setNewProjectName(event.target.value)}
                  disabled={!mainFolder || creatingProject}
                />
                <button
                  type="submit"
                  className="primary-button"
                  disabled={!mainFolder || creatingProject || !newProjectName.trim()}
                >
                  {creatingProject ? 'Creating...' : 'Create project'}
                </button>
              </div>
            </form>

            {bannerMessage && <p className="inline-message">{bannerMessage}</p>}
            {projectsError && <p className="inline-message inline-message--error">{projectsError}</p>}

            <div className="projects-table__wrapper">
              <table className="projects-table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Active</th>
                    <th>Status</th>
                    <th>Details</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {projects.map((project) => (
                    <tr key={project.path}>
                      <td>{project.name}</td>
                      <td>
                        {project.isActive ? (
                          <span className="status-badge status-badge--ready">Active</span>
                        ) : (
                          <button
                            type="button"
                            className="ghost-button"
                            onClick={() => handleSetActiveProject(project.path)}
                            disabled={!mainFolder}
                          >
                            Use project
                          </button>
                        )}
                      </td>
                      <td>
                        <span className={`status-badge status-badge--${project.status}`}>
                          {STATUS_LABELS[project.status]}
                        </span>
                        {project.missing && project.missing.length > 0 && (
                          <small className="status-note">
                            Missing: {project.missing.join(', ')}
                          </small>
                        )}
                      </td>
                      <td>
                        <dl className="project-stats">
                          <div>
                            <dt>Ableton set</dt>
                            <dd>{project.stats?.abletonFile ? 'Linked' : 'Not found'}</dd>
                          </div>
                          <div>
                            <dt>Videos</dt>
                            <dd>{project.stats?.videoClips ?? 0}</dd>
                          </div>
                          <div>
                            <dt>Audio</dt>
                            <dd>{project.stats?.audioClips ?? 0}</dd>
                          </div>
                          <div>
                            <dt>Images</dt>
                            <dd>{project.stats?.imageFiles ?? 0}</dd>
                          </div>
                        </dl>
                      </td>
                      <td>
                        <button
                          type="button"
                          className="ghost-button"
                          onClick={() => openProjectFolder(project.path)}
                        >
                          Open folder
                        </button>
                      </td>
                    </tr>
                  ))}
                  {projectsLoading && (
                    <tr>
                      <td colSpan={4}>
                        <p className="empty-state">Loading projects...</p>
                      </td>
                    </tr>
                  )}
                  {projectsEmptyState && (
                    <tr>
                      <td colSpan={4}>{projectsEmptyState}</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>
        ) : activeTab === 'ingest' ? (
          <IngestDetail
            activeProjectPath={activeProjectPath}
            mainFolder={mainFolder}
            refreshProjects={fetchProjects}
            onNavigateToDevices={() => setActiveTab('devices')}
          />
        ) : activeTab === 'cueSpeaker' ? (
          <CueSpeakerPanel />
        ) : activeTab === 'abletonConnection' ? (
          <AbletonConnectionPanel activeProjectPath={activeProjectPath} />
        ) : activeTab === 'record' ? (
          <RecordPanel activeProjectPath={activeProjectPath} />
        ) : activeTab === 'postprocess' ? (
          <PostprocessPanel activeProjectPath={activeProjectPath} />
        ) : activeTab === 'primaryCues' ? (
          <PrimaryCuePanel activeProjectPath={activeProjectPath} />
        ) : activeTab === 'align' ? (
          <AlignFootagePanel activeProjectPath={activeProjectPath} />
        ) : activeTab === 'videoGen' ? (
          <VideoGeneratorPanel activeProjectPath={activeProjectPath} />
        ) : activeTab === 'devices' ? (
          <DevicesPanel
            mainFolder={mainFolder}
            activeProjectPath={activeProjectPath}
          />
        ) : (
          <section className="placeholder-panel">
            <h2>{TABS.find((tab) => tab.id === activeTab)?.label}</h2>
            <p>We&apos;re still building this area. Stay tuned!</p>
          </section>
        )}
      </main>
    </div>
  )
}

export default App
