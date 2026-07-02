/**
 * 聊天状态管理 — Pinia Store。
 *
 * 管理消息列表、会话列表、SSE 流式接收和 SQLite 持久化。
 * 遵循 coding-standards.md §2.4：Composition API 风格。
 */
import { ref, computed } from 'vue';
import { defineStore } from 'pinia';
import { streamChat, listSessions, getSession, deleteSessionApi } from '@/api';

/** 生成简易唯一 ID。 */
function uid() {
  return `${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

export const useChatStore = defineStore('chat', () => {
  // ─── State ───

  const messages = ref([]);
  const currentSessionId = ref(null);
  const isStreaming = ref(false);
  const error = ref(null);

  /** 会话历史列表 */
  const sessions = ref([]);

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

  /** 初始化会话 ID。 */
  function initSession() {
    if (!currentSessionId.value) {
      currentSessionId.value = `session_${Date.now()}`;
    }
  }

  /** 从后端加载会话列表。 */
  async function loadSessions() {
    try {
      sessions.value = await listSessions();
    } catch {
      // 后端不可用时静默失败
    }
  }

  /** 加载指定会话的历史消息。 */
  async function loadSession(sessionId) {
    try {
      const data = await getSession(sessionId);
      currentSessionId.value = sessionId;
      messages.value = (data.messages || []).map((m) => ({
        id: m.id,
        role: m.role,
        text: m.text,
        timestamp: new Date(m.created_at).getTime(),
        intent: m.intent_label ? { intent: m.intent_label, confidence: m.intent_confidence } : null,
        sentiment: m.sentiment_label ? { label: m.sentiment_label, score: m.sentiment_score } : null,
        isStreaming: false,
      }));
    } catch {
      error.value = '加载会话失败';
    }
  }

  /** 删除会话。 */
  async function deleteSession(sessionId) {
    try {
      await deleteSessionApi(sessionId);
      sessions.value = sessions.value.filter((s) => s.id !== sessionId);
      if (currentSessionId.value === sessionId) {
        clearSession();
      }
    } catch {
      error.value = '删除会话失败';
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
      entities: null,
      isStreaming: true,
    };
    messages.value.push(botMsg);

    isStreaming.value = true;

    // 3. 发起 SSE 流式请求
    //    所有回调必须通过 messages.value 访问响应式代理
    await streamChat(currentSessionId.value, text.trim(), {
      onIntent(data) {
        const msg = messages.value[messages.value.length - 1];
        if (msg && msg.intent === null) {
          msg.intent = data;
        }
      },

      onSentiment(data) {
        const msg = messages.value[messages.value.length - 1];
        if (msg && msg.sentiment === null) {
          msg.sentiment = data;
        }
      },

      onEntity(data) {
        const msg = messages.value[messages.value.length - 1];
        if (msg && msg.entities === null) {
          msg.entities = data;
        }
      },

      onToken(token) {
        const msg = messages.value[messages.value.length - 1];
        if (msg) {
          msg.text += token;
        }
      },

      onDone(data) {
        const msg = messages.value[messages.value.length - 1];
        if (msg) {
          msg.isStreaming = false;
          if (!msg.text && data.full_answer) {
            msg.text = data.full_answer;
          }
        }
        isStreaming.value = false;
        // 刷新会话列表（新会话会出现在列表中）
        loadSessions();
      },

      onError(errMsg) {
        const msg = messages.value[messages.value.length - 1];
        if (msg) {
          msg.isStreaming = false;
          if (!msg.text) {
            msg.text = '抱歉，服务暂时不可用，请稍后重试。';
          }
        }
        isStreaming.value = false;
        error.value = errMsg;
      },
    });

    // 兜底：确保 streaming 状态被清除
    isStreaming.value = false;
    const msg = messages.value[messages.value.length - 1];
    if (msg && msg.isStreaming) {
      msg.isStreaming = false;
    }
  }

  return {
    // state
    messages,
    currentSessionId,
    isStreaming,
    error,
    sessions,
    // getters
    lastBotMessage,
    // actions
    initSession,
    clearSession,
    sendMessage,
    loadSessions,
    loadSession,
    deleteSession,
  };
});
