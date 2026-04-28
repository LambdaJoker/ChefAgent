<template>
  <div class="flex h-screen bg-gray-50 overflow-hidden text-gray-900">
    <!-- Sidebar Desktop -->
    <aside 
      class="bg-white border-r border-gray-200 flex flex-col transition-all duration-300 z-10 hidden md:flex"
      :class="isDesktopSidebarOpen ? 'w-64' : 'w-0 overflow-hidden'"
    >
      <div class="p-4 flex items-center justify-between min-w-[16rem]">
        <h1 class="text-xl font-semibold flex items-center gap-2">
          <ChefHat class="w-6 h-6 text-blue-600" aria-hidden="true" />
          ChefAgent
        </h1>
        <button @click="toggleDesktopSidebar" class="p-1 hover:bg-gray-100 rounded text-gray-500 transition-colors" aria-label="收起侧边栏">
          <PanelLeftClose class="w-5 h-5" aria-hidden="true" />
        </button>
      </div>
      
      <div class="px-4 pb-4 min-w-[16rem]">
        <button 
          @click="$emit('new-chat')"
          aria-label="新建对话"
          class="w-full flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 text-white py-2 px-4 rounded-lg transition-colors font-medium shadow-sm focus:ring-2 focus:ring-blue-500/50 outline-none"
        >
          <Plus class="w-5 h-5" aria-hidden="true" />
          新建对话
        </button>
      </div>

      <div class="flex-1 overflow-y-auto px-3 space-y-1 custom-scrollbar min-w-[16rem]">
        <div class="text-xs font-medium text-gray-400 mb-3 px-2 mt-2" aria-hidden="true">历史记录</div>
        <div
          v-for="session in sessions"
          :key="session.id"
          @click="$emit('select-session', session.id)"
          class="w-full text-left px-3 py-2.5 rounded-lg transition-all group relative flex items-center gap-3 cursor-pointer focus-within:ring-2 focus-within:ring-blue-500/20"
          :class="session.id === currentSessionId ? 'bg-blue-50 text-blue-700' : 'hover:bg-gray-100 text-gray-700'"
          :aria-current="session.id === currentSessionId ? 'page' : undefined"
        >
          <MessageSquare class="w-4 h-4 shrink-0" :class="session.id === currentSessionId ? 'text-blue-600' : 'text-gray-400 group-hover:text-gray-600'" aria-hidden="true" />
          
          <!-- 编辑模式 -->
          <input 
            v-if="editingSessionId === session.id"
            v-model="editTitleText"
            @blur="saveEditTitle(session)"
            @keyup.enter="saveEditTitle(session)"
            @keyup.esc="cancelEdit"
            @click.stop
            ref="editInputRef"
            class="flex-1 bg-white border border-blue-300 rounded px-1 py-0.5 text-sm outline-none text-gray-900"
            maxlength="20"
          />
          <!-- 正常显示模式 -->
          <div v-else class="flex-1 truncate text-sm select-none">{{ session.title || '新对话' }}</div>
          
          <!-- 操作按钮组 -->
          <div class="opacity-0 group-hover:opacity-100 flex items-center gap-1 absolute right-2 transition-all">
            <button 
              v-if="editingSessionId !== session.id"
              @click.stop="startEditTitle(session)"
              aria-label="重命名对话"
              class="p-1 hover:bg-blue-100 hover:text-blue-600 rounded transition-all focus:opacity-100 focus:outline-none"
            >
              <Edit2 class="w-3.5 h-3.5" aria-hidden="true" />
            </button>
            <button 
              @click.stop="$emit('delete-session', session.id)"
              aria-label="删除对话"
              class="p-1 hover:bg-red-100 hover:text-red-600 rounded transition-all focus:opacity-100 focus:outline-none"
            >
              <Trash2 class="w-3.5 h-3.5" aria-hidden="true" />
            </button>
          </div>
        </div>
        <div v-if="sessions.length === 0" class="text-center text-sm text-gray-400 py-4">
          暂无历史记录
        </div>
      </div>
      
      <!-- 清空所有会话 -->
      <div v-if="sessions.length > 0" class="p-3 border-t border-gray-100 min-w-[16rem]">
        <button 
          @click="$emit('clear-all-sessions')"
          class="w-full flex items-center justify-center gap-2 text-gray-500 hover:text-red-600 hover:bg-red-50 py-2 rounded-lg transition-colors text-sm"
        >
          <Trash class="w-4 h-4" />
          清空所有记录
        </button>
      </div>
    </aside>

    <!-- Desktop Sidebar Toggle Button (When Closed) -->
    <div 
      v-if="!isDesktopSidebarOpen" 
      class="hidden md:flex absolute left-0 top-1/2 -translate-y-1/2 z-20"
    >
      <button 
        @click="toggleDesktopSidebar" 
        class="bg-white border border-gray-200 border-l-0 rounded-r-lg p-2 shadow-sm hover:bg-gray-50 text-gray-500 transition-colors"
        aria-label="展开侧边栏"
      >
        <PanelLeftOpen class="w-5 h-5" />
      </button>
    </div>

    <!-- Mobile Sidebar Overlay & Drawer -->
    <div 
      v-if="isMobileMenuOpen" 
      class="fixed inset-0 bg-gray-900/50 z-40 md:hidden backdrop-blur-sm transition-opacity"
      @click="isMobileMenuOpen = false"
      aria-hidden="true"
    ></div>
    
    <aside 
      class="fixed inset-y-0 left-0 w-72 bg-white border-r border-gray-200 z-50 md:hidden transform transition-transform duration-300 ease-in-out shadow-2xl flex flex-col"
      :class="isMobileMenuOpen ? 'translate-x-0' : '-translate-x-full'"
      role="dialog"
      aria-modal="true"
      aria-label="手机端侧边栏"
    >
      <div class="p-4 flex items-center justify-between border-b border-gray-100">
        <h1 class="text-xl font-semibold flex items-center gap-2">
          <ChefHat class="w-6 h-6 text-blue-600" aria-hidden="true" />
          ChefAgent
        </h1>
        <button @click="isMobileMenuOpen = false" class="p-2 hover:bg-gray-100 rounded-lg text-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20" aria-label="关闭侧边栏">
          <X class="w-5 h-5" aria-hidden="true" />
        </button>
      </div>
      
      <div class="p-4">
        <button 
          @click="() => { $emit('new-chat'); isMobileMenuOpen = false; }"
          aria-label="新建对话"
          class="w-full flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 text-white py-2.5 px-4 rounded-xl transition-colors font-medium shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500/50"
        >
          <Plus class="w-5 h-5" aria-hidden="true" />
          新建对话
        </button>
      </div>

      <div class="flex-1 overflow-y-auto px-3 space-y-1 pb-4 custom-scrollbar">
        <div class="text-xs font-medium text-gray-400 mb-3 px-2 mt-2" aria-hidden="true">历史记录</div>
        <div
          v-for="session in sessions"
          :key="session.id"
          @click="() => { $emit('select-session', session.id); isMobileMenuOpen = false; }"
          @keydown.enter.prevent="() => { $emit('select-session', session.id); isMobileMenuOpen = false; }"
          @keydown.space.prevent="() => { $emit('select-session', session.id); isMobileMenuOpen = false; }"
          role="button"
          tabindex="0"
          class="w-full text-left px-3 py-3 rounded-xl transition-all group relative flex items-center gap-3 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
          :class="session.id === currentSessionId ? 'bg-blue-50 text-blue-700' : 'hover:bg-gray-50 text-gray-700'"
          :aria-current="session.id === currentSessionId ? 'page' : undefined"
        >
          <MessageSquare class="w-5 h-5 shrink-0" :class="session.id === currentSessionId ? 'text-blue-600' : 'text-gray-400'" aria-hidden="true" />
          <div class="flex-1 truncate text-[15px] font-medium">{{ session.title || '新对话' }}</div>
          
          <button 
            @click.stop="$emit('delete-session', session.id)"
            aria-label="删除对话"
            class="p-2 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors absolute right-1 focus:outline-none focus:ring-1 focus:ring-red-500"
          >
            <Trash2 class="w-4 h-4" aria-hidden="true" />
          </button>
        </div>
        <div v-if="sessions.length === 0" class="text-center text-sm text-gray-400 py-4">
          暂无历史记录
        </div>
      </div>
    </aside>

    <!-- Mobile Header -->
    <div class="md:hidden absolute top-0 left-0 right-0 h-14 bg-white border-b border-gray-200 flex items-center justify-between px-4 z-20">
      <button @click="isMobileMenuOpen = true" class="p-2 hover:bg-gray-100 rounded-lg text-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500/20" aria-label="打开菜单">
        <Menu class="w-5 h-5" aria-hidden="true" />
      </button>
      <h1 class="text-lg font-semibold flex items-center gap-2">
        <ChefHat class="w-5 h-5 text-blue-600" aria-hidden="true" />
        ChefAgent
      </h1>
      <button @click="$emit('new-chat')" class="p-2 text-gray-600 hover:bg-gray-100 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/20" aria-label="新建对话">
        <Plus class="w-5 h-5" aria-hidden="true" />
      </button>
    </div>

    <!-- Main Content Slot -->
    <main class="flex-1 flex flex-col relative pt-14 md:pt-0 h-full w-full">
      <slot></slot>
    </main>
  </div>
</template>

<script setup>
import { ref, nextTick } from 'vue'
import { ChefHat, Plus, MessageSquare, Trash2, Trash, Menu, X, Edit2, PanelLeftClose, PanelLeftOpen } from 'lucide-vue-next'

defineProps({
  sessions: {
    type: Array,
    required: true
  },
  currentSessionId: {
    type: String,
    required: true
  }
})

defineEmits(['new-chat', 'select-session', 'delete-session', 'clear-all-sessions'])

const isMobileMenuOpen = ref(false)

// 桌面端侧边栏展开/折叠状态
const isDesktopSidebarOpen = ref(true)
const toggleDesktopSidebar = () => {
  isDesktopSidebarOpen.value = !isDesktopSidebarOpen.value
}

// 会话标题编辑相关状态
const editingSessionId = ref(null)
const editTitleText = ref('')
const editInputRef = ref(null)

const startEditTitle = async (session) => {
  editingSessionId.value = session.id
  editTitleText.value = session.title || '新对话'
  
  // 等待 DOM 更新后聚焦输入框
  await nextTick()
  if (editInputRef.value && editInputRef.value.length > 0) {
    editInputRef.value[0].focus()
  } else if (editInputRef.value) {
    editInputRef.value.focus()
  }
}

const saveEditTitle = (session) => {
  if (editingSessionId.value === session.id) {
    const newTitle = editTitleText.value.trim()
    if (newTitle) {
      session.title = newTitle
      // 如果需要防止App.vue的watch自动覆盖它，我们可以在session上加一个标记
      session.isTitleEdited = true
    }
    editingSessionId.value = null
  }
}

const cancelEdit = () => {
  editingSessionId.value = null
}
</script>
