<template>
  <AppLayout
    :sessions="sessions"
    :currentSessionId="currentSessionId"
    @new-chat="createNewSession"
    @select-session="selectSession"
    @delete-session="deleteSession"
    @clear-all-sessions="clearAllSessions"
  >
    <div class="flex-1 flex flex-col h-full bg-gray-50 md:p-6 w-full">
      <div class="flex-1 flex flex-col w-full mx-auto shadow-none md:shadow-lg md:rounded-2xl bg-white overflow-hidden border border-transparent md:border-gray-200">
        <!-- 聊天区域组件 -->
        <ChatArea
          :messages="currentMessages"
          :isGenerating="isGenerating"
          :isUploading="isUploading"
          @send="handleSendMessage"
        />
      </div>
    </div>
  </AppLayout>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import AppLayout from './components/AppLayout.vue'
import ChatArea from './components/ChatArea.vue'
import { uploadImageToOss, recognizeIngredientsByUrl, sendCookingChatMessage } from './api/client.js'

const AI_MESSAGE_STATUS = {
  STREAMING: 'streaming',
  DONE: 'done',
  INTERRUPTED: 'interrupted'
}

const TYPEWRITER_BATCH_SIZE = 2

const STORAGE_KEYS = {
  sessions: 'chefagent-sessions',
  currentSessionId: 'chefagent-current-session-id'
}

const loadStoredSessions = () => {
  try {
    const raw = localStorage.getItem(STORAGE_KEYS.sessions)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch (error) {
    console.warn('读取会话缓存失败，已忽略损坏数据:', error)
    return []
  }
}

const loadStoredCurrentSessionId = () => {
  try {
    return localStorage.getItem(STORAGE_KEYS.currentSessionId)
  } catch (error) {
    console.warn('读取当前会话 ID 失败:', error)
    return null
  }
}

const sessions = ref(loadStoredSessions())
const currentSessionId = ref(loadStoredCurrentSessionId())

// UI 状态
const isGenerating = ref(false)
const isUploading = ref(false)
let pendingPersistTimer = null

const persistSessionState = () => {
  try {
    localStorage.setItem(STORAGE_KEYS.sessions, JSON.stringify(sessions.value))
    if (currentSessionId.value) {
      localStorage.setItem(STORAGE_KEYS.currentSessionId, currentSessionId.value)
    } else {
      localStorage.removeItem(STORAGE_KEYS.currentSessionId)
    }
  } catch (error) {
    console.error('保存会话缓存失败:', error)
  }
}

const schedulePersistSessionState = (delay = 180) => {
  if (pendingPersistTimer) return
  pendingPersistTimer = setTimeout(() => {
    pendingPersistTimer = null
    persistSessionState()
  }, delay)
}

const flushPersistSessionState = () => {
  if (pendingPersistTimer) {
    clearTimeout(pendingPersistTimer)
    pendingPersistTimer = null
  }
  persistSessionState()
}

const buildImageRecognitionSummary = (recogRes) => {
  const parts = []

  if (recogRes.ingredients?.length) {
    parts.push(`图片识别结果：${recogRes.ingredients.join('、')}`)
  }

  if (recogRes.raw_description?.trim()) {
    const description = recogRes.raw_description.trim()
    if (!parts.includes(description)) {
      parts.push(description)
    }
  }

  return parts.join('\n')
}

const createStreamState = (label = '思考中', detail = '', phase = 'thinking') => ({
  label,
  detail,
  phase
})

const setAiStreamState = (msg, label, detail = '', phase = 'thinking') => {
  msg.streamState = createStreamState(label, detail, phase)
}

const typewriterStates = new Map()

const getTypewriterState = (msg) => {
  if (!msg?.id) return null
  if (!typewriterStates.has(msg.id)) {
    typewriterStates.set(msg.id, {
      frameId: null,
      isRunning: false,
      resolvers: []
    })
  }
  return typewriterStates.get(msg.id)
}

const resolveTypewriterWaiters = (msg) => {
  const state = getTypewriterState(msg)
  if (!state) return
  const resolvers = [...state.resolvers]
  state.resolvers.length = 0
  resolvers.forEach(resolve => resolve())
}

const stopTypewriter = (msg, syncToTarget = false) => {
  const state = getTypewriterState(msg)
  if (!state) return
  if (state.frameId) {
    cancelAnimationFrame(state.frameId)
    state.frameId = null
  }
  state.isRunning = false
  if (syncToTarget && typeof msg.targetContent === 'string') {
    msg.content = msg.targetContent
  }
  resolveTypewriterWaiters(msg)
}

const stepTypewriter = (msg) => {
  const state = getTypewriterState(msg)
  if (!state) return

  const currentContent = msg.content || ''
  const targetContent = msg.targetContent || currentContent

  if (currentContent.length >= targetContent.length) {
    msg.content = targetContent
    state.frameId = null
    state.isRunning = false
    resolveTypewriterWaiters(msg)
    return
  }

  const remaining = targetContent.length - currentContent.length
  const batchSize = remaining > 120
    ? TYPEWRITER_BATCH_SIZE * 4
    : remaining > 40
      ? TYPEWRITER_BATCH_SIZE * 2
      : TYPEWRITER_BATCH_SIZE

  msg.content = targetContent.slice(0, currentContent.length + batchSize)
  state.frameId = requestAnimationFrame(() => stepTypewriter(msg))
}

const syncAiTargetContent = (msg, nextContent, immediate = false) => {
  msg.targetContent = nextContent
  if (immediate) {
    msg.content = nextContent
    stopTypewriter(msg)
    return
  }

  const state = getTypewriterState(msg)
  if (!state || state.isRunning) return
  state.isRunning = true
  state.frameId = requestAnimationFrame(() => stepTypewriter(msg))
}

const waitForTypewriterToFinish = (msg) => {
  const targetContent = msg?.targetContent || msg?.content || ''
  if ((msg?.content || '') === targetContent) {
    return Promise.resolve()
  }

  const state = getTypewriterState(msg)
  if (!state) return Promise.resolve()

  return new Promise(resolve => {
    state.resolvers.push(resolve)
    if (!state.isRunning) {
      state.isRunning = true
      state.frameId = requestAnimationFrame(() => stepTypewriter(msg))
    }
  })
}

const finalizeAiVisibleContent = async (msg, finalContent) => {
  syncAiTargetContent(msg, finalContent)
  await waitForTypewriterToFinish(msg)
  msg.content = finalContent
  delete msg.targetContent
  stopTypewriter(msg)
}

const createAiMessage = (initialContent = '') => ({
  id: Date.now().toString(),
  role: 'ai',
  content: initialContent,
  targetContent: initialContent,
  status: AI_MESSAGE_STATUS.STREAMING,
  thinking: true,
  timeTaken: 0,
  timestamp: new Date().toISOString(),
  streamState: createStreamState()
})

const isValidAiStatus = (status) => Object.values(AI_MESSAGE_STATUS).includes(status)

const normalizeAiMessage = (msg) => {
  if (msg.role !== 'ai') return

  if (!isValidAiStatus(msg.status)) {
    if (msg.thinking) {
      msg.status = AI_MESSAGE_STATUS.STREAMING
    } else if (msg.content && msg.content.trim() !== '') {
      msg.status = AI_MESSAGE_STATUS.DONE
    } else {
      msg.status = AI_MESSAGE_STATUS.INTERRUPTED
    }
  }

  // 兼容旧数据，并避免之后继续依赖 thinking 推断消息状态。
  if (msg.status === AI_MESSAGE_STATUS.STREAMING) {
    msg.status = AI_MESSAGE_STATUS.INTERRUPTED
  }

  // 旧版本会把中断提示直接写进正文，这里迁移为空内容，交给 UI 的状态条统一展示。
  if (msg.status === AI_MESSAGE_STATUS.INTERRUPTED && msg.content?.trim() === '> 对话已中断') {
    msg.content = ''
  }

  if (!msg.streamState || typeof msg.streamState !== 'object') {
    msg.streamState = createStreamState(
      msg.status === AI_MESSAGE_STATUS.INTERRUPTED ? '已中断' : '已完成',
      '',
      msg.status === AI_MESSAGE_STATUS.INTERRUPTED ? 'error' : 'done'
    )
  }

  msg.thinking = msg.status === AI_MESSAGE_STATUS.STREAMING
  msg.targetContent = msg.content || ''
}

// 当前会话数据
const currentSession = computed(() => {
  return sessions.value.find(s => s.id === currentSessionId.value)
})

const currentMessages = computed(() => {
  return currentSession.value ? currentSession.value.messages : []
})

// 会话管理
const createNewSession = () => {
  const newSession = {
    id: Date.now().toString(),
    title: '新对话',
    createdAt: new Date().toISOString(),
    messages: [],
    contextIngredients: [] // 保存当前会话识别到的食材上下文
  }
  sessions.value.unshift(newSession)
  currentSessionId.value = newSession.id
  flushPersistSessionState()
}

const selectSession = (id) => {
  currentSessionId.value = id
  flushPersistSessionState()
}

const deleteSession = (id) => {
  const index = sessions.value.findIndex(s => s.id === id)
  if (index !== -1) {
    sessions.value.splice(index, 1)
    if (currentSessionId.value === id) {
      currentSessionId.value = sessions.value.length > 0 ? sessions.value[0].id : null
    }
    flushPersistSessionState()
  }
}

const clearAllSessions = () => {
  if (confirm('确定要清空所有对话记录吗？')) {
    sessions.value = []
    createNewSession()
  }
}

// 初始化
onMounted(() => {
  // 清理异常状态，并将旧版 thinking 字段迁移为显式 status 字段。
  let hasNormalizedChanges = false
  sessions.value.forEach(session => {
    session.messages.forEach(msg => {
      const before = JSON.stringify(msg)
      normalizeAiMessage(msg)
      if (before !== JSON.stringify(msg)) {
        hasNormalizedChanges = true
      }
      // 如果图片还是 blob 链接，它在刷新后已经失效了，可以替换为空或占位符
      if (msg.image && msg.image.startsWith('blob:')) {
        // 清除无效的 blob 链接，避免显示破损图片
        msg.image = null;
        hasNormalizedChanges = true
      }
    });
  });

  if (hasNormalizedChanges) {
    flushPersistSessionState()
  }

  if (sessions.value.length === 0) {
    createNewSession()
  } else if (!currentSessionId.value || !sessions.value.some(s => s.id === currentSessionId.value)) {
    currentSessionId.value = sessions.value[0].id
    flushPersistSessionState()
  }
})

// 自动更新会话标题
watch(() => currentMessages.value, (newMessages) => {
  if (currentSession.value && !currentSession.value.isTitleEdited && currentSession.value.title === '新对话' && newMessages.length > 0) {
    const firstUserMsg = newMessages.find(m => m.role === 'user')
    if (firstUserMsg && firstUserMsg.content) {
      // 截取前 15 个字符作为标题
      currentSession.value.title = firstUserMsg.content.slice(0, 15) + (firstUserMsg.content.length > 15 ? '...' : '')
      schedulePersistSessionState()
    } else if (firstUserMsg && firstUserMsg.image) {
      currentSession.value.title = '图片识别'
      schedulePersistSessionState()
    }
  }
}, { deep: true })

// 核心发送逻辑
const handleSendMessage = async ({ text, image }) => {
  if (!currentSession.value) createNewSession()
  
  const session = currentSession.value
  const startTime = performance.now()

  // 1. 构造并添加用户消息
  const userMessage = {
    id: Date.now().toString(),
    role: 'user',
    content: text || '',
    image: image ? URL.createObjectURL(image) : null,
    timestamp: new Date().toISOString()
  }
  session.messages.push(userMessage)
  flushPersistSessionState()

  // 2. 构造并添加 AI 思考状态消息
  const aiMessage = createAiMessage()
  aiMessage.id = (Date.now() + 1).toString()
  session.messages.push(aiMessage)
  flushPersistSessionState()
  
  try {
    if (image) {
      await handleImageRecognition(image, text, session, aiMessage, startTime, userMessage)
    } else if (text) {
      isGenerating.value = true
      await continueChatFlow(text, session, startTime, aiMessage)
    }
  } catch (error) {
    handleApiError(error, aiMessage, startTime)
  } finally {
    isGenerating.value = false
    isUploading.value = false
    // 确保在流程结束时，无论成功失败，都将状态重置到非 streaming。
    if (aiMessage && aiMessage.status === AI_MESSAGE_STATUS.STREAMING) {
      aiMessage.status = aiMessage.content?.trim()
        ? AI_MESSAGE_STATUS.DONE
        : AI_MESSAGE_STATUS.INTERRUPTED
      aiMessage.thinking = false
      flushPersistSessionState()
    }
  }
}

// 处理图片上传和识别
const handleImageRecognition = async (image, text, session, aiMessage, startTime, userMessage) => {
  isUploading.value = true
  aiMessage.status = AI_MESSAGE_STATUS.STREAMING
  aiMessage.thinking = true
  aiMessage.content = ''
  setAiStreamState(aiMessage, '正在识别图片', '正在上传并识别图片中的食材', 'tool')
  flushPersistSessionState()

  const uploadRes = await uploadImageToOss(image)
  const imageUrl = uploadRes.object_url
  isUploading.value = false

  // 替换本地 blob URL 为 OSS URL，以便刷新后仍然可以显示图片
  if (userMessage) {
    userMessage.image = imageUrl
    flushPersistSessionState()
  }

  isGenerating.value = true
  setAiStreamState(aiMessage, '正在识别图片', '图片上传完成，正在识别食材', 'tool')
  flushPersistSessionState()
  const recogRes = await recognizeIngredientsByUrl(imageUrl, text)
  
  if (recogRes.ingredients && recogRes.ingredients.length > 0) {
    const newSet = new Set([...session.contextIngredients, ...recogRes.ingredients])
    session.contextIngredients = Array.from(newSet)
    flushPersistSessionState()
  }

  const recognitionSummary = buildImageRecognitionSummary(recogRes)
  const fallbackSummary = text
    ? '暂未从图片中识别出明确食材，我先结合你的文字需求继续分析。'
    : '暂未从图片中识别出明确食材，请尝试补充文字说明或换一张更清晰的图片。'
  const finalRecognitionSummary = recognitionSummary || fallbackSummary

  if (text) {
    const prefixContent = `${finalRecognitionSummary}\n\n`
    aiMessage.content = prefixContent
    aiMessage.status = AI_MESSAGE_STATUS.STREAMING
    aiMessage.thinking = true
    setAiStreamState(aiMessage, '思考中', '正在结合图片识别结果思考回复', 'thinking')
    aiMessage.targetContent = aiMessage.content
    flushPersistSessionState()

    await continueChatFlow(text, session, startTime, aiMessage, { prefixContent })
    return
  }

  aiMessage.content = finalRecognitionSummary
  aiMessage.status = AI_MESSAGE_STATUS.DONE
  aiMessage.thinking = false
  aiMessage.timeTaken = performance.now() - startTime
  setAiStreamState(aiMessage, '已完成', '', 'done')
  delete aiMessage.targetContent
  flushPersistSessionState()
}

// 处理 API 错误
const handleApiError = (error, aiMessage, startTime) => {
  console.error('发送消息失败:', error)
  stopTypewriter(aiMessage, true)
  aiMessage.status = AI_MESSAGE_STATUS.INTERRUPTED
  aiMessage.thinking = false
  const errorMessage = `> 请求失败\n\n${error.response?.data?.detail || error.message || '未知错误，请重试。'}`
  aiMessage.content = aiMessage.content?.trim()
    ? `${aiMessage.content}\n\n${errorMessage}`
    : errorMessage
  aiMessage.timeTaken = performance.now() - startTime
  setAiStreamState(aiMessage, '已中断', '请求失败', 'error')
  flushPersistSessionState()
}

// 继续对话流程
const continueChatFlow = async (text, session, startTime, existingAiMsg = null, options = {}) => {
  const prefixContent = options.prefixContent || ''
  let currentAiMsg = existingAiMsg;
  
  if (!currentAiMsg) {
    currentAiMsg = createAiMessage(prefixContent);
    session.messages.push(currentAiMsg);
    flushPersistSessionState()
  } else {
    currentAiMsg.status = AI_MESSAGE_STATUS.STREAMING
    currentAiMsg.thinking = true
    if (prefixContent) {
      currentAiMsg.content = prefixContent
      currentAiMsg.targetContent = prefixContent
    }
    setAiStreamState(currentAiMsg, '思考中', '正在准备回答', 'thinking')
    flushPersistSessionState()
  }

  try {
    const finalAnswer = await sendCookingChatMessage(
      text, 
      session.contextIngredients || [],
      session.id,
      async (streamEvent, fullText) => {
        currentAiMsg.status = AI_MESSAGE_STATUS.STREAMING

        if (streamEvent.event === 'status') {
          const { label = '思考中', detail = '', phase = 'thinking' } = streamEvent.data || {}
          currentAiMsg.thinking = phase !== 'done' && phase !== 'error'
          setAiStreamState(currentAiMsg, label, detail, phase)
        } else if (streamEvent.event === 'content') {
          currentAiMsg.thinking = false
          syncAiTargetContent(currentAiMsg, `${prefixContent}${fullText}`)
        } else if (streamEvent.event === 'error') {
          throw new Error(streamEvent.data?.message || '流式请求失败')
        } else if (streamEvent.event === 'done') {
          syncAiTargetContent(currentAiMsg, `${prefixContent}${streamEvent.data?.final_text || fullText}`)
        }
        await new Promise(resolve => requestAnimationFrame(resolve))
      }
    );
    
    await finalizeAiVisibleContent(currentAiMsg, `${prefixContent}${finalAnswer}`)
    currentAiMsg.status = AI_MESSAGE_STATUS.DONE
    currentAiMsg.thinking = false
    currentAiMsg.timeTaken = performance.now() - startTime
    setAiStreamState(currentAiMsg, '已完成', '', 'done')
    flushPersistSessionState()
  } catch (error) {
    handleApiError(error, currentAiMsg, startTime)
  }
}
</script>
