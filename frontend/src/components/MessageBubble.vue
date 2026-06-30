<script setup>
/**
 * 消息气泡组件。
 *
 * Props:
 *   message: { id, role, text, timestamp, intent?, isStreaming? }
 */
defineProps({
  message: {
    type: Object,
    required: true,
  },
});

/** 格式化时间戳为短时间格式。 */
function formatTime(ts) {
  const d = new Date(ts);
  const h = String(d.getHours()).padStart(2, '0');
  const m = String(d.getMinutes()).padStart(2, '0');
  return `${h}:${m}`;
}
</script>

<template>
  <div
    class="msg-bubble"
    :class="{
      'msg-bubble--user': message.role === 'user',
      'msg-bubble--assistant': message.role === 'assistant',
    }"
  >
    <div class="msg-bubble__inner">
      <!-- 意图标签（仅 bot 消息且有意图时显示） -->
      <span
        v-if="message.role === 'assistant' && message.intent"
        class="msg-bubble__intent-tag"
      >
        {{ message.intent.intent }}
      </span>

      <!-- 消息文本 -->
      <div class="msg-bubble__text">
        {{ message.text }}
        <span v-if="message.isStreaming" class="msg-bubble__cursor">|</span>
      </div>

      <!-- 时间 -->
      <div class="msg-bubble__time">{{ formatTime(message.timestamp) }}</div>
    </div>
  </div>
</template>

<style scoped>
.msg-bubble {
  display: flex;
  margin-bottom: var(--space-lg);
  max-width: 80%;
}

.msg-bubble--user {
  align-self: flex-end;
  margin-left: auto;
}

.msg-bubble--assistant {
  align-self: flex-start;
}

.msg-bubble__inner {
  padding: var(--space-md) var(--space-lg);
  border-radius: var(--radius-lg);
  position: relative;
}

.msg-bubble--user .msg-bubble__inner {
  background-color: var(--color-btn-dark);
  color: #ffffff;
  border-bottom-right-radius: var(--space-xs);
}

.msg-bubble--assistant .msg-bubble__inner {
  background-color: var(--color-card);
  color: var(--color-text-primary);
  border-bottom-left-radius: var(--space-xs);
}

.msg-bubble__intent-tag {
  display: inline-block;
  font-size: var(--font-size-xs);
  padding: 1px 6px;
  border-radius: var(--radius-sm);
  background-color: var(--color-accent-blue-bg);
  color: var(--color-accent-blue);
  margin-bottom: var(--space-sm);
  font-weight: var(--font-weight-medium);
}

.msg-bubble__text {
  font-size: var(--font-size-md);
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
}

.msg-bubble__cursor {
  display: inline;
  animation: blink 0.8s step-end infinite;
  font-weight: var(--font-weight-regular);
  color: inherit;
  opacity: 0.6;
}

@keyframes blink {
  0%, 100% { opacity: 0.6; }
  50% { opacity: 0; }
}

.msg-bubble__time {
  font-size: var(--font-size-xs);
  margin-top: var(--space-xs);
  opacity: 0.5;
}

.msg-bubble--user .msg-bubble__time {
  text-align: right;
}
</style>
