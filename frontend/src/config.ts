// 全局后端基地址配置
// 优先使用构建期的环境变量 VITE_API_URL；未设置时回落到当前页面的 origin（同域部署场景）。
export const API_BASE_URL = (import.meta as any).env?.VITE_API_URL || window.location.origin;

