/**
 * 聊天状态管理 — Pinia Store。
 *
 * 管理消息列表、会话状态和 SSE 流式接收。
 * 遵循 coding-standards.md §2.4：Composition API 风格。
 */
import { ref, computed } from 'vue';
import { defineStore } from 'pinia';
import { streamChat } from '@/api';

/** 生成简易唯一 ID。 */
function uid() {
  return `${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

export const useChatStore = defineStore('chat', () => {
  // ─── State ───

  /** @type {import('vue').Ref<Array<{id: string, role: string, text: string, timestamp: number, intent?: object, isStreaming?: boolean}>>} */
  const messages = ref([]);

  /** @type {import('vue').Ref<string|null>} */
  const currentSessionId = ref(null);

  /** @type {import('vue').Ref<boolean>} */
  const isStreaming = ref(false);

  /** @type {import('vue').Ref<string|null>} */
  const error = ref(null);

  // ─── Getters ───

  /** 最后一条 bot 消息（用于逐字追加 token）。 */
  const lastBotMessage = computed(() => {
    const msgs = messages.value;
    for (let i = msgs.length - 1; i >= 0; i--) {
      if (msgs[i].role === 'assistant') return msgs[i];
    }
    return null;
  });

  // ─── Actions ───

  /** 初始化会话 ID（仅在前端生成临时 ID）。 */
  function initSession() {
    if (!currentSessionId.value) {
      currentSessionId.value = `session_${Date.now()}`;
    }
  }

  /** 清空当前会话，开始新对话。 */
  function clearSession() {
    messages.value = [];
    currentSessionId.value = null;
    isStreaming.value = false;
    error.value = null;
  }

  /**
   * 发送用户消息并接收 SSE 流式回复。
   *
   * @param {string} text - 用户输入的消息文本。
   */
  async function sendMessage(text) {
    if (!text.trim() || isStreaming.value) return;

    initSession();
    error.value = null;

    // 1. 追加用户消息
    const userMsg = {
      id: uid(),
      role: 'user',
      text: text.trim(),
      timestamp: Date.now(),
    };
    messages.value.push(userMsg);

    // 2. 追加占位 bot 消息
    const botMsg = {
      id: uid(),
      role: 'assistant',
      text: '',
      timestamp: Date.now(),
      intent: null,
      sentiment: null,
      isStreaming: true,
    };
    messages.value.push(botMsg);

    isStreaming.value = true;

    // 3. 发起 SSE 流式请求
    await streamChat(currentSessionId.value, text.trim(), {
      onIntent(data) {
        if (botMsg.intent === null) {
          botMsg.intent = data;
        }
      },

      onSentiment(data) {
        if (botMsg.sentiment === null) {
          botMsg.sentiment = data;
        }
      },

      onToken(token) {
        botMsg.text += token;
      },

      onDone(data) {
        botMsg.isStreaming = false;
        isStreaming.value = false;
        // 若后端返回完整文本但前端未逐字收到，做兜底
        if (!botMsg.text && data.full_answer) {
          botMsg.text = data.full_answer;
        }
      },

      onError(errMsg) {
        botMsg.isStreaming = false;
        isStreaming.value = false;
        error.value = errMsg;
        // 若 bot 消息仍为空，追加错误提示
        if (!botMsg.text) {
          botMsg.text = '抱歉，服务暂时不可用，请稍后重试。';
        }
      },
    });

    // 兜底：确保 streaming 状态被清除
    isStreaming.value = false;
    if (botMsg.isStreaming) {
      botMsg.isStreaming = false;
    }
  }

  return {
    // state
    messages,
    currentSessionId,
    isStreaming,
    error,
    // getters
    lastBotMessage,
    // actions
    initSession,
    clearSession,
    sendMessage,
  };
});
