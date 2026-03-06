<template>
  <div class="pc-page">
    <div class="pc-wrap" :class="{ 'is-collapsed': asideCollapsed, 'is-collapsing': asideCollapsing }">

      <!-- Left: server picker glass panel -->
      <div class="pc-left">
        <div class="pc-glass-panel">
          <ConfigServerPicker
            :plugin-title="pluginTitle"
            :servers="servers"
            :loading="loadingServers"
            :installed-map="installedMap"
            :is-allowed="isAllowed"
            :installing-server-id="installingServerId"
            :active-server-id="activeServer?.id ?? null"
            @select="$emit('update:activeServer', $event)"
            @install="$emit('install', $event)"
          />
        </div>
      </div>

      <!-- Right: config form or empty state -->
      <div class="pc-right">
        <div v-if="!activeServer" class="pc-placeholder">
          <div class="placeholder-icon">
            <el-icon :size="22"><Setting /></el-icon>
          </div>
          <p class="placeholder-text">请从左侧选择一台已安装 <strong>{{ pluginTitle }}</strong> 的服务器</p>
        </div>

        <div v-else class="pc-glass-card">
          <div class="shimmer-line" aria-hidden="true" />
          <div class="pc-form-wrap">
            <PluginConfigForm
              :plugin-key="pluginKey"
              :server-id="activeServer.id"
              :server-name="activeServer.name"
              :show-raw-button="true"
              :naked="false"
            />
          </div>
        </div>
      </div>

    </div>
  </div>
</template>

<script setup lang="ts">
import { useUiStore } from '@/store/ui'
import { storeToRefs } from 'pinia'
import { Setting } from '@element-plus/icons-vue'
import ConfigServerPicker from './ConfigServerPicker.vue'
import PluginConfigForm from './PluginConfigForm.vue'

defineProps<{
  pluginTitle: string
  pluginKey: string
  servers: any[]
  loadingServers: boolean
  installedMap: Map<number, boolean>
  isAllowed: (s: any) => boolean
  installingServerId: number | null
  activeServer: any | null
}>()

defineEmits<{
  'update:activeServer': [s: any | null]
  install: [s: any]
}>()

const { asideCollapsed, asideCollapsing } = storeToRefs(useUiStore())
</script>

<style scoped>
/* ── Page layout ─────────────────────────────────────────── */
.pc-page {
  height: calc(100vh - var(--el-header-height) - 48px);
  overflow: hidden;
  min-height: 0;
}

.pc-wrap {
  display: flex;
  gap: 16px;
  align-items: stretch;
  height: 100%;
  min-height: 0;
}

/* ── Left panel ──────────────────────────────────────────── */
.pc-left {
  width: 300px;
  flex-shrink: 0;
  height: 100%;
  min-height: 0;
  transition: width 0.32s cubic-bezier(.34, 1.56, .64, 1);
  will-change: width;
  overflow: hidden;
}
.is-collapsed .pc-left,
.is-collapsing .pc-left {
  width: 0 !important;
}

.pc-glass-panel {
  height: 100%;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.58);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  backdrop-filter: saturate(180%) blur(20px);
  border: 1px solid rgba(119, 181, 254, 0.18);
  box-shadow: 0 4px 32px rgba(119, 181, 254, 0.10);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
:global(.dark) .pc-glass-panel {
  background: rgba(15, 23, 42, 0.65);
  border-color: rgba(119, 181, 254, 0.12);
}

/* ── Right panel ─────────────────────────────────────────── */
.pc-right {
  flex: 1 1 auto;
  min-height: 0;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

/* Empty state */
.pc-placeholder {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  height: 100%;
  color: var(--el-text-color-secondary);
}
.placeholder-icon {
  width: 56px; height: 56px;
  border-radius: 16px;
  background: rgba(119, 181, 254, 0.08);
  border: 1px solid rgba(119, 181, 254, 0.18);
  display: flex; align-items: center; justify-content: center;
  color: var(--brand-primary);
}
.placeholder-text {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  margin: 0;
}
.placeholder-text strong {
  color: var(--brand-primary);
}

/* Glass card (active server) */
.pc-glass-card {
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.58);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  backdrop-filter: saturate(180%) blur(20px);
  border: 1px solid rgba(119, 181, 254, 0.18);
  box-shadow: 0 4px 32px rgba(119, 181, 254, 0.10), inset 0 1px 0 rgba(255, 255, 255, 0.80);
  overflow: hidden;
  transition: border-color 0.3s ease, box-shadow 0.3s ease;
}
.pc-glass-card:hover {
  border-color: rgba(119, 181, 254, 0.28);
  box-shadow: 0 8px 40px rgba(119, 181, 254, 0.14), inset 0 1px 0 rgba(255, 255, 255, 0.80);
}
:global(.dark) .pc-glass-card {
  background: rgba(15, 23, 42, 0.65);
  border-color: rgba(119, 181, 254, 0.12);
  box-shadow: 0 4px 32px rgba(0, 0, 0, 0.40), inset 0 1px 0 rgba(255, 255, 255, 0.04);
}

/* Shimmer accent line */
.shimmer-line {
  height: 3px;
  flex-shrink: 0;
  background: linear-gradient(90deg, var(--brand-primary) 0%, #a78bfa 50%, var(--brand-primary) 100%);
  background-size: 200% 100%;
  animation: shimmer-slide 3s linear infinite;
  border-radius: 3px 3px 0 0;
}
@keyframes shimmer-slide {
  0%   { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.pc-form-wrap {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  scrollbar-width: thin;
  padding: 16px;
}

/* Strip the inner el-card box-shadow so it blends into our glass card */
.pc-form-wrap :deep(.el-card) {
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
}
.pc-form-wrap :deep(.el-card__header) {
  border-bottom: 1px solid rgba(119, 181, 254, 0.12);
}
</style>
