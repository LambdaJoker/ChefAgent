# ChefAgent

一个前后端分离的多模态智能体项目：用户上传菜品图片后，系统先上传到阿里云 OSS，再由 Minimax/Qwen 模型识别食材，最后给出菜谱推荐和对话式烹饪建议。
当前版本已支持基于 SSE 的流式对话输出、逐字显示打字机效果、多会话本地持久化，以及按需联网搜索菜谱来源。

## 1. 能力与边界

- 支持图片上传并转存阿里云 OSS
- 支持按 OSS 图片 URL 进行食材识别（使用 Qwen-VL 等视觉模型）
- 支持基于食材进行菜谱推荐（推荐度、难度、营养综合评分）
- 支持对话式私厨建议（结合当前识别食材，支持 SSE 流式输出）
- 支持按需联网搜索（仅当用户明确要求搜索、来源、最新资料等场景时启用）
- 支持对话记忆与多轮上下文（按 `session_id` 维持会话）
- **类 DeepSeek 现代化 UI**：
  - **会话管理**：支持多会话本地持久化、修改会话名称、清空历史记录。
  - **响应式侧边栏**：桌面端支持折叠/展开，移动端支持抽屉式菜单。
  - **沉浸式对话体验**：支持 Markdown 渲染、代码高亮、AI 思考过程（Thinking State）折叠/展开、生成耗时显示。
  - **流式体验**：支持状态提示、逐字显示打字机效果、自动滚动到底部。
  - **便捷操作**：支持一键复制 AI 回答（自动过滤思考过程），支持将单条聊天记录导出为 Markdown 文件。
- 当前菜谱库为内置样例数据（可后续接数据库/向量检索）

## 2. 技术栈

- 前端：Vue 3 + Vite + Tailwind CSS + Lucide Icons + Markdown-it
- 后端：FastAPI + LangChain + HTTPX（流式响应）+ Minimax/Qwen + oss2 + Tavily（可选联网搜索）
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
npm run dev
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
- `TAVILY_API_KEY=...`（可选；启用联网搜索工具）
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
  - 入参：`{ "message": "...", "ingredients": [...], "session_id": "可选" }`
  - 返回：`text/event-stream`
  - 事件类型：
    - `status`：阶段状态，如思考中、搜索中、生成中
    - `content`：流式正文片段
    - `error`：错误信息
    - `done`：最终完成事件，包含 `final_text`

### 6.1 SSE 事件示例

```text
event: status
data: {"phase":"thinking","label":"思考中","detail":"正在分析你的需求并生成做法"}

event: content
data: {"text":"先把西红柿切块，鸡蛋打散。"}

event: done
data: {"final_text":"先把西红柿切块，鸡蛋打散。..."}
```

说明：
- 前端会消费上述 SSE 事件并实时渲染，不会直接显示底层 `event:` / `data:` 协议文本。
- 聊天页面会在流式阶段展示状态条，并以逐字方式将内容输出到消息气泡中。

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
- 联网搜索未触发：确认已配置 `TAVILY_API_KEY`，且用户问题明确包含“搜索 / 查一下 / 来源 / 最新”等意图
- 聊天接口看起来不像流式：确认后端已重启到最新版本，并检查浏览器是否直接命中了 `/api/v1/chat` 的 SSE 响应
- 页面没有逐字效果：确认前端已刷新到最新版本；当前逐字显示由前端实现，依赖浏览器正常执行 `requestAnimationFrame`
