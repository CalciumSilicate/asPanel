<template>
  <div class="picker-wrap">

    <!-- Fixed top controls -->
    <div class="picker-top">
      <div class="picker-header">
        <div class="ph-icon"><el-icon :size="15"><Box /></el-icon></div>
        <span class="ph-title">选择服务器</span>
        <span class="ph-total">{{ servers.length }} 台 · {{ totalModsCount }} 个模组</span>
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

      <div v-if="groups.length > 1" class="type-pills">
        <button
          :class="['type-pill', { active: activeType === '' }]"
          @click="activeType = ''"
        >全部<span class="pill-cnt">{{ filteredServers.length }}</span></button>
        <button
          v-for="g in groups"
          :key="g.type"
          :class="['type-pill', { active: activeType === g.type }]"
          @click="activeType = g.type"
        >{{ g.label }}<span class="pill-cnt">{{ g.servers.length }}</span></button>
      </div>
    </div>

    <!-- Scrollable list -->
    <div class="list-wrap" v-loading="loading" element-loading-background="transparent">
      <el-empty
        v-if="!loading && filteredServers.length === 0"
        description="暂无匹配服务器"
        :image-size="56"
      />

      <template v-for="g in displayedGroups" :key="g.type">
        <div v-if="activeType === '' && groups.length > 1" class="group-label">
          <span>{{ g.label }}</span>
        </div>
        <button
          v-for="s in g.servers"
          :key="s.id"
          class="srv-row"
          :class="{ 'is-unsupported': isUnsupported(s) }"
          :disabled="isUnsupported(s)"
          @click="isUnsupported(s) ? undefined : $emit('select', s)"
        >
          <div class="srv-avatar" :style="{ background: isUnsupported(s) ? '#9ca3af' : avatarColor(s.id) }">
            {{ (s.name || '?')[0].toUpperCase() }}
          </div>
          <span class="srv-name">{{ s.name }}</span>
          <el-tag v-if="isUnsupported(s)" size="small" type="info" effect="plain" class="unsupported-tag">不支持</el-tag>
          <template v-else-if="s.mods_count_state === 'ok'">
            <span class="srv-count">{{ s.mods_count ?? 0 }} 个</span>
          </template>
          <template v-else-if="s.mods_count_state === 'failed'">
            <span class="srv-error">失败</span>
          </template>
          <template v-else>
            <span class="srv-pending">…</span>
          </template>
          <el-icon class="srv-arrow" :size="12"><ArrowRight /></el-icon>
        </button>
      </template>
    </div>

  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { Box, Search, ArrowRight } from '@element-plus/icons-vue'

const props = defineProps<{
  servers: any[]
  loading: boolean
  totalModsCount: number | string
}>()

defineEmits<{ 'select': [any] }>()

const searchQuery = ref('')
const activeType = ref('')

const TYPE_LABELS: Record<string, string> = {
  velocity: 'Velocity', bungeecord: 'BungeeCord',
  fabric: 'Fabric', forge: 'Forge',
  paper: 'Paper', spigot: 'Spigot',
  vanilla: 'Vanilla', other: '其他',
}
const TYPE_ORDER = ['velocity', 'bungeecord', 'fabric', 'forge', 'paper', 'spigot', 'vanilla', 'other']

function getType(s: any): string {
  const cfg = s?.core_config || {}
  const t = (cfg.server_type || cfg.serverType || '').toLowerCase()
  if (t === 'velocity') return 'velocity'
  if (t === 'bungeecord') return 'bungeecord'
  if (t === 'forge') return 'forge'
  if (t === 'fabric' || (t === 'vanilla' && (cfg.is_fabric || cfg.isFabric))) return 'fabric'
  if (t === 'paper') return 'paper'
  if (t === 'spigot') return 'spigot'
  if (t === 'vanilla') return 'vanilla'
  return 'other'
}

const searched = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  return q ? props.servers.filter(s => s.name?.toLowerCase().includes(q)) : props.servers
})

const groups = computed(() => {
  const map = new Map<string, { type: string; label: string; servers: any[] }>()
  searched.value.forEach(s => {
    const t = getType(s)
    if (!map.has(t)) map.set(t, { type: t, label: TYPE_LABELS[t] ?? t, servers: [] })
    map.get(t)!.servers.push(s)
  })
  return TYPE_ORDER.filter(t => map.has(t)).map(t => map.get(t)!)
})

const filteredServers = computed(() =>
  activeType.value
    ? searched.value.filter(s => getType(s) === activeType.value)
    : searched.value
)

const displayedGroups = computed(() => {
  if (activeType.value) {
    const g = groups.value.find(g => g.type === activeType.value)
    return g ? [g] : []
  }
  return groups.value
})

const COLORS = ['#a78bfa','#77B5FE','#34d399','#fb923c','#f472b6','#60a5fa','#facc15','#4ade80']
const avatarColor = (id: number) => COLORS[id % COLORS.length]

function isUnsupported(s: any): boolean {
  return getType(s) === 'vanilla'
}
</script>

<style scoped>
/* ── Root: fill the placeholder container ────────────────── */
.picker-wrap {
  font-family: 'Lexend', -apple-system, sans-serif;
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
  border-bottom: 1px solid rgba(167, 139, 250, 0.12);
}

.picker-header {
  display: flex;
  align-items: center;
  gap: 8px;
}
.ph-icon {
  width: 28px; height: 28px;
  border-radius: 8px;
  background: linear-gradient(135deg, #a78bfa 0%, var(--brand-primary) 100%);
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
  border: 1px solid rgba(167, 139, 250, 0.20) !important;
  box-shadow: none !important;
  transition: border-color 0.18s ease, background 0.18s ease !important;
}
.search-input :deep(.el-input__wrapper:hover) { border-color: rgba(167, 139, 250, 0.40) !important; }
.search-input :deep(.el-input__wrapper.is-focus) {
  border-color: rgba(167, 139, 250, 0.60) !important;
  box-shadow: 0 0 0 3px rgba(167, 139, 250, 0.10) !important;
  background: rgba(255, 255, 255, 0.88) !important;
}
:global(.dark) .search-input :deep(.el-input__wrapper) {
  background: rgba(15, 23, 42, 0.55) !important;
  border-color: rgba(167, 139, 250, 0.18) !important;
}

/* Type filter pills */
.type-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
}
.type-pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 10px;
  border-radius: 999px;
  border: 1px solid rgba(167, 139, 250, 0.20);
  background: transparent;
  color: var(--el-text-color-secondary);
  font-size: 11px;
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
  transition: background 0.15s ease, border-color 0.15s ease, color 0.15s ease;
  white-space: nowrap;
}
.type-pill:not(.active):hover {
  background: rgba(167, 139, 250, 0.08);
  border-color: rgba(167, 139, 250, 0.35);
  color: #a78bfa;
}
.type-pill.active {
  background: linear-gradient(135deg, #a78bfa, var(--brand-primary));
  border-color: transparent;
  color: #fff;
}
.pill-cnt {
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  opacity: 0.85;
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

/* Group label */
.group-label {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 4px 4px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--el-text-color-secondary);
}
.group-label::after {
  content: '';
  flex: 1;
  height: 1px;
  background: rgba(167, 139, 250, 0.14);
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
.srv-row:hover {
  background: rgba(167, 139, 250, 0.09);
  transform: translateX(2px);
}
:global(.dark) .srv-row:hover {
  background: rgba(167, 139, 250, 0.10);
}
.srv-row.is-unsupported {
  opacity: 0.45;
  cursor: not-allowed;
}
.srv-row.is-unsupported:hover {
  background: transparent;
  transform: none;
}
.unsupported-tag { flex-shrink: 0; }

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
.srv-count {
  font-size: 11px;
  font-weight: 600;
  color: #a78bfa;
  font-variant-numeric: tabular-nums;
  flex-shrink: 0;
}
.srv-pending { font-size: 11px; color: var(--el-text-color-placeholder); flex-shrink: 0; }
.srv-error   { font-size: 11px; color: #ef4444; flex-shrink: 0; }

.srv-arrow {
  color: var(--el-text-color-placeholder);
  flex-shrink: 0;
  transition: transform 0.15s ease, color 0.15s ease;
}
.srv-row:hover .srv-arrow {
  color: #a78bfa;
  transform: translateX(2px);
}
</style>
