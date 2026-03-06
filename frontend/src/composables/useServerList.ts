import { ref, reactive, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox, ElNotification } from 'element-plus'
import { useRouter } from 'vue-router'
import { io } from 'socket.io-client'
import apiClient, { isRequestCanceled } from '@/api'
import { useUserStore } from '@/store/user'
import { useSettingsStore } from '@/store/settings'
import { useTasksStore } from '@/store/tasks'
import { storeToRefs } from 'pinia'

// ── Types ────────────────────────────────────────────────────────
export interface Server {
  id: number
  name: string
  status: string
  path: string
  port?: number
  last_startup?: string | null
  size_mb?: number | null
  size_calc_state?: string
  return_code?: number | null
  core_config: {
    server_type?: string
    core_version?: string
    is_fabric?: boolean
    loader_version?: string
    auto_start?: boolean
    launcher_jar?: string
    server_jar?: string
    [key: string]: unknown
  }
  loading?: boolean
  map?: { nether_json?: unknown; end_json?: unknown }
  [key: string]: unknown
}

// ── Helpers ──────────────────────────────────────────────────────
export const getStatusTagType = (row: Server) => {
  const s = row?.status
  if (s === 'running') return 'success'
  if (s === 'pending') return 'info'
  if (s === 'stopped') return 'warning'
  if (s === 'new_setup') return 'info'
  return 'danger'
}

export const getStatusTagText = (row: Server) => {
  const s = row?.status
  if (s === 'running') return '运行中'
  if (s === 'pending') return '启动中'
  if (s === 'stopped') return '未启动'
  if (s === 'new_setup') return '未配置'
  return row?.return_code != null ? `已停止 (${row.return_code})` : '已停止'
}

export const formatServerSize = (sizeMb: unknown) => {
  const n = Number(sizeMb)
  if (!Number.isFinite(n)) return ''
  let decimals = 3
  if (n >= 1 && n <= 1000) decimals = 2
  if (n > 1000) decimals = 1
  const fixed = n.toFixed(decimals)
  if (n <= 1000) return `${fixed} MB`
  const parts = fixed.split('.')
  const intPart = parts[0] || '0'
  const fracPart = parts[1]
  const withCommas = intPart.replace(/\B(?=(\d{3})+(?!\d))/g, ',')
  return fracPart != null ? `${withCommas}.${fracPart} MB` : `${withCommas} MB`
}

export const formatRelativeTime = (dateStr: string | null | undefined) => {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMinutes = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)
  if (diffMinutes < 1) return '刚刚'
  if (diffMinutes < 60) return `${diffMinutes}分钟前`
  if (diffHours < 24) return `${diffHours}小时前`
  if (diffDays < 7) return `${diffDays}天前`
  const thisYear = now.getFullYear()
  const dateYear = date.getFullYear()
  const month = date.getMonth() + 1
  const day = date.getDate()
  if (dateYear === thisYear) return `${month}月${day}日`
  return `${dateYear}年${month}月${day}日`
}

export const sortByLastStartup = (a: Server, b: Server) => {
  const timeA = a.last_startup ? new Date(a.last_startup).getTime() : 0
  const timeB = b.last_startup ? new Date(b.last_startup).getTime() : 0
  return timeA - timeB
}

// ── Composable ───────────────────────────────────────────────────
export function useServerList() {
  const router = useRouter()
  const userStore = useUserStore()
  const user = userStore.user
  const { activeGroupIds, activeGroupId, isPlatformAdmin } = storeToRefs(userStore)
  const { hasRole } = userStore
  const settings = useSettingsStore().settings
  const { fetchTasks } = useTasksStore()

  // ── View mode (persisted) ──────────────────────────────────────
  const viewMode = ref<'card' | 'table'>(
    (localStorage.getItem('serverListViewMode') as 'card' | 'table') || 'card',
  )
  watch(viewMode, (v) => localStorage.setItem('serverListViewMode', v))

  // ── Search / filter ───────────────────────────────────────────
  const searchQuery = ref('')
  const statusFilter = ref('')

  // ── Core server list state ────────────────────────────────────
  const serverList = ref<Server[]>([])
  const loading = ref(true)
  const loaded = ref(false)
  const selectedServers = ref<Server[]>([])
  const isBatchProcessing = ref(false)
  const autoStartSaving = reactive<Record<number, boolean>>({})

  // Table ref
  const tableRef = ref<InstanceType<any> | null>(null)

  // ── Computed filtered list ────────────────────────────────────
  const filteredServerList = computed(() => {
    let list = serverList.value
    if (searchQuery.value.trim()) {
      const q = searchQuery.value.trim().toLowerCase()
      list = list.filter(
        (s) =>
          s.name.toLowerCase().includes(q) ||
          String(s.port || '').includes(q) ||
          (s.core_config?.core_version || '').toLowerCase().includes(q),
      )
    }
    if (statusFilter.value) {
      list = list.filter((s) => s.status === statusFilter.value)
    }
    return list
  })

  // ── Pagination ────────────────────────────────────────────────
  const currentPage = ref(1)
  const pageSize = ref(12)

  const sortedFilteredList = computed(() =>
    [...filteredServerList.value].sort((a, b) => {
      const timeA = a.last_startup ? new Date(a.last_startup).getTime() : 0
      const timeB = b.last_startup ? new Date(b.last_startup).getTime() : 0
      return timeB - timeA
    }),
  )

  const pagedServerList = computed(() => {
    const start = (currentPage.value - 1) * pageSize.value
    return sortedFilteredList.value.slice(start, start + pageSize.value)
  })

  watch([searchQuery, statusFilter, viewMode], () => { currentPage.value = 1 })

  // ── Server link groups (for create/import/copy dialogs) ───────
  const serverLinkGroups = ref<{ id: number; name: string }[]>([])
  const serverLinkGroupsLoading = ref(false)
  const selectableGroups = computed(() => {
    if (isPlatformAdmin.value) return serverLinkGroups.value
    const adminGroupIds = new Set(
      (user as any).group_permissions
        .filter((p: any) => p.role === 'ADMIN')
        .map((p: any) => p.group_id),
    )
    return serverLinkGroups.value.filter((g) => adminGroupIds.has(g.id))
  })

  // ── Dialog visibility ─────────────────────────────────────────
  const createDialogVisible = ref(false)
  const importDialogVisible = ref(false)
  const copyDialogVisible = ref(false)
  const commandDialogVisible = ref(false)
  const configDialogVisible = ref(false)
  const renameDialogVisible = ref(false)
  const addSubServerDialogVisible = ref(false)

  // ── Form refs ─────────────────────────────────────────────────
  const formRef = ref<InstanceType<any> | null>(null)
  const importFormRef = ref<InstanceType<any> | null>(null)
  const copyFormRef = ref<InstanceType<any> | null>(null)
  const renameFormRef = ref<InstanceType<any> | null>(null)
  const subServerSelectionTable = ref<InstanceType<any> | null>(null)
  const netherMapUploaderRef = ref<InstanceType<any> | null>(null)
  const endMapUploaderRef = ref<InstanceType<any> | null>(null)

  // ── Create/import/copy/rename form data ───────────────────────
  const newServerForm = ref({ name: '', serverLinkGroupIds: [] as number[] })
  const importServerForm = ref({ name: '', path: '', serverLinkGroupIds: [] as number[] })
  const copyServerForm = ref({ name: '', serverLinkGroupIds: [] as number[] })
  const sourceServerToCopy = ref<Server | null>(null)
  const renameForm = ref({ newName: '' })
  const renameLoading = ref(false)
  const serverToRename = ref<Server | null>(null)
  const batchCommand = ref('')

  // ── Form rules ────────────────────────────────────────────────
  const formRules = reactive({
    name: [{ required: true, message: '请输入服务器名称', trigger: 'blur' }],
    serverLinkGroupIds: [{ required: true, type: 'array', min: 1, message: '请选择至少一个服务器组', trigger: 'change' }],
  })
  const importFormRules = reactive({
    name: [{ required: true, message: '请输入服务器名称', trigger: 'blur' }],
    path: [{ required: true, message: '请输入服务器的绝对路径', trigger: 'blur' }],
    serverLinkGroupIds: [{ required: true, type: 'array', min: 1, message: '请选择至少一个服务器组', trigger: 'change' }],
  })
  const copyFormRules = reactive({
    name: [{ required: true, message: '请输入新服务器的名称', trigger: 'blur' }],
    serverLinkGroupIds: [{ required: true, type: 'array', min: 1, message: '请选择至少一个服务器组', trigger: 'change' }],
  })
  const renameFormRules = reactive({
    newName: [{ required: true, message: '请输入新的服务器名称', trigger: 'blur' }],
  })

  // ── Config dialog state ───────────────────────────────────────
  const configLoading = ref(false)
  const isSavingConfig = ref(false)
  const currentConfigServer = ref<Server | null>(null)
  const configFormData = ref<Record<string, any>>({})
  const selectedServerTypeForSetup = ref('')
  const mojangVersions = ref<any[]>([])
  const velocityVersions = ref<string[]>([])
  const fabricGameVersions = ref<string[]>([])
  const isFetchingVersions = ref(false)
  const fabricLoaderVersions = ref<string[]>([])
  const isFetchingFabricVersions = ref(false)
  const forgeGameVersions = ref<string[]>([])
  const forgeLoaderVersions = ref<string[]>([])
  const isFetchingForgeGameVersions = ref(false)
  const isFetchingForgeLoaderVersions = ref(false)
  const showSnapshots = ref(false)
  const showExperiments = ref(false)
  const isDownloading = ref(false)
  const downloadProgress = ref(0)
  const javaCmdOptions = ref<string[]>([])
  const commandEditMode = ref('start_command')
  const currentView = ref('select_type')
  const dialogState = reactive({ isNewSetup: false, coreFileExists: false, configFileExists: false })
  let pollInterval: ReturnType<typeof setInterval> | null = null

  // Map uploads
  const netherMapFileList = ref<any[]>([])
  const endMapFileList = ref<any[]>([])
  const netherMapFile = ref<File | null>(null)
  const endMapFile = ref<File | null>(null)
  const isUploadingMap = reactive({ nether: false, end: false })

  // Config editor
  const editorDialog = reactive({
    visible: false, loading: false, saving: false, title: '', content: '', language: '', fileType: '',
  })

  // Velocity sub-servers
  const velocitySubServersList = ref<{ id: string; name: string; ip: string; port: string }[]>([])
  const velocityTryOrderNames = ref<string[]>([])
  const selectedSubServersFromDialog = ref<Server[]>([])

  // ── Config computed ───────────────────────────────────────────
  const dialogTitle = computed(() => {
    if (!currentConfigServer.value) return '配置服务器'
    if (dialogState.isNewSetup) return `初始化服务器配置 - ${currentConfigServer.value.name}`
    return `配置服务器 - ${currentConfigServer.value.name}`
  })
  const isVanillaFamily = computed(() => {
    const type = configFormData.value?.core_config?.server_type
    return type === 'vanilla' || type === 'beta18'
  })
  const isForgeType = computed(() => configFormData.value?.core_config?.server_type === 'forge')
  const filteredMojangVersions = computed(() =>
    mojangVersions.value.filter((v) => {
      if (v.type === 'release') return true
      if (showSnapshots.value && v.type === 'snapshot') return true
      if (showExperiments.value && v.type === 'old_beta') return true
      return false
    }),
  )
  const availableSubServers = computed(() => {
    if (!currentConfigServer.value) return []
    return serverList.value.filter(
      (s) => s.core_config.server_type !== 'velocity' && s.id !== currentConfigServer.value!.id,
    )
  })
  const isFabricAvailable = computed(() => {
    if (configFormData.value?.core_config?.server_type !== 'vanilla') return false
    if (!configFormData.value?.core_config?.core_version || fabricGameVersions.value.length === 0) return false
    return fabricGameVersions.value.includes(configFormData.value.core_config.core_version)
  })

  // Static options
  const serverTypes = [
    { label: 'Vanilla / Fabric', value: 'vanilla' },
    { label: 'Vanilla Legacy / Beta 1.8 (旧版官方)', value: 'beta18' },
    { label: 'Velocity (新一代群组服)', value: 'velocity' },
    { label: 'Bukkit (暂不支持配置)', value: 'bukkit', disabled: true },
    { label: 'Forge', value: 'forge' },
  ]
  const gamemodeOptions = [
    { label: '生存 (Survival)', value: 'survival' },
    { label: '创造 (Creative)', value: 'creative' },
    { label: '冒险 (Adventure)', value: 'adventure' },
    { label: '观察者 (Spectator)', value: 'spectator' },
  ]
  const difficultyOptions = [
    { label: '和平 (Peaceful)', value: 'peaceful' },
    { label: '简单 (Easy)', value: 'easy' },
    { label: '普通 (Normal)', value: 'normal' },
    { label: '困难 (Hard)', value: 'hard' },
  ]

  // ── Plugin manager state ──────────────────────────────────────
  const currentServerForPlugins = ref<Server | null>(null)
  const pluginConfigDialogVisible = ref(false)
  const installedPlugins = ref<any[]>([])
  const onlinePlugins = ref<any[]>([])
  const pluginsLoading = ref(false)
  const onlinePluginsLoading = ref(false)
  const installedPluginsQuery = ref('')
  const installedPluginsFilter = ref('all')
  const onlinePluginsQuery = ref('')
  const onlinePluginsSelected = ref<any[]>([])
  const addOnlinePluginDialogVisible = ref(false)
  const addDbPluginDialogVisible = ref(false)
  const dbPlugins = ref<any[]>([])
  const dbPluginsLoading = ref(false)
  const dbPluginsQuery = ref('')
  const dbPluginsSelected = ref<any[]>([])
  const installConfirmDialogVisible = ref(false)
  const pluginsToInstall = ref<any[]>([])
  const isInstallingPlugins = ref(false)

  const onlinePluginsMap = computed(() => {
    const map = new Map<string, any>()
    onlinePlugins.value.forEach((p) => { if (p.meta?.id) map.set(p.meta.id, p) })
    return map
  })
  const filteredInstalledPlugins = computed(() =>
    installedPlugins.value.filter((p) => {
      if (installedPluginsFilter.value === 'enabled' && !p.enabled) return false
      if (installedPluginsFilter.value === 'disabled' && p.enabled) return false
      if (installedPluginsQuery.value) {
        const q = installedPluginsQuery.value.toLowerCase()
        return (p.meta?.name || '').toLowerCase().includes(q) || (p.meta?.id || '').toLowerCase().includes(q)
      }
      return true
    }),
  )
  const filteredOnlinePlugins = computed(() => {
    if (!onlinePluginsQuery.value) return onlinePlugins.value
    const q = onlinePluginsQuery.value.toLowerCase()
    return onlinePlugins.value.filter(
      (p) => (p.meta?.name || '').toLowerCase().includes(q) || (p.meta?.id || '').toLowerCase().includes(q),
    )
  })

  // ── Config watchers ───────────────────────────────────────────
  watch(isFabricAvailable, (isAvailable) => {
    if (!isAvailable && configFormData.value?.core_config?.server_type === 'vanilla' && configFormData.value?.core_config?.is_fabric) {
      configFormData.value.core_config.is_fabric = false
      if (configDialogVisible.value) ElMessage.warning('当前游戏版本不支持 Fabric，已自动禁用。')
    }
  })
  watch(() => configFormData.value?.core_config?.is_fabric, (enabled) => {
    if (!configDialogVisible.value) return
    const coreConfig = configFormData.value?.core_config
    if (!coreConfig || coreConfig.server_type !== 'vanilla') return
    if (!enabled) { fabricLoaderVersions.value = []; if (coreConfig.loader_version) coreConfig.loader_version = ''; return }
    fetchFabricLoaderVersions(coreConfig.core_version)
  })
  watch(() => configFormData.value?.core_config?.core_version, (newVersion) => {
    if (!configDialogVisible.value) return
    const coreConfig = configFormData.value?.core_config
    if (!coreConfig) return
    if (coreConfig.server_type === 'vanilla' && coreConfig.is_fabric) fetchFabricLoaderVersions(newVersion)
    if (coreConfig.server_type === 'forge') fetchForgeLoaderVersions(newVersion)
  })
  watch(() => configFormData.value?.core_config?.server_type, async (type) => {
    if (!configDialogVisible.value) return
    if (type === 'forge') {
      await fetchForgeGameVersions()
      if (configFormData.value.core_config?.is_fabric) configFormData.value.core_config.is_fabric = false
      if (configFormData.value.core_config?.core_version) await fetchForgeLoaderVersions(configFormData.value.core_config.core_version)
      else forgeLoaderVersions.value = []
    } else { forgeLoaderVersions.value = [] }
    if (type !== 'vanilla' && fabricLoaderVersions.value.length > 0) fabricLoaderVersions.value = []
  })
  watch(activeGroupIds, () => { fetchServers() }, { deep: true })

  // ── Size fetching ─────────────────────────────────────────────
  let serverSizesRequestSeq = 0
  const fetchServerSizes = async (requestId: number) => {
    try {
      const { data } = await apiClient.get('/api/servers/sizes')
      if (requestId !== serverSizesRequestSeq) return
      const sizeMap = new Map<number, unknown>((data || []).map((item: any) => [Number(item.id), item.size_mb]))
      serverList.value.forEach((s) => {
        if (sizeMap.has(Number(s.id))) { s.size_mb = sizeMap.get(Number(s.id)) as number; s.size_calc_state = 'ok' }
        else { s.size_mb = null; s.size_calc_state = 'failed' }
      })
    } catch {
      if (requestId !== serverSizesRequestSeq) return
      serverList.value.forEach((s) => { s.size_mb = null; s.size_calc_state = 'failed' })
    }
  }

  // ── Server list fetching ──────────────────────────────────────
  const fetchServers = async () => {
    loading.value = true
    try {
      const { data } = await apiClient.get('/api/servers')
      const selectedIds = new Set(selectedServers.value.map((s) => s.id))
      serverList.value = data.map((s: any) => {
        const coreConfig = s.core_config || {}
        if (coreConfig.auto_start == null) coreConfig.auto_start = false
        return { ...s, core_config: coreConfig, loading: false, size_mb: null, size_calc_state: 'pending' }
      })
      await nextTick()
      if (tableRef.value) {
        tableRef.value.clearSelection()
        serverList.value.forEach((server) => {
          if (selectedIds.has(server.id)) tableRef.value!.toggleRowSelection(server, true)
        })
      }
      const requestId = ++serverSizesRequestSeq
      fetchServerSizes(requestId)
    } finally {
      loading.value = false
      if (!loaded.value) loaded.value = true
    }
  }

  const fetchServerLinkGroups = async () => {
    serverLinkGroupsLoading.value = true
    try {
      const { data } = await apiClient.get('/api/tools/server-link/groups')
      serverLinkGroups.value = Array.isArray(data) ? data : []
    } catch { serverLinkGroups.value = [] }
    finally { serverLinkGroupsLoading.value = false }
  }

  const fetchJavaCmdOptions = async () => {
    try {
      const { data } = await apiClient.get('/api/settings/java-options')
      javaCmdOptions.value = Array.isArray(data) ? data : []
    } catch { javaCmdOptions.value = [] }
  }

  // ── JVM helpers ───────────────────────────────────────────────
  const buildStartCommandFromJvm = (cfg: any) => {
    const jvm = cfg?.jvm || {}
    const core = cfg?.core_config || {}
    const javaCmd = (jvm.java_command || settings.java_command || 'java').toString().trim() || 'java'
    const minMem = (jvm.min_memory || '1G').toString().trim() || '1G'
    const maxMem = (jvm.max_memory || '4G').toString().trim() || '4G'
    const extra = (jvm.extra_args || '').toString().trim()
    const extraTokens = extra ? extra.split(/\s+/).filter(Boolean) : []
    const jar = core.launcher_jar || core.server_jar || 'server.jar'
    return [javaCmd, `-Xms${minMem}`, `-Xmx${maxMem}`, ...extraTokens, '-jar', jar].join(' ')
  }
  const parseStartCommandToJvm = (command: string) => {
    const raw = (command || '').toString().trim()
    const tokens = raw ? raw.split(/\s+/).filter(Boolean) : []
    const javaCmd = (tokens[0] || settings.java_command || 'java').toString().trim() || 'java'
    const jarIndex = tokens.indexOf('-jar')
    const jvmPart = jarIndex >= 0 ? tokens.slice(1, jarIndex) : tokens.slice(1)
    let minMem = '1G', maxMem = '4G'
    const extraTokens: string[] = []
    for (const t of jvmPart) {
      if (typeof t !== 'string') continue
      if (t.startsWith('-Xms') && t.length > 4) { minMem = t.slice(4); continue }
      if (t.startsWith('-Xmx') && t.length > 4) { maxMem = t.slice(4); continue }
      extraTokens.push(t)
    }
    return { java_command: javaCmd, min_memory: minMem, max_memory: maxMem, extra_args: extraTokens.join(' ') }
  }

  // ── Config dialog ─────────────────────────────────────────────
  const resetDialogState = () => {
    if (pollInterval) clearInterval(pollInterval)
    pollInterval = null
    configLoading.value = false
    isSavingConfig.value = false
    isDownloading.value = false
    downloadProgress.value = 0
    commandEditMode.value = 'start_command'
    currentView.value = 'select_type'
    configFormData.value = {}
    selectedServerTypeForSetup.value = ''
    netherMapFile.value = null
    endMapFile.value = null
    netherMapFileList.value = []
    endMapFileList.value = []
    isUploadingMap.nether = false
    isUploadingMap.end = false
    velocitySubServersList.value = []
    velocityTryOrderNames.value = []
    addSubServerDialogVisible.value = false
    selectedSubServersFromDialog.value = []
    Object.assign(dialogState, { isNewSetup: false, coreFileExists: false, configFileExists: false })
  }

  const openConfigDialog = async (server: Server) => {
    resetDialogState()
    currentConfigServer.value = server
    configDialogVisible.value = true
    configLoading.value = true
    try {
      const { data } = await apiClient.get(`/api/servers/config?server_id=${server.id}`)
      configFormData.value = data.config
      if (!configFormData.value?.jvm) configFormData.value.jvm = {}
      if (!configFormData.value.jvm.java_command) configFormData.value.jvm.java_command = settings.java_command || 'java'
      if (!configFormData.value.start_command) configFormData.value.start_command = buildStartCommandFromJvm(configFormData.value)
      dialogState.isNewSetup = data.is_new_setup
      dialogState.coreFileExists = data.core_file_exists
      dialogState.configFileExists = data.config_file_exists
      const type = configFormData.value.core_config.server_type
      if (dialogState.isNewSetup) {
        currentView.value = 'select_type'
        const pickable = serverTypes.some((t) => t.value === type && !t.disabled)
        selectedServerTypeForSetup.value = pickable ? type : ''
      } else if (type === 'velocity') {
        if (!dialogState.coreFileExists) { currentView.value = 'velocity_initial_setup'; await fetchVelocityVersions() }
        else if (!dialogState.configFileExists) { currentView.value = 'needs_first_start' }
        else {
          currentView.value = 'full_config'; await fetchVelocityVersions()
          const servers = data.config.velocity_toml?.servers || {}
          const tryOrder = data.config.velocity_toml?.try || []
          velocitySubServersList.value = Object.entries(servers).map(([name, address], index) => {
            const parts = (address as string).split(':')
            return { id: `${name}-${index}`, name, ip: parts[0], port: parts[1] || '' }
          })
          velocityTryOrderNames.value = (tryOrder as string[]).filter((name) => servers[name])
          if (velocityTryOrderNames.value.length === 0 && velocitySubServersList.value.length > 0)
            velocityTryOrderNames.value.push(velocitySubServersList.value[0].name)
        }
      } else if (type === 'forge') {
        currentView.value = 'full_config'; await fetchForgeGameVersions()
        if (configFormData.value.core_config.core_version) await fetchForgeLoaderVersions(configFormData.value.core_config.core_version)
      } else if (type === 'vanilla' || type === 'beta18') {
        currentView.value = 'full_config'; await fetchFabricGameVersions(); await fetchMojangVersions()
        if (configFormData.value.core_config.is_fabric) await fetchFabricLoaderVersions(configFormData.value.core_config.core_version)
      } else { currentView.value = 'unsupported_type' }
    } catch (error: any) {
      ElMessage.error(`加载配置失败: ${error.response?.data?.detail || error.message}`)
      configDialogVisible.value = false
    } finally { configLoading.value = false }
  }

  const confirmServerType = async () => {
    configFormData.value.core_config.server_type = selectedServerTypeForSetup.value
    const type = configFormData.value.core_config.server_type
    if (type === 'vanilla' || type === 'beta18') { currentView.value = 'full_config'; await fetchMojangVersions() }
    else if (type === 'forge') { currentView.value = 'full_config'; await fetchForgeGameVersions() }
    else if (type === 'velocity') { currentView.value = 'velocity_initial_setup'; await fetchVelocityVersions() }
    else currentView.value = 'unsupported_type'
  }

  const handleSaveConfig = async () => {
    isSavingConfig.value = true
    if (!configFormData.value?.jvm) configFormData.value.jvm = {}
    if (commandEditMode.value === 'start_command') {
      const parsed = parseStartCommandToJvm(configFormData.value.start_command)
      Object.assign(configFormData.value.jvm, parsed)
      configFormData.value.start_command = (configFormData.value.start_command || '').toString().trim()
    } else {
      if (!configFormData.value.jvm.java_command) configFormData.value.jvm.java_command = settings.java_command || 'java'
      configFormData.value.start_command = buildStartCommandFromJvm(configFormData.value)
    }
    if (configFormData.value.core_config.server_type === 'velocity' && configFormData.value.velocity_toml) {
      const newServers: Record<string, string> = {}
      for (const server of velocitySubServersList.value) {
        if (server.name?.trim() && server.ip?.trim() && server.port)
          newServers[server.name.trim()] = `${server.ip.trim()}:${server.port}`
      }
      configFormData.value.velocity_toml.servers = newServers
      configFormData.value.velocity_toml.try = velocityTryOrderNames.value
    }
    const payload = { server_id: currentConfigServer.value!.id, config: { ...configFormData.value } }
    try {
      const { data } = await apiClient.post('/api/servers/config', payload)
      if (data.status === 'downloading' && data.task_id) {
        currentView.value = 'downloading'; pollDownloadStatus(data.task_id); fetchTasks().catch(() => {})
      } else {
        ElMessage.success(data.message || '配置已成功保存！')
        if (configFormData.value.core_config.server_type === 'velocity' && !dialogState.configFileExists) {
          currentView.value = 'needs_first_start'; return
        }
        configDialogVisible.value = false; await fetchServers()
      }
    } catch (error: any) {
      ElMessage.error(`保存配置失败: ${error.response?.data?.detail || error.message}`)
    } finally { if (currentView.value !== 'downloading') isSavingConfig.value = false }
  }

  const pollDownloadStatus = (taskId: string) => {
    isSavingConfig.value = false
    pollInterval = setInterval(async () => {
      try {
        const { data } = await apiClient.get(`/api/system/task-progress/${taskId}`)
        downloadProgress.value = data.progress
        if (data.status === 'SUCCESS') {
          clearInterval(pollInterval!); pollInterval = null
          dialogState.coreFileExists = true
          if (configFormData.value.core_config.server_type === 'velocity' && !dialogState.configFileExists) {
            currentView.value = 'needs_first_start'
          } else {
            ElMessage.success('核心文件安装完成'); configDialogVisible.value = false; await fetchServers()
          }
        } else if (data.status === 'FAILED') {
          clearInterval(pollInterval!); pollInterval = null
          ElMessage.error(`处理失败: ${data.error || '未知错误'}`)
          currentView.value = configFormData.value.core_config.server_type === 'velocity' ? 'velocity_initial_setup' : 'full_config'
        }
      } catch {
        clearInterval(pollInterval!); pollInterval = null
        ElMessage.error('无法获取进度，请检查后端服务。')
        currentView.value = configFormData.value.core_config.server_type === 'velocity' ? 'velocity_initial_setup' : 'full_config'
      }
    }, 500)
  }

  const startAndContinue = async () => {
    if (!currentConfigServer.value) return
    currentView.value = 'waiting_for_startup'
    try {
      await apiClient.post(`/api/servers/start-for-while?server_id=${currentConfigServer.value.id}`)
      ElMessage.info(`已发送启动命令至 "${currentConfigServer.value.name}"`)
    } catch (e: any) {
      ElMessage.error(`启动失败: ${e.response?.data?.detail || e.message}`)
      currentView.value = 'needs_first_start'; return
    }
    let attempts = 0
    pollInterval = setInterval(async () => {
      attempts++
      if (attempts > 15) {
        clearInterval(pollInterval!); pollInterval = null
        ElMessage.error('服务器启动超时，请检查控制台日志。')
        currentView.value = 'needs_first_start'; return
      }
      try {
        const { data } = await apiClient.get(`/api/servers/config?server_id=${currentConfigServer.value!.id}`)
        if (data.config_file_exists) {
          clearInterval(pollInterval!); pollInterval = null
          ElMessage.success('服务器已就绪，正在加载完整配置！')
          await openConfigDialog(currentConfigServer.value!)
        }
      } catch (error: any) { console.warn(`Polling failed (attempt ${attempts}):`, error.message) }
    }, 2000)
  }

  // ── Version fetchers ──────────────────────────────────────────
  const fetchMojangVersions = async () => {
    if (mojangVersions.value.length > 0) return
    isFetchingVersions.value = true
    try { const { data } = await apiClient.get('/api/minecraft/versions'); mojangVersions.value = data.versions }
    catch (e: any) { if (!isRequestCanceled(e)) ElMessage.error('获取 Minecraft 版本列表失败') }
    finally { isFetchingVersions.value = false }
  }
  const fetchVelocityVersions = async () => {
    if (velocityVersions.value.length > 0) return
    isFetchingVersions.value = true
    try { const { data } = await apiClient.get('/api/velocity/versions'); velocityVersions.value = data.versions }
    catch (e: any) { if (!isRequestCanceled(e)) ElMessage.error('获取 Velocity 版本列表失败') }
    finally { isFetchingVersions.value = false }
  }
  const fetchFabricGameVersions = async () => {
    if (fabricGameVersions.value.length > 0) return
    try { const { data } = await apiClient.get('/api/fabric/game-versions'); fabricGameVersions.value = data.versions }
    catch (e: any) { if (!isRequestCanceled(e)) console.error('获取 Fabric 游戏版本失败:', e) }
  }
  const fetchFabricLoaderVersions = async (mcVersion: string) => {
    if (!mcVersion) { fabricLoaderVersions.value = []; return }
    isFetchingFabricVersions.value = true
    try { const { data } = await apiClient.get(`/api/fabric/loader-versions?version_id=${mcVersion}`); fabricLoaderVersions.value = data.versions }
    catch (e: any) { if (!isRequestCanceled(e)) ElMessage.error('获取 Fabric Loader 版本列表失败'); fabricLoaderVersions.value = [] }
    finally { isFetchingFabricVersions.value = false }
  }
  const fetchForgeGameVersions = async () => {
    if (forgeGameVersions.value.length > 0) return
    isFetchingForgeGameVersions.value = true
    try { const { data } = await apiClient.get('/api/forge/game-versions'); forgeGameVersions.value = data.versions }
    catch (e: any) { if (!isRequestCanceled(e)) ElMessage.error('获取 Forge 支持的游戏版本失败') }
    finally { isFetchingForgeGameVersions.value = false }
  }
  const fetchForgeLoaderVersions = async (mcVersion: string) => {
    if (!mcVersion) {
      forgeLoaderVersions.value = []
      if (configFormData.value?.core_config?.server_type === 'forge' && configFormData.value.core_config.loader_version)
        configFormData.value.core_config.loader_version = ''
      return
    }
    isFetchingForgeLoaderVersions.value = true
    try {
      const { data } = await apiClient.get(`/api/forge/loader-versions?version_id=${mcVersion}`)
      forgeLoaderVersions.value = data.versions
      if (configFormData.value?.core_config?.server_type === 'forge' &&
        configFormData.value.core_config.loader_version &&
        !forgeLoaderVersions.value.includes(configFormData.value.core_config.loader_version))
        configFormData.value.core_config.loader_version = ''
    } catch (e: any) { if (!isRequestCanceled(e)) ElMessage.error('获取 Forge 版本列表失败'); forgeLoaderVersions.value = [] }
    finally { isFetchingForgeLoaderVersions.value = false }
  }

  // ── Velocity sub-server helpers ───────────────────────────────
  const addManualSubServer = () => velocitySubServersList.value.push({ id: `manual-${Date.now()}`, name: '', ip: '127.0.0.1', port: '' })
  const removeSubServer = (index: number) => {
    const name = velocitySubServersList.value[index].name
    velocitySubServersList.value.splice(index, 1)
    const i = velocityTryOrderNames.value.indexOf(name)
    if (i > -1) velocityTryOrderNames.value.splice(i, 1)
  }
  const openAddSubServerDialog = () => { selectedSubServersFromDialog.value = []; addSubServerDialogVisible.value = true }
  const handleSubServerSelectionChange = (sel: Server[]) => { selectedSubServersFromDialog.value = sel }
  const confirmAddSubServers = () => {
    const existing = new Set(velocitySubServersList.value.map((s) => s.name))
    selectedSubServersFromDialog.value.forEach((srv) => {
      if (!existing.has(srv.name))
        velocitySubServersList.value.push({ id: String(srv.id), name: srv.name, ip: '127.0.0.1', port: String(srv.port || '') })
    })
    addSubServerDialogVisible.value = false
  }
  const removeTryServer = (name: string) => {
    const i = velocityTryOrderNames.value.indexOf(name)
    if (i > -1) velocityTryOrderNames.value.splice(i, 1)
  }

  // ── Map uploads ───────────────────────────────────────────────
  const handleMapFileChange = (kind: string, uploadFile: any) => {
    const raw = uploadFile?.raw || null
    if (kind === 'nether') netherMapFile.value = raw
    if (kind === 'end') endMapFile.value = raw
  }
  const handleMapExceed = (kind: string, files: any[]) => {
    const uploader = kind === 'nether' ? netherMapUploaderRef.value : endMapUploaderRef.value
    uploader?.clearFiles?.(); uploader?.handleStart?.(files?.[0])
  }
  const handleUploadMapJson = async (kind: string) => {
    if (!currentConfigServer.value || (kind !== 'nether' && kind !== 'end')) return
    const file = kind === 'nether' ? netherMapFile.value : endMapFile.value
    if (!file) { ElMessage.warning('请选择要上传的 JSON 文件'); return }
    ;(isUploadingMap as any)[kind] = true
    const formData = new FormData(); formData.append('file', file)
    try {
      const { data } = await apiClient.post(`/api/servers/${currentConfigServer.value.id}/map-json/${kind}`, formData)
      ElMessage.success('地图 JSON 上传成功')
      currentConfigServer.value.map = { ...(currentConfigServer.value.map || {}), ...(data.map || {}) }
      if (kind === 'nether') { netherMapFile.value = null; netherMapFileList.value = []; netherMapUploaderRef.value?.clearFiles?.() }
      else { endMapFile.value = null; endMapFileList.value = []; endMapUploaderRef.value?.clearFiles?.() }
    } catch (error: any) { ElMessage.error(error.response?.data?.detail || '上传失败') }
    finally { ;(isUploadingMap as any)[kind] = false }
  }

  // ── File editor ───────────────────────────────────────────────
  const openFileEditor = async (fileType: string) => {
    editorDialog.fileType = fileType
    editorDialog.loading = true; editorDialog.visible = true; editorDialog.content = ''
    const map: Record<string, { title: string; language: string }> = {
      mcdr_config: { title: '编辑 MCDR 配置文件 (config.yml)', language: 'yaml' },
      mc_properties: { title: '编辑 MC 配置文件 (server.properties)', language: 'properties' },
      velocity_toml: { title: '编辑 Velocity 配置文件 (velocity.toml)', language: 'toml' },
    }
    Object.assign(editorDialog, map[fileType])
    try {
      const response = await apiClient.get(`/api/servers/${currentConfigServer.value!.id}/config-file`, {
        params: { file_type: fileType }, transformResponse: [(data: any) => data],
      })
      editorDialog.content = response.data
    } catch (error: any) {
      ElMessage.error(`加载文件内容失败: ${error.response?.data?.detail || error.message}`)
      editorDialog.visible = false
    } finally { editorDialog.loading = false }
  }
  const handleSaveFile = async (newContent: string) => {
    editorDialog.saving = true
    try {
      await apiClient.post(`/api/servers/${currentConfigServer.value!.id}/config-file`, { file_type: editorDialog.fileType, content: newContent })
      ElMessage.success('文件已成功保存！'); await openConfigDialog(currentConfigServer.value!); editorDialog.visible = false
    } catch (error: any) { ElMessage.error(`保存文件失败: ${error.response?.data?.detail || error.message}`) }
    finally { editorDialog.saving = false }
  }

  // ── Create / import / copy / rename dialogs ───────────────────
  const openCreateDialog = async () => {
    await fetchServerLinkGroups(); createDialogVisible.value = true
    if (formRef.value) formRef.value.resetFields()
    let preselectedIds: number[] = []
    if (!isPlatformAdmin.value && activeGroupId.value) {
      const has = (user as any).group_permissions.some((p: any) => p.group_id === activeGroupId.value && p.role === 'ADMIN')
      if (has) preselectedIds = [activeGroupId.value]
    }
    newServerForm.value = { name: '', serverLinkGroupIds: preselectedIds }
  }
  const handleCreateServer = async () => {
    if (!formRef.value) return
    await formRef.value.validate(async (valid: boolean) => {
      if (valid) {
        try {
          const { data } = await apiClient.post('/api/servers/create', { name: newServerForm.value.name, server_link_group_ids: newServerForm.value.serverLinkGroupIds || [] })
          ElMessage.success(data?.message || '已提交创建服务器任务'); createDialogVisible.value = false
        } catch (e: any) { ElMessage.error(`创建失败: ${e.response?.data?.detail || e.message}`) }
      }
    })
  }
  const openImportDialog = async () => {
    await fetchServerLinkGroups(); importDialogVisible.value = true
    if (importFormRef.value) importFormRef.value.resetFields()
    importServerForm.value = { name: '', path: '', serverLinkGroupIds: [] }
  }
  const handleImportServer = async () => {
    if (!importFormRef.value) return
    await importFormRef.value.validate(async (valid: boolean) => {
      if (valid) {
        try {
          const { data } = await apiClient.post('/api/servers/import', { name: importServerForm.value.name, path: importServerForm.value.path, server_link_group_ids: importServerForm.value.serverLinkGroupIds || [] })
          ElMessage.success(data?.message || '已提交导入服务器任务'); importDialogVisible.value = false
        } catch (e: any) { ElMessage.error(`导入失败: ${e.response?.data?.detail || e.message}`) }
      }
    })
  }
  const openCopyDialog = async (server: Server) => {
    await fetchServerLinkGroups(); sourceServerToCopy.value = server
    let preselectedIds: number[] = []
    if (!isPlatformAdmin.value && activeGroupId.value) {
      const has = (user as any).group_permissions.some((p: any) => p.group_id === activeGroupId.value && p.role === 'ADMIN')
      if (has) preselectedIds = [activeGroupId.value]
    }
    copyServerForm.value = { name: '', serverLinkGroupIds: preselectedIds }
    copyDialogVisible.value = true
    nextTick(() => { if (copyFormRef.value) copyFormRef.value.clearValidate() })
  }
  const handleCopyServer = async () => {
    if (!copyFormRef.value) return
    await copyFormRef.value.validate(async (valid: boolean) => {
      if (valid) {
        try {
          const { data } = await apiClient.post('/api/servers/import', { name: copyServerForm.value.name, path: (sourceServerToCopy.value as any)?.path, server_link_group_ids: copyServerForm.value.serverLinkGroupIds || [] })
          ElMessage.success(data?.message || '已提交复制服务器任务'); copyDialogVisible.value = false
        } catch (e: any) { ElMessage.error(`复制失败: ${e.response?.data?.detail || e.message}`) }
      }
    })
  }
  const openRenameDialog = (server: Server) => {
    serverToRename.value = server; renameForm.value = { newName: server.name }; renameDialogVisible.value = true
    nextTick(() => { if (renameFormRef.value) renameFormRef.value.clearValidate() })
  }
  const handleRenameServer = async () => {
    if (!renameFormRef.value) return
    await renameFormRef.value.validate(async (valid: boolean) => {
      if (valid) {
        renameLoading.value = true
        try {
          const newName = renameForm.value.newName.trim()
          await apiClient.post(`/api/servers/${serverToRename.value!.id}/rename?new_name=${encodeURIComponent(newName)}`)
          ElMessage.success(`服务器已重命名为 "${newName}"`); renameDialogVisible.value = false
          const idx = serverList.value.findIndex((s) => s.id === serverToRename.value!.id)
          if (idx !== -1) serverList.value[idx].name = newName
        } catch (e: any) { ElMessage.error(`重命名失败: ${e.response?.data?.detail || e.message}`) }
        finally { renameLoading.value = false }
      }
    })
  }

  // ── Server actions ────────────────────────────────────────────
  const setAutoStart = async (s: Server, autoStart: boolean) => {
    if (!s?.id) return
    autoStartSaving[s.id] = true
    const revertTo = !autoStart
    try {
      const { data } = await apiClient.post('/api/servers/auto-start', { server_id: s.id, auto_start: !!autoStart })
      if (!s.core_config) s.core_config = {}
      s.core_config.auto_start = data?.auto_start ?? !!autoStart
      ElMessage.success(`${s.name} 已${s.core_config.auto_start ? '启用' : '关闭'}自动启动`)
    } catch (e: any) {
      ElMessage.error(`设置自动启动失败: ${e.response?.data?.detail || e.message}`)
      if (!s.core_config) s.core_config = {}
      s.core_config.auto_start = revertTo
    } finally { autoStartSaving[s.id] = false }
  }
  const startServer = async (s: Server) => {
    s.loading = true; s.status = 'pending'
    try { await apiClient.post(`/api/servers/start?server_id=${s.id}`); ElMessage.success(`${s.name} 已发送启动命令`) }
    catch (e: any) { ElMessage.error(`启动失败: ${e.response?.data?.detail || e.message}`); s.status = 'stopped'; s.loading = false }
  }
  const stopServer = async (s: Server) => {
    s.loading = true
    try { await apiClient.post(`/api/servers/stop?server_id=${s.id}`); ElMessage.success(`${s.name} 已发送停止命令`) }
    catch (e: any) { ElMessage.error(`停止失败: ${e.response?.data?.detail || e.message}`); s.loading = false }
  }
  const restartServer = async (s: Server) => {
    s.loading = true
    try { await apiClient.post(`/api/servers/restart?server_id=${s.id}`); ElMessage.success(`${s.name} 已发送重启命令`) }
    catch (e: any) { ElMessage.error(`重启失败: ${e.response?.data?.detail || e.message}`); s.loading = false }
  }
  const handleDeleteServer = (server: Server) => {
    if (server.status === 'running') { ElMessage.error('服务器正在运行，请先停止再删除！'); return }
    ElMessageBox.confirm(`您确定要删除服务器 "${server.name}" 吗？此操作将永久删除其所有文件和配置，且无法恢复。`, '危险操作：删除服务器', {
      confirmButtonText: '确认删除', cancelButtonText: '取消', type: 'warning', confirmButtonClass: 'el-button--danger',
    }).then(async () => {
      try { const { data } = await apiClient.delete(`/api/servers/${server.id}`); ElMessage.success(data?.message || `已开始删除服务器 "${server.name}"`) }
      catch (error: any) { ElMessage.error(`删除失败: ${error.response?.data?.detail || error.message}`) }
    }).catch(() => ElMessage.info('已取消删除操作'))
  }
  const forceKillServer = (server: Server) => {
    ElMessageBox.confirm(`这是一个危险操作，它会立即终止服务器进程，可能导致数据损坏。您确定要强制关闭服务器 "${server.name}" 吗？`, '确认强制关闭', {
      confirmButtonText: '强制关闭', cancelButtonText: '取消', type: 'warning', confirmButtonClass: 'el-button--danger',
    }).then(async () => {
      server.loading = true
      try { const { data } = await apiClient.post(`/api/servers/force-kill?server_id=${server.id}`); ElMessage.success(`${server.name} 已发送强制关闭命令: ${data.message}`) }
      catch (e: any) { ElMessage.error(`强制关闭失败: ${e.response?.data?.detail || e.message}`); server.loading = false }
    }).catch(() => ElMessage.info('已取消强制关闭操作'))
  }

  // ── Batch actions ─────────────────────────────────────────────
  const handleSelectionChange = (selection: Server[]) => { selectedServers.value = selection }
  const handleBatchAction = (action: string) => {
    if (selectedServers.value.length === 0) { ElMessage.warning('请至少选择一个服务器'); return }
    if (action === 'command') { batchCommand.value = ''; commandDialogVisible.value = true; return }
    const text: Record<string, string> = { start: '启动', stop: '停止', restart: '重启', delete: '删除' }
    ElMessageBox.confirm(`确定要批量 ${text[action]} ${selectedServers.value.length} 个服务器吗？`, '警告', {
      confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning',
    }).then(() => executeBatchAction(action)).catch(() => {})
  }
  const executeBatchAction = async (action: string, command: string | null = null) => {
    isBatchProcessing.value = true
    try { await apiClient.post('/api/servers/batch-action', { ids: selectedServers.value.map((s) => s.id), command }, { params: { action } }); ElMessage.success('批量操作指令已发送！') }
    catch (e: any) { ElMessage.error(`批量操作失败: ${e.response?.data?.detail || e.message}`) }
    finally { isBatchProcessing.value = false }
  }
  const handleSendCommand = () => {
    if (!batchCommand.value.trim()) { ElMessage.warning('指令不能为空'); return }
    executeBatchAction('command', batchCommand.value); commandDialogVisible.value = false
  }

  // ── Navigation & utils ────────────────────────────────────────
  const goToConsole = (serverId: number) => router.push(`/console/${serverId}`)
  const goToServerLinkGroups = () => {
    createDialogVisible.value = false; importDialogVisible.value = false; copyDialogVisible.value = false
    router.push('/server-groups')
  }
  const copyPath = async (path: string) => {
    if (!path) return
    try {
      if (navigator?.clipboard?.writeText) { await navigator.clipboard.writeText(path); ElMessage.success('服务器路径已复制！'); return }
    } catch { }
    try {
      const textarea = document.createElement('textarea'); textarea.value = path; textarea.setAttribute('readonly', '')
      textarea.style.position = 'absolute'; textarea.style.left = '-9999px'
      document.body.appendChild(textarea); textarea.select()
      const ok = document.execCommand('copy'); document.body.removeChild(textarea)
      if (ok) ElMessage.success('服务器路径已复制！')
      else throw new Error('execCommand 失败')
    } catch { ElMessage.error('复制失败，请手动复制。') }
  }
  const testPort = async (port: number | string) => {
    if (!port) return ElMessage.warning('请输入有效的端口号')
    const msg = ElMessage({ message: `正在测试端口 ${port}...`, type: 'info', duration: 0 } as any)
    try {
      const { data } = await apiClient.get(`/api/utils/check-port?port=${port}`)
      if (data.is_available) ElMessage.success(`端口 ${port} 当前可用`)
      else ElMessage.warning(`端口 ${port} 当前已被占用`)
    } catch (e: any) { ElMessage.error(`测试失败: ${e.response?.data?.detail || e.message}`) }
    finally { (msg as any).close() }
  }

  // ── Archive ───────────────────────────────────────────────────
  const handleCreateArchive = async (server: Server) => {
    try {
      await ElMessageBox.confirm(`这会打包服务器 "${server.name}" 的主世界文件夹，并创建一个永久备份。`, '确认创建永久备份', { type: 'info' })
      const { data } = await apiClient.post(`/api/archives/create/from-server/${server.id}`)
      ElMessage.success('创建备份任务已发起！将跳转至存档管理页面。')
      router.push({ path: '/tools/archives', query: { new_task_id: data.task_id } })
    } catch (error: any) { if (error !== 'cancel') ElMessage.error(error.response?.data?.detail || '发起创建备份任务失败') }
  }

  // ── Plugin management ─────────────────────────────────────────
  const compareVersions = (v1: string, v2: string) => {
    if (typeof v1 !== 'string' || typeof v2 !== 'string') return 0
    const parts1 = v1.replace(/^v/, '').split('-')[0].split('.').map((p) => parseInt(p, 10) || 0)
    const parts2 = v2.replace(/^v/, '').split('-')[0].split('.').map((p) => parseInt(p, 10) || 0)
    const len = Math.max(parts1.length, parts2.length)
    for (let i = 0; i < len; i++) {
      const p1 = parts1[i] || 0, p2 = parts2[i] || 0
      if (p1 > p2) return 1; if (p1 < p2) return -1
    }
    return 0
  }
  const getAuthorsArray = (meta: any) => {
    if (!meta) return []
    if (meta.authors) { if (Array.isArray(meta.authors)) return meta.authors.filter(Boolean); if (typeof meta.authors === 'string' && meta.authors.trim()) return [meta.authors] }
    if (meta.author) { if (Array.isArray(meta.author)) return meta.author.filter(Boolean); if (typeof meta.author === 'string' && meta.author.trim()) return [meta.author] }
    return []
  }
  const openPluginConfigDialog = async (server: Server) => {
    currentServerForPlugins.value = server; installedPluginsQuery.value = ''; installedPluginsFilter.value = 'all'
    pluginConfigDialogVisible.value = true
    await Promise.all([fetchInstalledPlugins(), fetchOnlinePlugins()])
  }
  const installedPluginRowClassName = ({ row }: any) => (!row.enabled ? 'disabled-plugin-row' : '')
  const fetchInstalledPlugins = async () => {
    if (!currentServerForPlugins.value) return
    pluginsLoading.value = true
    try { const { data } = await apiClient.get(`/api/plugins/server/${currentServerForPlugins.value.id}`); installedPlugins.value = (data.data || []).map((p: any) => ({ ...p, loading: false })) }
    catch (error: any) { ElMessage.error(`加载插件列表失败: ${error.response?.data?.detail || error.message}`); installedPlugins.value = [] }
    finally { pluginsLoading.value = false }
  }
  const handlePluginSwitch = async (plugin: any) => {
    plugin.loading = true
    const enable = !plugin.enabled
    try {
      await apiClient.post(`/api/plugins/server/${currentServerForPlugins.value!.id}/switch/${plugin.file_name}?enable=${enable}`)
      ElMessage.success(`插件 "${plugin.meta.name || plugin.file_name}" 已${enable ? '启用' : '禁用'}`); await fetchInstalledPlugins()
    } catch (error: any) {
      ElMessage.error(`操作失败: ${error.response?.data?.detail || error.message}`)
      const found = installedPlugins.value.find((p: any) => p.file_name === plugin.file_name)
      if (found) found.loading = false
    }
  }
  const handlePluginDelete = async (plugin: any) => {
    plugin.loading = true
    try {
      await apiClient.delete(`/api/plugins/server/${currentServerForPlugins.value!.id}/${plugin.file_name}`)
      ElMessage.success(`插件 "${plugin.meta.name || plugin.file_name}" 已删除`); await fetchInstalledPlugins()
    } catch (error: any) { ElMessage.error(`删除失败: ${error.response?.data?.detail || error.message}`); plugin.loading = false }
  }
  const openAddOnlinePluginDialog = async () => { addOnlinePluginDialogVisible.value = true; onlinePluginsQuery.value = ''; onlinePluginsSelected.value = []; await fetchOnlinePlugins() }
  const openAddDbPluginDialog = async () => { addDbPluginDialogVisible.value = true; dbPluginsQuery.value = ''; dbPluginsSelected.value = []; await fetchDbPlugins() }
  const fetchOnlinePlugins = async (force = false) => {
    if (onlinePlugins.value.length > 0 && !force) return
    onlinePluginsLoading.value = true
    try {
      const { data } = await apiClient.get('/api/plugins/mcdr/versions')
      const map = data?.plugins || {}
      onlinePlugins.value = Object.keys(map).map((k) => { const p = map[k]; return { meta: p.meta, plugin: p.plugin, release: p.release, repository: p.repository, latest: p?.release?.releases?.[0] ?? null } })
        .sort((a: any, b: any) => (b.repository?.stargazers_count ?? 0) - (a.repository?.stargazers_count ?? 0))
    } catch (error: any) { ElMessage.error(`加载 MCDR 市场插件失败: ${error.message}`) }
    finally { onlinePluginsLoading.value = false }
  }
  const fetchDbPlugins = async () => {
    dbPluginsLoading.value = true
    try { const { data } = await apiClient.get('/api/plugins/db'); dbPlugins.value = data || [] }
    catch (error: any) { ElMessage.error(`加载数据库插件失败: ${error.message}`) }
    finally { dbPluginsLoading.value = false }
  }
  const getPluginInstallStatus = (pluginId: string) => {
    if (!pluginId) return null
    const found = installedPlugins.value.find((p: any) => p.meta.id === pluginId)
    return found ? found.meta.version : null
  }
  const handleOnlineSelectionChange = (sel: any[]) => { onlinePluginsSelected.value = sel }
  const handleDbSelectionChange = (sel: any[]) => { dbPluginsSelected.value = sel }
  const isUpdateAvailable = (plugin: any) => {
    if (!plugin.meta.id) return false
    const online = onlinePluginsMap.value.get(plugin.meta.id)
    if (!online || !online.release?.latest_version || !plugin.meta.version) return false
    return compareVersions(online.release.latest_version, plugin.meta.version) > 0
  }
  const handleUpdatePlugin = async (plugin: any) => {
    const online = onlinePluginsMap.value.get(plugin.meta.id)
    if (!online) { ElMessage.error('在市场中找不到该插件，无法更新。'); return }
    plugin.loading = true
    try {
      await apiClient.post(`/api/plugins/server/${currentServerForPlugins.value!.id}/install/from-online?plugin_id=${encodeURIComponent(plugin.meta.id)}&tag_name=${encodeURIComponent(online.release.latest_version)}`)
      ElNotification({ title: '更新任务已创建', message: `插件 "${plugin.meta.name}" 已加入后台更新队列。`, type: 'success' })
      setTimeout(fetchInstalledPlugins, 3000)
    } catch (error: any) { ElNotification({ title: '更新请求失败', message: `插件 "${plugin.meta.name}": ${error.response?.data?.detail || error.message}`, type: 'error', duration: 0 }) }
    finally { plugin.loading = false }
  }
  const prepareInstallationConfirmation = () => {
    if (onlinePluginsSelected.value.length === 0) return
    pluginsToInstall.value = onlinePluginsSelected.value.map((plugin) => {
      const availableVersions = plugin.release?.releases?.map((r: any) => r.meta.version).filter(Boolean) || []
      return { ...plugin, availableVersions, selectedVersion: plugin.release?.latest_version || (availableVersions[0] ?? null) }
    })
    installConfirmDialogVisible.value = true
  }
  const executeInstallation = async () => {
    if (pluginsToInstall.value.length === 0) return
    isInstallingPlugins.value = true
    const serverId = currentServerForPlugins.value!.id
    const results = await Promise.all(pluginsToInstall.value.map((plugin) => {
      if (!plugin.selectedVersion) return Promise.resolve({ name: plugin.meta.name, status: 'rejected', reason: '未选择安装版本' })
      return apiClient.post(`/api/plugins/server/${serverId}/install/from-online?plugin_id=${encodeURIComponent(plugin.meta.id)}&tag_name=${encodeURIComponent(plugin.selectedVersion)}`)
        .then(() => ({ name: plugin.meta.name, status: 'fulfilled' }))
        .catch((err: any) => ({ name: plugin.meta.name, status: 'rejected', reason: err.response?.data?.detail || err.message }))
    }))
    let successCount = 0
    results.forEach((r: any) => {
      if (r.status === 'fulfilled') { successCount++; ElNotification({ title: '安装任务已创建', message: `插件 "${r.name}" 已加入后台安装队列。`, type: 'success' }) }
      else ElNotification({ title: '安装请求失败', message: `插件 "${r.name}": ${r.reason}`, type: 'error', duration: 0 })
    })
    isInstallingPlugins.value = false
    if (successCount > 0) { installConfirmDialogVisible.value = false; addOnlinePluginDialogVisible.value = false; setTimeout(fetchInstalledPlugins, 1000) }
  }
  const handleInstallDbPlugins = async () => {
    if (dbPluginsSelected.value.length === 0) return
    isInstallingPlugins.value = true
    const serverId = currentServerForPlugins.value!.id
    const results = await Promise.all(dbPluginsSelected.value.map((plugin) =>
      apiClient.post(`/api/plugins/server/${serverId}/install/from-db/${plugin.id}`)
        .then(() => ({ name: plugin.meta.name || plugin.file_name, status: 'fulfilled' }))
        .catch((err: any) => ({ name: plugin.meta.name || plugin.file_name, status: 'rejected', reason: err.response?.data?.detail || err.message })),
    ))
    let successCount = 0
    results.forEach((r: any) => {
      if (r.status === 'fulfilled') { successCount++; ElNotification({ title: '安装成功', message: `插件 "${r.name}" 已安装。`, type: 'success' }) }
      else ElNotification({ title: '安装失败', message: `插件 "${r.name}": ${r.reason}`, type: 'error', duration: 0 })
    })
    isInstallingPlugins.value = false
    if (successCount > 0) { addDbPluginDialogVisible.value = false; fetchInstalledPlugins() }
  }

  // ── WebSocket + lifecycle ─────────────────────────────────────
  let socket: ReturnType<typeof io> | null = null

  onMounted(() => {
    fetchServers(); fetchFabricGameVersions(); fetchForgeGameVersions(); fetchJavaCmdOptions()
    socket = io({ path: '/ws/socket.io' })
    socket.on('connect', () => console.log('WebSocket for ServerList connected.'))
    socket.on('server_status_update', (updatedServer: any) => {
      if (updatedServer?.id) {
        const index = serverList.value.findIndex((s) => s.id === updatedServer.id)
        if (index !== -1) {
          const orig = serverList.value[index]
          const merged = { ...orig, ...updatedServer, last_startup: updatedServer.last_startup ?? orig.last_startup, loading: false }
          if (merged.size_mb != null) merged.size_calc_state = 'ok'
          serverList.value[index] = merged
        }
      }
    })
    socket.on('server_delete', () => fetchServers())
    socket.on('server_create', () => fetchServers())
    socket.on('disconnect', () => console.log('WebSocket for ServerList disconnected.'))
    socket.on('connect_error', (err: Error) => console.error('WebSocket connection error:', err))
  })

  onUnmounted(() => {
    if (socket) socket.disconnect()
    if (pollInterval) clearInterval(pollInterval)
  })

  return {
    // View
    viewMode, searchQuery, statusFilter,
    // Core list
    serverList, filteredServerList, loading, loaded, selectedServers, isBatchProcessing, autoStartSaving,
    tableRef,
    // Pagination
    currentPage, pageSize, pagedServerList, sortedFilteredList,
    // Server link groups
    serverLinkGroups, serverLinkGroupsLoading, selectableGroups,
    // Dialog visibility
    createDialogVisible, importDialogVisible, copyDialogVisible, commandDialogVisible,
    configDialogVisible, renameDialogVisible, addSubServerDialogVisible,
    // Form refs
    formRef, importFormRef, copyFormRef, renameFormRef, subServerSelectionTable,
    netherMapUploaderRef, endMapUploaderRef,
    // Form data & rules
    newServerForm, importServerForm, copyServerForm, renameForm, batchCommand,
    formRules, importFormRules, copyFormRules, renameFormRules,
    renameLoading, serverToRename, sourceServerToCopy,
    // Config dialog
    configLoading, isSavingConfig, currentConfigServer, configFormData,
    selectedServerTypeForSetup, commandEditMode, currentView, dialogState, dialogTitle,
    mojangVersions, velocityVersions, fabricLoaderVersions, isFetchingVersions,
    isFetchingFabricVersions, forgeGameVersions, forgeLoaderVersions,
    isFetchingForgeGameVersions, isFetchingForgeLoaderVersions,
    showSnapshots, showExperiments, isDownloading, downloadProgress, javaCmdOptions,
    filteredMojangVersions, availableSubServers, isFabricAvailable,
    isVanillaFamily, isForgeType,
    serverTypes, gamemodeOptions, difficultyOptions,
    velocitySubServersList, velocityTryOrderNames, selectedSubServersFromDialog,
    netherMapFileList, endMapFileList, isUploadingMap,
    editorDialog,
    // Plugin state
    currentServerForPlugins, pluginConfigDialogVisible, installedPlugins, onlinePlugins,
    pluginsLoading, onlinePluginsLoading, installedPluginsQuery, installedPluginsFilter,
    onlinePluginsQuery, onlinePluginsSelected, addOnlinePluginDialogVisible, addDbPluginDialogVisible,
    dbPlugins, dbPluginsLoading, dbPluginsQuery, dbPluginsSelected,
    installConfirmDialogVisible, pluginsToInstall, isInstallingPlugins,
    onlinePluginsMap, filteredInstalledPlugins, filteredOnlinePlugins,
    // User / permissions
    isPlatformAdmin, hasRole,
    // Methods - server list
    fetchServers, handleSelectionChange,
    // Methods - server actions
    startServer, stopServer, restartServer, setAutoStart, handleDeleteServer, forceKillServer,
    handleBatchAction, handleSendCommand,
    // Methods - dialogs
    openCreateDialog, handleCreateServer, openImportDialog, handleImportServer,
    openCopyDialog, handleCopyServer, openRenameDialog, handleRenameServer,
    openConfigDialog, resetDialogState, confirmServerType, handleSaveConfig, startAndContinue,
    addManualSubServer, removeSubServer, openAddSubServerDialog,
    handleSubServerSelectionChange, confirmAddSubServers, removeTryServer,
    handleMapFileChange, handleMapExceed, handleUploadMapJson,
    openFileEditor, handleSaveFile,
    // Methods - utils
    goToConsole, goToServerLinkGroups, copyPath, testPort, handleCreateArchive,
    // Methods - plugin
    getAuthorsArray, openPluginConfigDialog, installedPluginRowClassName,
    fetchInstalledPlugins, handlePluginSwitch, handlePluginDelete,
    openAddOnlinePluginDialog, openAddDbPluginDialog,
    getPluginInstallStatus, handleOnlineSelectionChange, handleDbSelectionChange,
    isUpdateAvailable, handleUpdatePlugin, prepareInstallationConfirmation,
    executeInstallation, handleInstallDbPlugins,
  }
}
