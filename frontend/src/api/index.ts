import axios from 'axios';
import {ElMessage} from 'element-plus';
import router from '@/router'; // 引入 router

let isRedirectingToLogin = false;

const isRequestCanceled = (error: unknown): boolean => {
    if (!error || typeof error !== 'object') return false;
    const err = error as Record<string, unknown>;
    // Axios CancelToken / CanceledError
    if (typeof axios.isCancel === 'function' && axios.isCancel(error)) return true;
    if (err.__CANCEL__ === true) return true;
    // AbortController (axios v1 supports `signal`)
    if ((err.config as Record<string, unknown>)?.signal && ((err.config as Record<string, unknown>).signal as AbortSignal)?.aborted) return true;
    if ((err.cause as Record<string, unknown>)?.name === 'AbortError') return true;
    // Common axios cancellation shape
    if (err.code === 'ERR_CANCELED') return true;
    if (err.name === 'CanceledError' || err.name === 'AbortError') return true;
    const msg = typeof err.message === 'string' ? err.message.toLowerCase() : '';
    if (msg.includes('canceled') || msg.includes('cancelled') || msg.includes('aborted')) return true;
    return false;
};

const pendingRouteRequests = new Set<AbortController>();

export const cancelPendingRequests = (reason = 'route-change') => {
    pendingRouteRequests.forEach((controller) => {
        try {
            controller.abort(reason);
        } catch (e) {
            // ignore
        }
    });
    pendingRouteRequests.clear();
};

export { isRequestCanceled };

// 创建 Axios 实例（不设置 baseURL，统一使用相对路径请求 /api/**，由 Vite 代理或反向代理转发）
const apiClient = axios.create({
    timeout: 10000, // 请求超时时间
});

// 不需要注入组上下文的 URL 白名单（精确匹配或前缀匹配）
const GROUP_CONTEXT_SKIP_PATTERNS = [
    '/api/auth',
    '/api/users/me',
    '/api/login',
    '/api/register',
    '/api/settings',
    '/api/tools/server-link/groups', // 获取组列表本身不需要组上下文
];

const shouldSkipGroupContext = (url: string | undefined): boolean => {
    if (!url) return true;
    return GROUP_CONTEXT_SKIP_PATTERNS.some(pattern => url.startsWith(pattern));
};

// 请求拦截器 (Request Interceptor)
apiClient.interceptors.request.use(
    config => {
        const token = localStorage.getItem('token');
        if (token) {
            // 在每个请求的头部附加 Authorization
            config.headers['Authorization'] = `Bearer ${token}`;
        }

        // 注入组上下文 header（非平台管理员且有选中组时）
        // 动态导入避免循环依赖
        const skipGroupContext = (config as any)?.skipGroupContext === true;
        if (!skipGroupContext && !shouldSkipGroupContext(config.url)) {
            try {
                // 从 localStorage 读取保存的组选择（避免循环依赖）
                const savedGroupIds = localStorage.getItem('asPanel_activeGroupIds');
                if (savedGroupIds) {
                    const parsed = JSON.parse(savedGroupIds);
                    if (Array.isArray(parsed) && parsed.length > 0 && typeof parsed[0] === 'number') {
                        config.headers['X-Active-Group-Id'] = String(parsed[0]);
                    }
                }
            } catch {
                // ignore
            }
        }

        // 默认：在路由切换时中断未完成的请求，避免切换栏目时被旧请求拖住
        const cancelOnRouteChange = (config as any)?.cancelOnRouteChange;
        if (cancelOnRouteChange !== false && !config.signal) {
            const controller = new AbortController();
            (config as any).__routeCancelController = controller;
            config.signal = controller.signal;
            pendingRouteRequests.add(controller);
        }
        return config;
    },
    error => {
        // 对请求错误做些什么
        console.error('Request error:', error);
        return Promise.reject(error);
    }
);

// 响应拦截器 (Response Interceptor)
apiClient.interceptors.response.use(
    response => {
        const controller = (response.config as any)?.__routeCancelController;
        if (controller) pendingRouteRequests.delete(controller);
        // 对响应数据做点什么 (例如，如果所有响应都包裹在 'data' 字段中，可以在此解包)
        return response;
    },
    error => {
        const controller = (error?.config as any)?.__routeCancelController;
        if (controller) pendingRouteRequests.delete(controller);

        if (isRequestCanceled(error)) {
            // 路由切换主动中断等场景，不提示错误
            return Promise.reject(error);
        }

        // 处理 HTTP 错误
        if (error.response) {
            switch (error.response.status) {
                case 401:
                    // 未授权，通常是 token 过期或无效
                    if (!isRedirectingToLogin) {
                        isRedirectingToLogin = true;
                        localStorage.removeItem('token');
                        // 动态导入避免循环依赖
                        import('@/store/user').then(({ clearUser }) => {
                            clearUser();
                        });
                        router.push({
                            path: '/login',
                            query: { redirect: router.currentRoute.value.fullPath },
                        }).finally(() => {
                            // 延迟重置，避免并发请求多次触发
                            setTimeout(() => { isRedirectingToLogin = false; }, 1000);
                        });
                    }
                    break;
                case 403:
                    ElMessage.error('无权限执行此操作');
                    break;
                case 404:
                    // 通常由具体业务处理，但也可以在此统一提示
                    // ElMessage.error('请求的资源未找到。');
                    break;
                case 500:
                case 503:
                    break;
                default:
                    // 其他错误，使用后端返回的 detail 字段（如果有）
                    if (error.response.data && error.response.data.detail) {
                        // ElMessage.error(error.response.data.detail);
                    }
            }
        } else if (error.request) {
            // 请求已发出，但没有收到响应 (例如，网络问题或后端服务宕机)
            ElMessage.error('无法连接到服务器，请检查您的网络或联系管理员。');
        } else {
            // 发送请求时出了点问题
            console.error('Error', error.message);
        }
        return Promise.reject(error);
    }
);

// 绑定验证 API
export const bindApi = {
  requestBind: (playerName: string) =>
    apiClient.post('/api/users/me/bind-request', { player_name: playerName }),
  getPending: () =>
    apiClient.get('/api/users/me/bind-pending'),
  cancelBind: () =>
    apiClient.delete('/api/users/me/bind-request'),
}

export default apiClient;
