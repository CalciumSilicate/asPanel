<template>
  <div class="mm-toolbar">
    <div class="toolbar-left">

      <!-- Back button when server selected -->
      <button v-if="selectedServer" class="btn-back" @click="$emit('select-server', null)">
        <el-icon :size="13"><ArrowLeft /></el-icon>
        <span>返回</span>
      </button>

      <template v-if="selectedServer">
        <!-- Server chip -->
        <div class="server-chip">
          <span class="sc-dot" />
          <span class="sc-name">{{ selectedServer.name }}</span>
          <span v-if="isServerRunning" class="sc-running">运行中</span>
        </div>

        <div class="toolbar-divider" />
        <span class="count-badge">共 <strong>{{ modsCount }}</strong> 个模组</span>
      </template>

      <!-- No server: page title + total -->
      <template v-else>
        <span class="page-title">Mods 管理</span>
        <span v-if="totalModsCount !== '计算中'" class="count-badge">
          总计 <strong>{{ totalModsCount }}</strong> 个模组
        </span>
      </template>
    </div>

    <div class="toolbar-right">
      <template v-if="selectedServer">
        <el-tooltip content="检查更新" placement="top" :show-after="400">
          <button class="btn-icon" @click="$emit('check-updates')" :disabled="modsCount === 0">
            <el-icon :size="14"><Refresh /></el-icon>
          </button>
        </el-tooltip>
        <button class="btn-secondary" @click="$emit('copy')" :disabled="isServerRunning">
          <el-icon :size="13"><CopyDocument /></el-icon>
          <span>复制</span>
        </button>
        <button class="btn-secondary" @click="$emit('upload')" :disabled="isServerRunning">
          <el-icon :size="13"><Upload /></el-icon>
          <span>上传</span>
        </button>
        <button class="btn-secondary" @click="$emit('curseforge')" :disabled="isServerRunning">
          <el-icon :size="13"><Link /></el-icon>
          <span>Curseforge</span>
        </button>
        <button class="btn-create" @click="$emit('modrinth')" :disabled="isServerRunning">
          <el-icon :size="13"><Plus /></el-icon>
          <span>Modrinth</span>
        </button>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Refresh, Upload, CopyDocument, Plus, Link, ArrowLeft } from '@element-plus/icons-vue'

defineProps<{
  selectedServer: any | null
  modsCount: number
  totalModsCount: number | string
  isServerRunning: boolean
}>()

defineEmits<{
  'select-server': [number | null]
  'modrinth': []
  'curseforge': []
  'upload': []
  'copy': []
  'check-updates': []
}>()
</script>

<style scoped>
.mm-toolbar {
  font-family: 'Lexend', -apple-system, sans-serif;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 18px;
  background: rgba(255, 255, 255, 0.62);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  backdrop-filter: saturate(180%) blur(20px);
  border: 1px solid rgba(167, 139, 250, 0.18);
  border-radius: 20px;
  box-shadow: 0 4px 24px rgba(167, 139, 250, 0.10), inset 0 1px 0 rgba(255, 255, 255, 0.85);
  flex-shrink: 0;
  transition: box-shadow 0.3s ease, border-color 0.3s ease;
}
.mm-toolbar:hover {
  border-color: rgba(167, 139, 250, 0.28);
  box-shadow: 0 6px 32px rgba(167, 139, 250, 0.14), inset 0 1px 0 rgba(255, 255, 255, 0.85);
}
:global(.dark) .mm-toolbar {
  background: rgba(15, 23, 42, 0.68);
  border-color: rgba(167, 139, 250, 0.12);
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.35), inset 0 1px 0 rgba(255, 255, 255, 0.04);
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1 1 auto;
  min-width: 0;
  flex-wrap: wrap;
}
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

/* Back button */
.btn-back {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 32px;
  padding: 0 12px;
  border-radius: 22px;
  border: 1px solid rgba(167, 139, 250, 0.30);
  background: rgba(167, 139, 250, 0.07);
  color: #a78bfa;
  font-size: 12px;
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
  flex-shrink: 0;
  transition: background 0.18s ease, border-color 0.18s ease, transform 0.18s ease;
}
.btn-back:hover {
  background: rgba(167, 139, 250, 0.14);
  border-color: rgba(167, 139, 250, 0.50);
  transform: translateX(-1px);
}

/* Page title */
.page-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--color-text);
  flex-shrink: 0;
}

/* Server chip */
.server-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 10px 3px 8px;
  border-radius: 999px;
  background: rgba(167, 139, 250, 0.10);
  border: 1px solid rgba(167, 139, 250, 0.22);
  font-size: 12px;
  font-weight: 600;
  color: #a78bfa;
  white-space: nowrap;
  flex-shrink: 0;
}
.sc-dot {
  width: 6px; height: 6px;
  border-radius: 50%;
  background: #a78bfa;
  box-shadow: 0 0 4px rgba(167, 139, 250, 0.8);
  flex-shrink: 0;
}
.sc-name { max-width: 180px; overflow: hidden; text-overflow: ellipsis; }
.sc-running {
  padding: 1px 6px;
  border-radius: 6px;
  background: rgba(52, 211, 153, 0.15);
  color: #10b981;
  font-size: 11px;
}

.toolbar-divider {
  width: 1px; height: 20px;
  background: linear-gradient(180deg, transparent, rgba(167,139,250,0.35), transparent);
  flex-shrink: 0;
}

/* Count badge */
.count-badge { font-size: 12px; color: var(--el-text-color-secondary); white-space: nowrap; flex-shrink: 0; }
.count-badge strong { color: #a78bfa; font-variant-numeric: tabular-nums; }

/* Icon button */
.btn-icon {
  display: inline-flex; align-items: center; justify-content: center;
  width: 32px; height: 32px; border-radius: 9px;
  border: 1px solid rgba(167, 139, 250, 0.22);
  background: rgba(167, 139, 250, 0.06);
  color: var(--el-text-color-secondary);
  cursor: pointer; font-family: inherit;
  transition: background 0.18s ease, color 0.18s ease, border-color 0.18s ease;
  flex-shrink: 0;
}
.btn-icon:not(:disabled):hover { background: rgba(167, 139, 250, 0.14); color: #a78bfa; border-color: rgba(167, 139, 250, 0.40); }
.btn-icon:disabled { opacity: 0.30; cursor: not-allowed; }

/* Secondary buttons */
.btn-secondary {
  display: inline-flex; align-items: center; gap: 5px;
  height: 32px; padding: 0 12px; border-radius: 22px;
  border: 1px solid rgba(167, 139, 250, 0.28);
  background: rgba(167, 139, 250, 0.08);
  color: #a78bfa; font-size: 12px; font-weight: 600;
  font-family: inherit; cursor: pointer;
  transition: background 0.2s ease, border-color 0.2s ease;
}
.btn-secondary:not(:disabled):hover { background: rgba(167, 139, 250, 0.16); border-color: rgba(167, 139, 250, 0.50); }
.btn-secondary:disabled { opacity: 0.30; cursor: not-allowed; }

/* Create button */
.btn-create {
  display: inline-flex; align-items: center; gap: 6px;
  height: 34px; padding: 0 16px; border-radius: 22px; border: none;
  cursor: pointer; font-size: 13px; font-weight: 600; font-family: inherit; color: #fff;
  background: linear-gradient(135deg, #a78bfa 0%, var(--brand-primary) 100%);
  box-shadow: 0 4px 14px rgba(167, 139, 250, 0.40);
  transition: box-shadow 0.25s ease, transform 0.25s cubic-bezier(.34,1.56,.64,1);
}
.btn-create:not(:disabled):hover { box-shadow: 0 6px 22px rgba(167, 139, 250, 0.65); transform: translateY(-1px) scale(1.04); }
.btn-create:active:not(:disabled) { transform: scale(0.97); box-shadow: 0 2px 8px rgba(167, 139, 250, 0.30); }
.btn-create:disabled { opacity: 0.35; cursor: not-allowed; box-shadow: none; }
</style>
