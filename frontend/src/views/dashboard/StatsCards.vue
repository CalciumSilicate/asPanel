<template>
  <div class="stats-row">

    <!-- 服务器状态 -->
    <div class="stat-card stat-servers">
      <div class="card-deco" aria-hidden="true"></div>
      <div class="stat-head">
        <div class="stat-icon"><el-icon><Tickets /></el-icon></div>
        <span class="stat-label">服务器状态</span>
      </div>
      <div class="stat-value">
        {{ stats.running_servers }}<span class="stat-sub"> / {{ stats.total_servers }}</span>
      </div>
      <div class="stat-caption">台正在运行</div>
      <div class="stat-bar-row">
        <div class="bar-track">
          <div class="bar-fill" :style="{ width: serverPercent + '%' }"></div>
        </div>
        <span class="bar-pct">{{ serverPercent }}%</span>
      </div>
    </div>

    <!-- CPU -->
    <div class="stat-card stat-cpu">
      <div class="card-deco" aria-hidden="true"></div>
      <div class="stat-head">
        <div class="stat-icon"><el-icon><Cpu /></el-icon></div>
        <span class="stat-label">CPU 负载</span>
      </div>
      <div class="stat-value">
        {{ systemStatus.cpu_percent }}<span class="stat-sub">%</span>
      </div>
      <div class="stat-caption">主机处理器</div>
      <div class="stat-bar-row">
        <div class="bar-track">
          <div class="bar-fill" :style="{ width: systemStatus.cpu_percent + '%' }"></div>
        </div>
        <span class="bar-pct">{{ systemStatus.cpu_percent }}%</span>
      </div>
    </div>

    <!-- 内存 -->
    <div class="stat-card stat-memory">
      <div class="card-deco" aria-hidden="true"></div>
      <div class="stat-head">
        <div class="stat-icon"><el-icon><DataLine /></el-icon></div>
        <span class="stat-label">内存占用</span>
      </div>
      <div class="stat-value">
        {{ systemStatus.memory_used }}<span class="stat-sub"> GB</span>
      </div>
      <div class="stat-caption">共 {{ systemStatus.memory_total }} GB</div>
      <div class="stat-bar-row">
        <div class="bar-track">
          <div class="bar-fill" :style="{ width: systemStatus.memory_percent + '%' }"></div>
        </div>
        <span class="bar-pct">{{ systemStatus.memory_percent }}%</span>
      </div>
    </div>

    <!-- 磁盘 -->
    <div class="stat-card stat-disk">
      <div class="card-deco" aria-hidden="true"></div>
      <div class="stat-head">
        <div class="stat-icon"><el-icon><Folder /></el-icon></div>
        <span class="stat-label">磁盘占用</span>
      </div>
      <div class="stat-value">
        {{ systemStatus.disk_used_gb }}<span class="stat-sub"> GB</span>
      </div>
      <div class="stat-caption">共 {{ systemStatus.disk_total_gb }} GB</div>
      <div class="stat-bar-row">
        <div class="bar-track">
          <div class="bar-fill" :style="{ width: systemStatus.disk_percent + '%' }"></div>
        </div>
        <span class="bar-pct">{{ systemStatus.disk_percent }}%</span>
      </div>
    </div>

  </div>
</template>

<script setup lang="ts">
import { Tickets, Cpu, DataLine, Folder } from '@element-plus/icons-vue'
import type { SystemStatus, ServerStats } from '@/composables/useDashboard'

defineProps<{
  stats: ServerStats
  systemStatus: SystemStatus
  serverPercent: number
}>()
</script>

<style scoped>
/* ─── 网格布局 ──────────────────────────────────────────── */
.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}
@media (max-width: 1199px) { .stats-row { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 599px)  { .stats-row { grid-template-columns: 1fr; } }

/* ─── 卡片基础 ──────────────────────────────────────────── */
.stat-card {
  position: relative;
  overflow: hidden;
  border-radius: 18px;
  padding: 22px 24px 20px;
  background: rgba(255, 255, 255, 0.62);
  -webkit-backdrop-filter: saturate(160%) blur(16px);
  backdrop-filter: saturate(160%) blur(16px);
  border: 1px solid rgba(255, 255, 255, 0.40);
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.05);
  transition:
    transform 0.28s cubic-bezier(.34,1.56,.64,1),
    box-shadow 0.28s ease,
    border-color 0.28s ease;
  animation: stat-card-in 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) both;
}
.stat-card:nth-child(1) { animation-delay: 0ms; }
.stat-card:nth-child(2) { animation-delay: 75ms; }
.stat-card:nth-child(3) { animation-delay: 150ms; }
.stat-card:nth-child(4) { animation-delay: 225ms; }
@keyframes stat-card-in {
  from {
    opacity: 0;
    transform: translateY(22px) scale(0.94);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}
.stat-card:hover {
  transform: translateY(-5px);
  box-shadow: 0 16px 48px var(--card-glow), 0 0 0 1px var(--card-border-h);
  border-color: var(--card-border-h);
}
:global(.dark) .stat-card {
  background: rgba(15, 23, 42, 0.68);
  border-color: rgba(255, 255, 255, 0.06);
}

/* ─── 右上角装饰光晕 ────────────────────────────────────── */
.card-deco {
  position: absolute;
  top: -40px; right: -40px;
  width: 120px; height: 120px;
  border-radius: 50%;
  background: radial-gradient(circle, var(--card-glow-bright), transparent 70%);
  pointer-events: none;
  transition: opacity 0.3s ease;
  opacity: 0.6;
}
.stat-card:hover .card-deco { opacity: 1; }

/* ─── 每卡片专属 accent ─────────────────────────────────── */
.stat-servers {
  --card-color:        var(--stat-servers-color);
  --card-icon-bg:      rgba(64,201,198,0.12);
  --card-glow:         rgba(64,201,198,0.18);
  --card-glow-bright:  rgba(64,201,198,0.32);
  --card-border-h:     rgba(64,201,198,0.32);
}
.stat-cpu {
  --card-color:        var(--stat-cpu-color);
  --card-icon-bg:      rgba(54,163,247,0.12);
  --card-glow:         rgba(54,163,247,0.18);
  --card-glow-bright:  rgba(54,163,247,0.30);
  --card-border-h:     rgba(54,163,247,0.32);
}
.stat-memory {
  --card-color:        var(--stat-memory-color);
  --card-icon-bg:      rgba(244,81,108,0.12);
  --card-glow:         rgba(244,81,108,0.18);
  --card-glow-bright:  rgba(244,81,108,0.30);
  --card-border-h:     rgba(244,81,108,0.32);
}
.stat-disk {
  --card-color:        var(--stat-disk-color);
  --card-icon-bg:      rgba(149,117,205,0.12);
  --card-glow:         rgba(149,117,205,0.18);
  --card-glow-bright:  rgba(149,117,205,0.30);
  --card-border-h:     rgba(149,117,205,0.32);
}

/* ─── 卡片内部元素 ──────────────────────────────────────── */
.stat-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.stat-icon {
  width: 44px; height: 44px;
  border-radius: 12px;
  background: var(--card-icon-bg);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--card-color);
  font-size: 22px;
  transition: transform 0.3s cubic-bezier(.34,1.56,.64,1), box-shadow 0.3s ease;
}
.stat-card:hover .stat-icon {
  transform: scale(1.12) rotate(-6deg);
  box-shadow: 0 0 18px var(--card-glow);
}
.stat-label {
  font-size: 13px;
  font-weight: 500;
  color: var(--el-text-color-secondary);
  letter-spacing: 0.02em;
}
.stat-value {
  font-size: 34px;
  font-weight: 800;
  color: var(--color-text);
  line-height: 1;
  margin-bottom: 4px;
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.02em;
}
.stat-sub {
  font-size: 16px;
  font-weight: 400;
  color: var(--el-text-color-secondary);
}
.stat-caption {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-bottom: 16px;
}

/* ─── 进度条 ─────────────────────────────────────────────── */
.stat-bar-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.bar-track {
  flex: 1;
  height: 4px;
  border-radius: 999px;
  background: rgba(128, 128, 128, 0.12);
  overflow: hidden;
}
.bar-fill {
  height: 100%;
  border-radius: 999px;
  background: var(--card-color);
  box-shadow: 0 0 8px var(--card-glow-bright);
  transition: width 0.7s cubic-bezier(.34,1.56,.64,1);
}
.bar-pct {
  font-size: 12px;
  font-weight: 700;
  color: var(--card-color);
  min-width: 36px;
  text-align: right;
  font-variant-numeric: tabular-nums;
}
</style>
