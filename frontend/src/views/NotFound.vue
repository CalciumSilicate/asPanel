<template>
  <div class="not-found">
    <div class="not-found-content">
      <div class="code">404</div>
      <div class="title">页面不存在</div>
      <div class="desc">您访问的页面不存在，请检查地址是否正确。</div>
      <el-button type="primary" @click="router.push('/dashboard')">返回仪表盘</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
const router = useRouter()
</script>

<style scoped>
.not-found {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100vh;
}
.not-found-content {
  text-align: center;
}
.code {
  font-size: 96px;
  font-weight: 700;
  line-height: 1;
  color: var(--el-color-primary);
  margin-bottom: 16px;
}
.title {
  font-size: 24px;
  font-weight: 600;
  margin-bottom: 8px;
}
.desc {
  color: var(--el-text-color-secondary);
  margin-bottom: 24px;
}
</style>
