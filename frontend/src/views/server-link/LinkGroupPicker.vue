<template>
  <div class="group-picker">
    <div class="picker-shell">
      <span class="shell-shimmer"></span>
      <span class="shell-orb shell-orb-1"></span>
      <span class="shell-orb shell-orb-2"></span>

      <div class="picker-header">
        <div class="header-icon-ring">
          <el-icon :size="30"><Link /></el-icon>
        </div>
        <h2 class="picker-title">服务器组管理</h2>
        <p class="picker-subtitle">
          共 <strong>{{ groups.length }}</strong> 个服务器组，点击进入联动配置与绑定详情
        </p>
      </div>

      <div v-if="groups.length === 0" class="picker-loading">
        <div class="loading-orbit">
          <el-icon class="loading-spin" :size="24"><Loading /></el-icon>
        </div>
        <div class="loading-copy">
          <strong>正在加载服务器组</strong>
          <span>准备联动配置、QQ 绑定与节点信息…</span>
        </div>
      </div>

      <div v-else class="picker-grid">
        <div
          v-for="(g, i) in groups"
          :key="g.id"
          class="group-card"
          :class="'accent-' + (i % 6)"
          @click="$emit('select', g)"
        >
          <span class="card-shimmer"></span>
          <div class="card-deco" aria-hidden="true" />

          <div class="card-top">
            <div class="card-icon-wrap">
              <el-icon :size="22"><Link /></el-icon>
            </div>
            <div class="qq-badge" v-if="g.qqGroup">
              <span class="pulse-dot" />
              已绑定 QQ
            </div>
            <div class="unbound-badge" v-else>未绑定</div>
          </div>

          <div class="card-name-row">
            <div class="card-name">{{ g.name }}</div>
            <div class="card-id">ID {{ g.id }}</div>
          </div>

          <div class="card-stats">
            <div class="stat-chip">
              <span class="stat-label">服务器数</span>
              <strong>{{ serverCount(g) }}</strong>
            </div>
            <div class="stat-chip muted">
              <span class="stat-label">QQ 群</span>
              <strong>{{ g.qqGroup || '未绑定' }}</strong>
            </div>
          </div>

          <div class="card-footer">
            <div class="bar-track">
              <div class="bar-fill" :style="{ width: barWidth(g) }" />
            </div>
            <div class="footer-row">
              <span class="bar-label">{{ serverCount(g) }} 台服务器</span>
              <span class="qq-label">{{ g.qqGroup ? `QQ ${g.qqGroup}` : '等待绑定' }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Link, Loading } from '@element-plus/icons-vue'
import type { ServerLinkGroup } from '@/composables/useServerLink'

defineProps<{
  groups: ServerLinkGroup[]
}>()

defineEmits<{ select: [group: ServerLinkGroup] }>()

const serverCount = (g: ServerLinkGroup): number => {
  const ids = g.serverIds
  return Array.isArray(ids) ? ids.length : 0
}

const barWidth = (g: ServerLinkGroup) => {
  if (!serverCount(g)) return '0%'
  return '100%'
}
</script>

<style scoped>
.group-picker {
  width: 100%;
  height: 100%;
  padding: 28px 32px 32px;
  overflow-y: auto;
  box-sizing: border-box;
  scrollbar-width: thin;
  scrollbar-color: rgba(239,183,186,0.28) transparent;
}

.group-picker::-webkit-scrollbar {
  width: 5px;
}

.group-picker::-webkit-scrollbar-thumb {
  background: linear-gradient(180deg, rgba(119,181,254,0.45), rgba(239,183,186,0.45));
  border-radius: 3px;
}

.picker-shell {
  position: relative;
  overflow: hidden;
  min-height: 100%;
  display: flex;
  flex-direction: column;
  gap: 30px;
  padding: 28px;
  border-radius: 28px;
  background: rgba(255,255,255,0.58);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  backdrop-filter: saturate(180%) blur(20px);
  border: 1px solid rgba(119,181,254,0.18);
  box-shadow:
    0 24px 60px rgba(119,181,254,0.10),
    inset 0 1px 0 rgba(255,255,255,0.9);
}

:global(.dark) .picker-shell {
  background: rgba(15,23,42,0.58);
  border-color: rgba(119,181,254,0.12);
  box-shadow:
    0 28px 80px rgba(0,0,0,0.42),
    inset 0 1px 0 rgba(255,255,255,0.05);
}

.shell-shimmer {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 1px;
  background: linear-gradient(90deg, transparent 0%, rgba(119,181,254,0.5) 30%, rgba(239,183,186,0.45) 65%, transparent 100%);
}

.shell-orb {
  position: absolute;
  border-radius: 50%;
  pointer-events: none;
  filter: blur(70px);
  opacity: 0.7;
}

.shell-orb-1 {
  width: 220px;
  height: 220px;
  top: -60px;
  right: -40px;
  background: rgba(119,181,254,0.18);
}

.shell-orb-2 {
  width: 180px;
  height: 180px;
  bottom: -40px;
  left: -20px;
  background: rgba(239,183,186,0.18);
}

.picker-header {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  text-align: center;
}

.header-icon-ring {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  padding: 3px;
  background: linear-gradient(135deg, var(--brand-primary), #a78bfa, #efb7ba, var(--brand-primary));
  background-size: 300% 300%;
  animation: ring-shift 5s ease-in-out infinite;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
}

.header-icon-ring::after {
  content: '';
  position: absolute;
  inset: -3px;
  border-radius: 50%;
  background: inherit;
  filter: blur(10px);
  opacity: 0.45;
  z-index: -1;
  animation: ring-shift 5s ease-in-out infinite;
}

.header-icon-ring :deep(.el-icon) {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  background: var(--color-surface, #fff);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--brand-primary);
}

:global(.dark) .header-icon-ring :deep(.el-icon) {
  background: var(--color-surface, #0f1729);
}

@keyframes ring-shift {
  0%, 100% { background-position: 0% 50%; }
  50% { background-position: 100% 50%; }
}

.picker-kicker {
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(119,181,254,0.08);
  border: 1px solid rgba(119,181,254,0.14);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--brand-primary);
}

.picker-title {
  margin: 0;
  font-size: clamp(24px, 3vw, 30px);
  font-weight: 800;
  background: linear-gradient(135deg, var(--brand-primary) 0%, #a78bfa 50%, #efb7ba 100%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  background-size: 200% 200%;
  animation: text-shift 6s ease-in-out infinite;
}

@keyframes text-shift {
  0%, 100% { background-position: 0% 50%; }
  50% { background-position: 100% 50%; }
}

.picker-subtitle {
  margin: 0;
  max-width: 580px;
  font-size: 14px;
  line-height: 1.7;
  color: var(--color-text-secondary, var(--el-text-color-secondary));
}

.picker-subtitle strong {
  color: var(--brand-primary);
  font-weight: 700;
}

.picker-summary {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
  gap: 10px;
}

.summary-pill {
  padding: 6px 12px;
  border-radius: 999px;
  border: 1px solid rgba(119,181,254,0.16);
  background: rgba(255,255,255,0.42);
  color: var(--color-text-secondary, var(--el-text-color-secondary));
  font-size: 12px;
}

:global(.dark) .summary-pill {
  background: rgba(10,16,32,0.55);
}

.picker-loading {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  flex: 1 1 auto;
  min-height: 320px;
  border-radius: 24px;
  border: 1px solid rgba(119,181,254,0.14);
  background: linear-gradient(135deg, rgba(255,255,255,0.36), rgba(119,181,254,0.08));
}

:global(.dark) .picker-loading {
  background: linear-gradient(135deg, rgba(10,16,32,0.8), rgba(18,28,46,0.72));
}

.loading-orbit {
  width: 52px;
  height: 52px;
  border-radius: 16px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: rgba(119,181,254,0.12);
  color: var(--brand-primary);
  box-shadow: 0 12px 24px rgba(119,181,254,0.14);
}

.loading-copy {
  display: flex;
  flex-direction: column;
  gap: 4px;
  color: var(--color-text-secondary, var(--el-text-color-secondary));
}

.loading-copy strong {
  color: var(--color-text);
  font-size: 15px;
}

.loading-copy span {
  font-size: 13px;
}

.loading-spin {
  animation: spin 1.2s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.picker-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 18px;
}

.picker-grid .group-card {
  animation: db-rise 0.72s cubic-bezier(0.34,1.56,0.64,1) both;
}

.picker-grid .group-card:nth-child(1) { animation-delay: 0ms; }
.picker-grid .group-card:nth-child(2) { animation-delay: 160ms; }
.picker-grid .group-card:nth-child(3) { animation-delay: 320ms; }
.picker-grid .group-card:nth-child(4) { animation-delay: 480ms; }
.picker-grid .group-card:nth-child(5) { animation-delay: 640ms; }
.picker-grid .group-card:nth-child(6) { animation-delay: 800ms; }
.picker-grid .group-card:nth-child(n + 7) { animation-delay: 960ms; }

@keyframes db-rise {
  from {
    opacity: 0;
    transform: translateY(36px) scale(0.95);
    filter: blur(10px);
  }
  60% {
    filter: blur(0);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

@media (max-width: 1199px) {
  .picker-grid { grid-template-columns: repeat(3, 1fr); }
}

@media (max-width: 899px) {
  .picker-grid { grid-template-columns: repeat(2, 1fr); }
}

@media (max-width: 599px) {
  .picker-grid { grid-template-columns: 1fr; }
}

.accent-0 { --c: #40c9c6; --glow: rgba(64,201,198,0.20); --glow-b: rgba(64,201,198,0.35); --border-h: rgba(64,201,198,0.32); --icon-bg: rgba(64,201,198,0.12); }
.accent-1 { --c: #36a3f7; --glow: rgba(54,163,247,0.20); --glow-b: rgba(54,163,247,0.35); --border-h: rgba(54,163,247,0.32); --icon-bg: rgba(54,163,247,0.12); }
.accent-2 { --c: #f4516c; --glow: rgba(244,81,108,0.20); --glow-b: rgba(244,81,108,0.35); --border-h: rgba(244,81,108,0.32); --icon-bg: rgba(244,81,108,0.12); }
.accent-3 { --c: #9575cd; --glow: rgba(149,117,205,0.20); --glow-b: rgba(149,117,205,0.35); --border-h: rgba(149,117,205,0.32); --icon-bg: rgba(149,117,205,0.12); }
.accent-4 { --c: #f59e0b; --glow: rgba(245,158,11,0.20); --glow-b: rgba(245,158,11,0.35); --border-h: rgba(245,158,11,0.32); --icon-bg: rgba(245,158,11,0.12); }
.accent-5 { --c: #34d399; --glow: rgba(52,211,153,0.20); --glow-b: rgba(52,211,153,0.35); --border-h: rgba(52,211,153,0.32); --icon-bg: rgba(52,211,153,0.12); }

.group-card {
  position: relative;
  overflow: hidden;
  border-radius: 20px;
  padding: 18px 18px 16px;
  background: rgba(255,255,255,0.62);
  -webkit-backdrop-filter: saturate(160%) blur(18px);
  backdrop-filter: saturate(160%) blur(18px);
  border: 1px solid rgba(119,181,254,0.18);
  box-shadow: 0 4px 24px rgba(119,181,254,0.10), 0 1px 0 rgba(255,255,255,0.9) inset;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 12px;
  transition: transform 0.28s cubic-bezier(.34,1.56,.64,1), box-shadow 0.28s ease, border-color 0.28s ease;
}

.group-card:hover {
  transform: translateY(-8px) scale(1.01);
  box-shadow: 0 18px 48px var(--glow), 0 0 0 1px var(--border-h), 0 18px 40px rgba(119,181,254,0.10);
  border-color: var(--border-h);
}

:global(.dark) .group-card {
  background: rgba(15,23,42,0.55);
  border-color: rgba(119,181,254,0.12);
  box-shadow: 0 4px 32px rgba(0,0,0,0.45), 0 0 0 1px rgba(119,181,254,0.08) inset;
}

:global(.dark) .group-card:hover {
  box-shadow: 0 18px 48px var(--glow-b), 0 0 0 1px var(--border-h), 0 24px 44px rgba(0,0,0,0.34);
}

.card-shimmer {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 1px;
  background: linear-gradient(90deg, transparent 0%, rgba(119,181,254,0.5) 30%, rgba(239,183,186,0.45) 65%, transparent 100%);
}

.card-deco {
  position: absolute;
  top: -36px;
  right: -36px;
  width: 110px;
  height: 110px;
  border-radius: 50%;
  background: radial-gradient(circle, var(--glow-b), transparent 70%);
  pointer-events: none;
  opacity: 0.7;
  transition: opacity 0.28s ease;
}

.group-card:hover .card-deco {
  opacity: 1;
}

.card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.card-icon-wrap {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  background: var(--icon-bg);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--c);
  transition: transform 0.3s cubic-bezier(.34,1.56,.64,1), box-shadow 0.3s ease;
}

.group-card:hover .card-icon-wrap {
  transform: scale(1.14) rotate(-6deg);
  box-shadow: 0 0 16px var(--glow);
}

.card-name-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.qq-badge,
.unbound-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
}

.qq-badge {
  background: rgba(52,211,153,0.12);
  border: 1px solid rgba(52,211,153,0.25);
  color: #34d399;
  box-shadow: 0 4px 16px rgba(52,211,153,0.12);
}

.unbound-badge {
  background: rgba(148,163,184,0.10);
  border: 1px solid rgba(148,163,184,0.20);
  color: var(--el-text-color-secondary);
}

.pulse-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #34d399;
  box-shadow: 0 0 5px rgba(52,211,153,0.7);
  animation: pulse 2.2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { box-shadow: 0 0 4px rgba(52,211,153,0.55); }
  50% { box-shadow: 0 0 9px rgba(52,211,153,0.90), 0 0 18px rgba(52,211,153,0.28); }
}

.card-name {
  font-size: 16px;
  font-weight: 800;
  color: var(--color-text);
  line-height: 1.2;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.card-id {
  font-size: 11px;
  color: var(--color-text-secondary, var(--el-text-color-secondary));
}

.card-stats {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.stat-chip {
  padding: 10px 12px;
  border-radius: 14px;
  background: rgba(119,181,254,0.08);
  border: 1px solid rgba(119,181,254,0.14);
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.stat-chip.muted {
  background: rgba(239,183,186,0.08);
  border-color: rgba(239,183,186,0.16);
}

.stat-label {
  font-size: 11px;
  color: var(--color-text-secondary, var(--el-text-color-secondary));
}

.stat-chip strong {
  font-size: 15px;
  color: var(--color-text);
}

.card-footer {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.bar-track {
  height: 4px;
  border-radius: 999px;
  background: rgba(128,128,128,0.12);
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, var(--c), rgba(119,181,254,0.92));
  box-shadow: 0 0 8px var(--glow-b);
  transition: width 0.7s cubic-bezier(.34,1.56,.64,1);
}

.footer-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.bar-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--c);
  font-variant-numeric: tabular-nums;
}

.qq-label {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: var(--color-text-secondary, var(--el-text-color-secondary));
  white-space: nowrap;
}

@media (max-width: 899px) {
  .group-picker {
    padding: 20px;
  }

  .picker-shell {
    padding: 20px;
    border-radius: 24px;
  }
}

@media (max-width: 599px) {
  .picker-loading {
    flex-direction: column;
    text-align: center;
  }

  .card-stats {
    grid-template-columns: 1fr;
  }

  .footer-row {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
