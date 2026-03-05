<template>
  <el-card shadow="never" class="resource-monitor-card">
    <template #header>
      <div class="card-header">
        <span>资源监控</span>
        <span class="header-hint">仅显示运行中 · 每 5 秒刷新</span>
      </div>
    </template>

    <div v-if="servers.length === 0" class="resource-empty">
      <el-empty description="当前没有正在运行的服务器" />
    </div>
    <el-row v-else :gutter="16" class="resource-grid">
      <el-col
        v-for="server in servers"
        :key="server.id"
        :xs="24" :sm="12" :md="8" :lg="6"
      >
        <ServerUsageCard
          :server="server"
          :host-memory-total-mb="hostMemoryTotalMb"
          :show-console="showConsole"
          @console="emit('console', $event)"
        />
      </el-col>
    </el-row>
  </el-card>
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
.card-header {
  font-weight: bold;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.header-hint {
  font-weight: normal;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.resource-empty { padding: 20px 0; }
.resource-grid { padding: 4px 2px 2px; }
</style>
