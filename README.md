# AS Panel

一个基于 FastAPI + Vue3 的 Minecraft 服务器面板。

## 特性概览
- 后端：FastAPI、SQLAlchemy、Socket.IO（ASGI）。
- 前端：Vite + Vue3 + TypeScript。
- 数据与日志默认存放于 `storages/`（已被 `.gitignore` 忽略）。

## 目录结构
- `backend/`：后端源码，ASGI 入口在 `backend/main.py` 的 `main_asgi_app`。
- `frontend/`：前端源码，Vite 项目。
- `storages/`：运行时数据（数据库、日志、上传文件、归档等）。

## 环境要求
- Python 3.10+，Node.js 18+
- Linux 推荐安装 `build-essential`

## 快速开始（开发环境）
### 后端
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
uvicorn backend.main:main_asgi_app --host 0.0.0.0 --port 8000 --reload
```

健康检查：`GET http://localhost:8000/api/health` → `{ "status": "ok" }`

### 前端
```bash
cd frontend
npm install
cp .env.example .env.development  # 可选，设置 VITE_API_URL
npm run dev
```

默认开发代理：
- `/api` → `http://localhost:8000`
- WebSocket：客户端使用 `path: '/ws/socket.io'`

## 生产部署
### 构建前端
```bash
cd frontend
npm install && npm run build
```
静态产物位于 `frontend/dist/`，可由 Nginx 或任意静态服务托管。

### 运行后端（示例）
```bash
source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.main:main_asgi_app --host 0.0.0.0 --port 8000 --workers 1
```

### Nginx 反向代理片段
```nginx
location / { root /path/to/frontend/dist; try_files $uri /index.html; }
location /api/ { proxy_pass http://127.0.0.1:8000; }
location /ws/socket.io {
  proxy_set_header Upgrade $http_upgrade;
  proxy_set_header Connection "upgrade";
  proxy_http_version 1.1;
  proxy_read_timeout 600s;
  proxy_pass http://127.0.0.1:8000;
}
```

## 配置与安全
- JWT 密钥：可通过环境变量 `ASPANEL_SECRET_KEY`（或 `SECRET_KEY`）设置；未设置时将自动在 `storages/secret.key` 生成并持久化。
- CORS：生产建议将 `backend/core/config.py` 中的 `ALLOWED_ORIGINS` 限定为你的域名。
- `storages/`、`.env*` 等已在 `.gitignore` 中忽略。

## 依赖安装
后端依赖见 `requirements.txt`。

## Git 工作流
- 默认分支：`main`
- 首次推送示例：
```bash
git add -A
git commit -m "chore: repo ready for GitHub"
# 如未设置远端：
# git remote add origin <your_repo_url>
git push -u origin main
```

> 注意：若仓库历史中已包含 `.env.devlopment` / `.env.production` 等文件，建议使用以下命令将其从索引中移除（不删除本地文件）：
> ```bash
> git rm --cached frontend/.env.devlopment frontend/.env.production
> ```

## 额外说明
- MCDReforged 相关功能依赖系统已安装 `mcdreforged` 与 Java 运行环境，本文不包含其安装说明。
