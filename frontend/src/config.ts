// 全局后端基地址配置（统一走相对路径）
// 说明：
// - 开发环境：通过 Vite 代理（vite.config.ts -> server.proxy）转发到后端
// - 生产环境：前端与后端建议同域部署，由反向代理（如 Nginx）将 /api 等前缀转发到后端
// - 因此这里固定使用相对路径，避免在 HTTPS 场景下出现 Mixed Content（前端去请求 http://...）。
export const API_BASE_URL = '' as const;
