# AI 私厨后端（FastAPI + Minimax + OSS）

## 1. 模块说明

- `app/api/routes.py`：接口路由层
- `app/services/minimax_client.py`：模型调用层（多模态识别、聊天）
- `app/services/oss_service.py`：阿里云 OSS 上传层
- `app/services/recipe_service.py`：菜谱推荐层
- `app/core/config.py`：环境变量与配置加载
- `app/models/schemas.py`：请求/响应模型

## 2. 运行方式

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 3. 环境变量（详细）

### 3.1 服务配置
- `APP_NAME=AI私厨 Backend`
- `APP_HOST=0.0.0.0`
- `APP_PORT=8000`
- `FRONTEND_ORIGIN=http://localhost:5173`

### 3.2 Minimax 配置
- `MINIMAX_API_KEY=你的SK`
- `MINIMAX_BASE_URL=https://api.minimaxi.chat/v1`
- `MINIMAX_MODEL=MiniMax-M2.7`
- `MINIMAX_TIMEOUT=60`
- `ALLOW_MOCK_WITHOUT_KEY=true`

### 3.3 备用模型配置（可选）
- OpenAI：`OPENAI_API_KEY`、`OPENAI_BASE_URL`、`OPENAI_MODEL`
- DeepSeek：`DEEPSEEK_API_KEY`、`DEEPSEEK_BASE_URL`、`DEEPSEEK_MODEL`
- 通义千问：`QWEN_API_KEY`、`QWEN_BASE_URL`、`QWEN_MODEL`
- Kimi：`KIMI_API_KEY`、`KIMI_BASE_URL`、`KIMI_MODEL`

### 3.4 OSS 配置
- `OSS_ACCESS_KEY_ID`
- `OSS_ACCESS_KEY_SECRET`
- `OSS_BUCKET_NAME`
- `OSS_ENDPOINT=oss-cn-hangzhou.aliyuncs.com`
- `OSS_BUCKET_DOMAIN=https://<bucket>.oss-cn-hangzhou.aliyuncs.com`
- `OSS_OBJECT_PREFIX=chefagent/uploads`

## 4. 接口清单

### 4.1 健康检查
- `GET /api/v1/health`

### 4.2 图片上传 OSS
- `POST /api/v1/uploads/image`
- Content-Type: `multipart/form-data`
- 字段：`image`

示例响应：

```json
{
  "object_key": "chefagent/uploads/2026/04/28/xxxx.jpg",
  "object_url": "https://bucket.oss-cn-hangzhou.aliyuncs.com/chefagent/uploads/2026/04/28/xxxx.jpg"
}
```

### 4.3 URL 食材识别
- `POST /api/v1/recognize-by-url`

示例请求：

```json
{
  "image_url": "https://bucket.oss-cn-hangzhou.aliyuncs.com/chefagent/uploads/...jpg",
  "hint": "冰箱里还有一点胡萝卜"
}
```

### 4.4 菜谱推荐
- `POST /api/v1/recipes/recommend`

### 4.5 对话问答
- `POST /api/v1/chat`

## 5. 故障排查

- 401/403：检查 Minimax SK 或 OSS AK 权限
- CORS 错误：检查 `FRONTEND_ORIGIN`
- 上传成功但图片打不开：检查 `OSS_BUCKET_DOMAIN` 是否正确和 bucket 公开读权限
- 识别返回空：检查模型额度、请求图像质量和提示词
