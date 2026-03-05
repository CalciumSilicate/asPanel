<template>
  <div class="welcome-card">
    <!-- 装饰光晕 -->
    <div class="deco" aria-hidden="true">
      <span class="deco-blob deco-1"></span>
      <span class="deco-blob deco-2"></span>
      <span class="deco-blob deco-3"></span>
    </div>

    <div class="welcome-body">
      <!-- 头像 -->
      <div class="avatar-ring">
        <el-avatar :size="64" :src="avatarUrl" :icon="UserFilled" class="avatar" />
      </div>

      <!-- 文字 -->
      <div class="welcome-text">
        <p class="greeting">{{ greeting }}</p>
        <h1 class="username">{{ username }}</h1>
        <p class="subtitle">这是服务器状态总览</p>
      </div>
    </div>

    <!-- 底部辉光扫线 -->
    <div class="shimmer-line" aria-hidden="true"></div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { UserFilled } from '@element-plus/icons-vue'

defineProps<{
  username: string
  avatarUrl: string | undefined
}>()

const greeting = computed(() => {
  const h = new Date().getHours()
  if (h >= 5  && h < 11) return '早上好,'
  if (h >= 11 && h < 13) return '中午好,'
  if (h >= 13 && h < 18) return '下午好,'
  if (h >= 18 && h < 22) return '晚上好,'
  return '深夜了,'
})
</script>

<style scoped>
/* ─── 卡片容器 ──────────────────────────────────────────── */
.welcome-card {
  position: relative;
  overflow: hidden;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.62);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  backdrop-filter: saturate(180%) blur(20px);
  border: 1px solid rgba(119, 181, 254, 0.22);
  padding: 28px 32px;
  box-shadow:
    0 4px 24px rgba(119, 181, 254, 0.10),
    inset 0 1px 0 rgba(255, 255, 255, 0.85);
  transition: box-shadow 0.3s ease, border-color 0.3s ease;
}
.welcome-card:hover {
  border-color: rgba(119, 181, 254, 0.38);
  box-shadow: 0 8px 40px rgba(119, 181, 254, 0.16), inset 0 1px 0 rgba(255, 255, 255, 0.85);
}
:global(.dark) .welcome-card {
  background: rgba(15, 23, 42, 0.68);
  border-color: rgba(119, 181, 254, 0.14);
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.40), inset 0 1px 0 rgba(255, 255, 255, 0.04);
}

/* ─── 装饰光晕 ──────────────────────────────────────────── */
.deco { position: absolute; inset: 0; pointer-events: none; overflow: hidden; }
.deco-blob {
  position: absolute;
  border-radius: 50%;
  filter: blur(40px);
}
.deco-1 {
  width: 220px; height: 220px;
  background: radial-gradient(circle, rgba(119,181,254,0.30), transparent 70%);
  right: -40px; top: -50px;
}
.deco-2 {
  width: 160px; height: 160px;
  background: radial-gradient(circle, rgba(239,183,186,0.28), transparent 70%);
  right: 120px; bottom: -30px;
}
.deco-3 {
  width: 100px; height: 100px;
  background: radial-gradient(circle, rgba(167,139,250,0.22), transparent 70%);
  right: 60px; top: 20px;
}

/* ─── 内容区 ─────────────────────────────────────────────── */
.welcome-body {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: 24px;
}

/* ─── 头像辉光环 ─────────────────────────────────────────── */
.avatar-ring {
  position: relative;
  flex-shrink: 0;
  border-radius: 50%;
  padding: 3px;
  background: linear-gradient(135deg, #77B5FE, #a78bfa, #EFB7BA, #77B5FE);
  background-size: 300% 300%;
  animation: ring-shift 5s ease-in-out infinite;
}
.avatar-ring::after {
  content: '';
  position: absolute;
  inset: -2px;
  border-radius: 50%;
  background: inherit;
  filter: blur(8px);
  opacity: 0.55;
  z-index: -1;
  animation: ring-shift 5s ease-in-out infinite;
}
@keyframes ring-shift {
  0%,100% { background-position: 0% 50%; }
  50%      { background-position: 100% 50%; }
}
.avatar-ring .avatar { display: block; border-radius: 50%; }

/* ─── 文字区 ─────────────────────────────────────────────── */
.welcome-text { min-width: 0; }
.greeting {
  margin: 0 0 3px;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--el-text-color-secondary);
}
.username {
  margin: 0 0 6px;
  font-size: 28px;
  font-weight: 800;
  line-height: 1.1;
  background: linear-gradient(135deg, #77B5FE 0%, #a78bfa 45%, #EFB7BA 100%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  background-size: 200% 200%;
  animation: text-shift 6s ease-in-out infinite;
}
@keyframes text-shift {
  0%,100% { background-position: 0% 50%; }
  50%      { background-position: 100% 50%; }
}
.subtitle {
  margin: 0;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

/* ─── 底部辉光扫线 ──────────────────────────────────────── */
.shimmer-line {
  position: absolute;
  bottom: 0; left: 0; right: 0;
  height: 2px;
  background: linear-gradient(
    90deg,
    transparent,
    rgba(119,181,254,0.7),
    rgba(239,183,186,0.6),
    rgba(167,139,250,0.5),
    transparent
  );
  background-size: 200% 100%;
  animation: shimmer 5s linear infinite;
}
@keyframes shimmer {
  0%   { background-position:  200% 0; }
  100% { background-position: -200% 0; }
}
</style>
