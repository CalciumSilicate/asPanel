<template>
  <div class="sl-page">
    <div class="left-wrap" :class="{ 'is-collapsed': asideCollapsed, 'is-collapsing': asideCollapsing }">
      <!-- 左侧：服务器组列表（照搬 ServerLink 左侧） -->
      <div class="table-card left-panel">
        <el-card shadow="never">
          <template #header>
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <span class="text-base font-medium">聊天室</span>
              </div>
              <div class="flex items-center gap-2">
                <el-button type="danger" size="small" @click="sendAlert">全局通知</el-button>
              </div>
            </div>
          </template>

          <el-input v-model="groupQuery" placeholder="搜索服务器组" clearable class="mb-2">
            <template #prefix><el-icon><Search/></el-icon></template>
          </el-input>

          <el-table :data="filteredGroups" size="small" stripe @row-click="selectGroup" :row-class-name="row => (activeGroup && row.row.id===activeGroup.id) ? 'active-row' : ''" :fit="true" style="width: 100%;">
            <el-table-column label="组名" min-width="160">
              <template #default="{ row }">
                <div class="flex items-center justify-between w-full">
                  <div class="server-cell">
                    <div class="name">{{ row.name }}</div>
                    <div class="muted">ID: {{ row.id }}</div>
                  </div>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="在线服务器数" width="120" align="center">
              <template #default="{ row }">
                <el-tag type="success">{{ onlineCount(row) }}</el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </div>

      <!-- 右侧：聊天窗口 -->
      <div class="right-panel">
        <div v-if="!activeGroup" class="main-placeholder">
          <el-empty description="请从左侧选择一个服务器组以进行聊天"/>
        </div>
        <el-card v-else shadow="never" class="mb-3">
          <template #header>
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <span class="text-base font-medium">{{ activeGroup ? activeGroup.name : '请选择服务器组' }}</span>
                <el-tag v-if="activeGroup" size="small" type="info">在线服务器：{{ activeGroup ? onlineCount(activeGroup) : 0 }}</el-tag>
              </div>
            </div>
          </template>

          <div class="chat-wrapper">
            <div class="chat-left">
              <div class="chat-main" ref="chatMainRef" @scroll="onScroll">
                <div class="load-older">
                  <el-button v-if="hasMoreOlder" class="btn-load-older" size="small" :loading="loadingOlder" @click="loadMoreHistory">加载更多</el-button>
                  <div v-else-if="noMoreOlder" class="no-more">没有更多信息了</div>
                </div>
                <template v-for="(m, i) in messages" :key="m.id || 'm-'+i">
                  <div class="msg-row" :class="{ compact: isCompact(i), 'is-alert': m.level==='ALERT' }">
                    <div class="avatar-col">
                      <img v-if="!isCompact(i)" class="avatar" :src="m.avatar || defaultAvatar" :alt="m.display"/>
                    </div>
                    <div class="bubble">
                      <div v-if="!isCompact(i)" class="meta">
                        <span class="name">{{ m.display }}</span>
                        <span class="time">{{ formatTime(m.created_at) }}</span>
                        <el-tag v-if="m.level==='ALERT'" size="small" type="danger">ALERT</el-tag>
                      </div>
                      <div class="content" :class="m.level==='ALERT' ? 'alert' : ''">{{ m.content }}</div>
                    </div>
                  </div>
                </template>
                <el-button v-if="showJumpBottom" class="jump-bottom btn-plain-primary" size="small" type="primary" @click="scrollToBottom">
                  <el-icon><ArrowDown /></el-icon>
                </el-button>
              </div>
              <div class="chat-input">
                <el-input
                  v-model="draft"
                  placeholder="输入消息，回车发送"
                  @keyup.enter.native="doSend"
                  clearable
                  class="chat-input__field"
                />
                <el-button
                  class="btn-send"
                  type="primary"
                  plain
                  :disabled="!activeGroup || !draft.trim()"
                  @click="doSend"
                >
                  <el-icon><Promotion /></el-icon>
                  <span>发送</span>
                </el-button>
              </div>
            </div>
            <div class="chat-side">
              <div class="side-title">在线用户</div>
              <div class="side-list">
                <div class="side-item" v-for="u in users" :key="u.id || u.username">
                  <img class="avatar-small" :src="u.avatar_url || defaultAvatar"/>
                  <span class="uname">{{ u.username }}</span>
                </div>
              </div>
            </div>
          </div>
        </el-card>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, ArrowDown, Promotion } from '@element-plus/icons-vue'
import apiClient from '@/api'
import { io } from 'socket.io-client'
import { API_BASE_URL } from '@/config'
import { asideCollapsed, asideCollapsing } from '@/store/ui'

const defaultAvatar = 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64"><circle cx="32" cy="24" r="14" fill="#bbb"/><rect x="12" y="40" width="40" height="18" rx="9" fill="#bbb"/></svg>'

const socket = io(API_BASE_URL, { path: '/ws/socket.io' })

const groups = ref([])
const servers = ref([])
// 在线列表：面板用户 + 组内玩家，最终渲染合并到 users
const webUsers = ref([])
const groupPlayers = ref([])
const users = ref([])
const me = ref(null)
const groupQuery = ref('')
const activeGroup = ref(null)
const joinedGroupId = ref(null)
const chatMainRef = ref(null)
const messages = ref([])
const draft = ref('')
const showJumpBottom = ref(false)

const filteredGroups = computed(() => {
  const q = groupQuery.value.trim().toLowerCase()
  if (!q) return groups.value
  return groups.value.filter(g => g.name?.toLowerCase().includes(q) || String(g.id).includes(q))
})

const onlineCount = (g) => {
  if (!g) return 0
  const ids = g.server_ids || []
  const map = new Map(servers.value.map(s => [s.id, s.status]))
  let n = 0
  ids.forEach(id => { if (map.get(id) === 'running') n++ })
  return n
}

const selectGroup = (row) => {
  // 离开旧组
  if (joinedGroupId.value && joinedGroupId.value !== row.id) {
    socket.emit('leave_chat_group', { group_id: joinedGroupId.value })
  }
  activeGroup.value = row
  // 进入新组
  if (me.value) {
    socket.emit('join_chat_group', { group_id: row.id, user: me.value })
    joinedGroupId.value = row.id
  }
  // 重置在线列表与分页状态
  webUsers.value = []
  groupPlayers.value = []
  users.value = []
  hasMoreOlder.value = false
  noMoreOlder.value = false
  loadHistory()
}

const loadGroups = async () => {
  const { data } = await apiClient.get('/api/tools/server-link/groups')
  groups.value = data || []
  // 默认不自动进入第一个聊天室，保持空白，等待用户手动选择
}
const loadServers = async () => {
  const { data } = await apiClient.get('/api/servers')
  servers.value = data || []
}
const loadMe = async () => {
  try {
    const { data } = await apiClient.get('/api/users/me')
    me.value = { id: data.id, username: data.username, avatar_url: resolveAvatar(data.avatar_url) }
  } catch (e) { me.value = null }
}

const toUIMsg = (r) => {
  if (r.source === 'game') {
    return {
      id: r.id,
      content: r.content,
      display: `${r.player_name}@${r.server_name}`,
      avatar: mcAvatar(r.player_name),
      level: r.level,
      created_at: r.created_at,
      key: `${r.player_name}@${r.server_name}`
    }
  }
  return {
    id: r.id,
    content: r.content,
    display: `${r.sender_username}@AS-Panel` ,
    avatar: resolveAvatar(r.sender_avatar),
    level: r.level,
    created_at: r.created_at,
    key: `web:${r.sender_username}`
  }
}

const isAtBottom = () => {
  const el = chatMainRef.value
  if (!el) return true
  return el.scrollTop + el.clientHeight >= el.scrollHeight - 10
}
const scrollToBottom = () => {
  nextTick(() => {
    const el = chatMainRef.value
    if (el) el.scrollTop = el.scrollHeight
    showJumpBottom.value = false
  })
}
const onScroll = () => { showJumpBottom.value = !isAtBottom() }

const isCompact = (i) => {
  if (i===0) return false
  const a = messages.value[i]
  const b = messages.value[i-1]
  return a && b && a.key === b.key && a.level === b.level
}

const hasMoreOlder = ref(false)
const noMoreOlder = ref(false)
const loadingOlder = ref(false)

const loadHistory = async () => {
  if (!activeGroup.value) return
  const { data } = await apiClient.get('/api/tools/chat/history', { params: { group_id: activeGroup.value.id, limit: 200, offset: 0 } })
  messages.value = (data || []).map(toUIMsg)
  // 初次判断是否还有更多：若正好 200 条，可能还有更多
  hasMoreOlder.value = (Array.isArray(data) && data.length === 200)
  noMoreOlder.value = !hasMoreOlder.value
  scrollToBottom()
}

const loadMoreHistory = async () => {
  if (!activeGroup.value) return
  loadingOlder.value = true
  try {
    const el = chatMainRef.value
    const prevHeight = el ? el.scrollHeight : 0
    const offset = messages.value.length
    const { data } = await apiClient.get('/api/tools/chat/history', { params: { group_id: activeGroup.value.id, limit: 200, offset } })
    const arr = (data || []).map(toUIMsg)
    if (arr.length > 0) {
      messages.value = [...arr, ...messages.value]
      await nextTick()
      if (el) {
        const newHeight = el.scrollHeight
        el.scrollTop = newHeight - prevHeight + el.scrollTop
      }
    }
    if (!Array.isArray(data) || data.length < 200) {
      hasMoreOlder.value = false
      noMoreOlder.value = true
    }
  } catch (e) {
    // 失败时不改变按钮状态
  } finally {
    loadingOlder.value = false
  }
}

const onChatMessage = (msg) => {
  // ALERT 全部显示；NORMAL 仅当前组
  if (!activeGroup.value) return
  if (msg.level === 'ALERT' || msg.group_id === activeGroup.value.id) {
    messages.value.push(toUIMsg(msg))
    if (isAtBottom()) scrollToBottom()
    // 新消息到达不改变“更多历史”按钮状态
  }
}

const doSend = async () => {
  if (!activeGroup.value || !draft.value.trim()) return
  try {
    await apiClient.post('/api/tools/chat/send', { group_id: activeGroup.value.id, message: draft.value, level: 'NORMAL' })
    draft.value = ''
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '发送失败')
  }
}

const onEnter = (e) => {
  if (e.shiftKey) return
  doSend()
}

const sendAlert = async () => {
  try {
    const { value } = await ElMessageBox.prompt('请输入要发送的 ALERT 文本', 'ALERT', { inputPlaceholder: '消息内容' })
    if (value && value.trim()) {
      await apiClient.post('/api/tools/chat/send', { message: value, level: 'ALERT' })
      ElMessage.success('ALERT 已发送')
    }
  } catch (e) {}
}

const onPresence = (payload) => {
  if (!activeGroup.value || payload.group_id !== activeGroup.value.id) return
  // 聚合为 UI 用户列表
  webUsers.value = (payload.web_users || []).map(u => ({...u, avatar_url: resolveAvatar(u.avatar_url)}))
  const playerUsers = (payload.players || []).map(p => ({ username: `${p.player}@${p.server}`, avatar_url: mcAvatar(p.player) }))
  users.value = [...webUsers.value, ...playerUsers]
}

// 尽早注册实时事件监听，避免在 onMounted 之前到达的消息被丢弃
socket.on('chat_message', onChatMessage)
socket.on('chat_presence', onPresence)

onMounted(async () => {
  await loadMe()
  await Promise.all([loadGroups(), loadServers()])
})

onUnmounted(() => {
  if (joinedGroupId.value) {
    socket.emit('leave_chat_group', { group_id: joinedGroupId.value })
    joinedGroupId.value = null
  }
  socket.off('chat_message', onChatMessage)
  socket.off('chat_presence', onPresence)
})

// helpers
const resolveAvatar = (url) => {
  if (!url) return null
  if (url.startsWith('http://') || url.startsWith('https://')) return url
  const path = url.startsWith('/') ? url : `/${url}`
  return `${BASE_URL}${path}`
}

const mcAvatar = (name) => {
  if (!name) return defaultAvatar;
  try { return `https://mc-heads.net/avatar/${encodeURIComponent(name)}` } catch { return `https://mc-heads.net/avatar/${name}` }
}
const pad = (n) => String(n).padStart(2, '0')
const formatTime = (dt) => {
  try {
    const d = new Date(dt)
    const Y = d.getFullYear(), M = pad(d.getMonth()+1), D = pad(d.getDate())
    const h = pad(d.getHours()), m = pad(d.getMinutes()), s = pad(d.getSeconds())
    return `${Y}-${M}-${D} ${h}:${m}:${s}`
  } catch { return '' }
}
</script>

<style scoped>
.sl-page { height: 100%; overflow: hidden; }
.left-wrap { display: flex; gap: 16px; align-items: stretch; height: 100%; overflow: hidden; min-height: 0; }
.left-panel { width: 320px; flex-shrink: 0; align-self: flex-start; }
.left-panel { overflow-x: hidden; min-width: 0; box-sizing: border-box; }
.left-panel :deep(.el-card) { display: block; }
.left-panel :deep(.el-card__body) { padding: 8px; }
.left-panel :deep(.el-input), .left-panel :deep(.el-input__wrapper) { width: 100%; }
.left-panel :deep(.el-table) { width: 100%; }
.left-panel :deep(.el-table__inner-wrapper) { width: 100%; }
.right-panel { flex: 1 1 auto; min-height: 0; overflow: hidden; display: flex; flex-direction: column; }
.right-panel :deep(.el-descriptions) { border-radius: 8px; overflow: hidden; }
/* 让右侧唯一卡片填满高度，且去除外边距 */
.right-panel > :deep(.el-card) { flex: 1 1 auto; height: 100%; }
.right-panel > :deep(.el-card.mb-3) { margin-bottom: 0 !important; }
.mb-2 { margin-bottom: 8px; }
.mb-3 { margin-bottom: 12px; }
.flex { display: flex; }
.items-center { align-items: center; }
.justify-between { justify-content: space-between; }
.gap-2 { gap: 8px; }
.text-base { font-size: 14px; }
.font-medium { font-weight: 600; }
.muted { color: #909399; font-size: 12px; }
.server-cell .name { line-height: 18px; }

.chat-wrapper { display: grid; grid-template-columns: 1fr 240px; gap: 12px; align-items: start; flex: 1 1 auto; min-height: 0; }
.chat-left { display: flex; flex-direction: column; min-height: 0; height: 100%; }
.chat-main { position: relative; background: transparent; padding: 6px 4px; overflow: auto; flex: 0 1 auto; margin-top: auto; max-height: 100%; }
/* 自定义滚动条：白灰色，默认隐藏，hover 显示 */
.chat-main { scrollbar-width: thin; scrollbar-color: rgba(200,200,200,.6) transparent; }
.chat-main::-webkit-scrollbar { width: 0; height: 0; }
.chat-main:hover::-webkit-scrollbar { width: 8px; height: 8px; }
.chat-main::-webkit-scrollbar-thumb { background: rgba(200,200,200,.7); border-radius: 4px; }
.chat-main::-webkit-scrollbar-track { background: transparent; }
.load-older { display: flex; justify-content: center; align-items: center; padding: 6px 0; color: var(--el-text-color-secondary); }
.no-more { font-size: 12px; color: var(--el-text-color-secondary); }
.jump-bottom { position: sticky; bottom: 8px; left: calc(100% - 48px); }

/* 按钮样式：白底蓝字、白字主色 */
.btn-plain-primary { /* Element Plus plain primary 即白底蓝字，这里仅确保边距与圆角 */ }
.btn-load-older { color: #fff !important; background-color: var(--el-color-primary) !important; border-color: var(--el-color-primary) !important; }
/* 发送按钮（外置）确保蓝字白底，避免主题覆盖为黑色 */
.btn-send {
  --el-button-text-color: var(--el-color-primary);
  --el-button-bg-color: #fff;
  --el-button-border-color: var(--el-color-primary);
  color: var(--el-color-primary) !important;
  background-color: #fff !important;
  border-color: var(--el-color-primary) !important;
  border-radius: 18px;
  padding: 6px 12px;
}
.btn-send :deep(.el-button__content) { color: var(--el-color-primary) !important; }
.btn-send :deep(.el-icon) { margin-right: 4px; color: var(--el-color-primary) !important; }
.msg-row { display: flex; align-items: flex-start; gap: 8px; margin-bottom: 2px; }
.msg-row.is-alert { margin-bottom: 8px; }
.avatar-col { width: 36px; flex-shrink: 0; }
.avatar { width: 36px; height: 36px; border-radius: 50%; background: #bbb; flex-shrink: 0; }
.bubble { max-width: 100%; }
.meta { font-size: 12px; color: var(--el-text-color-secondary); display: flex; align-items: center; gap: 8px; }
.name { font-weight: 600; }
.content { white-space: pre-wrap; word-break: break-word; padding: 1px 0; font-size: 13px; line-height: 1.35; }
.content.alert { color: #b71c1c; font-weight: 700; background: #ffe6e6; border: 1px solid #ffb3b3; border-radius: 6px; padding: 6px 8px; display: inline-block; }
.chat-side { border: 1px solid var(--el-border-color); border-radius: 8px; padding: 8px; background: var(--el-fill-color-blank); }
.side-title { font-weight: 600; margin-bottom: 8px; }
.side-item { display: flex; align-items: center; gap: 8px; padding: 4px 0; }
.avatar-small { width: 20px; height: 20px; border-radius: 50%; background: #bbb; }
.chat-input { display: flex; gap: 8px; align-items: center; padding: 8px 0; border-top: 1px solid var(--el-border-color); padding-top: 8px; }
/* 确保输入框占满可用宽度，append 内按钮不与输入内容重叠 */
.chat-input :deep(.el-input) { flex: 1 1 auto; width: 100%; }
.chat-input :deep(.el-input__wrapper) { width: 100%; }
/* 输入组按钮内部对齐 */
.chat-input :deep(.el-input-group__append) { padding: 0; }
.chat-input :deep(.el-input-group__append .el-button) { height: 32px; }
.active-row > td { background: var(--el-color-primary-light-9) !important; }

/* 空状态下让卡片主体也占满高度并居中提示 */
.main-placeholder { display: flex; align-items: center; justify-content: center; height: 100%; }
.placeholder-full { flex: 1 1 auto; min-height: 0; display: flex; align-items: center; justify-content: center; }

/* 左侧面板跟随主布局折叠动画 */
.left-panel { transition: width 0.32s cubic-bezier(.34,1.56,.64,1); will-change: width; overflow: hidden; }
.is-collapsed .left-panel, .is-collapsing .left-panel { width: 0 !important; }
.is-collapsing .left-panel :deep(.el-card__body), .is-collapsing .left-panel :deep(.el-card__header) { display: none !important; }

/* 让右侧卡片和内容正确分配高度，配合 chat-main 的滚动 */
.right-panel :deep(.el-card) { display: flex; flex-direction: column; min-height: 0; }
.right-panel :deep(.el-card__body) { flex: 1 1 auto; display: flex; flex-direction: column; min-height: 0; }

</style>
