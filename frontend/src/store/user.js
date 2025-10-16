// @/store/user.js

import { reactive, computed, ref } from 'vue';
import apiClient from '@/api';

// 存储用户基本信息
export const user = reactive({
  id: null,
  username: '',
  email: '',
  avatar_url: '', // 例如，后端返回 "/avatars/user_1.png"
  role: 'GUEST', // 后端返回的角色：GUEST/USER/HELPER/ADMIN/OWNER
});

// 用于破坏头像缓存的版本号。
const avatarVersion = ref(0);

// 计算属性，生成完整的、带缓存破坏参数的头像 URL
export const fullAvatarUrl = computed(() => {
  if (!user.avatar_url) return undefined
  // 始终使用相对路径（由 Vite 代理或生产反代转发到后端）
  const path = user.avatar_url.startsWith('/') ? user.avatar_url : `/${user.avatar_url}`
  return `${path}?v=${avatarVersion.value}`
});

// 角色等级映射与便捷检查
const ROLE_LEVELS = { GUEST: 0, USER: 1, HELPER: 2, ADMIN: 3, OWNER: 4 };
export const roleLevel = computed(() => ROLE_LEVELS[user.role] ?? 0);
export const hasRole = (required) => {
  const target = ROLE_LEVELS[required] ?? 0;
  return roleLevel.value >= target;
};

// 从后端获取用户信息的函数
export const fetchUser = async () => {
  try {
    const response = await apiClient.get('/api/users/me');
    Object.assign(user, response.data);
  } catch (error) {
    console.error('Failed to fetch user:', error);
    clearUser(); // 获取失败时清空用户信息
  }
};

// 一个专门用于刷新头像的函数
export const refreshAvatar = () => {
  // 核心：更新版本号，这将触发所有使用 fullAvatarUrl 的地方进行响应式更新
  avatarVersion.value++;
};

// 清除用户信息（注销时使用）
export const clearUser = () => {
  user.id = null;
  user.username = '';
  user.email = '';
  user.avatar_url = '';
  avatarVersion.value = 0; // 重置版本号
};
