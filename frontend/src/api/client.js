import axios from "axios";

const STREAM_DEBUG = import.meta.env.DEV;

const findSseSeparatorIndex = (buffer) => {
  const lfIndex = buffer.indexOf("\n\n");
  const crlfIndex = buffer.indexOf("\r\n\r\n");

  if (lfIndex === -1) return crlfIndex;
  if (crlfIndex === -1) return lfIndex;
  return Math.min(lfIndex, crlfIndex);
};

const getSseSeparatorLength = (buffer, separatorIndex) => {
  if (separatorIndex < 0) return 0;
  return buffer.startsWith("\r\n\r\n", separatorIndex) ? 4 : 2;
};

const parseSseEvent = (rawEventBlock) => {
  const lines = rawEventBlock
    .split(/\r?\n/)
    .map(line => line.trimEnd())
    .filter(Boolean);

  let event = "message";
  const dataLines = [];

  for (const line of lines) {
    if (line.startsWith("event:")) {
      event = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trim());
    }
  }

  if (!dataLines.length) return null;

  const rawData = dataLines.join("\n");
  try {
    return {
      event,
      data: JSON.parse(rawData),
    };
  } catch {
    return {
      event,
      data: { text: rawData },
    };
  }
};

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
 * 发送私厨对话消息并获取模型回复流。
 * 参数:
 * - message: string，用户输入文本。
 * - ingredients: string[]，上下文食材列表。
 * - onChunk: (chunk: string, fullText: string) => void，接收流数据的回调。
 * 返回:
 * - Promise<string>，最终完整的回答。
 */
export async function sendCookingChatMessage(message, ingredients, sessionId, onChunk) {
  const baseUrl = import.meta.env.VITE_API_BASE_URL;
  const requestStartedAt = performance.now();
  if (STREAM_DEBUG) {
    console.debug("[stream] request:start", {
      sessionId,
      messageLength: message?.length || 0,
      ingredientsCount: ingredients?.length || 0,
      startedAt: requestStartedAt,
    });
  }
  const response = await fetch(`${baseUrl}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ message, ingredients, session_id: sessionId }),
  });

  if (!response.ok) {
    const errData = await response.json().catch(() => ({}));
    throw new Error(errData.detail || "网络请求失败");
  }

  if (STREAM_DEBUG) {
    console.debug("[stream] response:open", {
      status: response.status,
      contentType: response.headers.get("content-type"),
      openedAfterMs: Number((performance.now() - requestStartedAt).toFixed(1)),
    });
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let done = false;
  let fullText = "";
  let chunkIndex = 0;
  let firstChunkLogged = false;
  let sseBuffer = "";

  while (!done) {
    const { value, done: readerDone } = await reader.read();
    done = readerDone;
    if (value) {
      chunkIndex += 1;
      // Decode with stream: true so that multi-byte characters aren't split incorrectly
      const chunk = decoder.decode(value, { stream: !done });
      if (STREAM_DEBUG) {
        const elapsedMs = Number((performance.now() - requestStartedAt).toFixed(1));
        if (!firstChunkLogged) {
          firstChunkLogged = true;
          console.debug("[stream] chunk:first", {
            chunkIndex,
            chunkLength: chunk.length,
            elapsedMs,
            preview: chunk.slice(0, 80),
          });
        } else {
          console.debug("[stream] chunk", {
            chunkIndex,
            chunkLength: chunk.length,
            totalLength: fullText.length,
            elapsedMs,
          });
        }
      }

      sseBuffer += chunk;
      let separatorIndex = findSseSeparatorIndex(sseBuffer);
      while (separatorIndex !== -1) {
        const rawEventBlock = sseBuffer.slice(0, separatorIndex);
        sseBuffer = sseBuffer.slice(separatorIndex + getSseSeparatorLength(sseBuffer, separatorIndex));
        const parsedEvent = parseSseEvent(rawEventBlock);
        if (parsedEvent) {
          if (parsedEvent.event === "content" && parsedEvent.data?.text) {
            fullText += parsedEvent.data.text;
          }
          if (onChunk) {
            await onChunk(parsedEvent, fullText);
          }
        }
        separatorIndex = findSseSeparatorIndex(sseBuffer);
      }
    }
  }

  if (sseBuffer.trim()) {
    const parsedEvent = parseSseEvent(sseBuffer);
    if (parsedEvent) {
      if (parsedEvent.event === "content" && parsedEvent.data?.text) {
        fullText += parsedEvent.data.text;
      }
      if (onChunk) {
        await onChunk(parsedEvent, fullText);
      }
    }
  }

  if (STREAM_DEBUG) {
    console.debug("[stream] request:done", {
      chunkCount: chunkIndex,
      totalLength: fullText.length,
      finishedAfterMs: Number((performance.now() - requestStartedAt).toFixed(1)),
    });
  }
  return fullText;
}
