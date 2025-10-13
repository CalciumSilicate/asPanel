<!-- src/views/Login.vue -->
<template>
  <div class="auth-container">
    <el-card class="auth-card">
      <template #header>
        <div class="card-title">
          <h3>AS Panel 登录</h3>
          <span>欢迎使用服务器管理面板</span>
        </div>
      </template>
      <el-form :model="form" @submit.prevent="handleLogin" label-position="top">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" placeholder="请输入用户名" autocomplete="username" size="large"
                    :prefix-icon="User"></el-input>
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="form.password" type="password" placeholder="请输入密码" show-password
                    autocomplete="current-password" size="large" :prefix-icon="Lock"></el-input>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" native-type="submit" style="width: 100%;" :loading="loading" size="large">
            {{ loading ? '登录中...' : '登 录' }}
          </el-button>
        </el-form-item>
        <el-form-item>
          <div class="footer-link">
            <router-link to="/register">还没有账户？立即注册</router-link>
          </div>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import {User, Lock} from '@element-plus/icons-vue';
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

.card-title { text-align: center; }
.card-title h3 { margin: 0 0 6px 0; }
.card-title span { font-size: 14px; color: var(--color-text-secondary); }

.footer-link { width: 100%; text-align: right; font-size: 14px; }
.footer-link a { color: var(--brand-primary); text-decoration: none; }
</style>
