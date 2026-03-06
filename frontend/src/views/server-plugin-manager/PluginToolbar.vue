<template>
  <div class="pm-toolbar">
    <div class="toolbar-left">

      <!-- Back button when server selected -->
      <button v-if="selectedServer" class="btn-back" @click="$emit('select-server', null)">
        <el-icon :size="13"><ArrowLeft /></el-icon>
        <span>返回</span>
      </button>

      <template v-if="selectedServer">
        <!-- Server name chip -->
        <div class="server-chip">
          <span class="sc-dot" />
          <span class="sc-name">{{ selectedServer.name }}</span>
        </div>

        <div class="toolbar-divider" />

        <!-- Search -->
        <div class="search-wrap">
          <el-input
            :model-value="query"
            placeholder="搜索插件名称、ID…"
            clearable
            class="search-input"
            @input="(v: string) => $emit('update:query', v)"
            @clear="$emit('update:query', '')"
          >
            <template #prefix>
              <el-icon style="color: var(--brand-primary)"><Search /></el-icon>
            </template>
          </el-input>
        </div>

        <!-- Filter group -->
        <div class="filter-group" role="group" aria-label="状态筛选">
          <button :class="['filter-btn', { active: filterStatus === 'all' }]"      @click="$emit('update:filterStatus', 'all')">全部</button>
          <button :class="['filter-btn', { active: filterStatus === 'enabled' }]"  @click="$emit('update:filterStatus', 'enabled')">已启用</button>
          <button :class="['filter-btn', { active: filterStatus === 'disabled' }]" @click="$emit('update:filterStatus', 'disabled')">已禁用</button>
        </div>

        <span class="count-badge" v-if="totalCount >= 0">
          共 <strong>{{ totalCount }}</strong> 个插件
        </span>

        <template v-if="totalPages > 1">
          <div class="toolbar-divider" />
          <div class="page-nav" role="group" aria-label="分页">
            <button class="page-btn" :disabled="currentPage <= 1" title="上一页" @click="$emit('prev-page')">
              <el-icon :size="13"><ArrowLeft /></el-icon>
            </button>
            <span class="page-indicator">{{ currentPage }}<span class="page-sep">/</span>{{ totalPages }}</span>
            <button class="page-btn" :disabled="currentPage >= totalPages" title="下一页" @click="$emit('next-page')">
              <el-icon :size="13"><ArrowRight /></el-icon>
            </button>
          </div>
        </template>
      </template>

      <!-- No server: page title + total -->
      <template v-else>
        <span class="page-title">插件管理</span>
        <span v-if="totalPluginCount > 0" class="count-badge">
          总计 <strong>{{ totalPluginCount }}</strong> 个插件
        </span>
      </template>
    </div>

    <div class="toolbar-right">
      <template v-if="selectedServer">
        <button class="btn-secondary" @click="$emit('add-db')">
          <el-icon :size="14"><Coin /></el-icon>
          <span>数据库</span>
        </button>
        <button class="btn-create" @click="$emit('add-online')">
          <el-icon :size="14"><Download /></el-icon>
          <span>联网插件</span>
        </button>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Search, Coin, Download, ArrowLeft, ArrowRight } from '@element-plus/icons-vue'

const props = defineProps<{
  selectedServer: any | null
  totalCount: number
  totalPluginCount: number
  query: string
  filterStatus: string
  currentPage: number
  pageSize: number
  totalFiltered: number
}>()

defineEmits<{
  'select-server': [number | null]
  'update:query': [string]
  'update:filterStatus': [string]
  'add-online': []
  'add-db': []
  'prev-page': []
  'next-page': []
}>()

const totalPages = computed(() => Math.ceil(props.totalFiltered / props.pageSize))
</script>

<style scoped>
.pm-toolbar {
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
  border: 1px solid rgba(119, 181, 254, 0.18);
  border-radius: 20px;
  box-shadow: 0 4px 24px rgba(119, 181, 254, 0.10), inset 0 1px 0 rgba(255, 255, 255, 0.85);
  flex-shrink: 0;
  transition: box-shadow 0.3s ease, border-color 0.3s ease;
}
.pm-toolbar:hover {
  border-color: rgba(119, 181, 254, 0.28);
  box-shadow: 0 6px 32px rgba(119, 181, 254, 0.14), inset 0 1px 0 rgba(255, 255, 255, 0.85);
}
:global(.dark) .pm-toolbar {
  background: rgba(15, 23, 42, 0.68);
  border-color: rgba(119, 181, 254, 0.12);
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
  gap: 8px;
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
  border: 1px solid rgba(119, 181, 254, 0.30);
  background: rgba(119, 181, 254, 0.07);
  color: var(--brand-primary);
  font-size: 12px;
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
  flex-shrink: 0;
  transition: background 0.18s ease, border-color 0.18s ease, transform 0.18s ease;
}
.btn-back:hover {
  background: rgba(119, 181, 254, 0.14);
  border-color: rgba(119, 181, 254, 0.50);
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
  background: rgba(119, 181, 254, 0.10);
  border: 1px solid rgba(119, 181, 254, 0.22);
  font-size: 12px;
  font-weight: 600;
  color: var(--brand-primary);
  white-space: nowrap;
  flex-shrink: 0;
}
.sc-dot {
  width: 6px; height: 6px;
  border-radius: 50%;
  background: var(--brand-primary);
  box-shadow: 0 0 4px rgba(119, 181, 254, 0.8);
  flex-shrink: 0;
}
.sc-name { max-width: 180px; overflow: hidden; text-overflow: ellipsis; }

.toolbar-divider {
  width: 1px; height: 20px;
  background: linear-gradient(180deg, transparent, rgba(119,181,254,0.35), transparent);
  flex-shrink: 0;
}

/* Search */
.search-wrap { flex: 1 1 auto; min-width: 140px; max-width: 240px; }
.search-input :deep(.el-input__wrapper) {
  border-radius: 22px !important;
  background: rgba(255, 255, 255, 0.60) !important;
  border: 1px solid rgba(119, 181, 254, 0.22) !important;
  box-shadow: none !important;
  padding-left: 10px !important;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, background 0.2s ease !important;
}
.search-input :deep(.el-input__wrapper:hover) { border-color: rgba(119, 181, 254, 0.42) !important; }
.search-input :deep(.el-input__wrapper.is-focus) {
  border-color: rgba(119, 181, 254, 0.60) !important;
  box-shadow: 0 0 0 3px rgba(119, 181, 254, 0.12) !important;
  background: rgba(255, 255, 255, 0.88) !important;
}
:global(.dark) .search-input :deep(.el-input__wrapper) {
  background: rgba(15, 23, 42, 0.60) !important;
  border-color: rgba(119, 181, 254, 0.18) !important;
}

/* Filter group */
.filter-group {
  display: inline-flex;
  background: rgba(119, 181, 254, 0.08);
  border: 1px solid rgba(119, 181, 254, 0.18);
  border-radius: 12px;
  padding: 3px;
  gap: 2px;
  flex-shrink: 0;
}
:global(.dark) .filter-group {
  background: rgba(119, 181, 254, 0.06);
  border-color: rgba(119, 181, 254, 0.14);
}
.filter-btn {
  display: inline-flex;
  align-items: center;
  padding: 4px 11px;
  border-radius: 9px;
  border: none;
  background: transparent;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
  transition: background 0.2s ease, color 0.2s ease;
  white-space: nowrap;
}
.filter-btn.active {
  background: linear-gradient(135deg, var(--brand-primary), #a78bfa);
  color: #fff;
  box-shadow: 0 2px 10px rgba(119, 181, 254, 0.40);
}
.filter-btn:not(.active):hover {
  background: rgba(119, 181, 254, 0.12);
  color: var(--brand-primary);
}

/* Count badge */
.count-badge { font-size: 12px; color: var(--el-text-color-secondary); white-space: nowrap; flex-shrink: 0; }
.count-badge strong { color: var(--brand-primary); font-variant-numeric: tabular-nums; }

/* Action buttons */
.btn-secondary {
  display: inline-flex; align-items: center; gap: 6px;
  height: 34px; padding: 0 14px; border-radius: 22px;
  border: 1px solid rgba(119, 181, 254, 0.28);
  background: rgba(119, 181, 254, 0.08);
  color: var(--brand-primary); font-size: 12px; font-weight: 600;
  font-family: inherit; cursor: pointer;
  transition: background 0.2s ease, border-color 0.2s ease;
}
.btn-secondary:hover { background: rgba(119, 181, 254, 0.16); border-color: rgba(119, 181, 254, 0.50); }

.btn-create {
  display: inline-flex; align-items: center; gap: 7px;
  height: 34px; padding: 0 16px; border-radius: 22px; border: none;
  cursor: pointer; font-size: 13px; font-weight: 600; font-family: inherit; color: #fff;
  background: linear-gradient(135deg, var(--brand-primary) 0%, #a78bfa 100%);
  box-shadow: 0 4px 14px rgba(119, 181, 254, 0.40);
  transition: box-shadow 0.25s ease, transform 0.25s cubic-bezier(.34,1.56,.64,1);
}
.btn-create:hover { box-shadow: 0 6px 22px rgba(119, 181, 254, 0.65); transform: translateY(-1px) scale(1.04); }
.btn-create:active { transform: scale(0.97); box-shadow: 0 2px 8px rgba(119, 181, 254, 0.30); }

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
  width: 28px; height: 28px;
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
.page-btn:disabled { opacity: 0.32; cursor: not-allowed; }
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
.page-sep { color: var(--el-text-color-placeholder); margin: 0 1px; font-weight: 400; }
</style>
