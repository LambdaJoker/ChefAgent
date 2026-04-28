# AI 私厨前端（Vue 3 + Vite）

## 1. 页面能力

- 上传本地图片到后端（后端转存 OSS）
- 基于 OSS URL 调用识别接口
- 显示识别食材与原始描述
- 展示推荐菜谱卡片
- 对话式厨艺助手

## 2. 技术栈

- Vue 3（Composition API）
- Vite
- Axios

## 3. 启动步骤

```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

## 4. 环境变量

- `VITE_API_BASE_URL=http://localhost:8000/api/v1`

## 5. 关键文件

- `src/App.vue`：主流程编排（上传 -> 识别 -> 推荐）
- `src/api/client.js`：统一接口封装
- `src/components/RecipeCard.vue`：菜谱卡片
- `src/components/ChatPanel.vue`：聊天面板

## 6. 交互链路

1. 用户选择图片
2. 调用 `/uploads/image` 获取 `object_url`
3. 调用 `/recognize-by-url` 得到食材
4. 调用 `/recipes/recommend` 获取推荐
5. 用户可继续通过 `/chat` 提问

## 7. 常见问题

- 请求失败：确认后端已启动、`VITE_API_BASE_URL` 正确
- 页面空白：确认 Node 版本满足 Vite 要求并重新 `npm install`
- 上传后无结果：检查 OSS 与模型配置是否有效
