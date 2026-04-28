<template>
  <section class="chat-panel">
    <h2>厨艺对话</h2>
    <div class="chat-window">
      <div v-for="(msg, index) in messages" :key="index" :class="`msg ${msg.role}`">
        {{ msg.content }}
      </div>
    </div>
    <div class="chat-input">
      <input v-model="inputMessage" placeholder="问我：这些食材怎么做更健康？" />
      <button :disabled="isSending" @click="handleSendMessage">
        {{ isSending ? "发送中..." : "发送" }}
      </button>
    </div>
  </section>
</template>

<script setup>
import { ref } from "vue";
import { sendCookingChatMessage } from "../api/client";

const props = defineProps({
  ingredients: {
    type: Array,
    default: () => [],
  },
});

const messages = ref([
  { role: "assistant", content: "你好，我是你的 AI 私厨。你可以先上传食材图片。" },
]);
const inputMessage = ref("");
const isSending = ref(false);

/**
 * 功能:
 * 发送用户聊天消息并追加模型回复。
 * 参数:
 * 无。
 * 返回:
 * - Promise<void>
 * 关键流程:
 * 1) 校验输入并先渲染用户消息；
 * 2) 调用后端 chat 接口；
 * 3) 渲染 assistant 回复或错误提示。
 * 异常处理:
 * 请求失败时追加兜底提示，不中断页面交互。
 */
async function handleSendMessage() {
  const trimmedMessage = inputMessage.value.trim();
  if (!trimmedMessage) return;

  messages.value.push({ role: "user", content: trimmedMessage });
  inputMessage.value = "";
  isSending.value = true;

  try {
    const response = await sendCookingChatMessage(trimmedMessage, props.ingredients);
    messages.value.push({ role: "assistant", content: response.answer });
  } catch (error) {
    messages.value.push({
      role: "assistant",
      content: "请求失败，请检查后端服务或模型配置。",
    });
  } finally {
    isSending.value = false;
  }
}
</script>
