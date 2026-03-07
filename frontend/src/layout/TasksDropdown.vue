<template>
  <el-dropdown
    trigger="click"
    class="tasks-dropdown"
    placement="bottom-end"
    :popper-options="dropdownPopperOptions"
    :hide-on-click="false"
  >
    <el-badge
      :value="activeTasksCount"
      :max="99"
      type="danger"
      :hidden="activeTasksCount === 0"
      class="tasks-badge"
    >
      <el-button
        class="tasks-toggle"
        aria-label="后台任务"
        title="后台任务"
      >
        <span class="tasks-toggle-glow"></span>
        <span class="tasks-toggle-icon-wrap">
          <el-icon :size="18" class="tasks-toggle-icon">
            <Operation />
          </el-icon>
        </span>
        <span class="tasks-toggle-copy">
          <span class="tasks-toggle-label">后台任务</span>
          <span class="tasks-toggle-meta">{{ tasksToggleMeta }}</span>
        </span>
      </el-button>
    </el-badge>
    <template #dropdown>
      <el-dropdown-menu class="tasks-menu">
        <el-dropdown-item class="tasks-menu-actions-item">
          <div class="tasks-menu-actions">
            <div class="tasks-menu-title-group">
              <span class="tasks-menu-icon">
                <el-icon><Operation /></el-icon>
              </span>
              <div>
                <span class="tasks-menu-header">后台任务</span>
                <p class="tasks-menu-subtitle">实时查看执行进度与结果回执</p>
              </div>
            </div>
            <el-button
              class="tasks-clear-btn"
              size="small"
              text
              :disabled="clearTasksDisabled"
              @click.stop="handleClearTasks"
            >
              {{ clearTasksText }}
            </el-button>
          </div>
        </el-dropdown-item>
        <el-dropdown-item v-for="t in tasks" :key="t.id" disabled>
          <div class="task-row" :class="`is-${(t.status || '').toLowerCase()}`">
            <div class="task-row-header">
              <span class="task-name">{{ taskTitle(t) }}</span>
              <span class="task-state">{{ statusLabel(t.status) }}</span>
              <span class="task-percent">{{ displayPercent(t) }}%</span>
            </div>
            <div class="task-row-desc" :title="taskDesc(t)">{{ taskDesc(t) }}</div>
            <el-progress
              v-if="t.status !== 'PENDING'"
              class="task-progress"
              :class="(t.status || '').toLowerCase()"
              :percentage="progressPercent(t)"
              :stroke-width="4"
              :show-text="false"
              :color="progressColor(t.status)"
            />
          </div>
        </el-dropdown-item>
        <el-dropdown-item v-if="tasks.length === 0" disabled>
          <div class="tasks-empty">暂无任务</div>
        </el-dropdown-item>
      </el-dropdown-menu>
    </template>
  </el-dropdown>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ElMessage } from 'element-plus'
import { Operation } from '@element-plus/icons-vue'
import { useTasksStore } from '@/store/tasks'
import { storeToRefs } from 'pinia'
import type { Task, TaskStatus } from '@/store/tasks'

const tasksStore = useTasksStore()
const { tasks, activeTasksCount, failedTasksCount, successTasksCount } = storeToRefs(tasksStore)
const { clearTasks } = tasksStore

const TASK_TYPE_LABELS: Record<string, string> = {
  DOWNLOAD: '下载',
  CREATE_ARCHIVE: '创建存档',
  UPLOAD_ARCHIVE: '上传存档',
  RESTORE_ARCHIVE: '恢复存档',
  IMPORT: '导入服务器',
  CREATE_SERVER: '创建服务器',
  DELETE_SERVER: '删除服务器',
  COMBINED: '组合任务',
  INSTALL_MOD: '安装模组',
  COPY_MODS: '复制模组',
  UPLOAD_MOD: '上传模组',
  CHECK_MOD_UPDATES: '检查模组更新',
  LITEMATIC_UPLOAD: '上传投影',
  LITEMATIC_GENERATE: '生成命令',
}

const dropdownPopperOptions = {
  modifiers: [
    { name: 'offset', options: { offset: [0, 8] } },
    { name: 'preventOverflow', options: { padding: 8, boundary: 'viewport' } },
    { name: 'flip', options: { fallbackPlacements: ['bottom-end', 'bottom-start', 'top-end', 'top-start'] } },
  ],
}

const taskTitle = (t: Partial<Task>): string => t?.name || TASK_TYPE_LABELS[t?.type ?? ''] || '任务'
const taskDesc = (t: Partial<Task>): string => t?.error || t?.message || ''

const progressColor = (status: TaskStatus | undefined): string => {
  if (status === 'RUNNING') return 'var(--el-color-primary)'
  if (status === 'FAILED') return 'var(--el-color-danger)'
  if (status === 'SUCCESS') return 'var(--el-color-success)'
  return 'var(--el-color-info)'
}

const STATUS_LABELS: Record<string, string> = {
  PENDING: '排队',
  RUNNING: '进行中',
  SUCCESS: '成功',
  FAILED: '失败',
}
const statusLabel = (status: TaskStatus): string => STATUS_LABELS[status] || status
const displayPercent = (t: Task): number => (t.status === 'SUCCESS' || t.status === 'FAILED') ? 100 : t.progress
const progressPercent = (t: Task): number => (t.status === 'SUCCESS' || t.status === 'FAILED') ? 100 : t.progress

const clearTasksText = computed(() => failedTasksCount.value > 0 ? '清除失败任务' : '清除已完成任务')
const clearTasksDisabled = computed(() => failedTasksCount.value === 0 && successTasksCount.value === 0)
const tasksToggleMeta = computed(() => {
  if (activeTasksCount.value > 0) return `${activeTasksCount.value} 个进行中`
  if (failedTasksCount.value > 0) return `${failedTasksCount.value} 个失败`
  if (successTasksCount.value > 0) return `${successTasksCount.value} 个已完成`
  return '实时状态'
})

const handleClearTasks = async () => {
  if (clearTasksDisabled.value) return
  const status = failedTasksCount.value > 0 ? 'FAILED' : 'SUCCESS'
  try {
    const cleared = await clearTasks(status)
    ElMessage.success(`已清理 ${cleared} 个任务`)
  } catch (e: any) {
    ElMessage.error(`清理失败: ${e.response?.data?.detail || e.message}`)
  }
}
</script>

<style scoped>
.tasks-dropdown {
  margin-right: 10px;
  position: relative;
}

.tasks-toggle {
  position: relative;
  overflow: hidden;
  display: inline-flex;
  align-items: center;
  gap: 10px;
  min-height: 42px;
  padding: 5px 14px 5px 6px !important;
  border-radius: 16px !important;
  border: 1px solid rgba(119,181,254,0.18) !important;
  background: rgba(255,255,255,0.5) !important;
  -webkit-backdrop-filter: saturate(160%) blur(16px);
  backdrop-filter: saturate(160%) blur(16px);
  box-shadow:
    0 10px 24px rgba(119,181,254,0.12),
    inset 0 1px 0 rgba(255,255,255,0.85) !important;
  transition:
    transform 0.25s cubic-bezier(.34,1.56,.64,1),
    box-shadow 0.25s ease,
    border-color 0.25s ease,
    background 0.25s ease !important;
}

.tasks-toggle:hover {
  transform: translateY(-1px) scale(1.01) !important;
  border-color: rgba(119,181,254,0.28) !important;
  box-shadow:
    0 14px 30px rgba(119,181,254,0.18),
    0 0 0 1px rgba(119,181,254,0.16),
    inset 0 1px 0 rgba(255,255,255,0.92) !important;
}

:global(.dark) .tasks-toggle {
  background: rgba(15,23,42,0.58) !important;
  border-color: rgba(119,181,254,0.14) !important;
  box-shadow:
    0 14px 28px rgba(0,0,0,0.34),
    inset 0 1px 0 rgba(255,255,255,0.04) !important;
}

:global(.dark) .tasks-toggle:hover {
  border-color: rgba(119,181,254,0.24) !important;
  box-shadow:
    0 18px 34px rgba(0,0,0,0.42),
    0 0 0 1px rgba(119,181,254,0.14),
    0 0 22px rgba(119,181,254,0.18) !important;
}

.tasks-toggle-glow {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(circle at top left, rgba(119,181,254,0.18), transparent 52%),
    radial-gradient(circle at right center, rgba(239,183,186,0.14), transparent 46%);
  opacity: 0.95;
  pointer-events: none;
}

.tasks-toggle-icon-wrap {
  position: relative;
  z-index: 1;
  width: 30px;
  height: 30px;
  border-radius: 12px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #77b5fe;
  background: rgba(119,181,254,0.12);
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.7);
}

.tasks-toggle-icon {
  filter: drop-shadow(0 0 8px rgba(119,181,254,0.35));
}

.tasks-toggle-copy {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  min-width: 0;
}

.tasks-toggle-label {
  font-size: 13px;
  font-weight: 700;
  line-height: 1.1;
  color: var(--color-text);
}

.tasks-toggle-meta {
  font-size: 11px;
  line-height: 1.1;
  color: var(--color-text-secondary);
}

.tasks-menu {
  width: 460px;
  max-width: min(560px, 92vw);
  padding: 0;
  overflow-x: hidden;
  box-sizing: border-box;
  border: 1px solid rgba(119,181,254,0.18);
  border-radius: 20px;
  background: rgba(255,255,255,0.78);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  backdrop-filter: saturate(180%) blur(20px);
  box-shadow:
    0 20px 60px rgba(119,181,254,0.18),
    0 4px 16px rgba(0,0,0,0.06);
}

:global(.dark) .tasks-menu {
  background: rgba(8,14,26,0.92);
  border-color: rgba(119,181,254,0.14);
  box-shadow:
    0 28px 80px rgba(0,0,0,0.72),
    inset 0 1px 0 rgba(255,255,255,0.04);
}

.tasks-menu :deep(.el-dropdown-menu__item) {
  white-space: normal;
  height: auto;
  line-height: 1.4;
  padding: 0 !important;
  display: block !important;
  align-items: initial !important;
  border-radius: 16px !important;
  margin: 6px 10px !important;
}

.tasks-menu :deep(.el-dropdown-menu__item:hover) {
  background: rgba(119,181,254,0.08) !important;
}

.tasks-menu-actions {
  position: relative;
  padding: 16px 18px 14px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid rgba(119,181,254,0.12);
  margin-bottom: 2px;
}

.tasks-menu-actions::before {
  content: '';
  position: absolute;
  top: 0;
  left: 18px;
  right: 18px;
  height: 1px;
  background: linear-gradient(90deg, transparent 0%, rgba(119,181,254,0.5) 32%, rgba(239,183,186,0.45) 68%, transparent 100%);
}

.tasks-menu-actions-item {
  cursor: default;
}

.tasks-menu-actions-item:hover {
  background-color: transparent !important;
}

.tasks-menu-title-group {
  display: flex;
  align-items: center;
  gap: 12px;
}

.tasks-menu-icon {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: rgba(119,181,254,0.12);
  color: #77b5fe;
}

.tasks-menu .tasks-menu-header {
  display: block;
  font-weight: 700;
  font-size: 14px;
  letter-spacing: 0.03em;
  background: linear-gradient(135deg, #77b5fe, #a78bfa);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}

.tasks-menu-subtitle {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--color-text-secondary);
}

.tasks-clear-btn {
  border-radius: 10px;
  border: 1px solid rgba(119,181,254,0.2);
  background: rgba(128,128,128,0.06);
  color: var(--color-text-secondary);
  padding: 0 12px;
}

.tasks-clear-btn:hover {
  color: var(--brand-primary);
  border-color: rgba(119,181,254,0.28);
  background: rgba(119,181,254,0.08);
}

.task-row {
  position: relative;
  overflow: hidden;
  padding: 14px 14px 12px;
  display: block;
  width: 100%;
  box-sizing: border-box;
  border: 1px solid rgba(119,181,254,0.1);
  border-radius: 16px;
  background: linear-gradient(180deg, rgba(255,255,255,0.36), rgba(119,181,254,0.05));
}

:global(.dark) .task-row {
  background: linear-gradient(180deg, rgba(18,28,46,0.74), rgba(10,16,32,0.92));
  border-color: rgba(119,181,254,0.1);
}

.task-row::before {
  content: '';
  position: absolute;
  inset: 0 auto 0 0;
  width: 3px;
  border-radius: 16px 0 0 16px;
  background: linear-gradient(180deg, rgba(119,181,254,0.9), rgba(239,183,186,0.7));
  opacity: 0;
  transition: opacity 0.22s ease;
}

.task-row.is-running::before,
.task-row.is-failed::before,
.task-row.is-success::before {
  opacity: 1;
}

.task-row-header {
  display: grid;
  grid-template-columns: 1fr auto auto;
  column-gap: 12px;
  align-items: baseline;
  margin-bottom: 4px;
}

.task-name {
  font-size: 13px;
  color: var(--color-text);
  font-weight: 600;
  text-align: left;
}

.task-state {
  font-size: 11px;
  color: var(--color-text-secondary);
  text-align: right;
  padding: 3px 8px;
  border-radius: 999px;
  background: rgba(119,181,254,0.08);
}

.task-percent {
  font-size: 12px;
  color: var(--color-text-secondary);
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.task-row-desc {
  font-size: 11px;
  color: var(--color-text-secondary);
  margin: 6px 0 10px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.task-progress {
  display: block;
  width: 100%;
  margin: 0;
}

.task-progress :deep(.el-progress-bar__outer) {
  background: rgba(119,181,254,0.1) !important;
  border-radius: 99px !important;
}

.task-progress :deep(.el-progress-bar__inner) {
  border-radius: 99px !important;
  box-shadow: 0 0 8px currentColor;
}

.task-progress.running :deep(.el-progress-bar__outer) {
  background-color: rgba(119,181,254,0.12) !important;
}

.task-progress.failed :deep(.el-progress-bar__outer),
.task-progress.failed :deep(.el-progress-bar__inner) {
  background-color: var(--el-color-danger) !important;
}

.tasks-empty {
  padding: 18px 16px;
  text-align: center;
  color: var(--color-text-secondary);
}

.tasks-badge :deep(.el-badge__content) {
  transform: translate(6px, -6px);
  border: none;
  min-width: 20px;
  height: 20px;
  padding: 0 6px;
  font-weight: 700;
  color: #fff;
  background: linear-gradient(135deg, #f4516c, #ef8aa0);
  box-shadow: 0 6px 14px rgba(244,81,108,0.34);
}

@media (max-width: 900px) {
  .tasks-toggle {
    padding-right: 10px !important;
  }

  .tasks-toggle-copy {
    display: none;
  }

  .tasks-menu {
    width: min(92vw, 460px);
  }
}
</style>
