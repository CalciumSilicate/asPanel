import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import type { Ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { io } from 'socket.io-client'
import { storeToRefs } from 'pinia'
import apiClient from '@/api'
import { useSettingsStore } from '@/store/settings'
import { useUserStore } from '@/store/user'
import { buildMessageSegments, normalizeContent } from '@/utils/cqParser'
import type { Segment } from '@/utils/cqParser'

export interface Group {
  id: number
  name: string
  server_ids: number[]
}

export interface Server {
  id: number
  name: string
  status: string
}

export interface OnlineUser {
  id?: number
  username: string
  avatar_url: string | null
}

export interface UIMessage {
  id?: number
  content: string
  display: string
  avatar: string | null
  level: string
  created_at: string
  key: string
  source: string
  segments: Segment[]
}

const resolveAvatar = (url: string | null | undefined): string | null => {
  if (!url) return null
  if (url.startsWith('http://') || url.startsWith('https://')) return url
  return url.startsWith('/') ? url : `/${url}`
}

const mcAvatar = (name: string): string => {
  if (!name) return ''
  try {
    return `/api/users/mc/avatar/${encodeURIComponent(name)}`
  } catch {
    return `/api/users/mc/avatar/${name}`
  }
}

export function useChatRoom(chatMainRef: Ref<HTMLElement | null>) {
  const settings = useSettingsStore().settings
  const userStore = useUserStore()
  const { isPlatformAdmin, activeGroupId, capabilities } = storeToRefs(userStore)

  const socket = io({ path: '/ws/socket.io' })

  const groups = ref<Group[]>([])
  const servers = ref<Server[]>([])
  const users = ref<OnlineUser[]>([])
  const me = ref<{ id: number; username: string; avatar_url: string | null } | null>(null)
  const activeGroup = ref<Group | null>(null)
  const joinedGroupId = ref<number | null>(null)
  const messages = ref<UIMessage[]>([])
  const draft = ref('')
  const showJumpBottom = ref(false)
  const shouldStickBottom = ref(true)
  const hasMoreOlder = ref(false)
  const noMoreOlder = ref(false)
  const loadingOlder = ref(false)
  const loaded = ref(false)

  const canSendAlert = computed(() => capabilities.value.canSendAlert)

  const onlineCount = (g: Group | null): number => {
    if (!g) return 0
    const ids = g.server_ids || []
    const map = new Map(servers.value.map((s) => [s.id, s.status]))
    return ids.filter((id) => map.get(id) === 'running').length
  }

  const formatTime = (dt: string): string => {
    try {
      return new Date(dt).toLocaleString('zh-CN', {
        timeZone: (settings as Record<string, string>).timezone || 'Asia/Shanghai',
      })
    } catch {
      return ''
    }
  }

  const toUIMsg = (r: Record<string, unknown>): UIMessage => {
    const rawContent = normalizeContent(r.content)
    const segments = buildMessageSegments(rawContent)
    if (r.source === 'game') {
      return {
        id: r.id as number | undefined,
        content: rawContent,
        display: `${r.player_name}@${r.server_name}`,
        avatar: mcAvatar(r.player_name as string),
        level: (r.level as string) || 'NORMAL',
        created_at: (r.created_at as string) || '',
        key: `${r.player_name}@${r.server_name}`,
        source: 'game',
        segments,
      }
    }
    if (r.source === 'qq') {
      const name = (r.sender_username as string) || 'QQ'
      const display = name.includes('@QQ') ? name : `${name}@QQ`
      let avatar = r.sender_avatar ? resolveAvatar(r.sender_avatar as string) : null
      if (!avatar && r.sender_qq) {
        avatar = `https://q1.qlogo.cn/g?b=qq&nk=${r.sender_qq}&s=640`
      }
      if (!avatar) {
        avatar = mcAvatar(name.replace(/\(.*\)@QQ$/, ''))
      }
      return {
        id: r.id as number | undefined,
        content: rawContent,
        display,
        avatar,
        level: (r.level as string) || 'NORMAL',
        created_at: (r.created_at as string) || '',
        key: `qq:${display}`,
        source: 'qq',
        segments,
      }
    }
    return {
      id: r.id as number | undefined,
      content: rawContent,
      display: `${r.sender_username}@AS-Panel`,
      avatar: resolveAvatar(r.sender_avatar as string),
      level: (r.level as string) || 'NORMAL',
      created_at: (r.created_at as string) || '',
      key: `web:${r.sender_username}`,
      source: (r.source as string) || 'web',
      segments,
    }
  }

  // ── Scroll helpers ──────────────────────────────────────────

  const isAtBottom = (): boolean => {
    const el = chatMainRef.value
    if (!el) return true
    return el.scrollTop + el.clientHeight >= el.scrollHeight - 10
  }

  const scrollToBottom = () => {
    shouldStickBottom.value = true
    nextTick(() => {
      const el = chatMainRef.value
      if (el) el.scrollTop = el.scrollHeight
      showJumpBottom.value = false
    })
  }

  const onScroll = () => {
    const atBottom = isAtBottom()
    showJumpBottom.value = !atBottom
    shouldStickBottom.value = atBottom
  }

  const onContentMediaLoad = (e: Event) => {
    if (!e?.target) return
    if (shouldStickBottom.value) requestAnimationFrame(() => scrollToBottom())
  }

  const isCompact = (i: number): boolean => {
    if (i === 0) return false
    const a = messages.value[i]
    const b = messages.value[i - 1]
    return !!(a && b && a.key === b.key && a.level === b.level)
  }

  // ── API loaders ─────────────────────────────────────────────

  const loadMe = async () => {
    try {
      const { data } = await apiClient.get('/api/users/me')
      me.value = {
        id: data.id,
        username: data.username,
        avatar_url: resolveAvatar(data.avatar_url),
      }
    } catch {
      me.value = null
    }
  }

  const loadGroups = async () => {
    const { data } = await apiClient.get('/api/tools/server-link/groups')
    groups.value = data || []
    if (!isPlatformAdmin.value && activeGroupId.value) {
      const target = groups.value.find((g) => g.id === activeGroupId.value)
      if (target && target.id !== activeGroup.value?.id) selectGroup(target)
    }
  }

  const loadServers = async () => {
    const { data } = await apiClient.get('/api/servers')
    servers.value = data || []
  }

  const selectGroup = (row: Group) => {
    if (joinedGroupId.value && joinedGroupId.value !== row.id) {
      socket.emit('leave_chat_group', { group_id: joinedGroupId.value })
    }
    activeGroup.value = row
    if (me.value) {
      socket.emit('join_chat_group', { group_id: row.id, user: me.value })
      joinedGroupId.value = row.id
    }
    users.value = []
    hasMoreOlder.value = false
    noMoreOlder.value = false
    loadHistory()
  }

  const loadHistory = async () => {
    if (!activeGroup.value) return
    const { data } = await apiClient.get('/api/tools/chat/history', {
      params: { group_id: activeGroup.value.id, limit: 50, offset: 0 },
    })
    messages.value = (data || []).map(toUIMsg)
    hasMoreOlder.value = Array.isArray(data) && data.length === 50
    noMoreOlder.value = !hasMoreOlder.value
    scrollToBottom()
  }

  const loadMoreHistory = async () => {
    if (!activeGroup.value) return
    loadingOlder.value = true
    try {
      const el = chatMainRef.value
      const prevHeight = el ? el.scrollHeight : 0
      const { data } = await apiClient.get('/api/tools/chat/history', {
        params: {
          group_id: activeGroup.value.id,
          limit: 200,
          offset: messages.value.length,
        },
      })
      const arr = (data || []).map(toUIMsg)
      if (arr.length > 0) {
        messages.value = [...arr, ...messages.value]
        await nextTick()
        if (el) el.scrollTop = el.scrollHeight - prevHeight + el.scrollTop
      }
      if (!Array.isArray(data) || data.length < 200) {
        hasMoreOlder.value = false
        noMoreOlder.value = true
      }
    } catch {
      // leave button state unchanged
    } finally {
      loadingOlder.value = false
    }
  }

  // ── Send / Alert ────────────────────────────────────────────

  const doSend = async () => {
    if (!activeGroup.value || !draft.value.trim()) return
    try {
      await apiClient.post('/api/tools/chat/send', {
        group_id: activeGroup.value.id,
        message: draft.value,
        level: 'NORMAL',
      })
      draft.value = ''
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      ElMessage.error(err?.response?.data?.detail || '发送失败')
    }
  }

  const sendAlert = async () => {
    try {
      const { value } = await ElMessageBox.prompt('请输入要发送的 ALERT 文本', 'ALERT', {
        inputPlaceholder: '消息内容',
      })
      if (value && value.trim()) {
        await apiClient.post('/api/tools/chat/send', { message: value, level: 'ALERT' })
        ElMessage.success('ALERT 已发送')
      }
    } catch {
      // cancelled
    }
  }

  // ── Socket handlers ─────────────────────────────────────────

  const onChatMessage = async (msg: Record<string, unknown>) => {
    if (!activeGroup.value) return
    if (msg.level === 'ALERT' || msg.group_id === activeGroup.value.id) {
      const stick = isAtBottom()
      messages.value.push(toUIMsg(msg))
      await nextTick()
      if (stick) scrollToBottom()
    }
  }

  const onPresence = (payload: {
    group_id: number
    web_users?: Array<{ id?: number; username: string; avatar_url?: string }>
    players?: Array<{ player: string; server: string }>
  }) => {
    if (!activeGroup.value || payload.group_id !== activeGroup.value.id) return
    const webUsers = (payload.web_users || []).map((u) => ({
      ...u,
      avatar_url: resolveAvatar(u.avatar_url ?? null),
    }))
    const playerUsers = (payload.players || []).map((p) => ({
      username: `${p.player}@${p.server}`,
      avatar_url: mcAvatar(p.player),
    }))
    users.value = [...webUsers, ...playerUsers]
  }

  socket.on('chat_message', onChatMessage)
  socket.on('chat_presence', onPresence)

  watch(activeGroupId, (newId) => {
    if (isPlatformAdmin.value || !newId) return
    const target = groups.value.find((g) => g.id === newId)
    if (target && target.id !== activeGroup.value?.id) selectGroup(target)
  })

  // Attach load-event listener whenever the scroll element mounts/unmounts.
  // Must use watch() because chatMainRef is inside v-else and is null at onMounted time.
  watch(chatMainRef, (el, prevEl) => {
    if (prevEl) prevEl.removeEventListener('load', onContentMediaLoad, true)
    if (el) el.addEventListener('load', onContentMediaLoad, true)
  })

  onMounted(async () => {
    await loadMe()
    await Promise.all([loadGroups(), loadServers()])
    loaded.value = true
  })

  onUnmounted(() => {
    if (joinedGroupId.value) {
      socket.emit('leave_chat_group', { group_id: joinedGroupId.value })
      joinedGroupId.value = null
    }
    socket.off('chat_message', onChatMessage)
    socket.off('chat_presence', onPresence)
    const el = chatMainRef.value
    if (el) el.removeEventListener('load', onContentMediaLoad, true)
  })

  return {
    groups,
    users,
    activeGroup,
    messages,
    draft,
    showJumpBottom,
    hasMoreOlder,
    noMoreOlder,
    loadingOlder,
    loaded,
    canSendAlert,
    onlineCount,
    selectGroup,
    loadMoreHistory,
    doSend,
    sendAlert,
    onScroll,
    scrollToBottom,
    isCompact,
    formatTime,
  }
}
