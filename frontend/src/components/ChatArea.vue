<script setup>
import { ref, watch, nextTick, onMounted, onUnmounted } from 'vue';
import { useChatStore } from '@/stores/chat';
import MessageBubble from './MessageBubble.vue';

const selectedModel = ref('DeepSeek-V4-Flash');
const inputText = ref('');

const models = [
  { id: 'deepseek-v4-flash', label: 'DeepSeek-V4-Flash', badge: 'New' },
  { id: 'deepseek-v4-pro', label: 'DeepSeek-V4-Pro', badge: 'New' },
];

const suggestedQuestions = [
  '我买的衣服不合适怎么退？',
  '我的快递到哪了？',
  '这款手机支持5G吗？',
];

const isModelDropdownOpen = ref(false);
const selectorRef = ref(null);
const messagesRef = ref(null);

const chatStore = useChatStore();

function handleDocClick(e) {
  if (selectorRef.value && !selectorRef.value.contains(e.target)) {
    isModelDropdownOpen.value = false;
  }
}

onMounted(() => document.addEventListener('click', handleDocClick));
onUnmounted(() => document.removeEventListener('click', handleDocClick));

function handleSuggestedClick(question) {
  chatStore.sendMessage(question);
}

function handleSend() {
  const text = inputText.value.trim();
  if (!text || chatStore.isStreaming) return;
  inputText.value = '';
  chatStore.sendMessage(text);
}

function handleKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    handleSend();
  }
}

/** 新消息到达时自动滚动到底部。 */
watch(
  () => chatStore.messages.length,
  () => nextTick(() => {
    if (messagesRef.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight;
    }
  }),
);

/** 流式 token 追加时也滚动。 */
watch(
  () => {
    const last = chatStore.lastBotMessage;
    return last ? last.text.length : 0;
  },
  () => nextTick(() => {
    if (messagesRef.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight;
    }
  }),
);
</script>

<template>
  <main class="chat-area">
    <!-- Header -->
    <header class="chat-area__header">
      <div ref="selectorRef" class="chat-area__model-selector">
        <button
          class="chat-area__model-btn"
          @click="isModelDropdownOpen = !isModelDropdownOpen"
        >
          <span class="chat-area__model-name">{{ selectedModel }}</span>
          <span
            v-for="model in models"
            :key="model.id"
            v-show="model.label === selectedModel && model.badge"
            class="chat-area__badge chat-area__badge--new"
          >{{ model.badge }}</span>
          <svg class="chat-area__model-arrow" :class="{ 'chat-area__model-arrow--open': isModelDropdownOpen }" width="12" height="12" viewBox="0 0 12 12" fill="none">
            <path d="M3 4.5l3 3 3-3" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </button>

        <transition name="dropdown">
          <div v-if="isModelDropdownOpen" class="chat-area__model-dropdown">
            <button
              v-for="model in models"
              :key="model.id"
              class="chat-area__model-option"
              :class="{ 'chat-area__model-option--active': model.label === selectedModel }"
              @click="selectedModel = model.label; isModelDropdownOpen = false"
            >
              <span>{{ model.label }}</span>
              <span v-if="model.badge" class="chat-area__badge chat-area__badge--new">{{ model.badge }}</span>
            </button>
          </div>
        </transition>
      </div>

      <div class="chat-area__header-actions">
        <button class="chat-area__btn-outline">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M6 2H3a1 1 0 00-1 1v8a1 1 0 001 1h8a1 1 0 001-1V8" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
            <path d="M7 7h5M9.5 4.5L12 7l-2.5 2.5" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          API 服务
        </button>
        <button class="chat-area__btn-primary">立即登录</button>
      </div>
    </header>

    <!-- Messages Area -->
    <div v-if="chatStore.messages.length" ref="messagesRef" class="chat-area__messages">
      <MessageBubble
        v-for="msg in chatStore.messages"
        :key="msg.id"
        :message="msg"
      />
    </div>

    <!-- Welcome / Empty State -->
    <div v-else class="chat-area__welcome">
      <div class="chat-area__welcome-inner">
        <h1 class="chat-area__title">智能客服系统</h1>
        <p class="chat-area__subtitle">问题自动分类与回答生成，为您提供快速准确的电商客服支持</p>

        <div class="chat-area__divider" />

        <p class="chat-area__suggest-label">您可以这样问</p>

        <div class="chat-area__suggest-list">
          <button
            v-for="(q, idx) in suggestedQuestions"
            :key="idx"
            class="chat-area__suggest-item"
            @click="handleSuggestedClick(q)"
          >
            {{ q }}
          </button>
        </div>
      </div>
    </div>

    <!-- Input Area -->
    <div class="chat-area__input-wrapper">
      <div class="chat-area__input-box">
        <textarea
          v-model="inputText"
          class="chat-area__textarea"
          placeholder="请输入您的问题..."
          rows="1"
          @keydown="handleKeydown"
        />
        <div class="chat-area__input-actions">
          <button class="chat-area__input-btn" title="附件">
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
              <path d="M9 3v12M3 9h12" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>
            </svg>
          </button>
          <button
            class="chat-area__send-btn"
            :class="{ 'chat-area__send-btn--active': inputText.trim() }"
            :disabled="!inputText.trim()"
            @click="handleSend"
            title="发送"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M3 8h10M9 4l4 4-4 4" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </button>
        </div>
      </div>
      <p class="chat-area__footer-text">
        本网站为电商客服智能问答系统原型，回答由 AI 生成，仅供参考。
      </p>
    </div>
  </main>
</template>

<style scoped>
.chat-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
  background-color: var(--color-bg);
}

/* ─── Header ─── */
.chat-area__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: var(--header-height);
  padding: 0 var(--space-2xl);
  flex-shrink: 0;
  border-bottom: 1px solid var(--color-border-light);
}

.chat-area__model-selector {
  position: relative;
}

.chat-area__model-btn {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  padding: var(--space-xs) var(--space-sm);
  border-radius: var(--radius-md);
  font-size: var(--font-size-md);
  font-weight: var(--font-weight-medium);
  color: var(--color-text-primary);
  transition: background-color 0.15s ease;
}

.chat-area__model-btn:hover {
  background-color: var(--color-card);
}

.chat-area__model-arrow {
  color: var(--color-text-tertiary);
  transition: transform 0.2s ease;
}

.chat-area__model-arrow--open {
  transform: rotate(180deg);
}

.chat-area__model-dropdown {
  position: absolute;
  top: calc(100% + var(--space-xs));
  left: 0;
  min-width: 200px;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-md);
  padding: var(--space-xs);
  z-index: 100;
}

.chat-area__model-option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: var(--space-sm) var(--space-md);
  border-radius: var(--radius-sm);
  font-size: var(--font-size-md);
  color: var(--color-text-primary);
  transition: background-color 0.12s ease;
}

.chat-area__model-option:hover {
  background-color: var(--color-card);
}

.chat-area__model-option--active {
  font-weight: var(--font-weight-medium);
  background-color: var(--color-card);
}

.chat-area__badge {
  font-size: var(--font-size-xs);
  padding: 1px 6px;
  border-radius: var(--radius-full);
  font-weight: var(--font-weight-medium);
  line-height: 1.6;
}

.chat-area__badge--new {
  background-color: var(--color-badge-new-bg);
  color: var(--color-badge-new-text);
}

.chat-area__header-actions {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
}

.chat-area__btn-outline {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  padding: var(--space-sm) var(--space-lg);
  border: 1px solid var(--color-btn-outline-border);
  border-radius: var(--radius-md);
  font-size: var(--font-size-md);
  color: var(--color-text-primary);
  transition: all 0.15s ease;
}

.chat-area__btn-outline:hover {
  background-color: var(--color-card);
  border-color: var(--color-text-tertiary);
}

.chat-area__btn-primary {
  padding: var(--space-sm) var(--space-lg);
  background-color: var(--color-btn-dark);
  color: #ffffff;
  border-radius: var(--radius-md);
  font-size: var(--font-size-md);
  font-weight: var(--font-weight-medium);
  transition: background-color 0.15s ease;
}

.chat-area__btn-primary:hover {
  background-color: var(--color-btn-dark-hover);
}

/* ─── Messages Area ─── */
.chat-area__messages {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-2xl);
  display: flex;
  flex-direction: column;
}

/* ─── Welcome / Empty State ─── */
.chat-area__welcome {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 var(--space-2xl);
  overflow-y: auto;
}

.chat-area__welcome-inner {
  width: 100%;
  max-width: var(--content-max-width);
}

.chat-area__title {
  font-size: var(--font-size-hero);
  font-weight: var(--font-weight-bold);
  color: var(--color-text-primary);
  letter-spacing: -0.02em;
  margin-bottom: var(--space-sm);
}

.chat-area__subtitle {
  font-size: var(--font-size-lg);
  color: var(--color-text-secondary);
  line-height: 1.6;
  margin-bottom: var(--space-3xl);
}

.chat-area__divider {
  width: 100%;
  height: 1px;
  background-color: var(--color-border-light);
  margin-bottom: var(--space-xl);
}

.chat-area__suggest-label {
  font-size: var(--font-size-sm);
  color: var(--color-text-tertiary);
  margin-bottom: var(--space-md);
}

.chat-area__suggest-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
}

.chat-area__suggest-item {
  text-align: left;
  padding: var(--space-md) var(--space-lg);
  background-color: var(--color-card);
  border-radius: var(--radius-md);
  font-size: var(--font-size-md);
  color: var(--color-text-primary);
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  border: 1px solid transparent;
  width: 100%;
}

.chat-area__suggest-item:hover {
  background-color: var(--color-card-hover);
  border-color: var(--color-border);
  transform: translateX(4px);
}

/* ─── Input Area ─── */
.chat-area__input-wrapper {
  padding: 0 var(--space-2xl) var(--space-xl);
  flex-shrink: 0;
}

.chat-area__input-box {
  display: flex;
  align-items: flex-end;
  background-color: var(--color-input-bg);
  border: 1px solid var(--color-input-border);
  border-radius: var(--radius-lg);
  padding: var(--space-md) var(--space-lg);
  box-shadow: var(--shadow-input);
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.chat-area__input-box:focus-within {
  border-color: var(--color-text-tertiary);
  box-shadow: 0 2px 16px rgba(0, 0, 0, 0.08);
}

.chat-area__textarea {
  flex: 1;
  resize: none;
  min-height: 24px;
  max-height: 120px;
  line-height: 1.6;
  color: var(--color-text-primary);
  padding: var(--space-2xs) 0;
}

.chat-area__textarea::placeholder {
  color: var(--color-input-placeholder);
}

.chat-area__input-actions {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  margin-left: var(--space-md);
  flex-shrink: 0;
}

.chat-area__input-btn {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-full);
  color: var(--color-text-secondary);
  transition: all 0.15s ease;
}

.chat-area__input-btn:hover {
  background-color: var(--color-card);
  color: var(--color-text-primary);
}

.chat-area__send-btn {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-full);
  background-color: var(--color-border);
  color: var(--color-bg);
  transition: all 0.2s ease;
}

.chat-area__send-btn--active {
  background-color: var(--color-btn-dark);
  color: #ffffff;
}

.chat-area__send-btn--active:hover {
  background-color: var(--color-btn-dark-hover);
}

.chat-area__footer-text {
  text-align: center;
  font-size: var(--font-size-xs);
  color: var(--color-footer-text);
  margin-top: var(--space-sm);
}

/* ─── Dropdown Transition ─── */
.dropdown-enter-active,
.dropdown-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}

.dropdown-enter-from,
.dropdown-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
</style>
