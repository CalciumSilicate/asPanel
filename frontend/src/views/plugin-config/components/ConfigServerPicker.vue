<template>
  <div class="picker-wrap">

    <!-- Fixed top controls -->
    <div class="picker-top">
      <div class="picker-header">
        <div class="ph-icon"><el-icon :size="15"><Setting /></el-icon></div>
        <span class="ph-title">{{ pluginTitle }}</span>
        <span class="ph-total">{{ installedCount }} / {{ allowedCount }} 已安装</span>
      </div>

      <el-input
        v-model="searchQuery"
        placeholder="搜索服务器名称…"
        clearable
        size="small"
        class="search-input"
      >
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
    </div>

    <!-- Scrollable list -->
    <div class="list-wrap" v-loading="loading" element-loading-background="transparent">
      <el-empty
        v-if="!loading && filteredServers.length === 0"
        description="暂无匹配服务器"
        :image-size="56"
      />

      <button
        v-for="s in filteredServers"
        :key="s.id"
        class="srv-row"
        :class="{
          'is-active': activeServerId === s.id,
          'is-muted': !isAllowed(s),
        }"
        @click="handleRowClick(s)"
      >
        <div class="srv-avatar" :style="{ background: avatarColor(s.id) }">
          {{ (s.name || '?')[0].toUpperCase() }}
        </div>
        <span class="srv-name">{{ s.name }}</span>
        <div class="srv-status" @click.stop>
          <span v-if="!isAllowed(s)" class="status-chip chip-unsupported">
            <el-icon :size="10"><Remove /></el-icon>不支持
          </span>
          <template v-else>
            <span v-if="installedMap.get(s.id)" class="status-chip chip-installed">
              <el-icon :size="10"><Check /></el-icon>已安装
            </span>
            <button
              v-else
              class="install-btn"
              :disabled="installingServerId === s.id"
              @click="$emit('install', s)"
            >
              <el-icon v-if="installingServerId !== s.id" :size="10"><Download /></el-icon>
              <el-icon v-else :size="10" class="spin"><Loading /></el-icon>
              安装
            </button>
          </template>
        </div>
      </button>
    </div>

  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { Search, Setting, Check, Remove, Download, Loading } from '@element-plus/icons-vue'

const props = defineProps<{
  pluginTitle: string
  servers: any[]
  loading: boolean
  installedMap: Map<number, boolean>
  isAllowed: (s: any) => boolean
  installingServerId: number | null
  activeServerId: number | null
}>()

const emit = defineEmits<{
  select: [s: any]
  install: [s: any]
}>()

const searchQuery = ref('')

const filteredServers = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  return q
    ? props.servers.filter(s => s.name?.toLowerCase().includes(q) || String(s.id).includes(q))
    : props.servers
})

const allowedCount = computed(() => props.servers.filter(s => props.isAllowed(s)).length)
const installedCount = computed(() => props.servers.filter(s => props.isAllowed(s) && props.installedMap.get(s.id)).length)

const handleRowClick = (s: any) => {
  if (!props.isAllowed(s) || !props.installedMap.get(s.id)) return
  emit('select', s)
}

const COLORS = ['#77B5FE', '#a78bfa', '#34d399', '#fb923c', '#f472b6', '#60a5fa', '#facc15', '#4ade80']
const avatarColor = (id: number) => COLORS[id % COLORS.length]
</script>

<style scoped>
/* ── Root ────────────────────────────────────────────────── */
.picker-wrap {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

/* ── Fixed top section ───────────────────────────────────── */
.picker-top {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 20px 20px 12px;
  border-bottom: 1px solid rgba(119, 181, 254, 0.12);
}

.picker-header {
  display: flex;
  align-items: center;
  gap: 8px;
}
.ph-icon {
  width: 28px; height: 28px;
  border-radius: 8px;
  background: linear-gradient(135deg, var(--brand-primary) 0%, #a78bfa 100%);
  display: flex; align-items: center; justify-content: center;
  color: #fff;
  flex-shrink: 0;
}
.ph-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--color-text);
  flex: 1 1 auto;
}
.ph-total {
  font-size: 11px;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
}

/* Search */
.search-input :deep(.el-input__wrapper) {
  border-radius: 10px !important;
  background: rgba(255, 255, 255, 0.55) !important;
  border: 1px solid rgba(119, 181, 254, 0.20) !important;
  box-shadow: none !important;
  transition: border-color 0.18s ease, background 0.18s ease !important;
}
.search-input :deep(.el-input__wrapper:hover) { border-color: rgba(119, 181, 254, 0.40) !important; }
.search-input :deep(.el-input__wrapper.is-focus) {
  border-color: rgba(119, 181, 254, 0.60) !important;
  box-shadow: 0 0 0 3px rgba(119, 181, 254, 0.10) !important;
  background: rgba(255, 255, 255, 0.88) !important;
}
:global(.dark) .search-input :deep(.el-input__wrapper) {
  background: rgba(15, 23, 42, 0.55) !important;
  border-color: rgba(119, 181, 254, 0.18) !important;
}

/* ── Scrollable list ─────────────────────────────────────── */
.list-wrap {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  scrollbar-width: thin;
  padding: 8px 12px 12px;
}

/* Server row */
.srv-row {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 7px 10px;
  border: none;
  border-radius: 10px;
  background: transparent;
  cursor: pointer;
  text-align: left;
  font-family: inherit;
  transition: background 0.15s ease, transform 0.15s ease;
}
.srv-row:not(.is-muted):not(.is-active):hover {
  background: rgba(119, 181, 254, 0.09);
  transform: translateX(2px);
}
.srv-row.is-active {
  background: rgba(119, 181, 254, 0.13);
  transform: translateX(2px);
}
.srv-row.is-muted {
  cursor: default;
  opacity: 0.6;
}
:global(.dark) .srv-row:not(.is-muted):not(.is-active):hover,
:global(.dark) .srv-row.is-active {
  background: rgba(119, 181, 254, 0.10);
}

.srv-avatar {
  width: 28px; height: 28px;
  border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  flex-shrink: 0;
}
.srv-name {
  flex: 1 1 auto;
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  text-align: left;
}
.srv-status {
  flex-shrink: 0;
}

/* ── Status chips ────────────────────────────────────────── */
.status-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 9px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  white-space: nowrap;
  line-height: 1;
  height: 22px;
}
.chip-unsupported {
  background: rgba(144, 147, 153, 0.10);
  color: var(--el-text-color-placeholder);
  border: 1px solid rgba(144, 147, 153, 0.22);
}
.chip-installed {
  background: rgba(52, 211, 153, 0.10);
  color: #10b981;
  border: 1px solid rgba(52, 211, 153, 0.28);
}

/* ── Install button ──────────────────────────────────────── */
.install-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 22px;
  padding: 0 10px;
  border-radius: 999px;
  border: none;
  cursor: pointer;
  font-size: 11px;
  font-weight: 600;
  font-family: inherit;
  color: #fff;
  background: linear-gradient(135deg, var(--brand-primary) 0%, #a78bfa 100%);
  box-shadow: 0 2px 8px rgba(119, 181, 254, 0.35);
  transition: box-shadow 0.2s ease, transform 0.2s cubic-bezier(.34, 1.56, .64, 1);
  white-space: nowrap;
}
.install-btn:not(:disabled):hover {
  box-shadow: 0 4px 14px rgba(119, 181, 254, 0.55);
  transform: translateY(-1px) scale(1.04);
}
.install-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* Loading spin animation */
.spin {
  animation: spin 0.8s linear infinite;
}
@keyframes spin {
  from { transform: rotate(0deg); }
  to   { transform: rotate(360deg); }
}
</style>
