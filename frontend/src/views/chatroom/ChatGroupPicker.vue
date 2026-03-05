<template>
  <div class="group-picker">
    <!-- Header -->
    <div class="picker-header">
      <div class="header-icon-ring">
        <el-icon :size="30"><ChatDotRound /></el-icon>
      </div>
      <h2 class="picker-title">选择聊天室</h2>
      <p class="picker-subtitle">
        共 <strong>{{ groups.length }}</strong> 个服务器组可用，点击进入
      </p>
    </div>

    <!-- Loading -->
    <div v-if="groups.length === 0" class="picker-loading">
      <el-icon class="loading-spin" :size="22"><Loading /></el-icon>
      <span>正在加载服务器组…</span>
    </div>

    <!-- Grid -->
    <div v-else class="picker-grid">
      <div
        v-for="(g, i) in groups"
        :key="g.id"
        class="group-card"
        :class="'accent-' + (i % 6)"
        @click="$emit('select', g)"
      >
        <!-- Decorative corner glow -->
        <div class="card-deco" aria-hidden="true" />

        <!-- Top row: icon + online badge -->
        <div class="card-top">
          <div class="card-icon-wrap">
            <el-icon :size="22"><ChatDotRound /></el-icon>
          </div>
          <div class="online-badge" v-if="onlineCount(g) > 0">
            <span class="pulse-dot" />
            {{ onlineCount(g) }} 在线
          </div>
          <div class="offline-badge" v-else>离线</div>
        </div>

        <!-- Name + ID -->
        <div class="card-name">{{ g.name }}</div>
        <div class="card-id">ID {{ g.id }}</div>

        <!-- Progress bar + fraction -->
        <div class="card-footer">
          <div class="bar-track">
            <div class="bar-fill" :style="{ width: barWidth(g) }" />
          </div>
          <span class="bar-label">
            {{ onlineCount(g) }} / {{ g.server_ids.length }} 台运行
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ChatDotRound, Loading } from '@element-plus/icons-vue'
import type { Group } from '@/composables/useChatRoom'

const props = defineProps<{
  groups: Group[]
  onlineCount: (g: Group) => number
}>()

defineEmits<{ select: [group: Group] }>()

const barWidth = (g: Group) => {
  const total = g.server_ids.length
  if (!total) return '0%'
  return `${Math.min(100, Math.round((props.onlineCount(g) / total) * 100))}%`
}
</script>

<style scoped>
/* ─── Container ──────────────────────────────────────────── */
.group-picker {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 28px;
  padding: 36px 40px 32px;
  overflow-y: auto;
  box-sizing: border-box;
  scrollbar-width: thin;
  scrollbar-color: rgba(119,181,254,0.25) transparent;
}
.group-picker::-webkit-scrollbar { width: 5px; }
.group-picker::-webkit-scrollbar-thumb {
  background: rgba(119,181,254,0.30);
  border-radius: 3px;
}

/* ─── Header ─────────────────────────────────────────────── */
.picker-header {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  text-align: center;
}
.header-icon-ring {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  padding: 3px;
  background: linear-gradient(135deg, var(--brand-primary), #a78bfa, #EFB7BA, var(--brand-primary));
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
  50%       { background-position: 100% 50%; }
}
.picker-title {
  margin: 0;
  font-size: 24px;
  font-weight: 800;
  background: linear-gradient(135deg, var(--brand-primary) 0%, #a78bfa 50%, #EFB7BA 100%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  background-size: 200% 200%;
  animation: text-shift 6s ease-in-out infinite;
}
@keyframes text-shift {
  0%, 100% { background-position: 0% 50%; }
  50%       { background-position: 100% 50%; }
}
.picker-subtitle {
  margin: 0;
  font-size: 14px;
  color: var(--el-text-color-secondary);
}
.picker-subtitle strong { color: var(--brand-primary); font-weight: 700; }

/* ─── Loading ────────────────────────────────────────────── */
.picker-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  flex: 1 1 auto;
  font-size: 14px;
  color: var(--el-text-color-secondary);
}
.loading-spin { animation: spin 1.2s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

/* ─── Grid ───────────────────────────────────────────────── */
.picker-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}
@media (max-width: 1199px) { .picker-grid { grid-template-columns: repeat(3, 1fr); } }
@media (max-width: 899px)  { .picker-grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 599px)  { .picker-grid { grid-template-columns: 1fr; } }

/* ─── Per-card accent CSS vars ──────────────────────────── */
.accent-0 { --c: #40c9c6; --glow: rgba(64,201,198,0.20);  --glow-b: rgba(64,201,198,0.35);  --border-h: rgba(64,201,198,0.32);  --icon-bg: rgba(64,201,198,0.12); }
.accent-1 { --c: #36a3f7; --glow: rgba(54,163,247,0.20);  --glow-b: rgba(54,163,247,0.35);  --border-h: rgba(54,163,247,0.32);  --icon-bg: rgba(54,163,247,0.12); }
.accent-2 { --c: #f4516c; --glow: rgba(244,81,108,0.20);  --glow-b: rgba(244,81,108,0.35);  --border-h: rgba(244,81,108,0.32);  --icon-bg: rgba(244,81,108,0.12); }
.accent-3 { --c: #9575cd; --glow: rgba(149,117,205,0.20); --glow-b: rgba(149,117,205,0.35); --border-h: rgba(149,117,205,0.32); --icon-bg: rgba(149,117,205,0.12); }
.accent-4 { --c: #f59e0b; --glow: rgba(245,158,11,0.20);  --glow-b: rgba(245,158,11,0.35);  --border-h: rgba(245,158,11,0.32);  --icon-bg: rgba(245,158,11,0.12); }
.accent-5 { --c: #34d399; --glow: rgba(52,211,153,0.20);  --glow-b: rgba(52,211,153,0.35);  --border-h: rgba(52,211,153,0.32);  --icon-bg: rgba(52,211,153,0.12); }

/* ─── Group card ─────────────────────────────────────────── */
.group-card {
  position: relative;
  overflow: hidden;
  border-radius: 18px;
  padding: 20px 20px 16px;
  background: rgba(255, 255, 255, 0.62);
  -webkit-backdrop-filter: saturate(160%) blur(16px);
  backdrop-filter: saturate(160%) blur(16px);
  border: 1px solid rgba(255, 255, 255, 0.40);
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.05);
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 8px;
  transition:
    transform 0.28s cubic-bezier(.34,1.56,.64,1),
    box-shadow 0.28s ease,
    border-color 0.28s ease;
}
.group-card:hover {
  transform: translateY(-7px);
  box-shadow: 0 18px 48px var(--glow), 0 0 0 1px var(--border-h);
  border-color: var(--border-h);
}
:global(.dark) .group-card {
  background: rgba(15, 23, 42, 0.68);
  border-color: rgba(255, 255, 255, 0.06);
}
:global(.dark) .group-card:hover {
  box-shadow: 0 18px 48px var(--glow-b), 0 0 0 1px var(--border-h);
}

/* Corner deco blob */
.card-deco {
  position: absolute;
  top: -36px; right: -36px;
  width: 110px; height: 110px;
  border-radius: 50%;
  background: radial-gradient(circle, var(--glow-b), transparent 70%);
  pointer-events: none;
  opacity: 0.7;
  transition: opacity 0.28s ease;
}
.group-card:hover .card-deco { opacity: 1; }

/* Top row */
.card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}
.card-icon-wrap {
  width: 44px; height: 44px;
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

/* Online / Offline badge */
.online-badge, .offline-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
}
.online-badge {
  background: rgba(52, 211, 153, 0.12);
  border: 1px solid rgba(52, 211, 153, 0.25);
  color: #34d399;
}
.offline-badge {
  background: rgba(148, 163, 184, 0.10);
  border: 1px solid rgba(148, 163, 184, 0.20);
  color: var(--el-text-color-secondary);
}
.pulse-dot {
  display: inline-block;
  width: 6px; height: 6px;
  border-radius: 50%;
  background: #34d399;
  box-shadow: 0 0 5px rgba(52,211,153,0.7);
  animation: pulse 2.2s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { box-shadow: 0 0 4px rgba(52,211,153,0.55); }
  50%       { box-shadow: 0 0 9px rgba(52,211,153,0.90), 0 0 18px rgba(52,211,153,0.28); }
}

/* Text */
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
  color: var(--el-text-color-secondary);
  margin-top: -4px;
}

/* Footer: bar */
.card-footer {
  margin-top: 4px;
  display: flex;
  flex-direction: column;
  gap: 5px;
}
.bar-track {
  height: 4px;
  border-radius: 999px;
  background: rgba(128, 128, 128, 0.12);
  overflow: hidden;
}
.bar-fill {
  height: 100%;
  border-radius: 999px;
  background: var(--c);
  box-shadow: 0 0 8px var(--glow-b);
  transition: width 0.7s cubic-bezier(.34,1.56,.64,1);
}
.bar-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--c);
  font-variant-numeric: tabular-nums;
}
</style>
