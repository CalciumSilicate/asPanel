<template>
  <el-container class="main-layout">
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
        <!-- 主题切换按钮：放在头像左边 -->
        <el-tooltip :content="isDark ? '切换为日间模式' : '切换为夜间模式'" placement="bottom">
          <el-button
            class="theme-toggle"
            :aria-label="isDark ? '切换为日间模式' : '切换为夜间模式'"
            circle
            text
            @click="toggleTheme"
          >
            <el-icon :size="18">
              <Moon v-if="isDark"/>
              <Sunny v-else/>
            </el-icon>
          </el-button>
        </el-tooltip>

        <el-dropdown @command="handleCommand">
          <span class="user-info">
            <el-avatar size="small" :src="fullAvatarUrl" :icon="UserFilled"/>
            <span class="username">{{ user.username || 'User' }}</span>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="avatar">更换头像</el-dropdown-item>
              <el-dropdown-item command="profile" disabled>个人中心</el-dropdown-item>
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
        <el-scrollbar>
          <el-menu
            :default-active="activeMenu"
            class="el-menu-vertical-demo"
            :collapse="isCollapse"
            :router="true"
        >
          <!-- 基础功能 -->
          <el-menu-item index="/dashboard">
            <el-icon>
              <DataAnalysis/>
            </el-icon>
            <span>仪表盘</span>
          </el-menu-item>
          <el-menu-item index="/chat" v-if="hasRole('USER')">
            <el-icon>
              <ChatDotRound/>
            </el-icon>
            <span>聊天室</span>
          </el-menu-item>
          <el-menu-item index="/servers" v-if="hasRole('USER')">
            <el-icon>
              <Tickets/>
            </el-icon>
            <span>服务器列表</span>
          </el-menu-item>

          <!-- 服务器配置（已移动至工具前，保留此占位空白） -->


          <!-- 插件管理 -->
          <el-sub-menu index="plugin-management" v-if="hasRole('HELPER')">
            <template #title>
              <el-icon>
                <Management/>
              </el-icon>
              <span>插件管理</span>
            </template>
            <el-menu-item index="/server-plugins" v-if="hasRole('HELPER')">
              <el-icon>
                <Cpu/>
              </el-icon>
              <span>服务器插件</span>
            </el-menu-item>
            <el-menu-item index="/mcdr-plugin-explorer" v-if="hasRole('HELPER')">
              <el-icon>
                <Shop/>
              </el-icon>
              <span>联网插件库</span>
            </el-menu-item>
            <el-menu-item index="/db-plugin-manager" v-if="hasRole('ADMIN')">
              <el-icon>
                <Coin/>
              </el-icon>
              <span>数据库插件库</span>
            </el-menu-item>
          </el-sub-menu>

          <!-- Mods 管理 -->
          <el-menu-item index="/tools/mods-manager" v-if="hasRole('ADMIN')">
            <el-icon>
              <Grid/>
            </el-icon>
            <span>Mods管理</span>
          </el-menu-item>


          <!-- 插件配置（原“服务器配置”）移动至工具前 -->
          <el-sub-menu index="server-config" v-if="hasRole('ADMIN')">
            <template #title>
              <el-icon>
                <SetUp/>
              </el-icon>
              <span>插件配置</span>
            </template>
            <el-menu-item index="/server-config/via-version-config">
              <el-icon>
                <Connection/>
              </el-icon>
              <span>Via Version</span>
            </el-menu-item>
            <el-menu-item index="/server-config/velocity-proxy-config">
              <el-icon>
                <Link/>
              </el-icon>
              <span>Velocity Proxy</span>
            </el-menu-item>
            <el-menu-item index="/server-config/prime-backup-config">
              <el-icon>
                <Umbrella/>
              </el-icon>
              <span>Prime Backup</span>
            </el-menu-item>
            <el-menu-item index="/server-config/auto-plugin-reloader-config">
              <el-icon>
                <Refresh/>
              </el-icon>
              <span>Auto Plugin Reloader</span>
            </el-menu-item>
            <el-menu-item index="/server-config/bili-live-helper-config">
              <el-icon>
                <VideoPlay/>
              </el-icon>
              <span>Bili Live Helper</span>
            </el-menu-item>
            <el-menu-item index="/server-config/where-is-config">
              <el-icon>
                <LocationInformation/>
              </el-icon>
              <span>Where Is</span>
            </el-menu-item>
            <el-menu-item index="/server-config/bot-loader" disabled>
              <el-icon>
                <User/>
              </el-icon>
              <span>Bot Loader</span>
            </el-menu-item>
            <el-menu-item index="/server-config/command-set" disabled>
              <el-icon>
                <List/>
              </el-icon>
              <span>Command Set</span>
            </el-menu-item>
            <el-menu-item index="/server-config/crash-restart-config">
              <el-icon>
                <RefreshRight/>
              </el-icon>
              <span>Crash Restart</span>
            </el-menu-item>
            <el-menu-item index="/server-config/join-motd-config">
              <el-icon>
                <Comment/>
              </el-icon>
              <span>joinMOTD</span>
            </el-menu-item>
            <el-menu-item index="/server-config/quick-backup-multi-config">
              <el-icon>
                <DocumentCopy/>
              </el-icon>
              <span>Quick Backup Multi</span>
            </el-menu-item>
          </el-sub-menu>

          <!-- 工具箱 -->
          <el-sub-menu index="tools">
            <template #title>
              <el-icon>
                <Operation/>
              </el-icon>
              <span>工具</span>
            </template>
            <el-menu-item index="/tools/prime-backup" v-if="hasRole('USER')">
              <el-icon>
                <Umbrella/>
              </el-icon>
              <span>Prime Backup</span>
            </el-menu-item>

            <!-- 存档管理 -->
            <el-menu-item index="/tools/archives" v-if="hasRole('HELPER')">
              <el-icon>
                <Files/>
              </el-icon>
              <span>存档管理</span>
            </el-menu-item>
            <el-menu-item index="/tools/superflat" v-if="hasRole('USER')">
              <el-icon>
                <Grid/>
              </el-icon>
              <span>超平坦世界</span>
            </el-menu-item>
            <el-menu-item index="/tools/server-link" v-if="hasRole('USER')">
              <el-icon>
                <Link/>
              </el-icon>
              <span>Server Link</span>
            </el-menu-item>
            <el-menu-item index="/tools/qq-bot" disabled v-if="hasRole('ADMIN')">
              <el-icon>
                <Promotion/>
              </el-icon>
              <span>QQ机器人</span>
            </el-menu-item>
            <el-menu-item index="/tools/world-map" disabled v-if="hasRole('USER')">
              <el-icon>
                <MapLocation/>
              </el-icon>
              <span>世界地图</span>
            </el-menu-item>
            <el-menu-item index="/tools/litematica" v-if="hasRole('USER')">
              <el-icon>
                <Printer/>
              </el-icon>
              <span>Litematica</span>
            </el-menu-item>
            <el-menu-item index="/tools/pcrc" disabled v-if="hasRole('USER')">
              <el-icon>
                <VideoCamera/>
              </el-icon>
              <span>PCRC</span>
            </el-menu-item>
          </el-sub-menu>

          <!-- 系统功能 -->
          <el-menu-item index="/statistics" disabled v-if="hasRole('GUEST')">
            <el-icon>
              <TrendCharts/>
            </el-icon>
            <span>数据统计</span>
          </el-menu-item>
          <el-menu-item index="/player-management" disabled v-if="hasRole('ADMIN')">
            <el-icon>
              <User/>
            </el-icon>
            <span>玩家管理</span>
          </el-menu-item>
          <el-menu-item index="/settings" v-if="hasRole('ADMIN')">
            <el-icon>
              <Setting/>
            </el-icon>
            <span>设置</span>
          </el-menu-item>

        </el-menu>
      </el-scrollbar>
    </el-aside>

    <el-container class="content-wrapper">
      <!-- 主内容区域 -->
      <el-main>
        <router-view v-slot="{ Component, route }">
          <transition name="fade-transform" mode="out-in">
            <component :is="Component" :key="route.fullPath"/>
          </transition>
        </router-view>
      </el-main>
    </el-container>

    <!-- 头像上传对话框组件 -->
    <AvatarUploader
        v-model:visible="avatarDialogVisible"
        @success="handleAvatarSuccess"
    />
  </el-container>
  </el-container>
</template>

<script setup>
import {ref, computed, onMounted, watchEffect} from 'vue';
import {useRoute, useRouter} from 'vue-router';
import { asideCollapsed as isCollapse, asideCollapsing as isCollapsing, toggleAside as toggleCollapse } from '@/store/ui';
import {
  // Original Icons
  UserFilled, Fold, Expand, DataAnalysis, Tickets, TrendCharts,
  ChatDotRound, Setting, Files, Management, Shop, Coin, VideoCamera,
  // New Icons for placeholders
  Cpu, Grid, Umbrella, Tools, Promotion, MapLocation, Connection, User, Printer,
  // Icons for Server Configuration
  SetUp, Link, Refresh, VideoPlay, Key,
  LocationInformation, Place, List, RefreshRight, Comment, DocumentCopy, Operation,
  // Theme toggle icons
  Sunny, Moon
} from '@element-plus/icons-vue';
import {user, fullAvatarUrl, fetchUser, clearUser, refreshAvatar, hasRole} from '@/store/user';
import AvatarUploader from '@/components/AvatarUploader.vue';

// 折叠状态由全局 ui store 提供
// const isCollapse = ref(false);
// const isCollapsing = ref(false); // 折叠过渡前的瞬时隐藏与子菜单上收阶段
const route = useRoute();
const router = useRouter();
const avatarDialogVisible = ref(false);

// 主题状态
const isDark = ref(false);
const THEME_KEY = 'theme';

const applyTheme = (dark) => {
  const root = document.documentElement;
  if (dark) {
    root.classList.add('dark');
    localStorage.setItem(THEME_KEY, 'dark');
  } else {
    root.classList.remove('dark');
    localStorage.setItem(THEME_KEY, 'light');
  }
};

const toggleTheme = () => {
  isDark.value = !isDark.value;
};

const activeMenu = computed(() => {
  const {meta, path} = route;
  // 如果路由的 meta 中有 activeMenu 字段，则用它来高亮父菜单
  if (meta.activeMenu) {
    return meta.activeMenu;
  }
  return path;
});

watchEffect(() => applyTheme(isDark.value));

// 折叠/展开逻辑改为使用全局 ui store 的 toggleAside（此处不再定义同名函数）

const handleCommand = (command) => {
  if (command === 'logout') {
    clearUser();
    localStorage.removeItem('token');
    router.push('/login');
  } else if (command === 'avatar') {
    avatarDialogVisible.value = true;
  }
};

const handleAvatarSuccess = async () => {
  await fetchUser();
  refreshAvatar();
};

onMounted(() => {
  fetchUser();
  // 初始化主题：优先使用本地设置，其次跟随系统
  const saved = localStorage.getItem(THEME_KEY);
  if (saved === 'dark' || saved === 'light') {
    isDark.value = saved === 'dark';
  } else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
    isDark.value = true;
  }
});
</script>

<style scoped>
/* 浅色布局样式（搭配全局主题变量） */
.main-layout {
  height: 100vh;
}

.el-aside {
  transition: width 0.28s var(--ease-standard);
  overflow: hidden; /* 隐藏原生滚动条 */
  display: flex;
  flex-direction: column;
  border-right: none; /* 去掉侧边分割线，更一体 */
}

.sidebar-logo {
  height: 16px; /* 再次缩小顶部空白 */
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-text);
  font-size: 14px;
  font-weight: 600;
  background: transparent;
  border-bottom: none;
}

.sidebar-logo img {
  width: 32px;
  height: 32px;
  margin-right: 12px;
}


/* 折叠动效：aside 宽度与文案淡入淡出（更Q弹） */
.app-aside {
  will-change: width;
  transform: translateZ(0);
  transition: width 0.32s cubic-bezier(.34,1.56,.64,1), box-shadow 0.32s var(--ease-standard);
}
.app-aside.is-collapsed .sidebar-logo span { opacity: 0; transform: translateY(-2px); pointer-events: none; }

/* 菜单文本淡入淡出与位移（配合 Element Plus 折叠） */
:deep(.el-sub-menu__title span),
:deep(.el-menu-item span) {
  transition: opacity 0.26s cubic-bezier(.34,1.56,.64,1) 0.04s, transform 0.26s cubic-bezier(.34,1.56,.64,1) 0.04s;
  will-change: opacity, transform;
}
:deep(.el-menu--collapse .el-sub-menu__title span),
:deep(.el-menu--collapse .el-menu-item span) {
  /* 折叠态下文字应瞬间隐藏 */
  display: none !important;
}

/* 折叠触发瞬间隐藏文字（先隐藏，再执行宽度动画） */
.app-aside.is-collapsing :deep(.el-sub-menu__title span),
.app-aside.is-collapsing :deep(.el-menu-item span) {
  display: none !important;
}

/* 展开中的子菜单在折叠时做“向上回收”动画（Q弹） */
.app-aside :deep(.el-sub-menu.is-opened > .el-menu) {
  max-height: 800px;
  overflow: hidden;
  transform-origin: top center;
  will-change: max-height, transform, opacity;
}
.app-aside.is-collapsing :deep(.el-sub-menu.is-opened > .el-menu) {
  /* 使用关键帧实现“向上回收 + 轻微回弹”效果 */
  animation: submenu-collapse-bounce 380ms cubic-bezier(.34,1.56,.64,1) forwards;
}

@keyframes submenu-collapse-bounce {
  0% {
    max-height: 800px;
    opacity: 1;
    transform: translateY(0) scaleY(1);
  }
  55% {
    transform: translateY(-4px) scaleY(.98);
  }
  85% {
    opacity: 0.12;
    transform: translateY(-9px) scaleY(.94);
  }
  100% {
    max-height: 0;
    opacity: 0;
    transform: translateY(-12px) scaleY(.92);
  }
}

/* 展开动画：菜单与Logo轻微Q弹 */
@keyframes pop-in {
  0% { transform: translateX(-8px) scale(.98); opacity: 0; }
  60% { transform: translateX(3px) scale(1.02); opacity: 1; }
  100% { transform: translateX(0) scale(1); opacity: 1; }
}
.app-aside:not(.is-collapsed) .sidebar-logo span { animation: pop-in 360ms cubic-bezier(.34,1.56,.64,1); }
:deep(.el-menu:not(.el-menu--collapse) .el-sub-menu__title span),
:deep(.el-menu:not(.el-menu--collapse) .el-menu-item span) { animation: pop-in 360ms cubic-bezier(.34,1.56,.64,1); }

/* 折叠按钮轻微动效 */
.collapse-icon { transition: transform 0.2s var(--ease-standard), color 0.2s var(--ease-standard); }
.app-aside.is-collapsed ~ .content-wrapper .collapse-icon { transform: rotate(0deg); }

.el-menu { border-right: none; padding: 8px; }

/* Ensure scrollbar fills remaining space */
.el-scrollbar {
  height: 100%;
}

/* 隐藏侧边栏滚动条（保留滚动功能） */
.app-aside :deep(.el-scrollbar__bar) {
  display: none !important; /* 隐藏 Element Plus 自定义滚动条 */
}
.app-aside :deep(.el-scrollbar__wrap) {
  /* 隐藏各浏览器的原生滚动条，但仍可滚动 */
  scrollbar-width: none;           /* Firefox */
  -ms-overflow-style: none;        /* IE 10+ */
}
.app-aside :deep(.el-scrollbar__wrap::-webkit-scrollbar) {
  width: 0;                        /* Chrome/Safari */
  height: 0;
}

.content-wrapper {
  /* 让父级(main-layout)的统一渐变贯穿到主区域，避免与侧边栏分割处突兀 */
  background-color: transparent;
  height: calc(100vh - var(--el-header-height));
}

.el-header {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 20px;
  height: var(--el-header-height);
  background: transparent !important; /* 让渐变透过顶栏 */
  backdrop-filter: none !important;
  -webkit-backdrop-filter: none !important;
  border-bottom: none !important; /* 更一体 */
}

.header-left { display: flex; align-items: center; height: var(--el-header-height); }
.brand { margin-left: 8px; font-size: 18px; font-weight: 600; color: var(--color-text); line-height: var(--el-header-height); height: var(--el-header-height); display: inline-flex; align-items: center; transition: none; }

.collapse-icon {
  font-size: 22px;
  cursor: pointer;
  height: var(--el-header-height);
  width: 40px; /* 稍加宽，保证图标在折叠后仍居中 */
  display: inline-flex;
  align-items: center;
  justify-content: center;
  line-height: var(--el-header-height);
}
.collapse-icon :deep(svg) { display: block; }

.theme-toggle { margin-right: 8px; }
.header-right .user-info {
  display: flex;
  align-items: center;
  cursor: pointer;
}

.header-right .username {
  margin-left: 10px;
}

.el-main {
  padding: 20px 24px 24px 24px;
}

.fade-transform-leave-active,
.fade-transform-enter-active {
  transition: all 0.35s var(--ease-standard);
}

.fade-transform-enter-from {
  opacity: 0;
  transform: translateY(10px);
}

.fade-transform-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}

/* 降低侧边栏菜单项的高度 */
.el-menu-item,
:deep(.el-sub-menu__title) {
  height: 40px;
  line-height: 40px;
}
</style>
