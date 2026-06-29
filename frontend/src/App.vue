<script setup>
import Sidebar from './components/Sidebar.vue';
import ChatArea from './components/ChatArea.vue';
</script>

<template>
  <div class=app-layout>
    <Sidebar />
    <ChatArea />
  </div>
</template>

<style scoped>
.app-layout {
  display: flex;
  height: 100vh;
  width: 100vw;
  overflow: hidden;
}
</style>
