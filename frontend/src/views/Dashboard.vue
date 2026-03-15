<template>
  <div class="dashboard-container">
    <Transition name="db-skeleton">
      <div v-if="!loaded" class="skeleton-layout" aria-hidden="true">
        <div class="sk-hero">
          <div class="sk-hero-grid shimmer"></div>
          <div class="sk-hero-lines">
            <div class="sk-line shimmer" style="width:90px;height:12px"></div>
            <div class="sk-line shimmer" style="width:220px;height:40px;margin-top:10px"></div>
            <div class="sk-line shimmer" style="width:180px;height:12px;margin-top:10px"></div>
          </div>
        </div>
        <div class="sk-card sk-welcome">
          <div class="sk-avatar shimmer"></div>
          <div class="sk-lines">
            <div class="sk-line shimmer" style="width:60px;height:10px"></div>
            <div class="sk-line shimmer" style="width:160px;height:26px;margin-top:6px"></div>
            <div class="sk-line shimmer" style="width:110px;height:10px;margin-top:8px"></div>
          </div>
        </div>
        <div class="sk-stats-row">
          <div v-for="i in 4" :key="i" class="sk-card sk-stat">
            <div class="sk-icon shimmer"></div>
            <div class="sk-line shimmer" style="width:80px;height:32px;margin-top:16px"></div>
            <div class="sk-line shimmer" style="width:100px;height:10px;margin-top:8px"></div>
            <div class="sk-line shimmer" style="width:100%;height:4px;border-radius:999px;margin-top:16px"></div>
          </div>
        </div>
        <div class="sk-monitor">
          <div class="sk-line shimmer" style="width:120px;height:18px"></div>
          <div class="sk-server-grid">
            <div v-for="i in 4" :key="i" class="sk-card sk-server shimmer"></div>
          </div>
        </div>
      </div>
    </Transition>

    <Transition name="db-content">
      <div v-if="loaded" class="content-layout">
        <section class="dashboard-hero" aria-label="仪表盘概览">
          <div class="hero-grid" aria-hidden="true"></div>
          <div class="hero-copy">
            <div class="hero-kicker">
              <span class="hero-live-dot"></span>
              <span>Dashboard pulse</span>
            </div>
            <h1 class="hero-title">{{ heroTitle }}</h1>
            <p class="hero-subtitle">{{ heroSubtitle }}</p>
          </div>
          <div class="hero-metrics">
            <div class="hero-metric">
              <span class="hero-metric-label">在线率</span>
              <strong>{{ serverPercent }}%</strong>
              <span>{{ stats.running_servers }} / {{ stats.total_servers }} 台在线</span>
            </div>
            <div class="hero-metric">
              <span class="hero-metric-label">主机内存</span>
              <strong>{{ systemStatus.memory_percent }}%</strong>
              <span>{{ systemStatus.memory_used }} / {{ systemStatus.memory_total }} GB</span>
            </div>
            <div class="hero-metric">
              <span class="hero-metric-label">最近刷新</span>
              <strong>{{ lastUpdatedText }}</strong>
              <span>页面可见时每 5 秒同步</span>
            </div>
          </div>
        </section>

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
import { computed, ref, watch } from 'vue'
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

const lastUpdatedText = ref('等待同步')

watch(loaded, (ready) => {
  if (ready) {
    lastUpdatedText.value = new Intl.DateTimeFormat('zh-CN', {
      hour: '2-digit',
      minute: '2-digit',
    }).format(new Date())
  }
})

watch([stats, systemStatus], () => {
  if (loaded.value) {
    lastUpdatedText.value = new Intl.DateTimeFormat('zh-CN', {
      hour: '2-digit',
      minute: '2-digit',
    }).format(new Date())
  }
}, { deep: true })

const heroTitle = computed(() => {
  if (stats.value.running_servers === 0) return '当前没有在线服务器。'
  if (serverPercent.value >= 80) return '大部分服务器都在线。'
  if (serverPercent.value >= 40) return '服务器集群运行平稳。'
  return '现在是低负载时段。'
})

const heroSubtitle = computed(() => {
  if (systemStatus.value.cpu_percent >= 85 || systemStatus.value.memory_percent >= 85) {
    return '建议优先关注主机资源峰值，避免运行中的实例继续堆高负载。'
  }
  return '从这里快速掌握在线率、资源占用与运行中的实例状态。'
})

const goToConsole = (serverId: number) => router.push(`/console/${serverId}`)
</script>

<style scoped>
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

.dashboard-hero,
.sk-hero {
  position: relative;
  overflow: hidden;
  border-radius: 24px;
  padding: 24px;
  min-height: 220px;
}

.dashboard-hero {
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) minmax(280px, 420px);
  gap: 18px;
  background:
    radial-gradient(circle at 12% 18%, rgba(119,181,254,0.18), transparent 24%),
    radial-gradient(circle at 88% 24%, rgba(239,183,186,0.18), transparent 20%),
    linear-gradient(135deg, rgba(255,255,255,0.70), rgba(255,255,255,0.42));
  border: 1px solid rgba(119,181,254,0.16);
  box-shadow:
    0 18px 48px rgba(119,181,254,0.10),
    inset 0 1px 0 rgba(255,255,255,0.88);
}

:global(.dark) .dashboard-hero {
  background:
    radial-gradient(circle at 12% 18%, rgba(119,181,254,0.24), transparent 24%),
    radial-gradient(circle at 88% 24%, rgba(239,183,186,0.16), transparent 20%),
    linear-gradient(135deg, rgba(15,23,42,0.82), rgba(15,23,42,0.62));
  border-color: rgba(119,181,254,0.12);
  box-shadow:
    0 18px 54px rgba(0,0,0,0.36),
    inset 0 1px 0 rgba(255,255,255,0.04);
}

.hero-grid,
.sk-hero-grid {
  position: absolute;
  inset: 0;
  pointer-events: none;
  background:
    linear-gradient(rgba(119,181,254,0.08) 1px, transparent 1px),
    linear-gradient(90deg, rgba(119,181,254,0.08) 1px, transparent 1px);
  background-size: 30px 30px;
  mask-image: radial-gradient(circle at center, rgba(0,0,0,0.92), transparent 85%);
}

.hero-copy,
.hero-metrics {
  position: relative;
  z-index: 1;
}

.hero-copy {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 14px;
}

.hero-kicker {
  width: fit-content;
  min-height: 34px;
  padding: 0 12px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--brand-primary);
  background: rgba(119,181,254,0.10);
  border: 1px solid rgba(119,181,254,0.16);
}

.hero-live-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: linear-gradient(135deg, #77B5FE, #EFB7BA);
  box-shadow: 0 0 14px rgba(119,181,254,0.55);
}

.hero-title {
  margin: 0;
  max-width: 12ch;
  font-size: clamp(2.4rem, 5vw, 4.8rem);
  line-height: 0.95;
  letter-spacing: -0.06em;
  color: var(--color-text);
}

.hero-subtitle {
  margin: 0;
  max-width: 42rem;
  font-size: 1rem;
  line-height: 1.7;
  color: var(--color-text-secondary);
}

.hero-metrics {
  display: grid;
  gap: 12px;
  align-content: end;
}

.hero-metric {
  min-height: 72px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 4px;
  padding: 16px 18px;
  border-radius: 18px;
  background: rgba(255,255,255,0.50);
  border: 1px solid rgba(119,181,254,0.14);
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.82);
}

:global(.dark) .hero-metric {
  background: rgba(15,23,42,0.56);
  border-color: rgba(119,181,254,0.12);
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.04);
}

.hero-metric-label {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--color-text-secondary);
}

.hero-metric strong {
  font-size: 1.6rem;
  line-height: 1;
  letter-spacing: -0.04em;
  color: var(--color-text);
}

.hero-metric span:last-child {
  font-size: 13px;
  line-height: 1.5;
  color: var(--color-text-secondary);
}

.sk-hero {
  background: rgba(128, 128, 128, 0.06);
  border: 1px solid rgba(128, 128, 128, 0.08);
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
}

.sk-hero-lines {
  position: relative;
  z-index: 1;
}

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

.db-content-enter-active .db-item,
.db-content-enter-active .dashboard-hero {
  animation: db-rise 0.72s cubic-bezier(0.34, 1.56, 0.64, 1) both;
  animation-delay: var(--delay, 0ms);
}

.dashboard-hero {
  --delay: 0ms;
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

@keyframes shimmer-move {
  0% { background-position: -400px 0; }
  100% { background-position: 400px 0; }
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

.sk-card {
  border-radius: 18px;
  padding: 22px 24px;
  background: rgba(128, 128, 128, 0.06);
  border: 1px solid rgba(128, 128, 128, 0.08);
}
:global(.dark) .sk-card,
:global(.dark) .sk-hero {
  background: rgba(255, 255, 255, 0.03);
  border-color: rgba(255, 255, 255, 0.05);
}

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

.sk-stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}
@media (max-width: 1199px) { .sk-stats-row { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 599px) { .sk-stats-row { grid-template-columns: 1fr; } }

.sk-stat {
  display: flex;
  flex-direction: column;
}
.sk-icon {
  width: 44px;
  height: 44px;
  border-radius: 12px;
}

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
@media (max-width: 899px) { .sk-server-grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 599px) { .sk-server-grid { grid-template-columns: 1fr; } }

.sk-server {
  height: 120px;
}

@media (max-width: 960px) {
  .dashboard-hero {
    grid-template-columns: 1fr;
  }

  .hero-title {
    max-width: 14ch;
  }
}

@media (max-width: 640px) {
  .dashboard-hero,
  .sk-hero {
    padding: 18px;
    border-radius: 20px;
    min-height: 0;
  }

  .hero-title {
    font-size: 2.5rem;
  }

  .hero-metrics {
    grid-template-columns: 1fr;
  }
}

@media (prefers-reduced-motion: reduce) {
  .db-content-enter-active .db-item,
  .db-content-enter-active .dashboard-hero,
  .shimmer {
    animation: none !important;
  }
}
</style>
