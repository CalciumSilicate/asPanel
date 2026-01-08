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
        <!-- Group Context Selector: 只对非平台管理员显示 -->
        <div class="group-selector" v-if="user.id && !isPlatformAdmin && user.group_permissions.length > 0" style="margin-right: 12px;">
          <el-select
            :model-value="activeGroupIds[0]"
            @update:model-value="(val) => activeGroupIds = val ? [val] : []"
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

        <el-dropdown
          trigger="click"
          class="transfers-dropdown"
          placement="bottom-end"
          :popper-options="dropdownPopperOptions"
          :hide-on-click="false"
        >
          <el-badge
            :value="activeTransfersCount"
            :max="99"
            type="primary"
            :hidden="activeTransfersCount === 0"
            class="transfers-badge"
          >
            <el-button
              class="transfers-toggle"
              aria-label="传输"
              title="传输"
              circle
              text
            >
              <el-icon :size="18">
                <Download/>
              </el-icon>
            </el-button>
          </el-badge>
          <template #dropdown>
            <el-dropdown-menu class="transfers-menu">
              <el-dropdown-item class="transfers-menu-actions-item">
                <div class="transfers-menu-actions">
                  <span class="transfers-menu-header">传输</span>
                  <el-button
                    size="small"
                    text
                    :disabled="clearTransfersDisabled"
                    @click.stop="handleClearTransfers"
                  >
                    清除已完成
                  </el-button>
                </div>
              </el-dropdown-item>

              <el-dropdown-item v-for="t in transfers" :key="t.id" class="transfer-menu-item">
                <div class="transfer-row">
                  <div class="transfer-row-header">
                    <span class="transfer-name">
                      <el-icon v-if="t.type === 'upload'" class="transfer-type-icon"><Upload/></el-icon>
                      <el-icon v-else class="transfer-type-icon"><Download/></el-icon>
                      {{ t.title }}
                    </span>
                    <span class="transfer-state">{{ transferStatusLabel(t.status) }}</span>
                    <span class="transfer-percent">{{ transferDisplayPercent(t) }}%</span>
                  </div>
                  <div v-if="transferDesc(t)" class="transfer-row-desc" :title="transferDesc(t)">{{ transferDesc(t) }}</div>
                  <el-progress
                    v-if="t.status === 'TRANSFERRING' || t.status === 'PREPARING'"
                    class="transfer-progress"
                    :class="t.status.toLowerCase()"
                    :percentage="transferProgressPercent(t)"
                    :stroke-width="4"
                    :show-text="false"
                  />
                  <div class="transfer-row-actions" v-if="t.status === 'PREPARING' || t.status === 'TRANSFERRING'">
                    <el-button size="small" text @click.stop="cancelTransfer(t.id)">取消</el-button>
                  </div>
                </div>
              </el-dropdown-item>
              <el-dropdown-item v-if="transfers.length === 0" disabled>暂无传输</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>

        <el-dropdown
          trigger="click"
          class="tasks-dropdown"
          placement="bottom-end"
          :popper-options="dropdownPopperOptions"
          :hide-on-click="false"
        >
          <el-badge
            :value="activeTasksCount"
            :max="99"
            type="danger"
            :hidden="activeTasksCount === 0"
            class="tasks-badge"
          >
            <el-button
              class="tasks-toggle"
              aria-label="后台任务"
              title="后台任务"
              circle
              text
            >
              <el-icon :size="18">
                <Operation/>
              </el-icon>
            </el-button>
          </el-badge>
          <template #dropdown>
            <el-dropdown-menu class="tasks-menu">
              <el-dropdown-item class="tasks-menu-actions-item">
                <div class="tasks-menu-actions">
                  <span class="tasks-menu-header">后台任务</span>
                  <el-button
                    size="small"
                    text
                    :disabled="clearTasksDisabled"
                    @click.stop="handleClearTasks"
                  >
                    {{ clearTasksText }}
                  </el-button>
                </div>
              </el-dropdown-item>
              <el-dropdown-item v-for="t in tasks" :key="t.id" disabled>
                <div class="task-row">
                  <div class="task-row-header">
                    <span class="task-name">{{ taskTitle(t) }}</span>
                    <span class="task-state">{{ statusLabel(t.status) }}</span>
                    <span class="task-percent">{{ displayPercent(t) }}%</span>
                  </div>
                  <div class="task-row-desc" :title="taskDesc(t)">{{ taskDesc(t) }}</div>
                  <el-progress
                    v-if="t.status !== 'PENDING'"
                    class="task-progress"
                    :class="(t.status || '').toLowerCase()"
                    :percentage="progressPercent(t)"
                    :stroke-width="4"
                    :show-text="false"
                    :color="progressColor(t.status)"
                  />
                </div>
              </el-dropdown-item>
              <el-dropdown-item v-if="tasks.length === 0" disabled>暂无任务</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>

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
          <!-- 基础功能 -->
          <el-menu-item index="/dashboard" v-if="hasRole('GUEST')">
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
          <el-menu-item index="/server-groups" v-if="isPlatformAdmin">
            <el-icon>
              <Link/>
            </el-icon>
            <span>服务器组列表</span>
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
            <el-menu-item index="/db-plugin-manager" v-if="isPlatformAdmin">
              <el-icon>
                <Coin/>
              </el-icon>
              <span>数据库插件库</span>
            </el-menu-item>
          </el-sub-menu>

          <!-- Mods 管理 -->
          <el-menu-item index="/tools/mods-manager" v-if="capabilities.canManageMods">
            <el-icon>
              <Grid/>
            </el-icon>
            <span>Mods管理</span>
          </el-menu-item>


          <!-- 插件配置（原“服务器配置”）移动至工具前 -->
          <el-sub-menu index="server-config" v-if="hasRole('HELPER')">
            <template #title>
              <el-icon>
                <SetUp/>
              </el-icon>
              <span>插件配置</span>
            </template>
            <el-menu-item index="/server-config/via-version-config" v-if="hasRole('ADMIN')">
              <el-icon>
                <Connection/>
              </el-icon>
              <span>Via Version</span>
            </el-menu-item>
            <el-menu-item index="/server-config/velocity-proxy-config" v-if="hasRole('ADMIN')">
              <el-icon>
                <Link/>
              </el-icon>
              <span>Velocity Proxy</span>
            </el-menu-item>
            <el-menu-item index="/server-config/prime-backup-config" v-if="hasRole('HELPER')">
              <el-icon>
                <Umbrella/>
              </el-icon>
              <span>Prime Backup</span>
            </el-menu-item>
            <el-menu-item index="/server-config/auto-plugin-reloader-config" v-if="hasRole('HELPER')">
              <el-icon>
                <Refresh/>
              </el-icon>
              <span>Auto Plugin Reloader</span>
            </el-menu-item>
            <el-menu-item index="/server-config/bili-live-helper-config" v-if="hasRole('HELPER')">
              <el-icon>
                <VideoPlay/>
              </el-icon>
              <span>Bili Live Helper</span>
            </el-menu-item>
            <el-menu-item index="/server-config/where-is-config" v-if="hasRole('HELPER')">
              <el-icon>
                <LocationInformation/>
              </el-icon>
              <span>Where Is</span>
            </el-menu-item>
            <el-menu-item index="/server-config/bot-loader" disabled v-if="hasRole('ADMIN')">
              <el-icon>
                <User/>
              </el-icon>
              <span>Bot Loader</span>
            </el-menu-item>
            <el-menu-item index="/server-config/command-set" disabled v-if="hasRole('ADMIN')">
              <el-icon>
                <List/>
              </el-icon>
              <span>Command Set</span>
            </el-menu-item>
            <el-menu-item index="/server-config/crash-restart-config" v-if="hasRole('HELPER')">
              <el-icon>
                <RefreshRight/>
              </el-icon>
              <span>Crash Restart</span>
            </el-menu-item>
            <el-menu-item index="/server-config/join-motd-config" v-if="hasRole('ADMIN')">
              <el-icon>
                <Comment/>
              </el-icon>
              <span>joinMOTD</span>
            </el-menu-item>
            <el-menu-item index="/server-config/quick-backup-multi-config" v-if="hasRole('HELPER')">
              <el-icon>
                <DocumentCopy/>
              </el-icon>
              <span>Quick Backup Multi</span>
            </el-menu-item>
          </el-sub-menu>

          <!-- 工具箱 -->
          <el-sub-menu index="tools" v-if="hasRole('HELPER')">
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
          <el-menu-item index="/statistics" v-if="hasRole('USER')">
            <el-icon>
              <TrendCharts/>
            </el-icon>
            <span>数据统计</span>
          </el-menu-item>
          <el-menu-item index="/players" v-if="isOwner">
            <el-icon>
              <User/>
            </el-icon>
            <span>玩家管理</span>
          </el-menu-item>
          <el-menu-item index="/users" v-if="isOwner">
            <el-icon>
              <User/>
            </el-icon>
            <span>用户管理</span>
          </el-menu-item>
          <el-menu-item index="/settings" v-if="isOwner">
            <el-icon>
              <Setting/>
            </el-icon>
            <span>设置</span>
          </el-menu-item>
          <el-menu-item index="/profile">
            <el-icon>
              <UserFilled/>
            </el-icon>
            <span>个人中心</span>
          </el-menu-item>

        </el-menu>
      </el-scrollbar>
    </el-aside>

    <el-container class="content-wrapper">
      <!-- 主内容区域 -->
      <el-main>
        <router-view v-slot="{ Component, route }">
          <transition name="fade-transform">
            <component :is="Component" :key="route.fullPath"/>
          </transition>
        </router-view>
      </el-main>
    </el-container>

    <!-- 头像上传对话框组件（已移至个人中心页面） -->


  </el-container>
  </el-container>
</template>

<script setup>
import {ref, computed, onMounted, onUnmounted, nextTick} from 'vue';
import {useRoute, useRouter} from 'vue-router';
import { asideCollapsed as isCollapse, asideCollapsing as isCollapsing, toggleAside as toggleCollapse } from '@/store/ui';
import { ElMessage, ElNotification } from 'element-plus'
import {
  // Original Icons
  UserFilled, Fold, Expand, DataAnalysis, Tickets, TrendCharts,
  ChatDotRound, Setting, Files, Management, Shop, Coin, VideoCamera,
  // New Icons for placeholders
  Cpu, Grid, Umbrella, Tools, Promotion, MapLocation, Connection, User, Printer,
  // Icons for Server Configuration
  SetUp, Link, Refresh, VideoPlay, Key,
  LocationInformation, Place, List, RefreshRight, Comment, DocumentCopy, Operation, Download, Upload,
  Moon, Sunny
} from '@element-plus/icons-vue';
import {user, fullAvatarUrl, fetchUser, clearUser, hasRole, activeGroupIds, isPlatformAdmin, capabilities, isOwner} from '@/store/user';
import { isDark, toggleTheme } from '@/store/theme'
import {
  tasks,
  activeTasksCount,
  failedTasksCount,
  successTasksCount,
  fetchTasks,
  connectTasksSocket,
  disconnectTasksSocket,
  onTaskEvent,
  clearTasks,
} from '@/store/tasks'
import {
  transfers,
  activeTransfersCount,
  finishedTransfersCount,
  cancelTransfer,
  clearFinishedTransfers,
} from '@/store/transfers'
import { cancelPendingRequests } from '@/api'


// 折叠状态由全局 ui store 提供
// const isCollapse = ref(false);
// const isCollapsing = ref(false); // 折叠过渡前的瞬时隐藏与子菜单上收阶段
const route = useRoute();
const router = useRouter();

const TASK_TYPE_LABELS = {
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

const taskTitle = (t) => t?.name || TASK_TYPE_LABELS[t?.type] || '任务'
const taskDesc = (t) => t?.error || t?.message || ''

// 进度条颜色：RUNNING 蓝色、FAILED 红色、SUCCESS 绿色、其他信息色
const progressColor = (status) => {
  if (status === 'RUNNING') return 'var(--el-color-primary)';
  if (status === 'FAILED') return 'var(--el-color-danger)';
  if (status === 'SUCCESS') return 'var(--el-color-success)';
  return 'var(--el-color-info)';
};
// Dropdown 的 Popper 配置，防止溢出并靠右展开
const dropdownPopperOptions = {
  modifiers: [
    { name: 'offset', options: { offset: [0, 8] } },
    { name: 'preventOverflow', options: { padding: 8, boundary: 'viewport' } },
    { name: 'flip', options: { fallbackPlacements: ['bottom-end', 'bottom-start', 'top-end', 'top-start'] } },
  ],
};
// 状态中文文案
const statusLabel = (status) => ({
  PENDING: '排队',
  RUNNING: '进行中',
  SUCCESS: '成功',
  FAILED: '失败'
}[status] || status);
// 展示用百分比文案（SUCCESS/FAILED 都显示 100）
const displayPercent = (t) => (t.status === 'SUCCESS' || t.status === 'FAILED') ? 100 : t.progress;
// 实际进度条渲染百分比
const progressPercent = (t) => (t.status === 'SUCCESS' || t.status === 'FAILED') ? 100 : t.progress;

const clearTasksText = computed(() => (failedTasksCount.value > 0 ? '清除失败任务' : '清除已完成任务'))
const clearTasksDisabled = computed(() => failedTasksCount.value === 0 && successTasksCount.value === 0)
const handleClearTasks = async () => {
  if (clearTasksDisabled.value) return
  const status = failedTasksCount.value > 0 ? 'FAILED' : 'SUCCESS'
  try {
    const cleared = await clearTasks(status)
    ElMessage.success(`已清理 ${cleared} 个任务`)
  } catch (e) {
    ElMessage.error(`清理失败: ${e.response?.data?.detail || e.message}`)
  }
}

const clearTransfersDisabled = computed(() => finishedTransfersCount.value === 0)
const handleClearTransfers = () => {
  if (clearTransfersDisabled.value) return
  clearFinishedTransfers()
  ElMessage.success('已清理已完成传输')
}

const transferStatusLabel = (status) => ({
  PREPARING: '准备中',
  TRANSFERRING: '传输中',
  SUCCESS: '完成',
  FAILED: '失败',
  CANCELED: '已取消',
}[status] || status)
const transferDesc = (t) => t?.error || t?.message || ''
const transferDisplayPercent = (t) => (t.status === 'SUCCESS' || t.status === 'FAILED' || t.status === 'CANCELED') ? 100 : (t.progress || 0)
const transferProgressPercent = (t) => (t.status === 'SUCCESS' || t.status === 'FAILED' || t.status === 'CANCELED') ? 100 : (t.progress || 0)

// 右上角合并通知：新增/完成/失败
const NOTIFY_WINDOW_MS = 4500
const toastBuckets = {
  created: { count: 0, version: 0, handle: null, timer: null },
  success: { count: 0, version: 0, handle: null, timer: null },
  failed: { count: 0, version: 0, handle: null, timer: null },
}

const bumpToast = (bucketKey, opts) => {
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
    try {
      b.handle?.close()
    } catch (e) {
      // ignore
    }
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

const handleCommand = (command) => {
  if (command === 'logout') {
    clearUser();
    localStorage.removeItem('token');
    router.push('/login');
  } else if (command === 'profile') {
    router.push('/profile');
  }
};

let offTaskEvents = null
let removeCancelGuard = null

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

  // 预加载所有子页面组件
  nextTick(() => {
    preloadRouteComponents()
  })

  offTaskEvents = onTaskEvent((evt) => {
    if (evt.action === 'created') {
      bumpToast('created', {
        title: '新增任务',
        type: 'info',
        single: `新增 ${taskTitle(evt.task)} 任务：${taskDesc(evt.task)}`,
        multi: (n) => `新增 ${n} 个任务`,
      })
      return
    }
    if (evt.action === 'finished' && evt.task?.status === 'SUCCESS') {
      bumpToast('success', {
        title: '任务完成',
        type: 'success',
        single: `${taskTitle(evt.task)}：${taskDesc(evt.task)} 已完成`,
        multi: (n) => `完成 ${n} 个任务`,
      })
      return
    }
    if (evt.action === 'finished' && evt.task?.status === 'FAILED') {
      bumpToast('failed', {
        title: '任务失败',
        type: 'error',
        single: `${taskTitle(evt.task)}：${taskDesc(evt.task)} 失败`,
        multi: (n) => `失败 ${n} 个任务`,
      })
    }
  })
});

onUnmounted(() => {
  try {
    offTaskEvents?.()
  } catch (e) {
    // ignore
  }
  try {
    removeCancelGuard?.()
  } catch (e) {
    // ignore
  }
  disconnectTasksSocket()
})
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

/* 侧边栏滚动条保持可见（便于定位当前位置） */
.app-aside :deep(.el-scrollbar__bar) { opacity: 0.9; }

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
.header-right { display: flex; align-items: center; }
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

/* 任务按钮样式（小圆按钮） */
.tasks-dropdown { margin-right: 8px; }
.theme-toggle { margin-right: 8px; }

/* 任务下拉菜单内容样式 */
.tasks-menu { width: 460px; max-width: min(560px, 92vw); padding: 6px 0; overflow-x: hidden; box-sizing: border-box; }
/* 允许下拉项内多行布局，并改为块级容器以包裹自定义结构 */
.tasks-menu :deep(.el-dropdown-menu__item) {
  white-space: normal;
  height: auto;
  line-height: 1.4;
  padding: 0 !important;
  display: block !important;
  align-items: initial !important;
}
.tasks-menu-actions { padding: 10px 14px; display: flex; align-items: center; justify-content: space-between; }
.tasks-menu-actions-item { cursor: default; }
.tasks-menu-actions-item:hover { background-color: transparent !important; }
.tasks-menu .tasks-menu-header { font-weight: 600; color: var(--color-text); }
.task-row { padding: 10px 14px; display: block; width: 100%; box-sizing: border-box; }
.task-row-header { display: grid; grid-template-columns: 1fr auto auto; column-gap: 12px; align-items: baseline; margin-bottom: 4px; }
.task-name { font-size: 13px; color: var(--color-text); font-weight: 600; text-align: left; }
.task-state { font-size: 12px; color: var(--el-text-color-secondary); text-align: right; }
.task-percent { font-size: 12px; color: var(--el-text-color-secondary); text-align: right; }
.task-row-desc {
  font-size: 11px;
  color: var(--el-text-color-secondary);
  margin: 2px 0 6px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.task-progress { display: block; width: 96%; margin: 0 auto; }
.task-progress.running :deep(.el-progress-bar__outer) {
  background-color: #4c4d4f; /* 深灰未完成部分 */
}
.task-progress.failed :deep(.el-progress-bar__outer),
.task-progress.failed :deep(.el-progress-bar__inner) {
  background-color: var(--el-color-danger);
}
.tasks-badge :deep(.el-badge__content) { transform: translate(4px, -6px); }

.transfers-dropdown { margin-right: 8px; }
.transfers-menu { width: 420px; max-width: min(520px, 92vw); padding: 6px 0; overflow-x: hidden; box-sizing: border-box; }
.transfers-menu :deep(.el-dropdown-menu__item) {
  white-space: normal;
  height: auto;
  line-height: 1.4;
  padding: 0 !important;
  display: block !important;
  align-items: initial !important;
}
.transfers-menu-actions { padding: 10px 14px; display: flex; align-items: center; justify-content: space-between; }
.transfers-menu-actions-item { cursor: default; }
.transfers-menu-actions-item:hover { background-color: transparent !important; }
.transfers-menu .transfers-menu-header { font-weight: 600; color: var(--color-text); }
.transfer-row { padding: 10px 14px; display: block; width: 100%; box-sizing: border-box; }
.transfer-row-header { display: grid; grid-template-columns: 1fr auto auto; column-gap: 12px; align-items: baseline; margin-bottom: 4px; }
.transfer-name { font-size: 13px; color: var(--color-text); font-weight: 600; text-align: left; display: flex; align-items: center; gap: 4px; }
.transfer-type-icon { font-size: 14px; color: var(--el-text-color-secondary); flex-shrink: 0; }
.transfer-state, .transfer-percent { font-size: 12px; color: var(--el-text-color-secondary); text-align: right; }
.transfer-row-desc { font-size: 11px; color: var(--el-text-color-secondary); margin: 2px 0 6px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.transfer-progress { display: block; width: 96%; margin: 0 auto; }
.transfer-row-actions { display: flex; justify-content: flex-end; padding: 6px 14px 0; }
.transfers-badge :deep(.el-badge__content) { transform: translate(4px, -6px); }

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
  position: relative;
  overflow: hidden;
}

.fade-transform-leave-active,
.fade-transform-enter-active {
  transition: opacity 0.15s ease-out, transform 0.15s ease-out;
}

.fade-transform-leave-active {
  position: absolute;
  width: 100%;
}

.fade-transform-enter-from {
  opacity: 0;
  transform: translateY(6px);
}

.fade-transform-leave-to {
  opacity: 0;
}

/* 降低侧边栏菜单项的高度 */
.el-menu-item,
:deep(.el-sub-menu__title) {
  height: 40px;
  line-height: 40px;
}
</style>
