// src/router/index.ts

import { createRouter, createWebHistory } from 'vue-router';
import MainLayout from '../layout/MainLayout.vue';

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
                component: () => import('../views/Dashboard.vue')
            },
            {
                path: 'servers',
                name: 'ServerList',
                component: () => import('../views/ServerList.vue')
            },
            {
                path: 'mcdr-plugin-explorer',
                name: 'MCDRPluginExplorer',
                component: () => import('../views/MCDRPluginExplorer.vue')
            },
            {
                path: 'db-plugin-manager',
                name: 'DbPluginExplorer',
                component: () => import('../views/DbPluginExplorer.vue')
            },
            {
                path: 'server-plugins',
                name: 'ServerPluginManager',
                component: () => import('../views/ServerPluginManager.vue')
            },
            {
                path: 'tools/mods-manager',
                name: 'ModsManager',
                component: () => import('../views/ModsManager.vue')
            },
            {
                path: 'tools/superflat',
                name: 'SuperFlatWorld',
                component: () => import('../views/SuperFlatWorld.vue')
            },
            {
                path: 'tools/prime-backup',
                name: 'PrimeBackup',
                component: () => import('../views/PrimeBackup.vue')
            },
            {
                path: 'tools/server-link',
                name: 'ServerLink',
                component: () => import('../views/ServerLink.vue')
            },
            // 插件配置
            { path: 'server-config/via-version-config', name: 'ViaVersionConfig', component: () => import('../views/plugin-config/ViaVersionConfig.vue') },
            { path: 'server-config/velocity-proxy-config', name: 'VelocityProxyConfig', component: () => import('../views/plugin-config/VelocityProxyConfig.vue') },
            { path: 'server-config/prime-backup-config', name: 'PrimeBackupConfig', component: () => import('../views/plugin-config/PrimeBackupConfig.vue') },
            { path: 'server-config/auto-plugin-reloader-config', name: 'AutoPluginReloaderConfig', component: () => import('../views/plugin-config/AutoPluginReloaderConfig.vue') },
            { path: 'server-config/bili-live-helper-config', name: 'BiliLiveHelperConfig', component: () => import('../views/plugin-config/BiliLiveHelperConfig.vue') },
            { path: 'server-config/where-is-config', name: 'WhereIsConfig', component: () => import('../views/plugin-config/WhereIsConfig.vue') },
            { path: 'server-config/crash-restart-config', name: 'CrashRestartConfig', component: () => import('../views/plugin-config/CrashRestartConfig.vue') },
            { path: 'server-config/join-motd-config', name: 'JoinMOTDConfig', component: () => import('../views/plugin-config/JoinMOTDConfig.vue') },
            { path: 'server-config/quick-backup-multi-config', name: 'QuickBackupMultiConfig', component: () => import('../views/plugin-config/QuickBackupMultiConfig.vue') },
            {
                path: 'tools/litematica',
                name: 'Litematica',
                component: () => import('../views/Litematica.vue')
            },
            {
                path: 'chat',
                name: 'ChatRoom',
                component: () => import('../views/ChatRoom.vue')
            },
            {
                path: 'settings',
                name: 'Settings',
                component: () => import('../views/Settings.vue')
            },
            {
                // 【新增】存档管理页面的路由
                // 它必须作为 MainLayout 的子路由，才能被正确渲染在布局内部
                path: 'tools/archives',
                name: 'ArchiveManagement',
                component: () => import('../views/ArchiveManagement.vue')
            },
            {
                path: 'console/:server_id',
                name: 'Console',
                component: () => import('../views/Console.vue'),
                props: true
            }
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
router.beforeEach((to, from, next) => {
    const token = localStorage.getItem('token');
    const publicPages = ['/login', '/register'];
    const authRequired = to.matched.some(record => record.meta.requiresAuth);

    if (authRequired && !token) {
        return next({
            path: '/login',
            query: { redirect: to.fullPath }
        });
    }

    if (publicPages.includes(to.path) && token) {
        return next('/dashboard');
    }

    next();
});

export default router;
