<template>
  <el-container class="main-layout">
    <!-- 背景动态光球 -->
    <div class="bg-orbs" aria-hidden="true">
      <span class="orb orb-1"></span>
      <span class="orb orb-2"></span>
      <span class="orb orb-3"></span>
      <span class="orb orb-4"></span>
    </div>
    <!-- 顶栏（跨全宽） -->
    <el-header class="app-header">
      <div class="header-left">
        <el-icon class="collapse-icon" @click="toggleCollapse">
          <Fold v-if="!isCollapse"/>
          <Expand v-else/>
        </el-icon>
        <span class="brand" v-show="!isCollapse">AS Panel</span>
      </div>
      <div class="header-right">
        <!-- Group Context Selector: 只对非平台管理员显示 -->
        <div class="group-selector" v-if="user.id && !isPlatformAdmin && user.group_permissions.length > 0">
          <el-select
            :model-value="activeGroupIds[0]"
            @update:model-value="(val: number | undefined) => activeGroupIds = val ? [val] : []"
            placeholder="选择上下文"
            style="width: 180px;"
          >
            <el-option
              v-for="perm in user.group_permissions"
              :key="perm.group_id"
              :label="perm.group_name || `Group ${perm.group_id}`"
              :value="perm.group_id"
            >
              <span style="float: left">{{ perm.group_name || `Group ${perm.group_id}` }}</span>
              <span style="float: right; color: var(--el-text-color-secondary); font-size: 12px; margin-left: 10px;">{{ perm.role }}</span>
            </el-option>
          </el-select>
        </div>

        <TransfersDropdown />
        <TasksDropdown />

        <el-button
          class="theme-toggle"
          aria-label="切换主题"
          :title="isDark ? '浅色模式' : '深色模式'"
          circle
          text
          @click="toggleTheme"
        >
          <el-icon :size="18">
            <Sunny v-if="isDark" />
            <Moon v-else />
          </el-icon>
        </el-button>

        <el-dropdown @command="handleCommand">
          <span class="user-info">
            <el-avatar size="small" :src="fullAvatarUrl" :icon="UserFilled"/>
            <span class="username">{{ user.username || 'User' }}</span>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="profile">个人中心</el-dropdown-item>
              <el-dropdown-item command="logout" divided>注销</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </el-header>

    <el-container class="content-wrapper">
      <!-- 侧边栏 -->
      <el-aside :width="isCollapse ? '64px' : '220px'" class="app-aside" :class="{ 'is-collapsed': isCollapse, 'is-collapsing': isCollapsing }">
        <div class="sidebar-logo"></div>
        <el-scrollbar always>
          <el-menu
            :default-active="activeMenu"
            class="el-menu-vertical-demo"
            :collapse="isCollapse"
            :router="true"
            @select="handleMenuSelect"
        >
          <template v-for="entry in visibleMenu" :key="entry.type === 'item' ? entry.path : entry.key">
            <el-menu-item
              v-if="entry.type === 'item'"
              :index="entry.path"
              :disabled="entry.disabled ?? false"
            >
              <el-icon><component :is="entry.icon" /></el-icon>
              <span>{{ entry.label }}</span>
            </el-menu-item>
            <el-sub-menu v-else :index="entry.key">
              <template #title>
                <el-icon><component :is="entry.icon" /></el-icon>
                <span>{{ entry.label }}</span>
              </template>
              <el-menu-item
                v-for="child in entry.children"
                :key="child.path"
                :index="child.path"
                :disabled="child.disabled ?? false"
              >
                <el-icon><component :is="child.icon" /></el-icon>
                <span>{{ child.label }}</span>
              </el-menu-item>
            </el-sub-menu>
          </template>
        </el-menu>
      </el-scrollbar>
    </el-aside>

    <el-container class="content-wrapper">
      <!-- 主内容区域 -->
      <el-main>
        <div class="route-stage">
          <router-view v-slot="{ Component, route }">
            <transition name="fade-transform" mode="out-in">
              <div :key="route.fullPath" class="route-page">
                <component :is="Component" />
              </div>
            </transition>
          </router-view>
        </div>
      </el-main>
    </el-container>

    <!-- 头像上传对话框组件（已移至个人中心页面） -->


  </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, nextTick, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useUiStore } from '@/store/ui';
import { useUserStore } from '@/store/user';
import { isDark, toggleTheme } from '@/store/theme'
import { useTasksStore } from '@/store/tasks'
import { storeToRefs } from 'pinia'
import type { Task } from '@/store/tasks'
import { UserFilled, Fold, Expand, Moon, Sunny } from '@element-plus/icons-vue';
import { ElNotification } from 'element-plus'
import { cancelPendingRequests } from '@/api'
import { SIDEBAR_MENU, type MenuLeaf, type MenuGroup } from '@/menu'
import TasksDropdown from './TasksDropdown.vue'
import TransfersDropdown from './TransfersDropdown.vue'

const route = useRoute();
const router = useRouter();

const uiStore = useUiStore()
const { asideCollapsed: isCollapse, asideCollapsing: isCollapsing } = storeToRefs(uiStore)
const toggleCollapse = uiStore.toggleAside

// Pause all expensive paint work while the sidebar is animating
watch(isCollapsing, (v) => {
  document.documentElement.classList.toggle('aside-animating', v)
})

const userStore = useUserStore()
const user = userStore.user
const { fullAvatarUrl, activeGroupIds, isPlatformAdmin, isOwner } = storeToRefs(userStore)
const { fetchUser, clearUser, hasRole } = userStore

const isItemVisible = (item: MenuLeaf): boolean => {
  if (item.requiresOwner && !isOwner.value) return false
  if (item.requiresPlatformAdmin && !isPlatformAdmin.value) return false
  if (item.requiredRole && !hasRole(item.requiredRole)) return false
  return true
}

const visibleMenu = computed(() => {
  return SIDEBAR_MENU.flatMap((entry): Array<MenuLeaf | MenuGroup> => {
    if (entry.type === 'item') return isItemVisible(entry) ? [entry] : []
    const children = entry.children.filter(isItemVisible)
    if (children.length === 0) return []
    const groupVisible = !entry.requiredRole || hasRole(entry.requiredRole)
    return groupVisible ? [{ ...entry, children }] : []
  })
})

const tasksStore = useTasksStore()
const { fetchTasks, connectTasksSocket, disconnectTasksSocket, onTaskEvent } = tasksStore

const TASK_TYPE_LABELS: Record<string, string> = {
  DOWNLOAD: '下载',
  CREATE_ARCHIVE: '创建存档',
  UPLOAD_ARCHIVE: '上传存档',
  RESTORE_ARCHIVE: '恢复存档',
  IMPORT: '导入服务器',
  CREATE_SERVER: '创建服务器',
  DELETE_SERVER: '删除服务器',
  COMBINED: '组合任务',
  INSTALL_MOD: '安装模组',
  COPY_MODS: '复制模组',
  UPLOAD_MOD: '上传模组',
  CHECK_MOD_UPDATES: '检查模组更新',
  LITEMATIC_UPLOAD: '上传投影',
  LITEMATIC_GENERATE: '生成命令',
}

const taskTitle = (t: Partial<Task>): string => t?.name || TASK_TYPE_LABELS[t?.type ?? ''] || '任务'
const taskDesc = (t: Partial<Task>): string => t?.error || t?.message || ''

// 右上角合并通知：新增/完成/失败
const NOTIFY_WINDOW_MS = 4500
interface ToastBucket { count: number; version: number; handle: ReturnType<typeof ElNotification> | null; timer: ReturnType<typeof setTimeout> | null }
interface ToastOpts { title: string; type: 'info' | 'success' | 'error'; single: string; multi: (n: number) => string }
const toastBuckets: Record<string, ToastBucket> = {
  created: { count: 0, version: 0, handle: null, timer: null },
  success: { count: 0, version: 0, handle: null, timer: null },
  failed:  { count: 0, version: 0, handle: null, timer: null },
}

const bumpToast = (bucketKey: string, opts: ToastOpts) => {
  const b = toastBuckets[bucketKey]
  b.count += 1
  b.version += 1
  const v = b.version

  if (b.timer) clearTimeout(b.timer)
  if (b.handle) b.handle.close()

  const message = b.count === 1 ? opts.single : opts.multi(b.count)
  b.handle = ElNotification({
    title: opts.title,
    message,
    type: opts.type,
    duration: 0,
    onClose: () => {
      if (b.version !== v) return
      if (b.timer) clearTimeout(b.timer)
      b.timer = null
      b.handle = null
      b.count = 0
    },
  })
  b.timer = setTimeout(() => {
    if (b.version !== v) return
    try { b.handle?.close() } catch { /* ignore */ }
    b.handle = null
    b.timer = null
    b.count = 0
  }, NOTIFY_WINDOW_MS)
}

const activeMenu = computed(() => {
  const {meta, path} = route;
  // 如果路由的 meta 中有 activeMenu 字段，则用它来高亮父菜单
  if (meta.activeMenu) {
    return meta.activeMenu;
  }
  return path;
});

const handleMenuSelect = () => {
  cancelPendingRequests()
}

// 折叠/展开逻辑改为使用全局 ui store 的 toggleAside（此处不再定义同名函数）

const handleCommand = (command: string) => {
  if (command === 'logout') {
    clearUser();
    localStorage.removeItem('token');
    router.push('/login');
  } else if (command === 'profile') {
    router.push('/profile');
  }
};

let offTaskEvents: (() => void) | null = null
let removeCancelGuard: (() => void) | null = null

// 预加载所有子页面组件，在浏览器空闲时执行
const preloadRouteComponents = () => {
  const componentLoaders = [
    () => import('../views/Dashboard.vue'),
    () => import('../views/ServerList.vue'),
    () => import('../views/MCDRPluginExplorer.vue'),
    () => import('../views/DbPluginExplorer.vue'),
    () => import('../views/ServerPluginManager.vue'),
    () => import('../views/ModsManager.vue'),
    () => import('../views/SuperFlatWorld.vue'),
    () => import('../views/PrimeBackup.vue'),
    () => import('../views/ServerLink.vue'),
    () => import('../views/PlayerManager.vue'),
    () => import('../views/UserManager.vue'),
    () => import('../views/WorldMap.vue'),
    () => import('../views/Litematica.vue'),
    () => import('../views/ChatRoom.vue'),
    () => import('../views/Settings.vue'),
    () => import('../views/ArchiveManagement.vue'),
    () => import('../views/Console.vue'),
    () => import('../views/Statistics.vue'),
    () => import('../views/Profile.vue'),
    // 插件配置页面
    () => import('../views/plugin-config/ViaVersionConfig.vue'),
    () => import('../views/plugin-config/VelocityProxyConfig.vue'),
    () => import('../views/plugin-config/PrimeBackupConfig.vue'),
    () => import('../views/plugin-config/AutoPluginReloaderConfig.vue'),
    () => import('../views/plugin-config/BiliLiveHelperConfig.vue'),
    () => import('../views/plugin-config/WhereIsConfig.vue'),
    () => import('../views/plugin-config/CrashRestartConfig.vue'),
    () => import('../views/plugin-config/JoinMOTDConfig.vue'),
    () => import('../views/plugin-config/QuickBackupMultiConfig.vue'),
  ]

  let index = 0
  const loadNext = () => {
    if (index >= componentLoaders.length) return
    componentLoaders[index]().catch(() => {}) // 静默加载，忽略错误
    index++
    // 使用 requestIdleCallback 或 setTimeout 在空闲时继续加载下一个
    if ('requestIdleCallback' in window) {
      requestIdleCallback(loadNext, { timeout: 2000 })
    } else {
      setTimeout(loadNext, 50)
    }
  }
  // 延迟启动预加载，让当前页面先完成渲染
  setTimeout(loadNext, 500)
}

onMounted(() => {
  removeCancelGuard = router.beforeEach((to, from) => {
    if (to.fullPath !== from.fullPath) cancelPendingRequests()
    return true
  })

  fetchUser();
  fetchTasks().catch(() => {})
  connectTasksSocket()

  offTaskEvents = onTaskEvent((evt) => {
    if (evt.action === 'created') {
      bumpToast('created', {
        title: '新增任务', type: 'info',
        single: `新增 ${taskTitle(evt.task)} 任务：${taskDesc(evt.task)}`,
        multi: (n) => `新增 ${n} 个任务`,
      })
      return
    }
    if (evt.action === 'finished' && evt.task?.status === 'SUCCESS') {
      bumpToast('success', {
        title: '任务完成', type: 'success',
        single: `${taskTitle(evt.task)}：${taskDesc(evt.task)} 已完成`,
        multi: (n) => `完成 ${n} 个任务`,
      })
      return
    }
    if (evt.action === 'finished' && evt.task?.status === 'FAILED') {
      bumpToast('failed', {
        title: '任务失败', type: 'error',
        single: `${taskTitle(evt.task)}：${taskDesc(evt.task)} 失败`,
        multi: (n) => `失败 ${n} 个任务`,
      })
    }
  })

  // 预加载所有子页面组件
  nextTick(() => {
    preloadRouteComponents()
  })
});

onUnmounted(() => {
  try { offTaskEvents?.() } catch { /* ignore */ }
  try {
    removeCancelGuard?.()
  } catch {
    // ignore
  }
  disconnectTasksSocket()
})
</script>

<style scoped>
/* ─── 背景动态光球层 ─────────────────────────────────────── */
.bg-orbs {
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 0;
  overflow: hidden;
}

.orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.45;
  will-change: transform, opacity;
}

.orb-1 {
  width: 520px; height: 520px;
  background: radial-gradient(circle, rgba(119,181,254,0.7), rgba(119,181,254,0) 70%);
  top: -160px; left: -100px;
  animation: orb-drift-1 18s ease-in-out infinite;
}
.orb-2 {
  width: 420px; height: 420px;
  background: radial-gradient(circle, rgba(239,183,186,0.65), rgba(239,183,186,0) 70%);
  top: -80px; right: -80px;
  animation: orb-drift-2 22s ease-in-out infinite;
}
.orb-3 {
  width: 340px; height: 340px;
  background: radial-gradient(circle, rgba(149,117,205,0.4), rgba(149,117,205,0) 70%);
  bottom: 10%; left: 8%;
  animation: orb-drift-3 26s ease-in-out infinite;
}
.orb-4 {
  width: 280px; height: 280px;
  background: radial-gradient(circle, rgba(64,201,198,0.35), rgba(64,201,198,0) 70%);
  bottom: 5%; right: 12%;
  animation: orb-drift-4 20s ease-in-out infinite;
}

@keyframes orb-drift-1 {
  0%,100% { transform: translate(0, 0) scale(1); opacity: 0.45; }
  33%      { transform: translate(60px, 40px) scale(1.08); opacity: 0.55; }
  66%      { transform: translate(-30px, 70px) scale(0.94); opacity: 0.38; }
}
@keyframes orb-drift-2 {
  0%,100% { transform: translate(0, 0) scale(1); opacity: 0.4; }
  40%      { transform: translate(-50px, 55px) scale(1.1); opacity: 0.52; }
  70%      { transform: translate(20px, -30px) scale(0.96); opacity: 0.36; }
}
@keyframes orb-drift-3 {
  0%,100% { transform: translate(0, 0) scale(1); opacity: 0.3; }
  45%      { transform: translate(40px, -45px) scale(1.12); opacity: 0.42; }
  80%      { transform: translate(-20px, 25px) scale(0.92); opacity: 0.25; }
}
@keyframes orb-drift-4 {
  0%,100% { transform: translate(0, 0) scale(1); opacity: 0.28; }
  30%      { transform: translate(-35px, -40px) scale(1.06); opacity: 0.38; }
  65%      { transform: translate(30px, 20px) scale(0.95); opacity: 0.22; }
}

/* 深色模式：光球更鲜艳、更有力 */
:global(.dark) .orb-1 {
  background: radial-gradient(circle, rgba(119,181,254,0.95), rgba(119,181,254,0) 70%);
  filter: blur(65px);
  opacity: 0.62;
}
:global(.dark) .orb-2 {
  background: radial-gradient(circle, rgba(239,183,186,0.88), rgba(239,183,186,0) 70%);
  filter: blur(65px);
  opacity: 0.58;
}
:global(.dark) .orb-3 {
  background: radial-gradient(circle, rgba(167,139,250,0.80), rgba(167,139,250,0) 70%);
  filter: blur(55px);
  opacity: 0.52;
}
:global(.dark) .orb-4 {
  background: radial-gradient(circle, rgba(52,211,153,0.70), rgba(52,211,153,0) 70%);
  filter: blur(55px);
  opacity: 0.46;
}

/* ─── 布局骨架 ─────────────────────────────────────────── */
.main-layout {
  height: 100vh;
  position: relative;
  overflow: hidden;
}

.content-wrapper {
  background-color: transparent;
  height: calc(100vh - var(--el-header-height));
  position: relative;
  z-index: 1;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}

/* ─── 顶栏 ─────────────────────────────────────────────── */
.el-header {
  position: sticky;
  top: 0;
  z-index: 20;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 20px;
  height: var(--el-header-height);
  background: rgba(255,255,255,0.60) !important;
  border-bottom: none !important;
  box-shadow:
    0 1px 0 0 rgba(119,181,254,0.30),
    0 4px 24px rgba(119,181,254,0.10),
    inset 0 -1px 0 rgba(255,255,255,0.8);
}

:global(.dark) .el-header {
  background: rgba(15,23,42,0.72) !important;
  box-shadow:
    0 1px 0 0 rgba(119,181,254,0.20),
    0 4px 32px rgba(0,0,0,0.40),
    inset 0 -1px 0 rgba(119,181,254,0.08);
}

/* 顶栏底部动态扫光线 */
.el-header::after {
  content: '';
  position: absolute;
  bottom: 0; left: 0; right: 0;
  height: 1px;
  background: linear-gradient(
    90deg,
    transparent 0%,
    rgba(119,181,254,0.6) 30%,
    rgba(239,183,186,0.7) 55%,
    rgba(149,117,205,0.5) 75%,
    transparent 100%
  );
  background-size: 200% 100%;
  animation: header-shimmer 6s linear infinite;
}

@keyframes header-shimmer {
  0%   { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* ─── Brand 品牌标题 ────────────────────────────────────── */
.header-left { display: flex; align-items: center; height: var(--el-header-height); }
.header-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.group-selector {
  margin-right: 6px;
}

.group-selector :deep(.el-select__wrapper) {
  min-height: 42px;
  border-radius: 16px;
  background: rgba(255,255,255,0.46);
  border: 1px solid rgba(119,181,254,0.16);
  box-shadow:
    0 10px 24px rgba(119,181,254,0.08),
    inset 0 1px 0 rgba(255,255,255,0.82);
}

:global(.dark) .group-selector :deep(.el-select__wrapper) {
  background: rgba(15,23,42,0.56);
  border-color: rgba(119,181,254,0.12);
  box-shadow:
    0 14px 28px rgba(0,0,0,0.30),
    inset 0 1px 0 rgba(255,255,255,0.04);
}

.brand {
  margin-left: 8px;
  font-size: 18px;
  font-weight: 700;
  letter-spacing: 0.04em;
  line-height: var(--el-header-height);
  height: var(--el-header-height);
  display: inline-flex;
  align-items: center;
  background: linear-gradient(135deg, #77B5FE 0%, #a78bfa 40%, #EFB7BA 80%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  background-size: 200% 200%;
  animation: brand-gradient-shift 8s ease-in-out infinite;
  filter: drop-shadow(0 0 8px rgba(119,181,254,0.45));
  transition: filter 0.3s ease;
}
.brand:hover {
  filter: drop-shadow(0 0 14px rgba(119,181,254,0.80));
}

@keyframes brand-gradient-shift {
  0%,100% { background-position: 0% 50%; }
  50%      { background-position: 100% 50%; }
}

/* ─── 折叠按钮 ──────────────────────────────────────────── */
.collapse-icon {
  font-size: 22px;
  cursor: pointer;
  height: 36px;
  width: 36px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  color: var(--color-text-secondary);
  transition:
    color 0.25s ease,
    background 0.25s ease,
    box-shadow 0.25s ease,
    transform 0.3s cubic-bezier(.34,1.56,.64,1);
}
.collapse-icon:hover {
  color: var(--brand-primary);
  background: rgba(119,181,254,0.10);
  box-shadow: 0 0 0 1px rgba(119,181,254,0.25), 0 0 12px rgba(119,181,254,0.20);
  transform: scale(1.10);
}
.collapse-icon :deep(svg) { display: block; }

/* ─── 主题切换按钮 ──────────────────────────────────────── */
.theme-toggle {
  margin-right: 8px;
  border-radius: 50% !important;
  transition: box-shadow 0.25s ease, transform 0.25s cubic-bezier(.34,1.56,.64,1) !important;
}
.theme-toggle:hover {
  box-shadow: 0 0 0 1px rgba(119,181,254,0.3), 0 0 16px rgba(119,181,254,0.35) !important;
  transform: rotate(20deg) scale(1.1) !important;
}

/* ─── 用户信息区 ────────────────────────────────────────── */
.header-right .user-info {
  display: flex;
  align-items: center;
  cursor: pointer;
  padding: 4px 10px 4px 4px;
  border-radius: 24px;
  transition: background 0.25s ease, box-shadow 0.25s ease;
}
.header-right .user-info:hover {
  background: rgba(119,181,254,0.08);
  box-shadow: 0 0 0 1px rgba(119,181,254,0.20);
}
/* 头像辉光环 */
.header-right .user-info :deep(.el-avatar) {
  box-shadow: 0 0 0 2px rgba(119,181,254,0.4), 0 0 10px rgba(119,181,254,0.22);
  transition: box-shadow 0.3s ease;
}
.header-right .user-info:hover :deep(.el-avatar) {
  box-shadow: 0 0 0 2px rgba(119,181,254,0.7), 0 0 18px rgba(119,181,254,0.45);
}
.header-right .username {
  margin-left: 10px;
  font-weight: 500;
}

/* ─── 侧边栏 ────────────────────────────────────────────── */
.el-aside {
  overflow: hidden;
  display: flex;
  flex-direction: column;
  border-right: none;
  position: relative;
  z-index: 1;
  background: rgba(255,255,255,0.42) !important;
  box-shadow:
    1px 0 0 rgba(119,181,254,0.18),
    4px 0 20px rgba(119,181,254,0.06);
}

:global(.dark) .el-aside {
  background: rgba(15,23,42,0.55) !important;
  box-shadow:
    1px 0 0 rgba(119,181,254,0.12),
    4px 0 24px rgba(0,0,0,0.35);
}

/* 侧边栏右侧动态辉光分割线 */
.app-aside::after {
  content: '';
  position: absolute;
  top: 0; right: 0;
  width: 1px;
  height: 100%;
  background: linear-gradient(
    180deg,
    transparent 0%,
    rgba(119,181,254,0.5) 30%,
    rgba(239,183,186,0.45) 65%,
    transparent 100%
  );
  background-size: 100% 300%;
  animation: sidebar-shimmer 8s ease-in-out infinite;
}

@keyframes sidebar-shimmer {
  0%,100% { background-position: 0 -200%; opacity: 0.6; }
  50%      { background-position: 0 200%; opacity: 1; }
}

.app-aside {
  transform: translateZ(0);
  transition: width 0.30s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.30s var(--ease-standard);
}
.app-aside.is-collapsing {
  will-change: width;
}

/* ─── Logo区域 ──────────────────────────────────────────── */
.sidebar-logo {
  height: 16px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
}

/* ─── 菜单 ──────────────────────────────────────────────── */
.el-menu { border-right: none; padding: 8px; }
.el-scrollbar { height: 100%; }
.app-aside :deep(.el-scrollbar__bar) { opacity: 0.9; }

.el-menu-item,
:deep(.el-sub-menu__title) {
  height: 40px;
  line-height: 40px;
  border-radius: 10px !important;
  margin-bottom: 2px;
  transition:
    background 0.22s ease,
    color 0.22s ease,
    box-shadow 0.22s ease,
    transform 0.2s cubic-bezier(.34,1.56,.64,1) !important;
}

/* hover：左移 + 辉光描边 */
:deep(.el-menu-item:hover),
:deep(.el-sub-menu__title:hover) {
  background: rgba(119,181,254,0.10) !important;
  box-shadow: 0 0 0 1px rgba(119,181,254,0.15), inset 2px 0 0 rgba(119,181,254,0.4) !important;
  transform: translateX(2px);
}

/* 激活：辉光光晕 + 渐变背景 + 左侧高亮条 */
:deep(.el-menu-item.is-active) {
  color: var(--brand-primary) !important;
  background: linear-gradient(
    90deg,
    rgba(119,181,254,0.18) 0%,
    rgba(119,181,254,0.06) 100%
  ) !important;
  box-shadow:
    0 0 0 1px rgba(119,181,254,0.25),
    inset 3px 0 0 var(--brand-primary),
    0 4px 16px rgba(119,181,254,0.20) !important;
}

/* 激活图标脉冲辉光 */
:deep(.el-menu-item.is-active .el-icon) {
  color: var(--brand-primary);
  animation: icon-pulse 3s ease-in-out infinite;
}

@keyframes icon-pulse {
  0%,100% { filter: drop-shadow(0 0 4px rgba(119,181,254,0.5)); }
  50%      { filter: drop-shadow(0 0 10px rgba(119,181,254,0.9)); }
}

/* 暗色激活态 */
:global(.dark) :deep(.el-menu-item.is-active) {
  background: linear-gradient(
    90deg,
    rgba(119,181,254,0.22) 0%,
    rgba(119,181,254,0.06) 100%
  ) !important;
  box-shadow:
    0 0 0 1px rgba(119,181,254,0.30),
    inset 3px 0 0 var(--brand-primary),
    0 4px 24px rgba(119,181,254,0.28) !important;
}

/* 子菜单折叠动画 */
.app-aside :deep(.el-sub-menu.is-opened > .el-menu) {
  max-height: 800px;
  overflow: hidden;
  transform-origin: top center;
  will-change: max-height, transform, opacity;
}
.app-aside.is-collapsing :deep(.el-sub-menu.is-opened > .el-menu) {
  animation: submenu-collapse-bounce 380ms cubic-bezier(.34,1.56,.64,1) forwards;
}

@keyframes submenu-collapse-bounce {
  0%   { max-height: 800px; opacity: 1; transform: translateY(0) scaleY(1); }
  55%  { transform: translateY(-4px) scaleY(.98); }
  85%  { opacity: 0.12; transform: translateY(-9px) scaleY(.94); }
  100% { max-height: 0; opacity: 0; transform: translateY(-12px) scaleY(.92); }
}

/* 菜单文字展开/折叠 */
:deep(.el-sub-menu__title span),
:deep(.el-menu-item span) {
  transition: opacity 0.26s cubic-bezier(.34,1.56,.64,1) 0.04s, transform 0.26s cubic-bezier(.34,1.56,.64,1) 0.04s;
  will-change: opacity, transform;
}
:deep(.el-menu--collapse .el-sub-menu__title span),
:deep(.el-menu--collapse .el-menu-item span),
.app-aside.is-collapsing :deep(.el-sub-menu__title span),
.app-aside.is-collapsing :deep(.el-menu-item span) {
  display: none !important;
}

/* 展开弹入动画 */
@keyframes pop-in {
  0%   { transform: translateX(-8px) scale(.98); opacity: 0; }
  60%  { transform: translateX(3px) scale(1.02); opacity: 1; }
  100% { transform: translateX(0) scale(1); opacity: 1; }
}
.app-aside:not(.is-collapsed) .sidebar-logo span { animation: pop-in 360ms cubic-bezier(.34,1.56,.64,1); }
:deep(.el-menu:not(.el-menu--collapse) .el-sub-menu__title span),
:deep(.el-menu:not(.el-menu--collapse) .el-menu-item span) { animation: pop-in 360ms cubic-bezier(.34,1.56,.64,1); }
.app-aside.is-collapsed .sidebar-logo span { opacity: 0; transform: translateY(-2px); pointer-events: none; }

/* ─── 主内容区 ──────────────────────────────────────────── */
.el-main {
  padding: 20px 24px 24px 24px;
  position: relative;
  min-width: 0;
  min-height: 0;
  overflow-x: hidden;
  overflow-y: auto;
  scrollbar-gutter: stable;
}

.route-stage {
  position: relative;
  min-width: 0;
  min-height: 100%;
  isolation: isolate;
  overflow: hidden;
  overflow: clip;
}

.route-page {
  width: 100%;
  min-width: 0;
  min-height: 100%;
  transform-origin: center top;
  backface-visibility: hidden;
  will-change: transform, opacity, filter;
}

/* ─── 路由切换过渡（blur + scale） ─────────────────────── */
.fade-transform-enter-active {
  transition: opacity 0.22s ease-out, transform 0.22s cubic-bezier(.34,1.56,.64,1), filter 0.22s ease-out;
}
.fade-transform-leave-active {
  transition: opacity 0.18s ease-in, transform 0.18s ease-in, filter 0.18s ease-in;
}
.fade-transform-enter-from {
  opacity: 0;
  transform: translateY(10px) scale(0.99);
  filter: blur(4px);
}
.fade-transform-leave-to {
  opacity: 0;
  transform: translateY(-6px) scale(1.005);
  filter: blur(3px);
}

/* ─── 侧边栏动画期间：暂停所有重绘开销 ──────────────── */
/* Freeze backdrop-filter (biggest single cost) */
:global(.aside-animating) .el-aside {
  -webkit-backdrop-filter: none !important;
  backdrop-filter: none !important;
  background: rgba(240, 246, 255, 0.88) !important;
}
:global(.dark .aside-animating) .el-aside {
  background: rgba(13, 20, 35, 0.92) !important;
}
:global(.aside-animating) .el-header {
  -webkit-backdrop-filter: blur(6px) !important;
  backdrop-filter: blur(6px) !important;
}

/* Pause all continuous paint animations */
:global(.aside-animating) .orb {
  animation-play-state: paused !important;
}
:global(.aside-animating) .app-aside::after {
  animation-play-state: paused !important;
}
:global(.aside-animating) .el-header::after {
  animation-play-state: paused !important;
}
:global(.aside-animating) .brand {
  animation-play-state: paused !important;
  filter: none !important;
}
:global(.aside-animating .el-menu-item.is-active .el-icon) {
  animation: none !important;
  filter: none !important;
}

/* Disable the submenu collapse animation while sidebar itself is animating */
:global(.aside-animating) .app-aside :deep(.el-sub-menu.is-opened > .el-menu) {
  animation: none !important;
  max-height: none !important;
  opacity: 1 !important;
  transform: none !important;
}
</style>
