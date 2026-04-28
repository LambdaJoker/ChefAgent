# ChefAgent - AI 私人厨房

一个前后端分离的多模态智能体项目：用户上传菜品图片后，系统先上传到阿里云 OSS，再由 Minimax 模型识别食材，最后给出菜谱推荐和对话式烹饪建议。

## 1. 能力与边界

- 支持图片上传并转存阿里云 OSS
- 支持按 OSS 图片 URL 进行食材识别
- 支持基于食材进行菜谱推荐（推荐度、难度、营养综合评分）
- 支持对话式私厨建议（结合当前识别食材）
- 当前菜谱库为内置样例数据（可后续接数据库/向量检索）

## 2. 技术栈

- 前端：Vue 3 + Vite + Axios
- 后端：FastAPI + LangChain + Minimax + oss2
- Python 依赖管理：uv
- 配置管理：`.env` / `.env.example`

## 3. 目录结构

```text
ChefAgent/
  backend/
    app/
      api/               # 路由层
      core/              # 配置层
      models/            # 请求/响应模型
      services/          # 模型调用、OSS 上传、推荐逻辑
  frontend/
    src/
      api/               # 前端接口封装
      components/        # Vue 组件
      App.vue            # 主页面
```

## 4. 快速开始

### 4.1 启动后端

```bash
cd backend
# 复制 .env.example 到 .env，并填写 MINIMAX 和 OSS 参数
uv sync
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 4.2 启动前端

```bash
cd frontend
# 复制 .env.example 到 .env
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

## 5. 环境变量

### 5.1 后端 `backend/.env`

最小必填（生产）：
- `TEXT_API_KEY`（用于对话，默认 Minimax）
- `VISION_API_KEY`（用于识别，默认 Qwen）
- `OSS_ACCESS_KEY_ID`
- `OSS_ACCESS_KEY_SECRET`
- `OSS_BUCKET_NAME`
- `OSS_ENDPOINT`
- `OSS_BUCKET_DOMAIN`

常用配置：
- `TEXT_BASE_URL=https://api.minimax.chat/v1`
- `TEXT_MODEL=MiniMax-M2.7`
- `VISION_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1`
- `VISION_MODEL=qwen-vl-plus-latest`
- `ALLOW_MOCK_WITHOUT_KEY=true`（仅本地联调）
- `OSS_OBJECT_PREFIX=chefagent/uploads`

备用模型配置（可选，便于后续切换）：
- OpenAI：`OPENAI_API_KEY`、`OPENAI_BASE_URL`、`OPENAI_MODEL`
- DeepSeek：`DEEPSEEK_API_KEY`、`DEEPSEEK_BASE_URL`、`DEEPSEEK_MODEL`
- 通义千问：`QWEN_API_KEY`、`QWEN_BASE_URL`、`QWEN_MODEL`
- Kimi：`KIMI_API_KEY`、`KIMI_BASE_URL`、`KIMI_MODEL`

### 5.2 前端 `frontend/.env`

- `VITE_API_BASE_URL=http://localhost:8000/api/v1`

## 6. API 文档（核心）

- `POST /api/v1/uploads/image`
  - 入参：`multipart/form-data`，字段 `image`
  - 出参：`{ "object_key": "...", "object_url": "..." }`
- `POST /api/v1/recognize-by-url`
  - 入参：`{ "image_url": "...", "hint": "可选" }`
  - 出参：`{ "ingredients": [...], "raw_description": "..." }`
- `POST /api/v1/recipes/recommend`
  - 入参：`{ "ingredients": ["鸡蛋","番茄"], "top_k": 5 }`
  - 出参：`{ "recipes": [...] }`
- `POST /api/v1/chat`
  - 入参：`{ "message": "...", "ingredients": [...] }`
  - 出参：`{ "answer": "..." }`

## 7. 开发规范

- Python 函数命名使用 `snake_case`
- Vue/JS 函数命名使用 `camelCase`
- 事件处理函数使用 `handleXxx` 前缀
- 核心函数需包含函数体说明：功能、参数、返回、关键流程、异常处理

## 8. 常见问题

- 前端无法请求后端：检查 `VITE_API_BASE_URL` 与后端端口
- OSS 上传失败：检查 `OSS_*` 参数和 bucket 读写权限
- 识别失败：确认 `MINIMAX_API_KEY` 有效且模型额度充足
- 本地联调无 SK：可启用 `ALLOW_MOCK_WITHOUT_KEY=true`
