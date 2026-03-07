<template>
  <div class="card-scroll">
    <!-- Empty state -->
    <div v-if="servers.length === 0 && !loading" class="card-empty">
      <el-empty description="暂无服务器" />
    </div>

    <!-- Card grid -->
    <div v-else class="card-grid">
      <div
        v-for="(s, index) in servers"
        :key="s.id"
        class="server-card"
        :class="[getServerAccent(s), { 'is-running': s.status === 'running' }]"
        :style="{ '--i': Math.min(index, 8) }"
      >
        <div class="card-deco" aria-hidden="true" />

        <!-- Top row: icon + status badge -->
        <div class="card-top">
          <div class="card-icon-wrap">
            <el-icon :size="22"><Monitor /></el-icon>
          </div>
          <div :class="['status-badge', 'st-' + s.status]">
            <span v-if="s.status === 'running' || s.status === 'pending'" class="pulse-dot" />
            <span v-else class="static-dot" />
            {{ getStatusTagText(s) }}
          </div>
        </div>

        <!-- Name -->
        <el-tooltip
          effect="dark"
          :content="s.path || s.name"
          placement="top"
          :show-after="500"
          :persistent="false"
        >
          <div class="card-name" @click="copyPath(s.path)">{{ s.name }}</div>
        </el-tooltip>

        <!-- Meta row: type + version -->
        <div class="card-meta">
          <span class="meta-type">
            {{ s.core_config?.is_fabric ? 'fabric' : (s.core_config?.server_type || '—') }}
          </span>
          <span v-if="s.core_config?.core_version" class="meta-sep">·</span>
          <span v-if="s.core_config?.core_version" class="meta-version">{{ s.core_config.core_version }}</span>
        </div>

        <!-- Footer bar -->
        <div class="card-footer">
          <div class="footer-stats">
            <div v-if="s.port" class="stat-item">
              <el-icon :size="11"><Connection /></el-icon>
              <span>{{ s.port }}</span>
            </div>
            <div v-if="s.size_calc_state === 'ok' && s.size_mb != null" class="stat-item">
              <el-icon :size="11"><FolderOpened /></el-icon>
              <span>{{ formatServerSize(s.size_mb) }}</span>
            </div>
            <div v-if="s.last_startup" class="stat-item">
              <el-icon :size="11"><Clock /></el-icon>
              <span>{{ formatRelativeTime(s.last_startup) }}</span>
            </div>
          </div>

          <!-- Action row -->
          <div class="card-actions" @click.stop>
            <!-- Start / Stop / Restart -->
            <el-tooltip content="启动" placement="top" :show-after="400">
              <button
                class="act-btn act-start"
                :disabled="s.status === 'running' || s.status === 'pending' || s.status === 'new_setup' || s.loading"
                @click="$emit('start', s)"
              >
                <el-icon :size="13"><VideoPlay /></el-icon>
              </button>
            </el-tooltip>
            <el-tooltip v-if="hasAdmin" content="停止" placement="top" :show-after="400">
              <button
                class="act-btn act-stop"
                :disabled="s.status !== 'running' || s.loading"
                @click="$emit('stop', s)"
              >
                <el-icon :size="13"><SwitchButton /></el-icon>
              </button>
            </el-tooltip>
            <el-tooltip content="重启" placement="top" :show-after="400">
              <button
                class="act-btn act-restart"
                :disabled="s.status !== 'running' || s.loading"
                @click="$emit('restart', s)"
              >
                <el-icon :size="13"><Refresh /></el-icon>
              </button>
            </el-tooltip>

            <div class="act-divider" />

            <!-- More dropdown -->
            <el-dropdown v-if="hasHelper" trigger="click" placement="bottom-end">
              <button class="act-btn act-more">
                <el-icon :size="13"><MoreFilled /></el-icon>
              </button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item v-if="hasAdmin" :icon="Setting" @click="$emit('config', s)">配置</el-dropdown-item>
                  <el-dropdown-item v-if="hasAdmin" :icon="Monitor" :disabled="s.status === 'new_setup'" @click="$emit('console', s.id)">控制台</el-dropdown-item>
                  <el-dropdown-item v-if="hasHelper" :icon="FolderAdd" :disabled="s.core_config?.server_type === 'velocity'" @click="$emit('archive', s)">永久备份</el-dropdown-item>
                  <el-dropdown-item v-if="hasAdmin" :icon="DocumentCopy" :disabled="s.status === 'running'" @click="$emit('copy', s)">复制服务器</el-dropdown-item>
                  <el-dropdown-item v-if="hasAdmin" :icon="Edit" @click="$emit('rename', s)">重命名</el-dropdown-item>
                  <el-dropdown-item v-if="hasAdmin" divided :icon="CircleClose" @click="$emit('force-kill', s)">强制关闭</el-dropdown-item>
                  <el-dropdown-item v-if="hasAdmin" :icon="Delete" @click="$emit('delete', s)">删除</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </div>

        <!-- Loading overlay -->
        <transition name="fade">
          <div v-if="s.loading" class="card-loading-overlay">
            <el-icon class="loading-spin" :size="24"><Loading /></el-icon>
          </div>
        </transition>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import {
  Monitor, VideoPlay, SwitchButton, Refresh, MoreFilled, Setting,
  FolderAdd, DocumentCopy, Edit, CircleClose, Delete,
  Connection, FolderOpened, Clock, Loading,
} from '@element-plus/icons-vue'
import { getStatusTagText, formatServerSize, formatRelativeTime } from '@/composables/useServerList'
import type { Server } from '@/composables/useServerList'

const getServerAccent = (s: Server): string => {
  if (s.core_config?.is_fabric) return 'accent-0'       // teal  – Fabric
  const type = s.core_config?.server_type
  if (type === 'vanilla' || type === 'beta18') return 'accent-1'  // blue  – Vanilla
  if (type === 'forge') return 'accent-4'               // amber – Forge
  if (type === 'velocity') return 'accent-3'            // purple – Velocity
  if (!type || type === 'new_setup') return 'accent-5'  // green – unconfigured
  return 'accent-2'                                     // pink  – other
}

defineProps<{
  servers: Server[]
  loading: boolean
  hasAdmin: boolean
  hasHelper: boolean
  copyPath: (path: string) => void
}>()

defineEmits<{
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
}>()
</script>

<style scoped>
/* ── Container ─────────────────────────────────────────────────── */
.card-scroll {
  width: 100%;
  height: 100%;
  overflow-y: auto;
  padding: 24px 28px 28px;
  box-sizing: border-box;
  scrollbar-width: thin;
  scrollbar-color: rgba(119,181,254,0.25) transparent;
}
.card-scroll::-webkit-scrollbar { width: 5px; }
.card-scroll::-webkit-scrollbar-thumb { background: rgba(119,181,254,0.30); border-radius: 3px; }

.card-empty {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* ── Grid ──────────────────────────────────────────────────────── */
.card-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}
@media (max-width: 1400px) { .card-grid { grid-template-columns: repeat(3, 1fr); } }
@media (max-width: 1050px) { .card-grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 680px)  { .card-grid { grid-template-columns: 1fr; } }

/* ── Per-card accent vars ──────────────────────────────────────── */
.accent-0 { --c: #40c9c6; --glow: rgba(64,201,198,0.20);  --glow-b: rgba(64,201,198,0.35);  --border-h: rgba(64,201,198,0.32);  --icon-bg: rgba(64,201,198,0.12); }
.accent-1 { --c: #36a3f7; --glow: rgba(54,163,247,0.20);  --glow-b: rgba(54,163,247,0.35);  --border-h: rgba(54,163,247,0.32);  --icon-bg: rgba(54,163,247,0.12); }
.accent-2 { --c: #f4516c; --glow: rgba(244,81,108,0.20);  --glow-b: rgba(244,81,108,0.35);  --border-h: rgba(244,81,108,0.32);  --icon-bg: rgba(244,81,108,0.12); }
.accent-3 { --c: #9575cd; --glow: rgba(149,117,205,0.20); --glow-b: rgba(149,117,205,0.35); --border-h: rgba(149,117,205,0.32); --icon-bg: rgba(149,117,205,0.12); }
.accent-4 { --c: #f59e0b; --glow: rgba(245,158,11,0.20);  --glow-b: rgba(245,158,11,0.35);  --border-h: rgba(245,158,11,0.32);  --icon-bg: rgba(245,158,11,0.12); }
.accent-5 { --c: #34d399; --glow: rgba(52,211,153,0.20);  --glow-b: rgba(52,211,153,0.35);  --border-h: rgba(52,211,153,0.32);  --icon-bg: rgba(52,211,153,0.12); }

/* ── Card ──────────────────────────────────────────────────────── */
.server-card {
  position: relative;
  overflow: hidden;
  border-radius: 18px;
  padding: 18px 18px 14px;
  background: rgba(255, 255, 255, 0.62);
  -webkit-backdrop-filter: saturate(160%) blur(16px);
  backdrop-filter: saturate(160%) blur(16px);
  border: 1px solid rgba(255, 255, 255, 0.40);
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.05);
  cursor: default;
  display: flex;
  flex-direction: column;
  gap: 8px;
  transition: transform 0.28s cubic-bezier(.34,1.56,.64,1), box-shadow 0.28s ease, border-color 0.28s ease;
  animation: card-rise 0.65s cubic-bezier(0.34, 1.56, 0.64, 1) both;
  animation-delay: calc(var(--i, 0) * 50ms);
}
@keyframes card-rise {
  from { opacity: 0; transform: translateY(28px) scale(0.95); filter: blur(8px); }
  60%  { filter: blur(0px); }
  to   { opacity: 1; transform: translateY(0) scale(1); filter: blur(0px); }
}
.server-card:hover {
  transform: translateY(-6px);
  box-shadow: 0 16px 44px var(--glow), 0 0 0 1px var(--border-h);
  border-color: var(--border-h);
}
:global(.dark) .server-card {
  background: rgba(15, 23, 42, 0.68);
  border-color: rgba(255, 255, 255, 0.06);
}
:global(.dark) .server-card:hover {
  box-shadow: 0 16px 44px var(--glow-b), 0 0 0 1px var(--border-h);
}

.card-deco {
  position: absolute;
  top: -36px; right: -36px;
  width: 110px; height: 110px;
  border-radius: 50%;
  background: radial-gradient(circle, var(--glow-b), transparent 70%);
  pointer-events: none;
  opacity: 0.6;
  transition: opacity 0.28s ease;
}
.server-card:hover .card-deco { opacity: 1; }

/* ── Card top ──────────────────────────────────────────────────── */
.card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.card-icon-wrap {
  width: 42px; height: 42px;
  border-radius: 12px;
  background: var(--icon-bg);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--c);
  flex-shrink: 0;
  transition: transform 0.3s cubic-bezier(.34,1.56,.64,1), box-shadow 0.3s ease;
}
.server-card:hover .card-icon-wrap {
  transform: scale(1.12) rotate(-6deg);
  box-shadow: 0 0 14px var(--glow);
}

/* ── Status badge ──────────────────────────────────────────────── */
.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
  background: rgba(148, 163, 184, 0.10);
  border: 1px solid rgba(148, 163, 184, 0.20);
  color: var(--el-text-color-secondary);
}
.st-running {
  background: rgba(52, 211, 153, 0.12);
  border-color: rgba(52, 211, 153, 0.25);
  color: #10b981;
}
.st-pending {
  background: rgba(119, 181, 254, 0.12);
  border-color: rgba(119, 181, 254, 0.25);
  color: var(--brand-primary);
}
.st-new_setup {
  background: rgba(119, 181, 254, 0.08);
  border-color: rgba(119, 181, 254, 0.18);
  color: var(--brand-primary);
}
:global(.dark) .st-running { color: #34d399; }
:global(.dark) .st-pending, :global(.dark) .st-new_setup { color: var(--brand-primary); }

.pulse-dot {
  display: inline-block;
  width: 6px; height: 6px;
  border-radius: 50%;
  background: currentColor;
  box-shadow: 0 0 5px currentColor;
  animation: pulse 2.2s ease-in-out infinite;
}
.static-dot {
  display: inline-block;
  width: 6px; height: 6px;
  border-radius: 50%;
  background: currentColor;
  opacity: 0.6;
}
@keyframes pulse {
  0%, 100% { opacity: 1; box-shadow: 0 0 4px currentColor; }
  50%       { opacity: 0.7; box-shadow: 0 0 9px currentColor, 0 0 18px currentColor; }
}

/* ── Name ──────────────────────────────────────────────────────── */
.card-name {
  font-size: 16px;
  font-weight: 800;
  color: var(--color-text);
  line-height: 1.2;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  cursor: pointer;
  transition: color 0.2s ease;
}
.card-name:hover { color: var(--brand-primary); }

/* ── Meta ──────────────────────────────────────────────────────── */
.card-meta {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--el-text-color-secondary);
  min-height: 16px;
}
.meta-type { font-weight: 600; color: var(--c); }
.meta-sep { opacity: 0.4; }

/* ── Footer ────────────────────────────────────────────────────── */
.card-footer {
  margin-top: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.footer-stats {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.stat-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--el-text-color-secondary);
  font-variant-numeric: tabular-nums;
}
.stat-item .el-icon { color: var(--c); opacity: 0.8; }

/* ── Action row ────────────────────────────────────────────────── */
.card-actions {
  display: flex;
  align-items: center;
  gap: 5px;
  border-top: 1px solid rgba(119, 181, 254, 0.10);
  padding-top: 8px;
}
.act-divider { flex: 1 1 auto; }
.act-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px; height: 28px;
  border-radius: 8px;
  border: 1px solid transparent;
  background: transparent;
  cursor: pointer;
  color: var(--el-text-color-secondary);
  transition: background 0.18s ease, color 0.18s ease, border-color 0.18s ease, transform 0.18s ease;
}
.act-btn:not(:disabled):hover { transform: scale(1.12); }
.act-btn:disabled { opacity: 0.35; cursor: not-allowed; }
.act-start:not(:disabled):hover { background: rgba(52,211,153,0.14); color: #10b981; border-color: rgba(52,211,153,0.28); }
.act-stop:not(:disabled):hover  { background: rgba(248,113,113,0.14); color: #ef4444; border-color: rgba(248,113,113,0.28); }
.act-restart:not(:disabled):hover { background: rgba(245,158,11,0.14); color: #f59e0b; border-color: rgba(245,158,11,0.28); }
.act-more:not(:disabled):hover { background: rgba(119,181,254,0.12); color: var(--brand-primary); border-color: rgba(119,181,254,0.22); }

/* ── Loading overlay ───────────────────────────────────────────── */
.card-loading-overlay {
  position: absolute;
  inset: 0;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.65);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 5;
}
:global(.dark) .card-loading-overlay { background: rgba(15, 23, 42, 0.70); }
.loading-spin { animation: spin 1s linear infinite; color: var(--brand-primary); }
@keyframes spin { to { transform: rotate(360deg); } }
.fade-enter-active, .fade-leave-active { transition: opacity 0.2s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
