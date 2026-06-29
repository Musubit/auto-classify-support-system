<script setup>
// 应用根组件 — Phase 0 骨架占位
</script>

<template>
  <div class="app">
    <h1 class="app__title">智能客服系统</h1>
    <p class="app__hint">骨架已就绪，等待接入聊天界面</p>
  </div>
</template>

<style scoped>
.app {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
}

.app__title {
  color: var(--color-primary);
}

.app__hint {
  margin-top: 8px;
  color: var(--color-text-secondary);
}
</style>
