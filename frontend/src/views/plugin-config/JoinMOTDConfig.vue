<template>
  <ConfigPageLayout
    plugin-title="joinMOTD"
    plugin-key="join_motd"
    :servers="servers"
    :loading-servers="loadingServers"
    :installed-map="installedMap"
    :is-allowed="isAllowed"
    :installing-server-id="installingServerId"
    :active-server="activeServer"
    @update:active-server="activeServer = $event"
    @install="installFor"
  />
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { normalizeServerType, installMCDR, fetchServerPlugins, fetchServersCached, invalidateServerPlugins } from './_Shared'
import ConfigPageLayout from './components/ConfigPageLayout.vue'

const PLUGIN_ID = 'join_motd'

const servers = ref<any[]>([])
const loadingServers = ref(false)
const installingServerId = ref<number | null>(null)
const activeServer = ref<any | null>(null)
const installedMap = ref(new Map<number, boolean>())

const isAllowed = (s: any) => normalizeServerType(s) !== 'velocity'

const loadServers = async () => {
  loadingServers.value = true
  try { servers.value = await fetchServersCached() } catch { ElMessage.error('加载服务器失败') } finally { loadingServers.value = false }
  await refreshInstalled()
}

const refreshInstalled = async () => {
  installedMap.value = new Map()
  await Promise.allSettled(servers.value.map(async (s) => {
    try {
      const plugs = await fetchServerPlugins(s.id)
      installedMap.value.set(s.id, plugs.some((p: any) => (p?.meta?.id || '') === PLUGIN_ID))
    } catch { installedMap.value.set(s.id, false) }
  }))
}

const installFor = async (s: any) => {
  installingServerId.value = s.id
  try {
    await installMCDR(s.id, PLUGIN_ID)
    ElMessage.success(`已发起安装 ${PLUGIN_ID} 到 ${s.name}`)
    invalidateServerPlugins(s.id)
    installedMap.value.set(s.id, true)
  } catch (e: any) { ElMessage.error(e.response?.data?.detail || e.message || '安装失败') }
  finally { installingServerId.value = null }
}

onMounted(loadServers)
</script>
