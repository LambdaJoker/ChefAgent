import axios from "axios";

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  timeout: 120000,
});

/**
 * 功能:
 * 上传本地图片到后端，由后端转存到阿里云 OSS。
 * 参数:
 * - file: File，用户选择的图片文件。
 * 返回:
 * - Promise<{object_key: string, object_url: string}>
 * 关键流程:
 * 1) 组装 FormData；
 * 2) 调用上传接口；
 * 3) 返回 OSS 对象信息。
 * 异常处理:
 * 请求失败时抛出 axios 异常，交由调用方统一提示。
 */
export async function uploadImageToOss(file) {
  const formData = new FormData();
  formData.append("image", file);
  const response = await apiClient.post("/uploads/image", formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
  });
  return response.data;
}

/**
 * 功能:
 * 基于 OSS 图片 URL 调用识别接口，返回食材列表。
 * 参数:
 * - imageUrl: string，OSS 可访问图片 URL。
 * - hint: string，用户补充信息，可选。
 * 返回:
 * - Promise<{ingredients: string[], raw_description: string}>
 * 关键流程:
 * 1) 发送 JSON 请求；
 * 2) 获取识别结果；
 * 3) 返回标准响应结构。
 * 异常处理:
 * 接口报错时抛出异常，由上层组件进行降级处理。
 */
export async function recognizeIngredientsByUrl(imageUrl, hint) {
  const response = await apiClient.post("/recognize-by-url", {
    image_url: imageUrl,
    hint,
  });
  return response.data;
}

/**
 * 功能:
 * 按识别食材拉取推荐菜谱列表。
 * 参数:
 * - ingredients: string[]，识别得到的食材列表。
 * - topK: number，返回条数。
 * 返回:
 * - Promise<{recipes: Array}>
 * 关键流程:
 * 1) 发送推荐请求；
 * 2) 后端完成评分排序；
 * 3) 返回菜谱数组。
 * 异常处理:
 * 网络或服务错误时抛出异常。
 */
export async function fetchRecipeRecommendations(ingredients, topK = 5) {
  const response = await apiClient.post("/recipes/recommend", {
    ingredients,
    top_k: topK,
  });
  return response.data;
}

/**
 * 功能:
 * 发送私厨对话消息并获取模型回复。
 * 参数:
 * - message: string，用户输入文本。
 * - ingredients: string[]，上下文食材列表。
 * 返回:
 * - Promise<{answer: string}>
 * 关键流程:
 * 1) 组装请求体；
 * 2) 调用聊天接口；
 * 3) 返回回答文本。
 * 异常处理:
 * 请求失败时抛出异常。
 */
export async function sendCookingChatMessage(message, ingredients) {
  const response = await apiClient.post("/chat", {
    message,
    ingredients,
  });
  return response.data;
}
