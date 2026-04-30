<template>
  <div class="flex-1 flex flex-col h-full overflow-hidden bg-white md:rounded-tl-2xl md:shadow-sm border-l border-t border-gray-200 relative">
    
    <!-- Header Actions -->
    <div v-if="messages.length > 0" class="absolute top-4 right-4 md:right-8 z-10">
      <button 
        @click="exportChat"
        class="flex items-center gap-2 bg-white/90 backdrop-blur border border-gray-200 text-gray-600 hover:text-blue-600 hover:border-blue-300 px-3 py-1.5 rounded-lg text-sm shadow-sm transition-all focus:outline-none focus:ring-2 focus:ring-blue-500/20"
        title="导出为 Markdown"
      >
        <Download class="w-4 h-4" />
        导出
      </button>
    </div>

    <!-- Messages Area -->
    <div 
      class="flex-1 overflow-y-auto px-4 py-6 md:px-8 md:py-8 space-y-8 pb-32"
      ref="messagesContainer"
    >
      <template v-if="messages.length === 0">
        <div class="h-full flex flex-col items-center justify-center text-center text-gray-500 animate-in fade-in duration-500">
          <div class="w-16 h-16 bg-blue-50 text-blue-600 rounded-2xl flex items-center justify-center mb-6 shadow-sm">
            <ChefHat class="w-8 h-8" />
          </div>
          <h2 class="text-2xl font-semibold text-gray-800 mb-2">有什么我可以帮您的？</h2>
          <p class="max-w-sm text-sm text-gray-400">
            我是您的专属 ChefAgent。您可以直接告诉我家里有什么食材，或者上传食材图片，我来为您量身定制菜谱。
          </p>
        </div>
      </template>

      <template v-else>
        <div 
          v-for="(msg, index) in messages" 
          :key="index"
          class="flex w-full animate-in fade-in slide-in-from-bottom-2"
          :class="msg.role === 'user' ? 'justify-end' : 'justify-start'"
        >
          <!-- AI Avatar -->
          <div v-if="msg.role === 'ai'" class="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center text-blue-600 mr-3 shrink-0 mt-1">
            <Bot class="w-5 h-5" />
          </div>

          <!-- Message Bubble -->
          <div 
            class="max-w-[85%] md:max-w-[75%] rounded-2xl px-5 py-3 relative group"
            :class="[
              msg.role === 'user' 
                ? 'bg-gray-100 text-gray-800 rounded-br-sm' 
                : 'bg-white border border-gray-100 shadow-sm text-gray-800 rounded-bl-sm'
            ]"
          >
            <!-- User Uploaded Image -->
            <div v-if="msg.image" class="mb-3">
              <img :src="msg.image" alt="Uploaded" class="max-w-xs rounded-xl shadow-sm border border-gray-200" />
            </div>

            <!-- AI Content -->
            <template v-if="msg.role === 'ai'">
              <!-- Thinking Status Indicator (Before first content arrives) -->
              <div v-if="msg.thinking && !hasContent(msg.content)" class="flex items-center gap-2 text-sm text-gray-500 py-1">
                <Loader2 class="w-4 h-4 animate-spin text-blue-500" />
                <span>{{ getStreamingStatusLabel(msg) }}</span>
              </div>

              <!-- Markdown Content -->
              <div
                v-if="hasContent(msg.content)"
                class="prose prose-sm sm:prose-base max-w-none break-words"
                v-html="renderMarkdown(msg.content)"
              ></div>
              
              <div
                v-if="msg.status === 'interrupted'"
                class="mt-3 rounded-xl border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-500"
              >
                {{ getInterruptedNotice(msg.content) }}
              </div>
            </template>

            <!-- Plain Text (User) -->
            <div v-else class="whitespace-pre-wrap break-words text-[15px] leading-relaxed">
              {{ msg.content }}
            </div>

            <!-- Time Taken Indicator & Actions -->
            <div v-if="msg.status !== 'streaming' && hasContent(msg.content)" class="mt-3 flex items-center justify-between text-xs text-gray-400 font-mono">
              <div v-if="msg.role === 'ai' && msg.timeTaken" class="flex items-center gap-1.5">
                <Clock class="w-3.5 h-3.5" />
                <span>耗时 {{ (msg.timeTaken / 1000).toFixed(1) }}s</span>
              </div>
              <div v-else></div>
              <div class="flex items-center gap-2">
                <button 
                  v-if="msg.role === 'ai'"
                  @click="copyToClipboard(msg.content)"
                  class="flex items-center gap-1 hover:text-gray-600 hover:bg-gray-100 transition-colors px-2 py-1 rounded"
                  title="复制内容"
                >
                  <Copy class="w-3.5 h-3.5" />
                  <span>复制</span>
                </button>
                <button 
                  @click="$emit('deleteMessage', msg.id)"
                  class="flex items-center gap-1 hover:text-red-500 hover:bg-red-50 transition-colors px-2 py-1 rounded"
                  title="删除消息"
                >
                  <Trash2 class="w-3.5 h-3.5" />
                  <span>删除</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      </template>
    </div>

    <!-- Input Area -->
    <div class="p-4 md:p-6 bg-white border-t border-gray-100 w-full relative">
      <!-- Input Box Container -->
      <div class="max-w-4xl mx-auto relative flex flex-col rounded-2xl border border-gray-300 bg-white shadow-sm focus-within:ring-2 focus-within:ring-blue-500/20 focus-within:border-blue-500 transition-all overflow-hidden">
        
        <!-- Image Preview Area -->
        <div v-if="previewImage" class="px-4 pt-3 pb-1 flex relative group">
          <div class="relative inline-block">
            <img :src="previewImage.url" class="h-16 w-16 object-cover rounded-lg border border-gray-200" />
            <button 
              @click="clearImage" 
              class="absolute -top-2 -right-2 bg-gray-800 text-white rounded-full p-1 opacity-0 group-hover:opacity-100 transition-opacity"
            >
              <X class="w-3 h-3" />
            </button>
            <div v-if="isUploading" class="absolute inset-0 bg-white/60 flex items-center justify-center rounded-lg">
              <Loader2 class="w-5 h-5 animate-spin text-blue-600" />
            </div>
          </div>
        </div>

        <!-- Textarea -->
        <textarea
          ref="inputRef"
          v-model="inputMessage"
          @keydown.enter.prevent="handleEnter"
          @input="adjustHeight"
          rows="1"
          aria-label="输入您的食材或需求"
          placeholder="输入您的食材或需求，如：西红柿和鸡蛋怎么做？"
          class="w-full resize-none bg-transparent px-4 py-3.5 text-gray-800 placeholder-gray-400 focus:outline-none text-[15px] leading-relaxed max-h-48"
          :disabled="isGenerating"
        ></textarea>

        <!-- Actions -->
        <div class="flex items-center justify-between px-3 pb-3 pt-1">
          <div class="flex items-center gap-1 text-gray-400">
            <!-- Hidden File Input -->
            <input 
              type="file" 
              ref="fileInput" 
              class="hidden" 
              aria-label="上传图片"
              accept="image/png, image/jpeg, image/jpg, image/webp" 
              @change="handleFileUpload" 
            />
            <button 
              @click="$refs.fileInput.click()"
              class="p-2 hover:bg-gray-100 hover:text-gray-600 rounded-lg transition-colors focus:ring-2 focus:ring-blue-500/20 outline-none"
              title="上传图片"
              aria-label="上传图片"
              :disabled="isGenerating || isUploading"
            >
              <ImageIcon class="w-5 h-5" />
            </button>
          </div>

          <div class="flex items-center gap-2">
            <div class="text-xs text-gray-400 hidden sm:block" aria-hidden="true">
              按 Enter 发送，Shift + Enter 换行
            </div>
            
            <button 
              v-if="isGenerating"
              @click="$emit('stop')"
              class="px-3 py-2 rounded-xl transition-all flex items-center justify-center shadow-sm bg-red-50 text-red-600 hover:bg-red-100 outline-none"
              title="停止生成"
              aria-label="停止生成"
            >
              <div class="w-2.5 h-2.5 bg-red-600 rounded-sm mr-1.5"></div>
              <span class="text-sm font-medium">停止</span>
            </button>

            <button 
              v-else
              @click="sendMessage"
              class="p-2 rounded-xl transition-all flex items-center justify-center shadow-sm focus:ring-2 focus:ring-blue-500/20 outline-none"
              title="发送消息"
              aria-label="发送消息"
              :class="[
                inputMessage.trim() || previewImage 
                  ? 'bg-blue-600 hover:bg-blue-700 text-white' 
                  : 'bg-gray-100 text-gray-400 cursor-not-allowed'
              ]"
              :disabled="(!inputMessage.trim() && !previewImage) || isUploading"
            >
              <ArrowUp class="w-5 h-5" />
            </button>
          </div>
        </div>
      </div>
      
      <div class="text-center text-xs text-gray-400 mt-4 hidden sm:block">
        AI 内容由模型生成，可能存在误差，烹饪前请确认食材安全。
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick, onMounted } from 'vue'
import { ChefHat, Bot, User, ArrowUp, Image as ImageIcon, Loader2, Clock, X, Copy, Download, Trash2 } from 'lucide-vue-next'
import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js'
import 'highlight.js/styles/github-dark.css'

const props = defineProps({
  messages: {
    type: Array,
    required: true
  },
  isGenerating: {
    type: Boolean,
    default: false
  },
  isUploading: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['send', 'stop', 'deleteMessage'])

const inputMessage = ref('')
const inputRef = ref(null)
const messagesContainer = ref(null)
const fileInput = ref(null)
const previewImage = ref(null)

// Initialize Markdown-it with highlight.js
const md = new MarkdownIt({
  html: true,
  linkify: true,
  typographer: true,
  highlight: function (str, lang) {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return hljs.highlight(str, { language: lang }).value;
      } catch (__) {}
    }
    return ''; // use external default escaping
  }
})

const renderMarkdown = (content) => {
  if (!content) return ''
  
  let processed = content
  
  // Handle <think> tags for reasoning models
  if (processed.includes('<think>')) {
    // Replace all complete <think>...</think> blocks
    processed = processed.replace(
      /<think>([\s\S]*?)<\/think>/g, 
      (match, innerContent) => {
        return `<div class="thinking-wrapper mb-4">
          <details class="thinking-block group">
            <summary class="cursor-pointer select-none font-medium text-gray-400 text-xs hover:text-gray-600 transition-colors flex items-center gap-1.5 list-none">
              <span class="inline-block transition-transform text-[10px] group-open:rotate-90">▶</span>
              <span>思考过程</span>
            </summary>
            <div class="mt-2 pl-3 border-l-2 border-gray-200 text-xs text-gray-500 whitespace-pre-wrap leading-relaxed">${innerContent || '...'}</div>
          </details>
        </div>`
      }
    )
    
    // Handle any remaining unclosed <think> tag at the end
    if (processed.includes('<think>')) {
      processed = processed.replace(
        /<think>([\s\S]*)$/g, 
        (match, innerContent) => {
          return `<div class="thinking-wrapper mb-4">
            <details open class="thinking-block group">
              <summary class="cursor-pointer select-none font-medium text-gray-400 text-xs hover:text-gray-600 transition-colors flex items-center gap-1.5 list-none">
                <span class="inline-block animate-pulse text-blue-500">●</span>
                <span>深入思考中...</span>
              </summary>
              <div class="mt-2 pl-3 border-l-2 border-blue-100 text-xs text-gray-500 whitespace-pre-wrap leading-relaxed">${innerContent || '...'}</div>
            </details>
          </div>`
        }
      )
    }
  }

  // 哪怕最后没有普通文本，也要把 HTML 渲染出来，否则页面是空白的
  return md.render(processed) || processed
}

const escapeHtml = (content) => {
  return content
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

const stripThinkContent = (content) => {
  if (!content) return ''
  const withoutOpenThink = content.replace(/<think>[\s\S]*$/g, '')
  return withoutOpenThink.replace(/<think>[\s\S]*?<\/think>/g, '')
}

const getStreamingVisibleContent = (msg) => {
  return stripThinkContent(msg?.content || '')
}

const renderStreamingContent = (msg) => {
  return escapeHtml(getStreamingVisibleContent(msg))
}

const hasVisibleStreamingContent = (msg) => {
  return Boolean(getStreamingVisibleContent(msg).trim())
}

const hasRenderableAiContent = (msg) => {
  if (msg.role !== 'ai') return hasContent(msg.content)
  return msg.status === 'streaming'
    ? hasVisibleStreamingContent(msg)
    : hasContent(msg.content)
}

const getLatestThinkText = (content) => {
  if (!content || !content.includes('<think>')) return ''
  const matches = [...content.matchAll(/<think>([\s\S]*?)(?:<\/think>|$)/g)]
  if (!matches.length) return ''
  return (matches.at(-1)?.[1] || '').trim()
}

const getStreamingStatusLabel = (msg) => {
  if (msg?.streamState?.label) return msg.streamState.label

  const latestThinkText = getLatestThinkText(msg?.content)

  if (!latestThinkText) {
    return hasVisibleStreamingContent(msg) ? '继续生成中...' : '正在构思美味...'
  }

  if (/识别.*图片|图片.*识别|识别.*食材/.test(latestThinkText)) {
    return '正在识别图片'
  }

  if (/调用工具\s+web_search|搜索：/.test(latestThinkText)) {
    return '正在搜索'
  }

  if (/搜索完成/.test(latestThinkText)) {
    return '搜索完成'
  }

  if (/思考|评估|检索/.test(latestThinkText)) {
    return '思考中'
  }

  return hasVisibleStreamingContent(msg) ? '继续生成中...' : '正在构思美味...'
}

const getStreamingStatusDetail = (msg) => {
  if (msg?.streamState?.detail) return msg.streamState.detail

  const latestThinkText = getLatestThinkText(msg?.content)
  if (!latestThinkText) return ''

  const searchMatch = latestThinkText.match(/调用工具\s+web_search\s+搜索：(.+?)\.\.\./)
  if (searchMatch?.[1]) {
    return searchMatch[1]
  }

  const detailLine = latestThinkText
    .split('\n')
    .map(line => line.trim())
    .filter(Boolean)
    .find(line => !/搜索完成/.test(line))

  return detailLine || ''
}

const hasContent = (content) => Boolean(content && content.trim())

const getInterruptedNotice = (content) => {
  return hasContent(content)
    ? '本次回复已中断，以下为中断前已生成的内容。'
    : '本次回复已中断，请重新发送。'
}

// Auto scroll to bottom
const scrollToBottom = async () => {
  await nextTick()
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

watch(() => props.messages, scrollToBottom, { deep: true })
onMounted(scrollToBottom)

// Auto adjust textarea height
const adjustHeight = () => {
  const el = inputRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = `${Math.min(el.scrollHeight, 192)}px` // max-h-48 (192px)
}

const handleEnter = (e) => {
  if (e.shiftKey) return
  sendMessage()
}

const handleFileUpload = (e) => {
  const file = e.target.files[0]
  if (!file) return
  
  // Only accept images
  if (!file.type.startsWith('image/')) {
    alert('请上传图片文件')
    return
  }

  // Create local preview URL
  const objectUrl = URL.createObjectURL(file)
  previewImage.value = {
    file,
    url: objectUrl
  }
  
  // Reset file input
  e.target.value = ''
}

const clearImage = () => {
  if (previewImage.value?.url) {
    URL.revokeObjectURL(previewImage.value.url)
  }
  previewImage.value = null
}

const sendMessage = () => {
  if ((!inputMessage.value.trim() && !previewImage.value) || props.isGenerating || props.isUploading) return

  emit('send', {
    text: inputMessage.value.trim(),
    image: previewImage.value?.file
  })

  inputMessage.value = ''
  clearImage()
  
  nextTick(() => {
    adjustHeight()
  })
}

// 复制消息内容
const copyToClipboard = async (text) => {
  try {
    // 过滤掉 <think> 标签及其内容（如果是完整的内容，这里也可以选择保留，但通常用户更希望只复制最终结果）
    const cleanText = text.replace(/<think>[\s\S]*?<\/think>/g, '').trim()
    await navigator.clipboard.writeText(cleanText)
    // 可以添加一个小提示，但为了简单起见，这里直接完成
  } catch (err) {
    console.error('复制失败:', err)
  }
}

// 导出聊天记录为 Markdown
const exportChat = () => {
  if (props.messages.length === 0) return

  let mdContent = '# ChefAgent - 对话记录\n\n'
  
  props.messages.forEach(msg => {
    const roleName = msg.role === 'user' ? '👤 我' : '👨‍🍳 ChefAgent'
    const time = new Date(msg.timestamp).toLocaleString()
    
    mdContent += `### ${roleName} \n_${time}_\n\n`
    
    if (msg.image) {
      mdContent += `[图片]\n\n`
    }
    
    if (msg.content) {
      // 过滤掉 <think> 标签，或者保留？通常导出时可以保留并标记为思考过程
      let content = msg.content
      if (content.includes('<think>')) {
        content = content.replace(/<think>([\s\S]*?)<\/think>/g, '> **思考过程：**\n> $1\n\n')
      }
      mdContent += `${content}\n\n`
    }
    
    mdContent += '---\n\n'
  })

  const blob = new Blob([mdContent], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `ChefAgent_Chat_${new Date().toISOString().replace(/[:.]/g, '-')}.md`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
</script>
