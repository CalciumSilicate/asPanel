// src/router/index.ts

import { createRouter, createWebHistory } from 'vue-router';
import MainLayout from '../layout/MainLayout.vue';
import { hasRole, fetchUser, type UserRole } from '@/store/user';
import { ElMessage } from 'element-plus';

const routes = [
    {
        path: '/login',
        name: 'Login',
        component: () => import('../views/Login.vue')
    },
    {
        path: '/register',
        name: 'Register',
        component: () => import('../views/Register.vue'),
    },
    {
        path: '/',
        component: MainLayout, // 使用 MainLayout 作为根布局组件
        redirect: '/dashboard',
        meta: { requiresAuth: true }, // 权限验证放在父路由上
        children: [ // 确保 'archives' 在这个 children 数组中
            {
                path: 'dashboard',
                name: 'Dashboard',
                component: () => import('../views/Dashboard.vue'),
                meta: { requiredRole: 'GUEST' }
            },
            {
                path: 'servers',
                name: 'ServerList',
                component: () => import('../views/ServerList.vue'),
                meta: { requiredRole: 'USER' }
            },
            {
                path: 'mcdr-plugin-explorer',
                name: 'MCDRPluginExplorer',
                component: () => import('../views/MCDRPluginExplorer.vue'),
                meta: { requiredRole: 'HELPER' }
            },
            {
                path: 'db-plugin-manager',
                name: 'DbPluginExplorer',
                component: () => import('../views/DbPluginExplorer.vue'),
                meta: { requiredRole: 'ADMIN' }
            },
            {
                path: 'server-plugins',
                name: 'ServerPluginManager',
                component: () => import('../views/ServerPluginManager.vue'),
                meta: { requiredRole: 'HELPER' }
            },
            {
                path: 'tools/mods-manager',
                name: 'ModsManager',
                component: () => import('../views/ModsManager.vue'),
                meta: { requiredRole: 'ADMIN' }
            },
            {
                path: 'tools/superflat',
                name: 'SuperFlatWorld',
                component: () => import('../views/SuperFlatWorld.vue'),
                meta: { requiredRole: 'USER' }
            },
            {
                path: 'tools/prime-backup',
                name: 'PrimeBackup',
                component: () => import('../views/PrimeBackup.vue'),
                meta: { requiredRole: 'USER' }
            },
            {
                path: 'tools/server-link',
                name: 'ServerLink',
                component: () => import('../views/ServerLink.vue'),
                meta: { requiredRole: 'USER' }
            },
            // 插件配置
            { path: 'server-config/via-version-config', name: 'ViaVersionConfig', component: () => import('../views/plugin-config/ViaVersionConfig.vue'), meta: { requiredRole: 'ADMIN' } },
            { path: 'server-config/velocity-proxy-config', name: 'VelocityProxyConfig', component: () => import('../views/plugin-config/VelocityProxyConfig.vue'), meta: { requiredRole: 'ADMIN' } },
            { path: 'server-config/prime-backup-config', name: 'PrimeBackupConfig', component: () => import('../views/plugin-config/PrimeBackupConfig.vue'), meta: { requiredRole: 'HELPER' } },
            { path: 'server-config/auto-plugin-reloader-config', name: 'AutoPluginReloaderConfig', component: () => import('../views/plugin-config/AutoPluginReloaderConfig.vue'), meta: { requiredRole: 'HELPER' } },
            { path: 'server-config/bili-live-helper-config', name: 'BiliLiveHelperConfig', component: () => import('../views/plugin-config/BiliLiveHelperConfig.vue'), meta: { requiredRole: 'HELPER' } },
            { path: 'server-config/where-is-config', name: 'WhereIsConfig', component: () => import('../views/plugin-config/WhereIsConfig.vue'), meta: { requiredRole: 'HELPER' } },
            { path: 'server-config/crash-restart-config', name: 'CrashRestartConfig', component: () => import('../views/plugin-config/CrashRestartConfig.vue'), meta: { requiredRole: 'HELPER' } },
            { path: 'server-config/join-motd-config', name: 'JoinMOTDConfig', component: () => import('../views/plugin-config/JoinMOTDConfig.vue'), meta: { requiredRole: 'ADMIN' } },
            { path: 'server-config/quick-backup-multi-config', name: 'QuickBackupMultiConfig', component: () => import('../views/plugin-config/QuickBackupMultiConfig.vue'), meta: { requiredRole: 'HELPER' } },
            {
                path: 'players',
                name: 'PlayerManager',
                component: () => import('../views/PlayerManager.vue'),
                meta: { requiredRole: 'ADMIN' }
            },
            {
                path: 'users',
                name: 'UserManager',
                component: () => import('../views/UserManager.vue'),
                meta: { requiredRole: 'ADMIN' }
            },
            {
                path: 'tools/litematica',
                name: 'Litematica',
                component: () => import('../views/Litematica.vue'),
                meta: { requiredRole: 'USER' }
            },
            {
                path: 'chat',
                name: 'ChatRoom',
                component: () => import('../views/ChatRoom.vue'),
                meta: { requiredRole: 'USER' }
            },
            {
                path: 'settings',
                name: 'Settings',
                component: () => import('../views/Settings.vue'),
                meta: { requiredRole: 'ADMIN' }
            },
            {
                // 【新增】存档管理页面的路由
                // 它必须作为 MainLayout 的子路由，才能被正确渲染在布局内部
                path: 'tools/archives',
                name: 'ArchiveManagement',
                component: () => import('../views/ArchiveManagement.vue'),
                meta: { requiredRole: 'HELPER' }
            },
            {
                path: 'console/:server_id',
                name: 'Console',
                component: () => import('../views/Console.vue'),
                props: true,
                meta: { requiredRole: 'ADMIN' }
            },
            {
                path: 'statistics',
                name: 'Statistics',
                component: () => import('../views/Statistics.vue'),
                meta: { requiredRole: 'USER' }
            },
            // 未来可以在此添加 statistics, settings 等子路由
        ]
    },
     // 404 页面
    {
        path: '/:pathMatch(.*)*',
        redirect: '/dashboard'
    }
];

const router = createRouter({
    history: createWebHistory(),
    routes,
});

// 全局路由守卫 (逻辑不变)
router.beforeEach(async (to, from, next) => {
    const token = localStorage.getItem('token');
    const publicPages = ['/login', '/register'];
    const authRequired = to.matched.some(record => record.meta.requiresAuth);

    // 未登录访问受保护路由：提示并回到上一个页面；若无来源（直达），跳转登录
    if (authRequired && !token) {
        ElMessage.warning('请先登录');
        if (from && from.name) {
            return next(false); // 取消本次导航，停留在上一个页面
        }
        return next({ path: '/login', query: { redirect: to.fullPath } });
    }

    // 已登录访问登录/注册：直接去仪表盘
    if (publicPages.includes(to.path) && token) {
        return next('/dashboard');
    }

    // 按需拉取用户信息（用于角色判断）
    try {
        if (authRequired && token) {
            await fetchUser();
        }
    } catch (e) {
        // 忽略用户信息拉取失败，后端会最终裁决
    }

    // 角色不足：提示并回到上一个页面；若无来源（直达），回到仪表盘
    const requiredRole = (to.meta as any)?.requiredRole as UserRole | undefined;
    if (requiredRole && !hasRole(requiredRole)) {
        ElMessage.error('无权限访问该页面');
        if (from && from.name) {
            return next(false); // 取消本次导航，停留在上一个页面
        }
        return next('/dashboard');
    }

    next();
});

export default router;
