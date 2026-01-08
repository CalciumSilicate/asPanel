<!-- src/views/Register.vue -->
<template>
  <div class="auth-container">
    <el-card class="auth-card">
      <template #header>
        <div class="card-title">
          <h3>注册 AS Panel 账户</h3>
          <span>快速开始您的服务器管理之旅</span>
        </div>
      </template>
      <el-form :model="form" @submit.prevent="handleRegister" label-position="top">
        <el-form-item label="用户名">
          <el-input v-model="form.username" placeholder="请输入用户名" size="large" :prefix-icon="User" autocomplete="username"></el-input>
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" placeholder="请输入密码" show-password size="large" :prefix-icon="Lock" autocomplete="new-password"></el-input>
        </el-form-item>
        <el-form-item label="确认密码">
          <el-input v-model="form.confirmPassword" type="password" placeholder="请再次输入密码" show-password size="large" :prefix-icon="Lock" autocomplete="new-password"></el-input>
        </el-form-item>
        <el-form-item label="QQ">
          <el-input v-model="form.qq" placeholder="请输入 QQ 号（纯数字）" size="large"></el-input>
        </el-form-item>
        <el-form-item label="邮箱（可选）">
          <el-input v-model="form.email" placeholder="请输入邮箱" size="large" autocomplete="email"></el-input>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" native-type="submit" style="width: 100%;" :loading="loading" size="large">
            {{ loading ? '注册中...' : '注 册' }}
          </el-button>
        </el-form-item>
        <el-form-item>
          <div class="footer-link">
            <router-link to="/login">已有账户？立即登录</router-link>
          </div>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { User, Lock } from '@element-plus/icons-vue';
// 逻辑代码完全不变
import {reactive, ref} from 'vue';
import {useRouter} from 'vue-router';
import apiClient from '@/api';
import {ElMessage} from 'element-plus';

const router = useRouter();
const loading = ref(false);
const form = reactive({
  username: '',
  password: '',
  confirmPassword: '',
  qq: '',
  email: '',
});

const handleRegister = async () => {
  const username = (form.username || '').trim();
  const qq = (form.qq || '').trim();
  const email = (form.email || '').trim();

  if (!username || !form.password || !form.confirmPassword) {
    ElMessage.error('请填写用户名、密码与确认密码');
    return;
  }
  if (form.password !== form.confirmPassword) {
    ElMessage.error('两次输入的密码不一致');
    return;
  }
  if (qq && !/^\d+$/.test(qq)) {
    ElMessage.error('QQ 必须为纯数字');
    return;
  }

  loading.value = true;
  try {
    await apiClient.post('/api/users/register', {
      username,
      password: form.password,
      qq: qq || undefined,
      email: email || undefined,
    });
    ElMessage.success('注册成功！将跳转至登录页。');
    router.push('/login');
  } catch (error: any) {
    if (error.response && error.response.data && error.response.data.detail) {
      ElMessage.error(error.response.data.detail);
    } else {
      ElMessage.error('注册失败，请稍后重试');
    }
    console.error('Registration failed:', error);
  } finally {
    loading.value = false;
  }
};
</script>

<style scoped>
.auth-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  background: radial-gradient(1200px 600px at 10% 10%, var(--brand-soft) 0%, transparent 50%),
              radial-gradient(1200px 600px at 90% 90%, var(--brand-accent) 0%, transparent 55%),
              var(--color-bg);
  padding: 24px;
}

.auth-card {
  width: 420px;
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-md);
  animation: card-in .5s var(--ease-standard) both;
}

@keyframes card-in {
  from { opacity: 0; transform: translateY(12px) scale(.98); }
  to   { opacity: 1; transform: translateY(0)     scale(1); }
}
.card-title {
  text-align: center;
}
.card-title h3 {
  margin: 0 0 5px 0;
}
.card-title span {
  font-size: 14px;
  color: var(--color-text-secondary);
}

.footer-link {
  width: 100%;
  text-align: right;
  font-size: 14px;
}

.footer-link a {
  color: var(--brand-primary);
  text-decoration: none;
}
</style>
