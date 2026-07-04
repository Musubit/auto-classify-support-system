import { createRouter, createWebHistory } from 'vue-router';
import ChatArea from '@/components/ChatArea.vue';

const routes = [
  { path: '/', name: 'chat', component: ChatArea },
  {
    path: '/plan',
    name: 'analytics',
    component: () => import('@/views/AnalyticsView.vue'),
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

export default router;
