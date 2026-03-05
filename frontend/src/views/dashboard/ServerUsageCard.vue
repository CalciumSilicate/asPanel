<template>
  <div class="usage-card">
    <!-- 头部：状态 + 名称 + 控制台按钮 -->
    <div class="card-head">
      <div class="name-row">
        <span class="status-dot" aria-label="运行中"></span>
        <span class="server-name" :title="server.name">{{ server.name }}</span>
      </div>
      <el-tooltip v-if="showConsole" content="打开控制台" placement="top">
        <button class="console-btn" @click="emit('console', server.id)" aria-label="控制台">
          <el-icon><Monitor /></el-icon>
        </button>
      </el-tooltip>
    </div>

    <!-- 指标 -->
    <div class="metrics">
      <!-- CPU -->
      <div class="metric">
        <div class="metric-head">
          <span class="metric-label"><el-icon><Cpu /></el-icon>CPU</span>
          <span class="metric-val">{{ formatCpuPercent(server.cpu_percent) }}</span>
        </div>
        <div class="bar-track">
          <div class="bar-fill"
               :class="getUsageStatus(clampPercent(server.cpu_percent))"
               :style="{ width: clampPercent(server.cpu_percent) + '%' }">
          </div>
        </div>
      </div>

      <!-- 内存 -->
      <div class="metric">
        <div class="metric-head">
          <span class="metric-label"><el-icon><DataLine /></el-icon>内存</span>
          <span class="metric-val">{{ formatMemoryMb(server.memory_mb) }}</span>
        </div>
        <div class="bar-track">
          <div class="bar-fill"
               :class="getUsageStatus(memoryPercent)"
               :style="{ width: memoryPercent + '%' }">
          </div>
        </div>
        <div class="metric-hint" v-if="hostMemoryTotalMb > 0">
          占主机总内存 {{ memoryPercent.toFixed(1) }}%
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Monitor, Cpu, DataLine } from '@element-plus/icons-vue'
import type { ServerUsage } from '@/composables/useDashboard'
import { clampPercent, formatCpuPercent, formatMemoryMb, getUsageStatus } from '@/utils/metrics'

const props = defineProps<{
  server: ServerUsage
  hostMemoryTotalMb: number
  showConsole: boolean
}>()

const emit = defineEmits<{ console: [id: number] }>()

const memoryPercent = computed(() => {
  if (!props.hostMemoryTotalMb) return 0
  return clampPercent(((Number(props.server.memory_mb) || 0) / props.hostMemoryTotalMb) * 100)
})
</script>

<style scoped>
/* ─── 卡片 ──────────────────────────────────────────────── */
.usage-card {
  background: rgba(255, 255, 255, 0.55);
  -webkit-backdrop-filter: blur(14px);
  backdrop-filter: blur(14px);
  border: 1px solid rgba(119, 181, 254, 0.16);
  border-radius: 16px;
  padding: 16px 18px;
  transition:
    transform 0.25s cubic-bezier(.34,1.56,.64,1),
    box-shadow 0.25s ease,
    border-color 0.25s ease;
}
.usage-card:hover {
  transform: translateY(-4px);
  border-color: rgba(119, 181, 254, 0.35);
  box-shadow: 0 10px 36px rgba(119, 181, 254, 0.16);
}
:global(.dark) .usage-card {
  background: rgba(15, 23, 42, 0.62);
  border-color: rgba(119, 181, 254, 0.10);
}
:global(.dark) .usage-card:hover {
  border-color: rgba(119, 181, 254, 0.28);
  box-shadow: 0 10px 36px rgba(0, 0, 0, 0.40);
}

/* ─── 头部 ──────────────────────────────────────────────── */
.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 14px;
}
.name-row {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  flex: 1;
}

/* 状态圆点（搏动动画） */
.status-dot {
  flex-shrink: 0;
  width: 8px; height: 8px;
  border-radius: 50%;
  background: #34d399;
  box-shadow: 0 0 6px rgba(52, 211, 153, 0.7);
  animation: dot-pulse 2.4s ease-in-out infinite;
}
@keyframes dot-pulse {
  0%,100% { box-shadow: 0 0 4px rgba(52,211,153,0.55); }
  50%      { box-shadow: 0 0 10px rgba(52,211,153,0.90), 0 0 22px rgba(52,211,153,0.28); }
}

.server-name {
  font-size: 14px;
  font-weight: 700;
  color: var(--el-text-color-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 控制台按钮 */
.console-btn {
  flex-shrink: 0;
  width: 28px; height: 28px;
  border-radius: 8px;
  background: rgba(119, 181, 254, 0.10);
  border: 1px solid rgba(119, 181, 254, 0.22);
  color: var(--brand-primary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  transition: background 0.2s, box-shadow 0.2s, transform 0.2s cubic-bezier(.34,1.56,.64,1);
}
.console-btn:hover {
  background: rgba(119, 181, 254, 0.22);
  box-shadow: 0 0 10px rgba(119, 181, 254, 0.35);
  transform: scale(1.12);
}

/* ─── 指标区 ─────────────────────────────────────────────── */
.metrics { display: flex; flex-direction: column; gap: 10px; }
.metric  { display: flex; flex-direction: column; gap: 5px; }

.metric-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.metric-label {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.metric-val {
  font-size: 13px;
  font-weight: 700;
  color: var(--el-text-color-primary);
  font-variant-numeric: tabular-nums;
}
.metric-hint {
  font-size: 11px;
  color: var(--el-text-color-secondary);
  margin-top: 1px;
}

/* ─── 进度条 ─────────────────────────────────────────────── */
.bar-track {
  height: 5px;
  border-radius: 999px;
  background: rgba(128, 128, 128, 0.12);
  overflow: hidden;
}
.bar-fill {
  height: 100%;
  border-radius: 999px;
  background: var(--brand-primary);
  box-shadow: 0 0 6px rgba(119, 181, 254, 0.45);
  transition: width 0.55s cubic-bezier(.34,1.56,.64,1);
}
/* success / warning / exception 状态色 */
.bar-fill.success  { background: #34d399; box-shadow: 0 0 6px rgba(52,211,153,0.45); }
.bar-fill.warning  { background: #f59e0b; box-shadow: 0 0 6px rgba(245,158,11,0.45); }
.bar-fill.exception{ background: #f87171; box-shadow: 0 0 6px rgba(248,113,113,0.45); }
</style>
