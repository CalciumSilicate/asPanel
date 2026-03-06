<template>
  <div class="dashboard-container">
    <!-- 骨架屏：数据加载前显示 -->
    <Transition name="db-skeleton">
      <div v-if="!loaded" class="skeleton-layout" aria-hidden="true">
        <!-- WelcomeCard 骨架 -->
        <div class="sk-card sk-welcome">
          <div class="sk-avatar shimmer"></div>
          <div class="sk-lines">
            <div class="sk-line shimmer" style="width:60px;height:10px"></div>
            <div class="sk-line shimmer" style="width:160px;height:26px;margin-top:6px"></div>
            <div class="sk-line shimmer" style="width:110px;height:10px;margin-top:8px"></div>
          </div>
        </div>
        <!-- StatsCards 骨架 -->
        <div class="sk-stats-row">
          <div v-for="i in 4" :key="i" class="sk-card sk-stat">
            <div class="sk-icon shimmer"></div>
            <div class="sk-line shimmer" style="width:80px;height:32px;margin-top:16px"></div>
            <div class="sk-line shimmer" style="width:100px;height:10px;margin-top:8px"></div>
            <div class="sk-line shimmer" style="width:100%;height:4px;border-radius:999px;margin-top:16px"></div>
          </div>
        </div>
        <!-- ResourceMonitor 骨架 -->
        <div class="sk-monitor">
          <div class="sk-line shimmer" style="width:120px;height:18px"></div>
          <div class="sk-server-grid">
            <div v-for="i in 4" :key="i" class="sk-card sk-server shimmer"></div>
          </div>
        </div>
      </div>
    </Transition>

    <!-- 真实内容：数据加载后显示，带入场动画 -->
    <Transition name="db-content">
      <div v-if="loaded" class="content-layout">
        <div class="db-item" style="--delay: 0ms">
          <WelcomeCard :username="user.username || 'admin'" :avatar-url="fullAvatarUrl" />
        </div>
        <div class="db-item" style="--delay: 160ms">
          <StatsCards :stats="stats" :system-status="systemStatus" :server-percent="serverPercent" />
        </div>
        <div class="db-item" style="--delay: 320ms">
          <ResourceMonitor
            :servers="runningServersUsage"
            :host-memory-total-mb="hostMemoryTotalMb"
            :show-console="hasRole('ADMIN')"
            @console="goToConsole"
          />
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useUserStore } from '@/store/user'
import { useDashboard } from '@/composables/useDashboard'
import WelcomeCard from './dashboard/WelcomeCard.vue'
import StatsCards from './dashboard/StatsCards.vue'
import ResourceMonitor from './dashboard/ResourceMonitor.vue'

const router = useRouter()
const userStore = useUserStore()
const user = userStore.user
const { fullAvatarUrl, activeGroupIds } = storeToRefs(userStore)
const { hasRole } = userStore

const { stats, systemStatus, runningServersUsage, serverPercent, hostMemoryTotalMb, loaded } =
  useDashboard(activeGroupIds)

const goToConsole = (serverId: number) => router.push(`/console/${serverId}`)
</script>

<style scoped>
/* ─── 容器：grid 让骨架与内容重叠，消除高度跳变 ─────────── */
.dashboard-container {
  display: grid;
}

.skeleton-layout,
.content-layout {
  grid-area: 1 / 1;
  display: flex;
  flex-direction: column;
  gap: 20px;
  width: 100%;
}

/* ─── 骨架过渡：模糊淡出 + 上移缩小 ────────────────────── */
.db-skeleton-leave-active {
  transition: opacity 0.42s ease, transform 0.42s ease, filter 0.42s ease;
  pointer-events: none;
  z-index: 1;
}
.db-skeleton-leave-to {
  opacity: 0;
  transform: translateY(-14px) scale(0.98);
  filter: blur(6px);
}

/* ─── 内容入场：弹簧 + 模糊焦入，逐块错开 ──────────────── */
.db-content-enter-active .db-item {
  animation: db-rise 0.72s cubic-bezier(0.34, 1.56, 0.64, 1) both;
  animation-delay: var(--delay, 0ms);
}
@keyframes db-rise {
  from {
    opacity: 0;
    transform: translateY(36px) scale(0.95);
    filter: blur(10px);
  }
  60% {
    filter: blur(0px);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
    filter: blur(0px);
  }
}

/* ─── shimmer 动画 ───────────────────────────────────────── */
@keyframes shimmer-move {
  0%   { background-position: -400px 0; }
  100% { background-position:  400px 0; }
}
.shimmer {
  background: linear-gradient(
    90deg,
    rgba(128, 128, 128, 0.08) 25%,
    rgba(128, 128, 128, 0.18) 50%,
    rgba(128, 128, 128, 0.08) 75%
  );
  background-size: 800px 100%;
  animation: shimmer-move 1.5s linear infinite;
  border-radius: 10px;
}
:global(.dark) .shimmer {
  background: linear-gradient(
    90deg,
    rgba(255, 255, 255, 0.04) 25%,
    rgba(255, 255, 255, 0.10) 50%,
    rgba(255, 255, 255, 0.04) 75%
  );
  background-size: 800px 100%;
  animation: shimmer-move 1.5s linear infinite;
}

/* ─── 骨架卡片基础 ──────────────────────────────────────── */
.sk-card {
  border-radius: 18px;
  padding: 22px 24px;
  background: rgba(128, 128, 128, 0.06);
  border: 1px solid rgba(128, 128, 128, 0.08);
}
:global(.dark) .sk-card {
  background: rgba(255, 255, 255, 0.03);
  border-color: rgba(255, 255, 255, 0.05);
}

/* ─── Welcome 骨架 ──────────────────────────────────────── */
.sk-welcome {
  display: flex;
  align-items: center;
  gap: 20px;
}
.sk-avatar {
  width: 70px;
  height: 70px;
  border-radius: 50%;
  flex-shrink: 0;
}
.sk-lines {
  display: flex;
  flex-direction: column;
}
.sk-line {
  display: block;
}

/* ─── Stats 骨架行 ──────────────────────────────────────── */
.sk-stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}
@media (max-width: 1199px) { .sk-stats-row { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 599px)  { .sk-stats-row { grid-template-columns: 1fr; } }

.sk-stat {
  display: flex;
  flex-direction: column;
}
.sk-icon {
  width: 44px;
  height: 44px;
  border-radius: 12px;
}

/* ─── Monitor 骨架 ──────────────────────────────────────── */
.sk-monitor {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.sk-server-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
}
@media (max-width: 1199px) { .sk-server-grid { grid-template-columns: repeat(3, 1fr); } }
@media (max-width: 899px)  { .sk-server-grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 599px)  { .sk-server-grid { grid-template-columns: 1fr; } }

.sk-server {
  height: 120px;
}
</style>
