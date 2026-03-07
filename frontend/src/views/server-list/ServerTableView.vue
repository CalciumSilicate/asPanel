<template>
  <div
    v-loading="loading"
    element-loading-background="transparent"
    class="table-container"
  >
    <table class="srv-table">
      <colgroup>
        <col style="width:46px" />
        <col style="min-width:180px" />
        <col style="width:110px" />
        <col style="width:100px" />
        <col style="width:180px" />
        <col style="width:90px" />
        <col style="width:140px" />
        <col style="width:130px" />
        <col v-if="hasAdmin" style="width:90px" />
        <col v-if="hasUser" style="width:280px" />
      </colgroup>

      <!-- ── Header ─────────────────────────────────────── -->
      <thead>
        <tr class="thead-row">
          <th class="th-cell th-check">
            <el-checkbox
              :indeterminate="isIndeterminate"
              :model-value="isAllSelected"
              @change="toggleAll"
            />
          </th>
          <th class="th-cell th-sortable" @click="sortBy('name')">
            <span class="th-inner">
              <span class="th-label">服务器名称</span>
              <span class="sort-caret" :class="sortClass('name')">▾</span>
            </span>
          </th>
          <th class="th-cell th-center th-sortable" @click="sortBy('status')">
            <span class="th-inner">
              <span class="th-label">状态</span>
              <span class="sort-caret" :class="sortClass('status')">▾</span>
            </span>
          </th>
          <th class="th-cell th-center th-sortable" @click="sortBy('type')">
            <span class="th-inner">
              <span class="th-label">类型</span>
              <span class="sort-caret" :class="sortClass('type')">▾</span>
            </span>
          </th>
          <th class="th-cell th-center th-sortable" @click="sortBy('version')">
            <span class="th-inner">
              <span class="th-label">版本</span>
              <span class="sort-caret" :class="sortClass('version')">▾</span>
            </span>
          </th>
          <th class="th-cell th-center th-sortable" @click="sortBy('port')">
            <span class="th-inner">
              <span class="th-label">端口</span>
              <span class="sort-caret" :class="sortClass('port')">▾</span>
            </span>
          </th>
          <th class="th-cell th-center th-sortable" @click="sortBy('size_mb')">
            <span class="th-inner">
              <span class="th-label">占用空间</span>
              <span class="sort-caret" :class="sortClass('size_mb')">▾</span>
            </span>
          </th>
          <th class="th-cell th-center th-sortable" @click="sortBy('last_startup')">
            <span class="th-inner">
              <span class="th-label">上次启动</span>
              <span class="sort-caret" :class="sortClass('last_startup')">▾</span>
            </span>
          </th>
          <th v-if="hasAdmin" class="th-cell th-center">
            <span class="th-label">自启动</span>
          </th>
          <th v-if="hasUser" class="th-cell th-right">
            <span class="th-label">操作</span>
          </th>
        </tr>
      </thead>

      <!-- ── Body ───────────────────────────────────────── -->
      <tbody>
        <!-- Empty state -->
        <tr v-if="!loading && sortedRows.length === 0">
          <td :colspan="colCount" class="td-empty">
            <el-empty description="暂无服务器" :image-size="80" />
          </td>
        </tr>

        <tr
          v-for="(row, index) in sortedRows"
          :key="row.id"
          :style="{ '--i': Math.min(index, 10) }"
          :class="[
            'srv-row',
            { 'row-running': row.status === 'running', 'row-selected': selectedIds.has(row.id) },
          ]"
        >
          <!-- Checkbox -->
          <td class="td-cell td-check">
            <el-checkbox :model-value="selectedIds.has(row.id)" @change="() => toggleRow(row)" />
          </td>

          <!-- Name -->
          <td class="td-cell td-name">
            <el-tooltip
              effect="dark"
              :content="row.path"
              placement="top-start"
              :show-after="500"
              :persistent="false"
            >
              <span class="server-name" @click="$emit('copy-path', row.path)">
                <span class="name-dot" :class="'dot-' + getTypeKey(row)" />
                {{ row.name }}
              </span>
            </el-tooltip>
          </td>

          <!-- Status -->
          <td class="td-cell td-center">
            <span :class="['status-pill', 'sp-' + row.status]">
              <span v-if="row.status === 'running' || row.status === 'pending'" class="pulse-dot" />
              <span v-else class="static-dot" />
              {{ getStatusTagText(row) }}
            </span>
          </td>

          <!-- Type -->
          <td class="td-cell td-center">
            <span :class="['type-chip', 'tc-' + getTypeKey(row)]">
              {{ row.core_config?.is_fabric ? 'Fabric' : capitalize(row.core_config?.server_type || '—') }}
            </span>
          </td>

          <!-- Version -->
          <td class="td-cell td-center">
            <span class="mono-cell">{{ row.core_config?.core_version || '—' }}</span>
          </td>

          <!-- Port -->
          <td class="td-cell td-center">
            <span v-if="row.port" class="port-cell">{{ row.port }}</span>
            <span v-else class="muted">—</span>
          </td>

          <!-- Size -->
          <td class="td-cell td-center">
            <span v-if="row.size_calc_state === 'ok' && row.size_mb != null" class="mono-cell">
              {{ formatServerSize(row.size_mb) }}
            </span>
            <span v-else-if="row.size_calc_state === 'failed'" class="muted">计算失败</span>
            <span v-else class="size-calculating">
              <el-icon class="spin-icon"><Loading /></el-icon>计算中
            </span>
          </td>

          <!-- Last startup -->
          <td class="td-cell td-center">
            <span v-if="row.last_startup" class="time-cell">{{ formatRelativeTime(row.last_startup) }}</span>
            <span v-else class="muted">从未启动</span>
          </td>

          <!-- Auto start -->
          <td v-if="hasAdmin" class="td-cell td-center">
            <el-tooltip effect="dark" content="ASPanel 启动时自动启动该服务器" placement="top" :show-after="400">
              <div class="autostart-pill" :class="{ 'autostart-on': row.core_config.auto_start }">
                <el-icon :size="10"><Timer /></el-icon>
                <el-switch
                  v-model="row.core_config.auto_start"
                  size="small"
                  :disabled="!!autoStartSaving[row.id]"
                  @change="(v: boolean) => $emit('auto-start', row, v)"
                />
              </div>
            </el-tooltip>
          </td>

          <!-- Actions -->
          <td v-if="hasUser" class="td-cell td-right">
            <div class="row-actions">
              <div class="action-group">
                <el-tooltip v-if="hasUser" content="启动" placement="top" :show-after="400">
                  <button
                    class="act-btn act-start"
                    :disabled="
                      row.status === 'running' ||
                      row.status === 'pending' ||
                      row.status === 'new_setup' ||
                      !!row.loading
                    "
                    @click="$emit('start', row)"
                  >
                    <el-icon :size="13"><VideoPlay /></el-icon>
                  </button>
                </el-tooltip>
                <el-tooltip v-if="hasAdmin" content="停止" placement="top" :show-after="400">
                  <button
                    class="act-btn act-stop"
                    :disabled="row.status !== 'running' || !!row.loading"
                    @click="$emit('stop', row)"
                  >
                    <el-icon :size="13"><SwitchButton /></el-icon>
                  </button>
                </el-tooltip>
                <el-tooltip v-if="hasUser" content="重启" placement="top" :show-after="400">
                  <button
                    class="act-btn act-restart"
                    :disabled="row.status !== 'running' || !!row.loading"
                    @click="$emit('restart', row)"
                  >
                    <el-icon :size="13"><Refresh /></el-icon>
                  </button>
                </el-tooltip>
              </div>

              <div class="act-sep" />

              <el-tooltip v-if="hasAdmin" content="配置" placement="top" :show-after="400">
                <button class="act-btn act-config" @click="$emit('config', row)">
                  <el-icon :size="13"><Setting /></el-icon>
                </button>
              </el-tooltip>

              <el-dropdown v-if="hasHelper" trigger="click" placement="bottom-end">
                <button class="act-btn act-more">
                  <el-icon :size="13"><MoreFilled /></el-icon>
                </button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item
                      v-if="hasAdmin"
                      :icon="MonitorIcon"
                      :disabled="row.status === 'new_setup'"
                      @click="$emit('console', row.id)"
                    >控制台</el-dropdown-item>
                    <el-dropdown-item
                      v-if="hasHelper"
                      :icon="FolderAdd"
                      :disabled="row.core_config?.server_type === 'velocity'"
                      @click="$emit('archive', row)"
                    >永久备份</el-dropdown-item>
                    <el-dropdown-item
                      v-if="hasAdmin"
                      :icon="DocumentCopy"
                      :disabled="row.status === 'running'"
                      @click="$emit('copy', row)"
                    >复制服务器</el-dropdown-item>
                    <el-dropdown-item v-if="hasAdmin" :icon="Edit" @click="$emit('rename', row)">重命名</el-dropdown-item>
                    <el-dropdown-item v-if="hasAdmin" divided :icon="CircleClose" @click="$emit('force-kill', row)">强制关闭</el-dropdown-item>
                    <el-dropdown-item v-if="hasAdmin" :icon="Delete" @click="$emit('delete', row)">删除</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>

              <transition name="fade">
                <span v-if="row.loading" class="row-loading">
                  <el-icon class="spin-icon"><Loading /></el-icon>
                </span>
              </transition>
            </div>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import {
  VideoPlay, SwitchButton, Refresh, Setting, MoreFilled, Loading, Timer,
  Monitor as MonitorIcon, FolderAdd, DocumentCopy, Edit, CircleClose, Delete,
} from '@element-plus/icons-vue'
import { getStatusTagText, formatServerSize, formatRelativeTime } from '@/composables/useServerList'
import type { Server } from '@/composables/useServerList'

// ── Props / emits ──────────────────────────────────────────────
const props = defineProps<{
  servers: Server[]
  loading: boolean
  autoStartSaving: Record<number, boolean>
  hasAdmin: boolean
  hasHelper: boolean
  hasUser: boolean
}>()

const emit = defineEmits<{
  'selection-change': [Server[]]
  start: [Server]
  stop: [Server]
  restart: [Server]
  config: [Server]
  console: [number]
  archive: [Server]
  copy: [Server]
  rename: [Server]
  'force-kill': [Server]
  delete: [Server]
  'auto-start': [Server, boolean]
  'copy-path': [string]
}>()

// ── Helpers ────────────────────────────────────────────────────
const getTypeKey = (row: Server): string => {
  if (row.core_config?.is_fabric) return 'fabric'
  const t = row.core_config?.server_type
  if (!t || t === 'new_setup') return 'unknown'
  return t
}

const capitalize = (s: string) =>
  s ? s.charAt(0).toUpperCase() + s.slice(1) : s

// ── Sort ───────────────────────────────────────────────────────
const sortKey = ref<string>('last_startup')
const sortDir = ref<'asc' | 'desc'>('desc')

const sortBy = (key: string) => {
  if (sortKey.value === key) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortKey.value = key
    // Numbers and dates default to descending; strings to ascending
    sortDir.value = (key === 'last_startup' || key === 'size_mb' || key === 'port') ? 'desc' : 'asc'
  }
}

const sortClass = (key: string) => ({
  'sort-active': sortKey.value === key,
  'sort-asc': sortKey.value === key && sortDir.value === 'asc',
})

const getSortValue = (row: Server, key: string): number | string => {
  switch (key) {
    case 'name':         return row.name.toLowerCase()
    case 'status':       return row.status
    case 'type':         return getTypeKey(row)
    case 'version':      return row.core_config?.core_version || ''
    case 'port':         return row.port ?? 0
    case 'size_mb':      return row.size_mb ?? -1
    case 'last_startup': return row.last_startup ? new Date(row.last_startup).getTime() : 0
    default:             return ''
  }
}

const sortedRows = computed(() => {
  const key = sortKey.value
  const dir = sortDir.value
  return [...props.servers].sort((a, b) => {
    const va = getSortValue(a, key)
    const vb = getSortValue(b, key)
    let cmp = 0
    if (va < vb) cmp = -1
    else if (va > vb) cmp = 1
    return dir === 'asc' ? cmp : -cmp
  })
})

// ── Selection ──────────────────────────────────────────────────
const selectedIds = ref(new Set<number>())

const isAllSelected = computed(
  () => sortedRows.value.length > 0 && sortedRows.value.every((r) => selectedIds.value.has(r.id)),
)
const isIndeterminate = computed(
  () => !isAllSelected.value && sortedRows.value.some((r) => selectedIds.value.has(r.id)),
)

const emitSelection = () => {
  emit('selection-change', props.servers.filter((s) => selectedIds.value.has(s.id)))
}

const toggleRow = (row: Server) => {
  const s = new Set(selectedIds.value)
  if (s.has(row.id)) s.delete(row.id)
  else s.add(row.id)
  selectedIds.value = s
  emitSelection()
}

const toggleAll = (checked: boolean | string | number) => {
  selectedIds.value = checked
    ? new Set(sortedRows.value.map((r) => r.id))
    : new Set<number>()
  emitSelection()
}

// ── Column count (for empty-state colspan) ─────────────────────
const colCount = computed(() => 8 + (props.hasAdmin ? 1 : 0) + (props.hasUser ? 1 : 0))

// ── Public API (compatible with composable tableRef usage) ─────
const clearSelection = () => {
  selectedIds.value = new Set()
  emitSelection()
}
const toggleRowSelection = (row: Server, selected: boolean) => {
  const s = new Set(selectedIds.value)
  if (selected) s.add(row.id)
  else s.delete(row.id)
  selectedIds.value = s
  // Don't emit here — composable restores selections silently
}

defineExpose({
  tableEl: { clearSelection, toggleRowSelection },
})
</script>

<style scoped>
/* ── Container ─────────────────────────────────────────────────── */
.table-container {
  width: 100%;
  height: 100%;
  overflow-x: auto;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: rgba(119, 181, 254, 0.22) transparent;
}
.table-container::-webkit-scrollbar { width: 5px; height: 5px; }
.table-container::-webkit-scrollbar-thumb { background: rgba(119, 181, 254, 0.28); border-radius: 3px; }

/* ── Table skeleton ───────────────────────────────────────────── */
.srv-table {
  width: 100%;
  min-width: 980px;
  border-collapse: collapse;
  table-layout: fixed;
}

/* ── Sticky header ────────────────────────────────────────────── */
thead {
  position: sticky;
  top: 0;
  z-index: 10;
}
.thead-row {
  background: rgba(248, 250, 255, 0.95);
  -webkit-backdrop-filter: saturate(140%) blur(8px);
  backdrop-filter: saturate(140%) blur(8px);
  border-bottom: 1px solid rgba(119, 181, 254, 0.12);
}
:global(.dark) .thead-row {
  background: rgba(11, 17, 32, 0.95);
}

/* ── Header cells ─────────────────────────────────────────────── */
.th-cell {
  padding: 10px 12px;
  text-align: left;
  white-space: nowrap;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--el-text-color-secondary);
  opacity: 0.72;
}
.th-center { text-align: center; }
.th-right  { text-align: right; padding-right: 16px; }
.th-check  { width: 46px; }

.th-sortable {
  cursor: pointer;
  user-select: none;
  transition: color 0.15s ease, opacity 0.15s ease;
}
.th-sortable:hover { opacity: 1; color: var(--brand-primary); }

.th-inner {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.sort-caret {
  font-size: 10px;
  opacity: 0;
  display: inline-block;
  transition: opacity 0.15s ease, transform 0.15s ease;
}
.th-sortable:hover .sort-caret { opacity: 0.35; }
.sort-caret.sort-active { opacity: 1; color: var(--brand-primary); }
.sort-caret.sort-asc { transform: rotate(180deg); }

/* ── Body rows ────────────────────────────────────────────────── */
.srv-row {
  transition: background 0.12s ease;
  border-bottom: 1px solid rgba(119, 181, 254, 0.07);
  animation: row-rise 0.45s cubic-bezier(0.34, 1.56, 0.64, 1) both;
  animation-delay: calc(var(--i, 0) * 30ms);
}
@keyframes row-rise {
  from { opacity: 0; transform: translateY(10px); }
  to   { opacity: 1; transform: translateY(0); }
}
.srv-row:last-child { border-bottom: none; }
.srv-row:hover { background: rgba(119, 181, 254, 0.05); }
.srv-row.row-running {
  background: rgba(52, 211, 153, 0.04);
  box-shadow: inset 3px 0 0 rgba(52, 211, 153, 0.45);
}
.srv-row.row-running:hover { background: rgba(52, 211, 153, 0.08); }
.srv-row.row-selected { background: rgba(119, 181, 254, 0.07); }
.srv-row.row-selected:hover { background: rgba(119, 181, 254, 0.10); }

/* ── Body cells ───────────────────────────────────────────────── */
.td-cell {
  padding: 13px 12px;
  vertical-align: middle;
}
.td-center { text-align: center; }
.td-right  { text-align: right; padding-right: 16px; }
.td-check  { width: 46px; }
.td-empty  { text-align: center; padding: 48px 0; }

/* ── Server name ──────────────────────────────────────────────── */
.server-name {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  font-size: 14px;
  font-weight: 700;
  color: var(--color-text);
  cursor: pointer;
  transition: color 0.15s ease;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}
.server-name:hover { color: var(--brand-primary); }

/* Type-keyed dot */
.name-dot {
  display: inline-block;
  width: 7px; height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
  opacity: 0.85;
}
.dot-vanilla, .dot-beta18  { background: #36a3f7; box-shadow: 0 0 4px rgba(54,163,247,0.55); }
.dot-fabric                { background: #40c9c6; box-shadow: 0 0 4px rgba(64,201,198,0.55); }
.dot-forge                 { background: #f59e0b; box-shadow: 0 0 4px rgba(245,158,11,0.55); }
.dot-velocity              { background: #9575cd; box-shadow: 0 0 4px rgba(149,117,205,0.55); }
.dot-unknown               { background: #94a3b8; }

/* ── Status pill ──────────────────────────────────────────────── */
.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
  background: rgba(148, 163, 184, 0.10);
  border: 1px solid rgba(148, 163, 184, 0.20);
  color: var(--el-text-color-secondary);
}
.sp-running  { background: rgba(52,211,153,0.12); border-color: rgba(52,211,153,0.28); color: #10b981; }
.sp-pending  { background: rgba(119,181,254,0.12); border-color: rgba(119,181,254,0.28); color: var(--brand-primary); }
.sp-new_setup{ background: rgba(119,181,254,0.08); border-color: rgba(119,181,254,0.18); color: var(--brand-primary); }
:global(.dark) .sp-running  { color: #34d399; }
:global(.dark) .sp-pending,
:global(.dark) .sp-new_setup { color: var(--brand-primary); }

.pulse-dot {
  display: inline-block;
  width: 5px; height: 5px;
  border-radius: 50%;
  background: currentColor;
  box-shadow: 0 0 4px currentColor;
  animation: pulse 2.2s ease-in-out infinite;
}
.static-dot {
  display: inline-block;
  width: 5px; height: 5px;
  border-radius: 50%;
  background: currentColor;
  opacity: 0.55;
}
@keyframes pulse {
  0%, 100% { opacity: 1; box-shadow: 0 0 3px currentColor; }
  50%       { opacity: 0.6; box-shadow: 0 0 7px currentColor, 0 0 14px currentColor; }
}

/* ── Type chip ────────────────────────────────────────────────── */
.type-chip {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.02em;
}
.tc-vanilla, .tc-beta18 { background: rgba(54,163,247,0.12);  color: #36a3f7;  border: 1px solid rgba(54,163,247,0.25); }
.tc-fabric              { background: rgba(64,201,198,0.12);  color: #40c9c6;  border: 1px solid rgba(64,201,198,0.25); }
.tc-forge               { background: rgba(245,158,11,0.12);  color: #f59e0b;  border: 1px solid rgba(245,158,11,0.25); }
.tc-velocity            { background: rgba(149,117,205,0.12); color: #9575cd;  border: 1px solid rgba(149,117,205,0.25); }
.tc-unknown             { background: rgba(148,163,184,0.10); color: var(--el-text-color-secondary); border: 1px solid rgba(148,163,184,0.18); }

/* ── Misc cells ───────────────────────────────────────────────── */
.mono-cell {
  font-family: 'Lexend', -apple-system, BlinkMacSystemFont, sans-serif;
  font-size: 13px;
  color: var(--el-text-color-regular);
}
.port-cell {
  font-family: 'JetBrains Mono', 'Fira Code', ui-monospace, monospace;
  font-size: 13px;
  font-weight: 600;
  color: var(--brand-primary);
  background: rgba(119, 181, 254, 0.08);
  border: 1px solid rgba(119, 181, 254, 0.18);
  border-radius: 6px;
  padding: 1px 7px;
}
.time-cell { font-size: 13px; color: var(--el-text-color-secondary); }
.muted     { font-size: 13px; color: var(--el-text-color-placeholder); }
.size-calculating {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  color: var(--el-text-color-placeholder);
}

/* ── Auto-start pill ──────────────────────────────────────────── */
.autostart-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 8px 3px 7px;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.22);
  background: rgba(148, 163, 184, 0.06);
  transition: border-color 0.2s ease, background 0.2s ease;
  cursor: default;
}
.autostart-pill .el-icon {
  color: var(--el-text-color-placeholder);
  transition: color 0.2s ease;
  flex-shrink: 0;
}
.autostart-on {
  border-color: rgba(52, 211, 153, 0.30);
  background: rgba(52, 211, 153, 0.08);
}
.autostart-on .el-icon { color: #10b981; }

/* ── Action row ───────────────────────────────────────────────── */
.row-actions {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  justify-content: flex-end;
}
.action-group {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  background: rgba(119, 181, 254, 0.05);
  border: 1px solid rgba(119, 181, 254, 0.12);
  border-radius: 10px;
  padding: 3px;
}
.act-sep {
  width: 1px; height: 18px;
  background: rgba(119, 181, 254, 0.14);
  flex-shrink: 0;
  margin: 0 2px;
}
.act-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px; height: 26px;
  border-radius: 7px;
  border: 1px solid transparent;
  background: transparent;
  cursor: pointer;
  color: var(--el-text-color-secondary);
  transition: background 0.14s ease, color 0.14s ease, border-color 0.14s ease, transform 0.14s ease;
  flex-shrink: 0;
}
.act-btn:not(:disabled):hover { transform: scale(1.12); }
.act-btn:disabled { opacity: 0.28; cursor: not-allowed; }
.act-start:not(:disabled):hover   { background: rgba(52,211,153,0.14);  color: #10b981; border-color: rgba(52,211,153,0.28); }
.act-stop:not(:disabled):hover    { background: rgba(248,113,113,0.14); color: #ef4444; border-color: rgba(248,113,113,0.28); }
.act-restart:not(:disabled):hover { background: rgba(245,158,11,0.14);  color: #f59e0b; border-color: rgba(245,158,11,0.28); }
.act-config:not(:disabled):hover  { background: rgba(119,181,254,0.14); color: var(--brand-primary); border-color: rgba(119,181,254,0.28); }
.act-more:not(:disabled):hover    { background: rgba(167,139,250,0.12); color: #a78bfa; border-color: rgba(167,139,250,0.28); }

.row-loading {
  display: inline-flex;
  align-items: center;
  color: var(--brand-primary);
  margin-left: 2px;
}

/* ── Animations ───────────────────────────────────────────────── */
.spin-icon { animation: spin 1.2s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.fade-enter-active, .fade-leave-active { transition: opacity 0.2s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
