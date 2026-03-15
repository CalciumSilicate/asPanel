<template>
  <div class="sl-toolbar">
    <!-- Decorative blobs -->
    <div class="deco" aria-hidden="true">
      <span class="deco-blob deco-1" />
      <span class="deco-blob deco-2" />
    </div>

    <div class="toolbar-left">
      <!-- View mode toggle -->
      <div class="view-toggle" role="group" aria-label="显示模式">
        <button
          class="toggle-btn"
          :class="{ active: modelValue === 'card' }"
          @click="$emit('update:modelValue', 'card')"
          title="卡片视图"
        >
          <el-icon :size="15"><Grid /></el-icon>
          <span>卡片</span>
        </button>
        <button
          class="toggle-btn"
          :class="{ active: modelValue === 'table' }"
          @click="$emit('update:modelValue', 'table')"
          title="列表视图"
        >
          <el-icon :size="15"><List /></el-icon>
          <span>详细</span>
        </button>
      </div>

      <div class="toolbar-divider" />

      <!-- Search -->
      <div class="search-wrap">
        <el-input
          :model-value="searchQuery"
          placeholder="搜索服务器名称、端口…"
          clearable
          class="search-input"
          @input="(v: string) => $emit('update:searchQuery', v)"
          @clear="$emit('update:searchQuery', '')"
        >
          <template #prefix>
            <el-icon style="color: var(--brand-primary)"><Search /></el-icon>
          </template>
        </el-input>
      </div>

      <!-- Status filter -->
      <el-select
        :model-value="statusFilter"
        placeholder="全部状态"
        clearable
        style="width: 130px"
        class="status-select"
        @change="(v: string) => $emit('update:statusFilter', v)"
        @clear="$emit('update:statusFilter', '')"
      >
        <el-option label="运行中" value="running" />
        <el-option label="启动中" value="pending" />
        <el-option label="未启动" value="stopped" />
        <el-option label="未配置" value="new_setup" />
      </el-select>

      <!-- Server count badge -->
      <span class="server-count" v-if="totalCount > 0">
        共 <strong>{{ totalCount }}</strong> 台<template v-if="runningCount > 0">，<span class="running-count">{{ runningCount }}</span> 在线</template>
      </span>

      <!-- Pagination prev/next -->
      <template v-if="totalPages > 1">
        <div class="toolbar-divider" />
        <div class="page-nav" role="group" aria-label="分页">
          <button
            class="page-btn"
            :disabled="currentPage <= 1"
            title="上一页"
            @click="$emit('prev-page')"
          >
            <el-icon :size="13"><ArrowLeft /></el-icon>
          </button>
          <span class="page-indicator">{{ currentPage }}<span class="page-sep">/</span>{{ totalPages }}</span>
          <button
            class="page-btn"
            :disabled="currentPage >= totalPages"
            title="下一页"
            @click="$emit('next-page')"
          >
            <el-icon :size="13"><ArrowRight /></el-icon>
          </button>
        </div>
      </template>
    </div>

    <div class="toolbar-right">
      <!-- Batch actions dropdown (admin only) -->
      <el-dropdown
        v-if="hasAdmin && selectedCount > 0"
        trigger="click"
        @command="(cmd: string) => $emit('batch-action', cmd)"
      >
        <button class="btn-batch">
          批量操作 ({{ selectedCount }})
          <el-icon class="el-icon--right"><ArrowDown /></el-icon>
        </button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="start" :icon="VideoPlay">启动</el-dropdown-item>
            <el-dropdown-item command="stop" :icon="SwitchButton">停止</el-dropdown-item>
            <el-dropdown-item command="restart" :icon="Refresh">重启</el-dropdown-item>
            <el-dropdown-item command="delete" :icon="Delete">删除</el-dropdown-item>
            <el-dropdown-item command="command" :icon="Promotion">发送指令</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>

      <!-- Import (platform admin only) -->
      <button v-if="isPlatformAdmin" class="btn-secondary" @click="$emit('import')" title="导入本地服务器">
        <el-icon :size="14"><FolderChecked /></el-icon>
        <span>导入</span>
      </button>

      <!-- Create (admin only) -->
      <button v-if="hasAdmin" class="btn-create" @click="$emit('create')" title="新建服务器">
        <el-icon :size="14"><Plus /></el-icon>
        <span>新建服务器</span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import {
  Grid, List, Search, Plus, ArrowDown, ArrowLeft, ArrowRight,
  VideoPlay, SwitchButton, Refresh, Delete, Promotion, FolderChecked,
} from '@element-plus/icons-vue'
import type { Server } from '@/composables/useServerList'

const props = defineProps<{
  modelValue: 'card' | 'table'
  searchQuery: string
  statusFilter: string
  selectedCount: number
  servers: Server[]
  hasAdmin: boolean
  isPlatformAdmin: boolean
  currentPage: number
  pageSize: number
  totalFiltered: number
}>()

defineEmits<{
  'update:modelValue': ['card' | 'table']
  'update:searchQuery': [string]
  'update:statusFilter': [string]
  create: []
  import: []
  'batch-action': [string]
  'prev-page': []
  'next-page': []
}>()

const totalCount = computed(() => props.servers.length)
const runningCount = computed(() => props.servers.filter((s) => s.status === 'running').length)
const totalPages = computed(() => Math.ceil(props.totalFiltered / props.pageSize))
</script>

<style scoped>
.sl-toolbar {
  position: relative;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 20px;
  background: rgba(255, 255, 255, 0.62);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  backdrop-filter: saturate(180%) blur(20px);
  border: 1px solid rgba(119, 181, 254, 0.18);
  border-radius: 20px;
  box-shadow: 0 4px 24px rgba(119, 181, 254, 0.10), inset 0 1px 0 rgba(255, 255, 255, 0.85);
  flex-shrink: 0;
  transition: box-shadow 0.3s ease, border-color 0.3s ease;
}
.sl-toolbar:hover {
  border-color: rgba(119, 181, 254, 0.28);
  box-shadow: 0 6px 32px rgba(119, 181, 254, 0.14), inset 0 1px 0 rgba(255, 255, 255, 0.85);
}
:global(.dark) .sl-toolbar {
  background: rgba(15, 23, 42, 0.68);
  border-color: rgba(119, 181, 254, 0.12);
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.35), inset 0 1px 0 rgba(255, 255, 255, 0.04);
}

/* Decorative blobs */
.deco { position: absolute; inset: 0; pointer-events: none; overflow: hidden; }
.deco-blob { position: absolute; border-radius: 50%; filter: blur(28px); }
.deco-1 { width: 130px; height: 130px; background: radial-gradient(circle, rgba(119,181,254,0.22), transparent 70%); right: -20px; top: -50px; }
.deco-2 { width: 90px; height: 90px; background: radial-gradient(circle, rgba(167,139,250,0.18), transparent 70%); right: 180px; bottom: -24px; }

.toolbar-left {
  position: relative;
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  z-index: 1;
  min-width: 0;
}
.toolbar-right {
  position: relative;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
  z-index: 1;
}

/* View toggle */
.view-toggle {
  display: inline-flex;
  background: rgba(119, 181, 254, 0.08);
  border: 1px solid rgba(119, 181, 254, 0.18);
  border-radius: 12px;
  padding: 3px;
  gap: 2px;
  flex-shrink: 0;
}
:global(.dark) .view-toggle {
  background: rgba(119, 181, 254, 0.06);
  border-color: rgba(119, 181, 254, 0.14);
}
.toggle-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 12px;
  border-radius: 9px;
  border: none;
  background: transparent;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s ease, color 0.2s ease, box-shadow 0.2s ease;
  white-space: nowrap;
}
.toggle-btn.active {
  background: linear-gradient(135deg, var(--brand-primary), #a78bfa);
  color: #fff;
  box-shadow: 0 2px 10px rgba(119, 181, 254, 0.40);
}
.toggle-btn:not(.active):hover {
  background: rgba(119, 181, 254, 0.12);
  color: var(--brand-primary);
}

.toolbar-divider {
  width: 1px;
  height: 20px;
  background: linear-gradient(180deg, transparent, rgba(119,181,254,0.35), transparent);
  flex-shrink: 0;
}

/* Search input */
.search-wrap { flex: 1 1 auto; min-width: 160px; max-width: 260px; }
.search-input :deep(.el-input__wrapper) {
  border-radius: 22px !important;
  background: rgba(255, 255, 255, 0.60) !important;
  border: 1px solid rgba(119, 181, 254, 0.22) !important;
  box-shadow: none !important;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, background 0.2s ease !important;
  padding-left: 10px !important;
}
.search-input :deep(.el-input__wrapper:hover) {
  border-color: rgba(119, 181, 254, 0.42) !important;
  background: rgba(255, 255, 255, 0.78) !important;
}
.search-input :deep(.el-input__wrapper.is-focus) {
  border-color: rgba(119, 181, 254, 0.60) !important;
  box-shadow: 0 0 0 3px rgba(119, 181, 254, 0.12) !important;
  background: rgba(255, 255, 255, 0.88) !important;
}
:global(.dark) .search-input :deep(.el-input__wrapper) {
  background: rgba(15, 23, 42, 0.60) !important;
  border-color: rgba(119, 181, 254, 0.18) !important;
}
:global(.dark) .search-input :deep(.el-input__wrapper.is-focus) {
  background: rgba(15, 23, 42, 0.80) !important;
}

/* Status select */
.status-select :deep(.el-input__wrapper) {
  border-radius: 22px !important;
  background: rgba(255, 255, 255, 0.60) !important;
  border: 1px solid rgba(119, 181, 254, 0.22) !important;
  box-shadow: none !important;
  transition: border-color 0.2s ease, background 0.2s ease !important;
}
.status-select :deep(.el-input__wrapper.is-focus) {
  border-color: rgba(119, 181, 254, 0.60) !important;
  box-shadow: 0 0 0 3px rgba(119, 181, 254, 0.12) !important;
}
:global(.dark) .status-select :deep(.el-input__wrapper) {
  background: rgba(15, 23, 42, 0.60) !important;
  border-color: rgba(119, 181, 254, 0.18) !important;
}

/* Server count */
.server-count {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
  flex-shrink: 0;
}
.server-count strong { color: var(--brand-primary); font-variant-numeric: tabular-nums; }
.running-count { color: #34d399; font-weight: 700; }

/* ── Pagination prev/next ─────────────────────────────────────── */
.page-nav {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}
.page-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 9px;
  border: 1px solid rgba(119, 181, 254, 0.22);
  background: rgba(119, 181, 254, 0.06);
  color: var(--el-text-color-secondary);
  cursor: pointer;
  transition: background 0.18s ease, color 0.18s ease, border-color 0.18s ease, transform 0.18s ease;
  flex-shrink: 0;
}
.page-btn:not(:disabled):hover {
  background: rgba(119, 181, 254, 0.14);
  border-color: rgba(119, 181, 254, 0.45);
  color: var(--brand-primary);
  transform: scale(1.08);
}
.page-btn:disabled {
  opacity: 0.32;
  cursor: not-allowed;
}
:global(.dark) .page-btn {
  border-color: rgba(119, 181, 254, 0.16);
  background: rgba(119, 181, 254, 0.04);
}
.page-indicator {
  font-size: 12px;
  font-weight: 700;
  color: var(--el-text-color-regular);
  font-variant-numeric: tabular-nums;
  min-width: 36px;
  text-align: center;
  user-select: none;
}
.page-sep {
  color: var(--el-text-color-placeholder);
  margin: 0 1px;
  font-weight: 400;
}

/* Batch button */
.btn-batch {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 34px;
  padding: 0 14px;
  border-radius: 22px;
  border: 1px solid rgba(119, 181, 254, 0.28);
  background: rgba(119, 181, 254, 0.08);
  color: var(--brand-primary);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
}
.btn-batch:hover {
  background: rgba(119, 181, 254, 0.16);
  border-color: rgba(119, 181, 254, 0.50);
  box-shadow: 0 2px 10px rgba(119, 181, 254, 0.20);
}

/* Secondary button */
.btn-secondary {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 34px;
  padding: 0 14px;
  border-radius: 22px;
  border: 1px solid rgba(119, 181, 254, 0.28);
  background: rgba(119, 181, 254, 0.08);
  color: var(--brand-primary);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s ease, border-color 0.2s ease;
}
.btn-secondary:hover {
  background: rgba(119, 181, 254, 0.16);
  border-color: rgba(119, 181, 254, 0.50);
}

/* Create button */
.btn-create {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  height: 34px;
  padding: 0 16px;
  border-radius: 22px;
  border: none;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  color: #fff;
  background: linear-gradient(135deg, var(--brand-primary) 0%, #a78bfa 100%);
  box-shadow: 0 4px 14px rgba(119, 181, 254, 0.40);
  transition: box-shadow 0.25s ease, transform 0.25s cubic-bezier(.34,1.56,.64,1);
}
.btn-create:hover {
  box-shadow: 0 6px 22px rgba(119, 181, 254, 0.65);
  transform: translateY(-1px) scale(1.04);
}
.btn-create:active { transform: scale(0.97); box-shadow: 0 2px 8px rgba(119, 181, 254, 0.30); }

@media (max-width: 1080px) {
  .sl-toolbar {
    align-items: stretch;
    flex-direction: column;
    padding: 14px 16px;
  }

  .toolbar-left,
  .toolbar-right {
    width: 100%;
  }

  .toolbar-right {
    justify-content: flex-end;
    flex-wrap: wrap;
  }

  .search-wrap {
    max-width: none;
    min-width: 220px;
  }
}

@media (max-width: 720px) {
  .toolbar-left {
    gap: 8px;
  }

  .toolbar-divider {
    display: none;
  }

  .search-wrap,
  .status-select {
    width: 100%;
    max-width: none;
  }

  .status-select {
    flex: 1 1 100%;
  }

  .page-nav {
    margin-left: auto;
  }

  .server-count {
    width: 100%;
  }

  .btn-batch,
  .btn-secondary,
  .btn-create {
    flex: 1 1 auto;
    justify-content: center;
  }
}

@media (max-width: 520px) {
  .toggle-btn span,
  .btn-secondary span {
    display: none;
  }

  .btn-create span {
    font-size: 12px;
  }

  .page-nav {
    width: 100%;
    justify-content: space-between;
  }
}
</style>
