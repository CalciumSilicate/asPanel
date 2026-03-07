<!-- src/views/Login.vue -->
<template>
  <div class="auth-container">
    <!-- 氛围光球 -->
    <span class="orb orb-1" aria-hidden="true" />
    <span class="orb orb-2" aria-hidden="true" />
    <span class="orb orb-3" aria-hidden="true" />

    <div class="auth-card">
      <div class="shimmer-line" aria-hidden="true" />

      <!-- 卡片头部 -->
      <div class="card-head">
        <div class="card-icon">
          <el-icon :size="22"><Lock /></el-icon>
        </div>
        <div class="card-title-group">
          <span class="card-title">AS Panel 登录</span>
          <span class="card-subtitle">欢迎使用服务器管理面板</span>
        </div>
      </div>

      <!-- 表单 -->
      <el-form :model="form" @submit.prevent="handleLogin" label-position="top" class="auth-form">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" placeholder="请输入用户名" autocomplete="username" size="large"
                    :prefix-icon="User" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="form.password" type="password" placeholder="请输入密码" show-password
                    autocomplete="current-password" size="large" :prefix-icon="Lock" />
        </el-form-item>
        <el-form-item class="submit-item">
          <button class="auth-btn" type="submit" :disabled="loading">
            <span v-if="loading" class="btn-spinner" />
            <el-icon v-else :size="14"><Right /></el-icon>
            {{ loading ? '登录中…' : '登 录' }}
          </button>
        </el-form-item>
        <div class="footer-link">
          <router-link to="/register">还没有账户？<span>立即注册</span></router-link>
        </div>
      </el-form>
    </div>
  </div>
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
/* ─── 容器 ──────────────────────────────────────────────── */
.auth-container {
  position: relative;
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  overflow: hidden;
  background:
    radial-gradient(900px 500px at 8%  8%,  rgba(229,192,200,0.22) 0%, transparent 60%),
    radial-gradient(900px 500px at 92% 92%, rgba(239,183,186,0.18) 0%, transparent 60%),
    radial-gradient(600px 400px at 80% 10%, rgba(166,200,240,0.14) 0%, transparent 55%),
    var(--color-bg);
  padding: 24px;
}

/* ─── 氛围光球 ──────────────────────────────────────────── */
.orb {
  position: absolute;
  border-radius: 50%;
  pointer-events: none;
  filter: blur(80px);
  z-index: 0;
}
.orb-1 {
  width: 420px; height: 420px;
  top: -10%; left: -8%;
  background: rgba(119,181,254,0.13);
  animation: orb-float 22s ease-in-out infinite alternate;
}
.orb-2 {
  width: 340px; height: 340px;
  bottom: -8%; right: -6%;
  background: rgba(239,183,186,0.12);
  animation: orb-float 28s ease-in-out infinite alternate-reverse;
}
.orb-3 {
  width: 280px; height: 280px;
  top: 55%; left: 60%;
  background: rgba(166,200,240,0.10);
  animation: orb-float 20s ease-in-out infinite alternate;
}
@keyframes orb-float {
  from { transform: translate(0, 0); }
  to   { transform: translate(30px, 24px); }
}

/* ─── 玻璃卡片 ──────────────────────────────────────────── */
.auth-card {
  position: relative;
  z-index: 1;
  width: 420px;
  border-radius: 22px;
  padding: 32px 32px 28px;
  background: rgba(255,255,255,0.72);
  -webkit-backdrop-filter: saturate(160%) blur(20px);
  backdrop-filter: saturate(160%) blur(20px);
  border: 1px solid rgba(119,181,254,0.18);
  box-shadow:
    0 8px 40px rgba(119,181,254,0.13),
    0 2px 8px rgba(0,0,0,0.05),
    inset 0 1px 0 rgba(255,255,255,0.9);
  animation: card-in 0.68s cubic-bezier(0.34,1.56,0.64,1) both;
}
:global(.dark) .auth-card {
  background: rgba(15,23,42,0.62);
  border-color: rgba(119,181,254,0.14);
  box-shadow:
    0 8px 48px rgba(0,0,0,0.50),
    inset 0 1px 0 rgba(255,255,255,0.04);
}

@keyframes card-in {
  from { opacity:0; transform:translateY(32px) scale(0.96); filter:blur(8px); }
  60%  { filter:blur(0); }
  to   { opacity:1; transform:translateY(0) scale(1); }
}

/* ─── shimmer 装饰线 ────────────────────────────────────── */
.shimmer-line {
  position: absolute;
  top: 0; left: 0; right: 0;
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

/* ─── 卡片头部 ──────────────────────────────────────────── */
.card-head {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 28px;
}
.card-icon {
  width: 46px; height: 46px;
  border-radius: 14px;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
  background: rgba(119,181,254,0.12);
  color: #77B5FE;
  box-shadow: 0 0 0 1px rgba(119,181,254,0.20);
}
:global(.dark) .card-icon {
  background: rgba(119,181,254,0.15);
  box-shadow: 0 0 0 1px rgba(119,181,254,0.18), 0 0 16px rgba(119,181,254,0.20);
}
.card-title-group {
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.card-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--color-text);
  letter-spacing: -0.01em;
}
.card-subtitle {
  font-size: 13px;
  color: var(--color-text-secondary);
}

/* ─── 表单 ──────────────────────────────────────────────── */
.auth-form :deep(.el-form-item__label) {
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text);
  padding-bottom: 6px;
}
.auth-form :deep(.el-input__wrapper) {
  border-radius: 10px;
  border: 1px solid var(--color-border);
  background: rgba(255,255,255,0.60);
  box-shadow: none;
  transition: border-color 0.18s ease, box-shadow 0.18s ease, background 0.18s ease;
}
:global(.dark) .auth-form :deep(.el-input__wrapper) {
  background: rgba(15,23,42,0.50);
  border-color: rgba(119,181,254,0.18);
}
.auth-form :deep(.el-input__wrapper:hover) {
  border-color: rgba(119,181,254,0.45);
}
.auth-form :deep(.el-input__wrapper.is-focus) {
  border-color: #77B5FE;
  background: rgba(255,255,255,0.85);
  box-shadow: 0 0 0 4px rgba(119,181,254,0.14);
}
:global(.dark) .auth-form :deep(.el-input__wrapper.is-focus) {
  background: rgba(15,23,42,0.80);
  box-shadow: 0 0 0 4px rgba(119,181,254,0.18);
}

.submit-item {
  margin-top: 8px;
  margin-bottom: 4px;
}
.submit-item :deep(.el-form-item__content) {
  display: block;
}

/* ─── 提交按钮 ──────────────────────────────────────────── */
.auth-btn {
  width: 100%;
  height: 42px;
  border: none;
  border-radius: 12px;
  cursor: pointer;
  font-size: 15px;
  font-weight: 600;
  color: #fff;
  display: flex; align-items: center; justify-content: center; gap: 8px;
  background: linear-gradient(135deg, #77B5FE 0%, #a78bfa 100%);
  box-shadow: 0 4px 16px rgba(119,181,254,0.40);
  transition: transform 0.22s cubic-bezier(0.34,1.56,0.64,1), box-shadow 0.22s ease;
}
.auth-btn:hover:not(:disabled) {
  transform: translateY(-2px) scale(1.02);
  box-shadow: 0 8px 28px rgba(119,181,254,0.55);
}
.auth-btn:active:not(:disabled) {
  transform: scale(0.97);
  box-shadow: 0 2px 10px rgba(119,181,254,0.30);
}
.auth-btn:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

/* loading 旋转圆圈 */
.btn-spinner {
  width: 14px; height: 14px;
  border: 2px solid rgba(255,255,255,0.35);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
  flex-shrink: 0;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* ─── 底部链接 ──────────────────────────────────────────── */
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
  font-weight: 500;
}
.footer-link a:hover span {
  text-decoration: underline;
}
</style>
