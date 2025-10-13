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
          <el-input v-model="form.username" placeholder="请输入用户名" size="large" :prefix-icon="User"></el-input>
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" placeholder="请输入密码" show-password size="large" :prefix-icon="Lock"></el-input>
        </el-form-item>
        <el-form-item label="确认密码">
          <el-input v-model="form.confirmPassword" type="password" placeholder="请再次输入密码" show-password size="large" :prefix-icon="Lock"></el-input>
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
});

const handleRegister = async () => {
  if (!form.username || !form.password || !form.confirmPassword) {
    ElMessage.error('所有字段均为必填项');
    return;
  }
  if (form.password !== form.confirmPassword) {
    ElMessage.error('两次输入的密码不一致');
    return;
  }

  loading.value = true;
  try {
    await apiClient.post('/api/users/register', {
      username: form.username,
      password: form.password,
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
  background-image: linear-gradient(to top, #cfd9df 0%, #e2ebf0 100%);
}

.auth-card {
  width: 400px;
  border-radius: 8px;
}
.card-title {
  text-align: center;
}
.card-title h3 {
  margin: 0 0 5px 0;
}
.card-title span {
  font-size: 14px;
  color: #999;
}

.footer-link {
  width: 100%;
  text-align: right;
  font-size: 14px;
}

.footer-link a {
  color: #409eff;
  text-decoration: none;
}
</style>
