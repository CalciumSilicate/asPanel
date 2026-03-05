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
        circle
        text
      >
        <el-icon :size="18">
          <Operation />
        </el-icon>
      </el-button>
    </el-badge>
    <template #dropdown>
      <el-dropdown-menu class="tasks-menu">
        <el-dropdown-item class="tasks-menu-actions-item">
          <div class="tasks-menu-actions">
            <span class="tasks-menu-header">后台任务</span>
            <el-button
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
          <div class="task-row">
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
        <el-dropdown-item v-if="tasks.length === 0" disabled>暂无任务</el-dropdown-item>
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
.tasks-dropdown { margin-right: 8px; }
.tasks-menu { width: 460px; max-width: min(560px, 92vw); padding: 6px 0; overflow-x: hidden; box-sizing: border-box; }
.tasks-menu :deep(.el-dropdown-menu__item) {
  white-space: normal;
  height: auto;
  line-height: 1.4;
  padding: 0 !important;
  display: block !important;
  align-items: initial !important;
}
.tasks-menu-actions { padding: 10px 14px; display: flex; align-items: center; justify-content: space-between; }
.tasks-menu-actions-item { cursor: default; }
.tasks-menu-actions-item:hover { background-color: transparent !important; }
.tasks-menu .tasks-menu-header { font-weight: 600; color: var(--color-text); }
.task-row { padding: 10px 14px; display: block; width: 100%; box-sizing: border-box; }
.task-row-header { display: grid; grid-template-columns: 1fr auto auto; column-gap: 12px; align-items: baseline; margin-bottom: 4px; }
.task-name { font-size: 13px; color: var(--color-text); font-weight: 600; text-align: left; }
.task-state { font-size: 12px; color: var(--el-text-color-secondary); text-align: right; }
.task-percent { font-size: 12px; color: var(--el-text-color-secondary); text-align: right; }
.task-row-desc {
  font-size: 11px;
  color: var(--el-text-color-secondary);
  margin: 2px 0 6px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.task-progress { display: block; width: 96%; margin: 0 auto; }
.task-progress.running :deep(.el-progress-bar__outer) { background-color: #4c4d4f; }
.task-progress.failed :deep(.el-progress-bar__outer),
.task-progress.failed :deep(.el-progress-bar__inner) { background-color: var(--el-color-danger); }
.tasks-badge :deep(.el-badge__content) { transform: translate(4px, -6px); }
</style>
