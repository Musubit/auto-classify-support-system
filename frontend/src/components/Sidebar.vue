<script setup>
import { ref } from 'vue';

const activeNav = ref('chat');

const navItems = [
  { id: 'chat', label: '智能客服', icon: 'chat', badge: null },
];
</script>

<template>
  <aside class="sidebar">
    <!-- ─── Header ─── -->
    <div class="sidebar__header">
      <span class="sidebar__logo">智能客服系统</span>
      <button class="sidebar__header-btn" title="新建会话">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
          <rect x="2" y="3" width="12" height="10" rx="1.5" stroke="currentColor" stroke-width="1.2"/>
          <path d="M5 7h6M5 9.5h4" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
        </svg>
      </button>
    </div>

    <!-- ─── Navigation ─── -->
    <nav class="sidebar__nav">
      <button
        v-for="item in navItems"
        :key="item.id"
        class="sidebar__nav-item"
        :class="{ 'sidebar__nav-item--active': activeNav === item.id }"
        @click="activeNav = item.id"
      >
        <span class="sidebar__nav-icon">
          <svg v-if="item.icon === 'chat'" width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M2 3.5A1.5 1.5 0 013.5 2h9A1.5 1.5 0 0114 3.5v7a1.5 1.5 0 01-1.5 1.5H5l-2 2V3.5z" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round"/>
          </svg>
        </span>
        <span class="sidebar__nav-label">{{ item.label }}</span>
        <button v-if="activeNav === item.id" class="sidebar__nav-add" title="新建会话">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M7 3v8M3 7h8" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>
          </svg>
        </button>
      </button>
    </nav>

    <!-- ─── Spacer ─── -->
    <div class="sidebar__spacer" />

    <!-- ─── User Area ─── -->
    <div class="sidebar__user">
      <div class="sidebar__user-info">
        <div class="sidebar__user-avatar">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <circle cx="8" cy="5.5" r="3" stroke="currentColor" stroke-width="1.2"/>
            <path d="M2.5 14c0-3 2.5-5 5.5-5s5.5 2 5.5 5" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
          </svg>
        </div>
        <span class="sidebar__user-name">未登录</span>
      </div>
      <button class="sidebar__user-upgrade">升级</button>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  width: var(--sidebar-width);
  height: 100%;
  background-color: var(--color-sidebar);
  display: flex;
  flex-direction: column;
  padding: var(--space-lg) var(--space-md);
  border-right: 1px solid var(--color-border-light);
  flex-shrink: 0;
}

/* ─── Header ─── */
.sidebar__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-xs) var(--space-sm);
  margin-bottom: var(--space-xl);
}

.sidebar__logo {
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
  letter-spacing: -0.01em;
}

.sidebar__header-btn {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  color: var(--color-text-secondary);
  transition: background-color 0.15s ease, color 0.15s ease;
}

.sidebar__header-btn:hover {
  background-color: var(--color-sidebar-hover);
  color: var(--color-text-primary);
}

/* ─── Navigation ─── */
.sidebar__nav {
  display: flex;
  flex-direction: column;
  gap: var(--space-2xs);
}

.sidebar__nav-item {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  padding: var(--space-sm) var(--space-md);
  border-radius: var(--radius-md);
  color: var(--color-text-primary);
  font-size: var(--font-size-md);
  font-weight: var(--font-weight-medium);
  transition: background-color 0.15s ease;
  position: relative;
  width: 100%;
  text-align: left;
}

.sidebar__nav-item:hover {
  background-color: var(--color-sidebar-hover);
}

.sidebar__nav-item--active {
  background-color: var(--color-sidebar-active);
}

.sidebar__nav-icon {
  display: flex;
  align-items: center;
  color: var(--color-text-secondary);
  flex-shrink: 0;
}

.sidebar__nav-item--active .sidebar__nav-icon {
  color: var(--color-text-primary);
}

.sidebar__nav-label {
  flex: 1;
}

.sidebar__nav-add {
  width: 22px;
  height: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  color: var(--color-text-secondary);
  opacity: 0;
  transition: opacity 0.15s ease, background-color 0.15s ease, color 0.15s ease;
}

.sidebar__nav-item--active:hover .sidebar__nav-add,
.sidebar__nav-add:hover {
  opacity: 1;
}

.sidebar__nav-add:hover {
  background-color: var(--color-border);
  color: var(--color-text-primary);
}

/* ─── Spacer ── */
.sidebar__spacer {
  flex: 1;
}

/* ─── User Area ─── */
.sidebar__user {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-sm) var(--space-xs);
  margin-top: auto;
}

.sidebar__user-info {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
}

.sidebar__user-avatar {
  width: 28px;
  height: 28px;
  border-radius: var(--radius-full);
  background-color: var(--color-border);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-text-secondary);
}

.sidebar__user-name {
  font-size: var(--font-size-base);
  color: var(--color-text-secondary);
}

.sidebar__user-upgrade {
  padding: var(--space-2xs) var(--space-md);
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  transition: all 0.15s ease;
}

.sidebar__user-upgrade:hover {
  background-color: var(--color-bg);
  color: var(--color-text-primary);
  border-color: var(--color-btn-outline-border);
}
</style>
