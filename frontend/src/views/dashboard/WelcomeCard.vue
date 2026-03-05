<template>
  <el-card shadow="never" class="welcome-card">
    <div class="welcome-content">
      <el-avatar :size="70" :src="avatarUrl" :icon="UserFilled" />
      <div class="welcome-text">
        <div class="title">欢迎回来, {{ username }}!</div>
        <div class="subtitle">这是服务器状态总览。</div>
      </div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { UserFilled } from '@element-plus/icons-vue'

defineProps<{
  username: string
  avatarUrl: string | undefined
}>()
</script>

<style scoped>
.welcome-content {
  display: flex;
  align-items: center;
  gap: 20px;
}
.welcome-text .title {
  font-size: 20px;
  font-weight: 500;
  margin-bottom: 10px;
}
.welcome-text .subtitle {
  color: var(--el-text-color-secondary);
}
</style>
