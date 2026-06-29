<script setup>
import { ref } from 'vue';

const props = defineProps({
  collapsed: { type: Boolean, default: false },
});

const emit = defineEmits(['toggle']);

const activeNav = ref('chat');

const navItems = [
  { id: 'chat', label: '智能客服', icon: 'chat', badge: null },
];
</script>

<template>
  <aside
    :style="{
      height: '100%',
      width: collapsed ? '60px' : '220px',
      minWidth: collapsed ? '60px' : '220px',
      maxWidth: collapsed ? '60px' : '220px',
      flexShrink: 0,
      backgroundColor: collapsed ? 'transparent' : '#f5f5f7',
      borderRight: collapsed ? 'none' : '1px solid #f0f0f2',
      overflow: 'hidden',
      transition: 'width 0.3s ease',
      boxSizing: 'border-box',
    }"
  >
    <div
      :style="{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        padding: collapsed ? '12px 4px' : '16px 12px',
        minWidth: 0,
        boxSizing: 'border-box',
        alignItems: collapsed ? 'center' : 'stretch',
      }"
    >
      <!-- Header -->
      <div
        :style="{
          display: 'flex',
          alignItems: 'center',
          justifyContent: collapsed ? 'center' : 'space-between',
          gap: collapsed ? '8px' : '0',
          padding: collapsed ? '6px 0' : '6px 10px',
          marginBottom: collapsed ? '16px' : '20px',
          width: '100%',
          flexShrink: 0,
        }"
      >
        <span
          v-if="!collapsed"
          :style="{
            fontSize: '15px',
            fontWeight: '600',
            color: '#1d1d1f',
            whiteSpace: 'nowrap',
          }"
        >
          智能客服系统
        </span>

        <!-- 折叠/展开按钮 -->
        <button
          :title="collapsed ? '展开侧边栏' : '收起侧边栏'"
          @click="emit('toggle')"
          :style="{
            width: '22px',
            height: '22px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            borderRadius: '6px',
            color: '#86868b',
            border: 'none',
            background: 'none',
            cursor: 'pointer',
            flexShrink: 0,
            padding: 0,
          }"
        >
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
            <path fill="currentColor" d="M13.779 1.913c1.834 0 3.321 1.563 3.321 3.492v7.19c0 1.929-1.487 3.493-3.321 3.493H4.22C2.387 16.088.9 14.524.9 12.595v-7.19c0-1.929 1.487-3.492 3.321-3.492zM4.22 3.31c-1.1 0-1.992.938-1.992 2.095v7.19c0 1.157.892 2.095 1.992 2.095h2.783V3.31zm4.112 11.38h5.446c1.1 0 1.992-.938 1.992-2.095v-7.19c0-1.157-.892-2.095-1.992-2.095H8.333zM5.413 7.77c.366 0 .664.312.664.698s-.298.699-.665.699H3.896c-.367 0-.664-.313-.664-.699s.297-.698.664-.698zm0-2.682c.366 0 .664.313.664.698 0 .386-.298.699-.665.699H3.896c-.367 0-.664-.313-.664-.699s.297-.698.664-.698z"/>
          </svg>
        </button>

        <!-- 新建会话按钮（仅折叠态显示） -->
        <button
          v-if="collapsed"
          title="新建会话"
          :style="{
            width: '22px',
            height: '22px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            borderRadius: '6px',
            color: '#86868b',
            border: 'none',
            background: 'none',
            cursor: 'pointer',
            flexShrink: 0,
            padding: 0,
          }"
        >
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
            <path fill="currentColor" d="M8.824 1.627c.389 0 .704.326.704.727a.716.716 0 0 1-.704.728H4.246c-1.07 0-1.937.895-1.937 2v7.275c0 1.104.867 2 1.937 2h.637c.465 0 .925.1 1.351.294l1.807.824a1.89 1.89 0 0 0 1.565 0l1.808-.824a3.3 3.3 0 0 1 1.351-.294h.637c1.07 0 1.937-.896 1.937-2V8.719c0-.402.316-.727.705-.727s.704.325.704.727v3.638c0 1.907-1.498 3.454-3.346 3.454h-.637c-.27 0-.536.058-.782.17l-1.808.824a3.26 3.26 0 0 1-2.703 0l-1.807-.824a1.9 1.9 0 0 0-.782-.17h-.637C2.398 15.811.9 14.264.9 12.357V5.082c0-1.908 1.498-3.455 3.346-3.455zM13.578.9c.39 0 .705.326.705.727V3.81h2.113c.389 0 .704.326.704.727a.716.716 0 0 1-.704.727h-2.113v2.182a.716.716 0 0 1-.705.727.716.716 0 0 1-.704-.727V5.263H10.76a.716.716 0 0 1-.704-.727c0-.401.315-.727.704-.727h2.113V1.627c0-.401.315-.727.704-.727"/>
          </svg>
        </button>
      </div>

      <!-- Navigation (hidden when collapsed) -->
      <nav
        v-if="!collapsed"
        :style="{
          display: 'flex',
          flexDirection: 'column',
          gap: '2px',
          width: '100%',
        }"
      >
        <button
          v-for="item in navItems"
          :key="item.id"
          :title="item.label"
          @click="activeNav = item.id"
          :style="{
            display: 'flex',
            alignItems: 'center',
            gap: collapsed ? '0' : '8px',
            padding: collapsed ? '8px' : '8px 12px',
            borderRadius: '8px',
            color: '#1d1d1f',
            fontSize: '14px',
            fontWeight: activeNav === item.id ? '600' : '500',
            backgroundColor: activeNav === item.id ? '#e8e8ea' : 'transparent',
            border: 'none',
            cursor: 'pointer',
            width: '100%',
            textAlign: 'left',
            whiteSpace: 'nowrap',
            justifyContent: collapsed ? 'center' : 'flex-start',
            boxSizing: 'border-box',
          }"
        >
          <span
            :style="{
              display: 'flex',
              alignItems: 'center',
              color: activeNav === item.id ? '#1d1d1f' : '#86868b',
              flexShrink: 0,
            }"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M2 3.5A1.5 1.5 0 013.5 2h9A1.5 1.5 0 0114 3.5v7a1.5 1.5 0 01-1.5 1.5H5l-2 2V3.5z" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round"/>
            </svg>
          </span>
          <span v-if="!collapsed" :style="{ flex: 1 }">{{ item.label }}</span>
        </button>
      </nav>

      <!-- Spacer -->
      <div :style="{ flex: 1 }" />

      <!-- User Area (only when expanded) -->
      <div
        v-if="!collapsed"
        :style="{
          display: 'flex',
          alignItems: 'center',
          padding: '8px 4px',
          marginTop: 'auto',
          borderRadius: '8px',
          width: '100%',
          boxSizing: 'border-box',
        }"
      >
        <div
          :style="{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }"
        >
          <div
            :style="{
              width: '28px',
              height: '28px',
              borderRadius: '9999px',
              backgroundColor: '#e5e5e7',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#86868b',
              flexShrink: 0,
            }"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <circle cx="8" cy="5.5" r="3" stroke="currentColor" stroke-width="1.2"/>
              <path d="M2.5 14c0-3 2.5-5 5.5-5s5.5 2 5.5 5" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
            </svg>
          </div>
          <span
            :style="{
              fontSize: '13px',
              color: '#86868b',
            }"
          >
            未登录
          </span>
        </div>
      </div>
    </div>
  </aside>
</template>
<style scoped>
</style>
