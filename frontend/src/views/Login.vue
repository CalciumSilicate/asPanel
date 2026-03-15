<template>
  <main class="auth-container" aria-labelledby="login-title">
    <span class="orb orb-1" aria-hidden="true" />
    <span class="orb orb-2" aria-hidden="true" />
    <span class="orb orb-3" aria-hidden="true" />

    <section class="auth-shell">
      <div class="auth-story" aria-hidden="true">
        <p class="story-kicker">AS Panel</p>
        <h1 class="story-title">一个更轻、更稳的服务器控制台。</h1>
        <p class="story-copy">
          在手机和桌面上都能快速查看状态、切换上下文，并回到你最常用的管理流程。
        </p>
        <div class="story-grid">
          <div class="story-panel story-panel-primary">
            <span class="panel-label">Live Ops</span>
            <strong>状态、任务、资源</strong>
            <span>集中在同一条工作流里</span>
          </div>
          <div class="story-stack">
            <div class="story-panel">
              <span class="panel-label">Mobile-first</span>
              <strong>44px+</strong>
              <span>更适合触控操作</span>
            </div>
            <div class="story-panel">
              <span class="panel-label">Ambient UI</span>
              <strong>Glass + Aurora</strong>
              <span>保留已有设计语言</span>
            </div>
          </div>
        </div>
      </div>

      <div class="auth-card">
        <div class="shimmer-line" aria-hidden="true" />

        <div class="card-head">
          <div class="card-icon">
            <el-icon :size="22"><Lock /></el-icon>
          </div>
          <div class="card-title-group">
            <span class="card-eyebrow">欢迎回来</span>
            <h2 id="login-title" class="card-title">登录 AS Panel</h2>
            <p class="card-subtitle">输入账户信息后继续进入控制台。</p>
          </div>
        </div>

        <div class="auth-meta" aria-hidden="true">
          <span class="meta-pill">安全会话</span>
          <span class="meta-pill">深浅主题</span>
          <span class="meta-pill">移动端友好</span>
        </div>

        <el-form :model="form" @submit.prevent="handleLogin" label-position="top" class="auth-form">
          <el-form-item label="用户名" prop="username">
            <el-input
              v-model="form.username"
              placeholder="请输入用户名"
              autocomplete="username"
              size="large"
              :prefix-icon="User"
              aria-label="用户名"
            />
          </el-form-item>
          <el-form-item label="密码" prop="password">
            <el-input
              v-model="form.password"
              type="password"
              placeholder="请输入密码"
              show-password
              autocomplete="current-password"
              size="large"
              :prefix-icon="Lock"
              aria-label="密码"
            />
          </el-form-item>
          <p class="form-help">登录后会自动回到你刚才尝试访问的页面。</p>
          <el-form-item class="submit-item">
            <button class="auth-btn" type="submit" :disabled="loading" :aria-busy="loading">
              <span v-if="loading" class="btn-spinner" />
              <el-icon v-else :size="14"><Right /></el-icon>
              {{ loading ? '登录中…' : '进入控制台' }}
            </button>
          </el-form-item>
          <div class="footer-link">
            <router-link to="/register">还没有账户？<span>立即注册</span></router-link>
          </div>
        </el-form>
      </div>
    </section>
  </main>
</template>

<script setup lang="ts">
import { User, Lock, Right } from '@element-plus/icons-vue';
import { reactive, ref } from 'vue';
import { useRouter } from 'vue-router';
import apiClient from '@/api';
import { ElMessage } from 'element-plus';

const router = useRouter();
const loading = ref(false);
const form = reactive({
  username: '',
  password: '',
});

const handleLogin = async () => {
  if (!form.username || !form.password) {
    ElMessage.error('用户名和密码不能为空');
    return;
  }
  loading.value = true;
  const params = new URLSearchParams();
  params.append('username', form.username);
  params.append('password', form.password);

  try {
    const response = await apiClient.post('/api/token', params);
    localStorage.setItem('token', response.data.access_token);
    ElMessage.success('登录成功！');
    router.push((router.currentRoute.value.query.redirect as string) || '/dashboard');
  } catch (error: any) {
    ElMessage.error('用户名或密码错误');
    console.error('Login failed:', error);
  } finally {
    loading.value = false;
  }
};
</script>

<style scoped>
.auth-container {
  position: relative;
  min-height: 100vh;
  overflow: hidden;
  background:
    radial-gradient(900px 500px at 8% 8%, rgba(229,192,200,0.22) 0%, transparent 60%),
    radial-gradient(900px 500px at 92% 92%, rgba(239,183,186,0.18) 0%, transparent 60%),
    radial-gradient(600px 400px at 80% 10%, rgba(166,200,240,0.14) 0%, transparent 55%),
    var(--color-bg);
  padding: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.auth-shell {
  position: relative;
  z-index: 1;
  width: min(1080px, 100%);
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) minmax(320px, 420px);
  gap: 24px;
  align-items: stretch;
}

.auth-story,
.auth-card {
  position: relative;
  border-radius: 24px;
  backdrop-filter: saturate(160%) blur(20px);
  -webkit-backdrop-filter: saturate(160%) blur(20px);
}

.auth-story {
  overflow: hidden;
  padding: 32px;
  background: linear-gradient(180deg, rgba(255,255,255,0.58), rgba(255,255,255,0.32));
  border: 1px solid rgba(119,181,254,0.14);
  box-shadow:
    0 16px 48px rgba(119,181,254,0.10),
    inset 0 1px 0 rgba(255,255,255,0.92);
}

.auth-story::before {
  content: '';
  position: absolute;
  inset: 0;
  background:
    linear-gradient(rgba(119,181,254,0.08) 1px, transparent 1px),
    linear-gradient(90deg, rgba(119,181,254,0.08) 1px, transparent 1px);
  background-size: 32px 32px;
  mask-image: linear-gradient(180deg, rgba(0,0,0,0.9), transparent 88%);
  pointer-events: none;
}

.story-kicker {
  margin: 0 0 14px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--brand-primary);
}

.story-title {
  margin: 0;
  max-width: 10ch;
  font-size: clamp(2rem, 4vw, 4.5rem);
  line-height: 0.98;
  letter-spacing: -0.05em;
  color: var(--color-text);
}

.story-copy {
  position: relative;
  z-index: 1;
  margin: 18px 0 24px;
  max-width: 34rem;
  font-size: 1rem;
  line-height: 1.7;
  color: var(--color-text-secondary);
}

.story-grid {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: 1.2fr 0.8fr;
  gap: 14px;
}

.story-stack {
  display: grid;
  gap: 14px;
}

.story-panel {
  min-height: 120px;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  gap: 8px;
  padding: 18px;
  border-radius: 20px;
  background: rgba(255,255,255,0.55);
  border: 1px solid rgba(119,181,254,0.16);
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.8);
}

.story-panel-primary {
  min-height: 100%;
  background:
    radial-gradient(circle at 20% 20%, rgba(119,181,254,0.22), transparent 34%),
    radial-gradient(circle at 80% 80%, rgba(239,183,186,0.22), transparent 32%),
    rgba(255,255,255,0.58);
}

.panel-label {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--color-text-secondary);
}

.story-panel strong {
  font-size: 1.125rem;
  line-height: 1.1;
  color: var(--color-text);
}

.story-panel span:last-child {
  font-size: 13px;
  line-height: 1.5;
  color: var(--color-text-secondary);
}

.orb {
  position: absolute;
  border-radius: 50%;
  pointer-events: none;
  filter: blur(80px);
  z-index: 0;
}
.orb-1 {
  width: 420px;
  height: 420px;
  top: -10%;
  left: -8%;
  background: rgba(119,181,254,0.13);
  animation: orb-float 22s ease-in-out infinite alternate;
}
.orb-2 {
  width: 340px;
  height: 340px;
  bottom: -8%;
  right: -6%;
  background: rgba(239,183,186,0.12);
  animation: orb-float 28s ease-in-out infinite alternate-reverse;
}
.orb-3 {
  width: 280px;
  height: 280px;
  top: 55%;
  left: 60%;
  background: rgba(166,200,240,0.10);
  animation: orb-float 20s ease-in-out infinite alternate;
}
@keyframes orb-float {
  from { transform: translate(0, 0); }
  to { transform: translate(30px, 24px); }
}

.auth-card {
  z-index: 1;
  padding: 28px;
  background: rgba(255,255,255,0.74);
  border: 1px solid rgba(119,181,254,0.18);
  box-shadow:
    0 8px 40px rgba(119,181,254,0.13),
    0 2px 8px rgba(0,0,0,0.05),
    inset 0 1px 0 rgba(255,255,255,0.9);
  animation: card-in 0.68s cubic-bezier(0.34,1.56,0.64,1) both;
}

:global(.dark) .auth-story {
  background: linear-gradient(180deg, rgba(15,23,42,0.74), rgba(15,23,42,0.52));
  border-color: rgba(119,181,254,0.12);
  box-shadow:
    0 18px 54px rgba(0,0,0,0.34),
    inset 0 1px 0 rgba(255,255,255,0.04);
}

:global(.dark) .story-panel,
:global(.dark) .story-panel-primary,
:global(.dark) .auth-card {
  background: rgba(15,23,42,0.64);
  border-color: rgba(119,181,254,0.14);
  box-shadow:
    0 8px 48px rgba(0,0,0,0.50),
    inset 0 1px 0 rgba(255,255,255,0.04);
}

@keyframes card-in {
  from { opacity: 0; transform: translateY(32px) scale(0.96); filter: blur(8px); }
  60% { filter: blur(0); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

.shimmer-line {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 1px;
  border-radius: 22px 22px 0 0;
  background: linear-gradient(
    90deg,
    transparent 0%,
    rgba(119,181,254,0.55) 35%,
    rgba(239,183,186,0.50) 65%,
    transparent 100%
  );
}

.card-head {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  margin-bottom: 18px;
}

.card-icon {
  width: 48px;
  height: 48px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: rgba(119,181,254,0.12);
  color: #77B5FE;
  box-shadow: 0 0 0 1px rgba(119,181,254,0.20);
}

.card-title-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.card-eyebrow {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--brand-primary);
}

.card-title {
  margin: 0;
  font-size: clamp(1.75rem, 4vw, 2.25rem);
  font-weight: 800;
  line-height: 1;
  letter-spacing: -0.04em;
  color: var(--color-text);
}

.card-subtitle {
  margin: 0;
  font-size: 14px;
  line-height: 1.6;
  color: var(--color-text-secondary);
}

.auth-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 22px;
}

.meta-pill {
  min-height: 32px;
  padding: 0 12px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text-secondary);
  background: rgba(119,181,254,0.08);
  border: 1px solid rgba(119,181,254,0.14);
}

.auth-form :deep(.el-form-item__label) {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text);
  padding-bottom: 6px;
}

.auth-form :deep(.el-input__wrapper) {
  min-height: 48px;
  border-radius: 14px;
  border: 1px solid var(--color-border);
  background: rgba(255,255,255,0.66);
  box-shadow: none;
  transition: border-color 0.18s ease, box-shadow 0.18s ease, background 0.18s ease;
}

:global(.dark) .auth-form :deep(.el-input__wrapper) {
  background: rgba(15,23,42,0.54);
  border-color: rgba(119,181,254,0.18);
}

.auth-form :deep(.el-input__wrapper:hover) {
  border-color: rgba(119,181,254,0.45);
}

.auth-form :deep(.el-input__wrapper.is-focus) {
  border-color: #77B5FE;
  background: rgba(255,255,255,0.88);
  box-shadow: 0 0 0 4px rgba(119,181,254,0.14);
}

:global(.dark) .auth-form :deep(.el-input__wrapper.is-focus) {
  background: rgba(15,23,42,0.82);
  box-shadow: 0 0 0 4px rgba(119,181,254,0.18);
}

.form-help {
  margin: -2px 0 18px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--color-text-secondary);
}

.submit-item {
  margin-top: 6px;
  margin-bottom: 4px;
}

.submit-item :deep(.el-form-item__content) {
  display: block;
}

.auth-btn {
  width: 100%;
  min-height: 48px;
  border: none;
  border-radius: 14px;
  cursor: pointer;
  font-size: 15px;
  font-weight: 700;
  color: #08101d;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  background: linear-gradient(135deg, #77B5FE 0%, #a78bfa 52%, #EFB7BA 100%);
  box-shadow: 0 10px 28px rgba(119,181,254,0.30);
  transition: transform 0.22s cubic-bezier(0.34,1.56,0.64,1), box-shadow 0.22s ease;
}

.auth-btn:hover:not(:disabled) {
  transform: translateY(-2px) scale(1.01);
  box-shadow: 0 14px 34px rgba(119,181,254,0.38);
}

.auth-btn:active:not(:disabled) {
  transform: scale(0.98);
  box-shadow: 0 4px 14px rgba(119,181,254,0.24);
}

.auth-btn:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

.btn-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(8,16,29,0.22);
  border-top-color: #08101d;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
  flex-shrink: 0;
}
@keyframes spin { to { transform: rotate(360deg); } }

.footer-link {
  text-align: right;
  font-size: 13px;
  color: var(--color-text-secondary);
  margin-top: 16px;
}

.footer-link a {
  color: var(--color-text-secondary);
  text-decoration: none;
  transition: color 0.18s ease;
}

.footer-link a span {
  color: #77B5FE;
  font-weight: 600;
}

.footer-link a:hover span {
  text-decoration: underline;
}

@media (max-width: 960px) {
  .auth-shell {
    grid-template-columns: 1fr;
    max-width: 560px;
  }

  .auth-story {
    padding: 24px;
  }

  .story-title {
    max-width: 14ch;
  }

  .story-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .auth-container {
    padding: 14px;
    align-items: stretch;
  }

  .auth-shell {
    gap: 14px;
    align-content: center;
  }

  .auth-story,
  .auth-card {
    border-radius: 20px;
  }

  .auth-story,
  .auth-card {
    padding: 20px;
  }

  .story-title {
    font-size: 2.5rem;
  }

  .card-head {
    gap: 12px;
  }

  .card-icon {
    width: 44px;
    height: 44px;
  }

  .auth-meta {
    margin-bottom: 18px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .orb,
  .auth-card,
  .btn-spinner {
    animation: none !important;
  }
}
</style>
