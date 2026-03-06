<template>
  <div class="monitor-section">
    <!-- 区块标题 -->
    <div class="section-head">
      <div class="section-title">
        <span class="title-bar" aria-hidden="true"></span>
        资源监控
      </div>
      <span class="section-hint">仅显示运行中 · 每 5 秒刷新</span>
    </div>

    <!-- 空态 -->
    <div v-if="servers.length === 0" class="empty-state">
      <el-empty description="当前没有正在运行的服务器" />
    </div>

    <!-- 服务器网格 -->
    <div v-else class="server-grid">
      <ServerUsageCard
        v-for="server in servers"
        :key="server.id"
        :server="server"
        :host-memory-total-mb="hostMemoryTotalMb"
        :show-console="showConsole"
        @console="emit('console', $event)"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import ServerUsageCard from './ServerUsageCard.vue'
import type { ServerUsage } from '@/composables/useDashboard'

defineProps<{
  servers: ServerUsage[]
  hostMemoryTotalMb: number
  showConsole: boolean
}>()

const emit = defineEmits<{ console: [id: number] }>()
</script>

<style scoped>
/* ─── 容器 ──────────────────────────────────────────────── */
.monitor-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* ─── 标题行 ─────────────────────────────────────────────── */
.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.section-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 16px;
  font-weight: 700;
  color: var(--color-text);
}
/* 左侧渐变竖条 */
.title-bar {
  display: inline-block;
  width: 3px;
  height: 18px;
  border-radius: 999px;
  background: linear-gradient(180deg, var(--brand-primary), #a78bfa);
  box-shadow: 0 0 8px rgba(119, 181, 254, 0.55);
  flex-shrink: 0;
}
.section-hint {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

/* ─── 空态 ──────────────────────────────────────────────── */
.empty-state {
  background: rgba(255, 255, 255, 0.55);
  -webkit-backdrop-filter: blur(14px);
  backdrop-filter: blur(14px);
  border: 1px solid rgba(119, 181, 254, 0.14);
  border-radius: 18px;
  padding: 20px;
}
:global(.dark) .empty-state {
  background: rgba(15, 23, 42, 0.62);
  border-color: rgba(119, 181, 254, 0.10);
}

/* ─── 服务器网格 ─────────────────────────────────────────── */
.server-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
}
@media (max-width: 1199px) { .server-grid { grid-template-columns: repeat(3, 1fr); } }
@media (max-width: 899px)  { .server-grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 599px)  { .server-grid { grid-template-columns: 1fr; } }

.server-grid > :deep(*) {
  animation: server-card-in 0.55s cubic-bezier(0.34, 1.56, 0.64, 1) both;
}
.server-grid > :deep(*:nth-child(1))  { animation-delay: 0ms; }
.server-grid > :deep(*:nth-child(2))  { animation-delay: 55ms; }
.server-grid > :deep(*:nth-child(3))  { animation-delay: 110ms; }
.server-grid > :deep(*:nth-child(4))  { animation-delay: 165ms; }
.server-grid > :deep(*:nth-child(5))  { animation-delay: 220ms; }
.server-grid > :deep(*:nth-child(6))  { animation-delay: 275ms; }
.server-grid > :deep(*:nth-child(7))  { animation-delay: 330ms; }
.server-grid > :deep(*:nth-child(8))  { animation-delay: 385ms; }
@keyframes server-card-in {
  from {
    opacity: 0;
    transform: translateY(20px) scale(0.93);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}
</style>
