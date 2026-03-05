import { createRouter, createWebHistory } from 'vue-router';
import type { RouteRecordRaw } from 'vue-router'
import MainLayout from '../layout/MainLayout.vue';
import { useUserStore } from '@/store/user';
import { ElMessage } from 'element-plus';

declare module 'vue-router' {
    interface RouteMeta {
        requiresAuth?: boolean
        requiredRole?: import('@/store/user').LegacyRole
        requiresPlatformAdmin?: boolean
        requiresOwner?: boolean
    }
}

const routes: RouteRecordRaw[] = [
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
        component: MainLayout,
        redirect: '/dashboard',
        meta: { requiresAuth: true },
        children: [
            { path: 'dashboard', name: 'Dashboard', component: () => import('../views/Dashboard.vue'), meta: { requiredRole: 'GUEST' } },
            { path: 'servers', name: 'ServerList', component: () => import('../views/ServerList.vue'), meta: { requiredRole: 'USER' } },
            { path: 'mcdr-plugin-explorer', name: 'MCDRPluginExplorer', component: () => import('../views/MCDRPluginExplorer.vue'), meta: { requiredRole: 'HELPER' } },
            { path: 'db-plugin-manager', name: 'DbPluginExplorer', component: () => import('../views/DbPluginExplorer.vue'), meta: { requiredRole: 'ADMIN', requiresPlatformAdmin: true } },
            { path: 'server-plugins', name: 'ServerPluginManager', component: () => import('../views/ServerPluginManager.vue'), meta: { requiredRole: 'HELPER' } },
            { path: 'tools/mods-manager', name: 'ModsManager', component: () => import('../views/ModsManager.vue'), meta: { requiredRole: 'ADMIN' } },
            { path: 'tools/superflat', name: 'SuperFlatWorld', component: () => import('../views/SuperFlatWorld.vue'), meta: { requiredRole: 'USER' } },
            { path: 'tools/prime-backup', name: 'PrimeBackup', component: () => import('../views/PrimeBackup.vue'), meta: { requiredRole: 'HELPER' } },
            { path: 'server-groups', name: 'ServerLink', component: () => import('../views/ServerLink.vue'), meta: { requiredRole: 'ADMIN' } },
            { path: 'server-config/via-version-config', name: 'ViaVersionConfig', component: () => import('../views/plugin-config/ViaVersionConfig.vue'), meta: { requiredRole: 'ADMIN' } },
            { path: 'server-config/velocity-proxy-config', name: 'VelocityProxyConfig', component: () => import('../views/plugin-config/VelocityProxyConfig.vue'), meta: { requiredRole: 'ADMIN' } },
            { path: 'server-config/prime-backup-config', name: 'PrimeBackupConfig', component: () => import('../views/plugin-config/PrimeBackupConfig.vue'), meta: { requiredRole: 'HELPER' } },
            { path: 'server-config/auto-plugin-reloader-config', name: 'AutoPluginReloaderConfig', component: () => import('../views/plugin-config/AutoPluginReloaderConfig.vue'), meta: { requiredRole: 'HELPER' } },
            { path: 'server-config/bili-live-helper-config', name: 'BiliLiveHelperConfig', component: () => import('../views/plugin-config/BiliLiveHelperConfig.vue'), meta: { requiredRole: 'HELPER' } },
            { path: 'server-config/where-is-config', name: 'WhereIsConfig', component: () => import('../views/plugin-config/WhereIsConfig.vue'), meta: { requiredRole: 'HELPER' } },
            { path: 'server-config/crash-restart-config', name: 'CrashRestartConfig', component: () => import('../views/plugin-config/CrashRestartConfig.vue'), meta: { requiredRole: 'HELPER' } },
            { path: 'server-config/join-motd-config', name: 'JoinMOTDConfig', component: () => import('../views/plugin-config/JoinMOTDConfig.vue'), meta: { requiredRole: 'ADMIN' } },
            { path: 'server-config/quick-backup-multi-config', name: 'QuickBackupMultiConfig', component: () => import('../views/plugin-config/QuickBackupMultiConfig.vue'), meta: { requiredRole: 'HELPER' } },
            { path: 'players', name: 'PlayerManager', component: () => import('../views/PlayerManager.vue'), meta: { requiredRole: 'ADMIN', requiresPlatformAdmin: true } },
            { path: 'users', name: 'UserManager', component: () => import('../views/UserManager.vue'), meta: { requiredRole: 'OWNER' } },
            { path: 'tools/world-map', name: 'WorldMap', component: () => import('../views/WorldMap.vue'), meta: { requiredRole: 'USER' } },
            { path: 'tools/litematica', name: 'Litematica', component: () => import('../views/Litematica.vue'), meta: { requiredRole: 'USER' } },
            { path: 'chat', name: 'ChatRoom', component: () => import('../views/ChatRoom.vue'), meta: { requiredRole: 'USER' } },
            { path: 'settings', name: 'Settings', component: () => import('../views/Settings.vue'), meta: { requiredRole: 'OWNER', requiresOwner: true } },
            { path: 'tools/archives', name: 'ArchiveManagement', component: () => import('../views/ArchiveManagement.vue'), meta: { requiredRole: 'HELPER' } },
            { path: 'console/:server_id', name: 'Console', component: () => import('../views/Console.vue'), props: true, meta: { requiredRole: 'ADMIN' } },
            { path: 'statistics', name: 'Statistics', component: () => import('../views/Statistics.vue'), meta: { requiredRole: 'USER' } },
            { path: 'profile', name: 'Profile', component: () => import('../views/Profile.vue'), meta: { requiredRole: 'GUEST' } },
            { path: 'audit-log', name: 'AuditLog', component: () => import('../views/AuditLog.vue'), meta: { requiredRole: 'ADMIN', requiresPlatformAdmin: true } },
        ]
    },
    {
        path: '/:pathMatch(.*)*',
        name: 'NotFound',
        component: () => import('../views/NotFound.vue')
    }
];

const router = createRouter({
    history: createWebHistory(),
    routes,
});

router.beforeEach(async (to, from, next) => {
    const userStore = useUserStore();
    const token = localStorage.getItem('token');
    const publicPages = ['/login', '/register'];
    const authRequired = to.matched.some(record => record.meta.requiresAuth);

    if (authRequired && !token) {
        ElMessage.warning('请先登录');
        if (from && from.name) return next(false);
        return next({ path: '/login', query: { redirect: to.fullPath } });
    }

    if (publicPages.includes(to.path) && token) {
        return next('/dashboard');
    }

    try {
        if (authRequired && token && !userStore.user.id) {
            await userStore.fetchUser();
        }
    } catch (e) {
        localStorage.removeItem('token');
        userStore.clearUser();
        ElMessage.warning('登录已过期，请重新登录');
        return next({ path: '/login', query: { redirect: to.fullPath } });
    }

    const requiredRole = to.meta.requiredRole;
    if (requiredRole && !userStore.hasRole(requiredRole)) {
        ElMessage.error('无权限访问该页面');
        if (from && from.name) return next(false);
        return next('/dashboard');
    }

    if (to.meta.requiresPlatformAdmin && !userStore.isPlatformAdmin) {
        ElMessage.error('此页面仅对平台管理员开放');
        if (from && from.name) return next(false);
        return next('/dashboard');
    }

    if (to.meta.requiresOwner && !userStore.isOwner) {
        ElMessage.error('此页面仅对系统所有者开放');
        if (from && from.name) return next(false);
        return next('/dashboard');
    }

    next();
});

export default router;
