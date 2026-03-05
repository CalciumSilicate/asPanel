<template>
  <div class="dashboard-container">
    <WelcomeCard :username="user.username || 'admin'" :avatar-url="fullAvatarUrl" />
    <StatsCards :stats="stats" :system-status="systemStatus" :server-percent="serverPercent" />
    <ResourceMonitor
      :servers="runningServersUsage"
      :host-memory-total-mb="hostMemoryTotalMb"
      :show-console="hasRole('ADMIN')"
      @console="goToConsole"
    />
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

const { stats, systemStatus, runningServersUsage, serverPercent, hostMemoryTotalMb } =
  useDashboard(activeGroupIds)

const goToConsole = (serverId: number) => router.push(`/console/${serverId}`)
</script>

<style scoped>
.dashboard-container {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
</style>
