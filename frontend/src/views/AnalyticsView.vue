<script setup>
import { ref, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import VChart from 'vue-echarts';
import { http } from '@/api';
import { INTENT_LABELS, SENTIMENT_LABELS } from '@/utils/labels';

const router = useRouter();

// ─── 状态 ──────────────────────────────────────────
const loading = ref(true);
const error = ref(null);
const data = ref(null);

// ─── 数据获取 ──────────────────────────────────────
async function fetchData() {
  loading.value = true;
  error.value = null;
  try {
    const res = await http.get('/analytics');
    data.value = res.data.data;
  } catch (e) {
    error.value = e.message || '获取数据失败';
  } finally {
    loading.value = false;
  }
}

onMounted(fetchData);

// ─── 统计卡片 ──────────────────────────────────────
const statCards = computed(() => {
  if (!data.value) return [];
  const d = data.value;
  return [
    { label: '总会话数', value: d.total_sessions, icon: '💬' },
    { label: '总消息数', value: d.total_messages, icon: '📨' },
    { label: '平均会话深度', value: d.average_session_depth, icon: '📊' },
    { label: '今日活跃', value: d.today_active_sessions, icon: '🔥' },
  ];
});

// ─── 意图分布环形图 ────────────────────────────────
const intentOption = computed(() => {
  const items = data.value?.intent_distribution || [];
  const labels = items.map(i => INTENT_LABELS[i.intent_label] || i.intent_label);
  const values = items.map(i => i.count);

  return {
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c} ({d}%)',
    },
    legend: {
      orient: 'vertical',
      right: '5%',
      top: 'center',
      textStyle: { color: '#86868b', fontSize: 12 },
      itemWidth: 8,
      itemHeight: 8,
    },
    series: [{
      type: 'pie',
      radius: ['45%', '75%'],
      center: ['40%', '50%'],
      avoidLabelOverlap: false,
      itemStyle: { borderRadius: 4, borderColor: '#fff', borderWidth: 2 },
      label: { show: false },
      emphasis: {
        label: { show: true, fontSize: 14, fontWeight: 'bold' },
        scaleSize: 8,
      },
      data: labels.map((name, i) => ({ name, value: values[i] })),
      color: ['#0071e3', '#5856d6', '#34c759', '#ff9500', '#ff3b30', '#aeaeb2', '#5ac8fa'],
    }],
  };
});

// ─── 情感分布柱状图 ────────────────────────────────
const sentimentOption = computed(() => {
  const items = data.value?.sentiment_distribution || [];
  const labels = items.map(i => SENTIMENT_LABELS[i.sentiment_label] || i.sentiment_label);
  const values = items.map(i => i.count);
  const colors = { '正面': '#34c759', '中性': '#aeaeb2', '负面': '#ff3b30' };

  return {
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      data: labels,
      axisLine: { lineStyle: { color: '#e5e5ea' } },
      axisTick: { show: false },
      axisLabel: { color: '#86868b', fontSize: 12 },
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: '#f5f5f7' } },
      axisLabel: { color: '#86868b', fontSize: 12 },
    },
    series: [{
      type: 'bar',
      data: values.map((v, i) => ({
        value: v,
        itemStyle: {
          color: colors[labels[i]] || '#0071e3',
          borderRadius: [4, 4, 0, 0],
        },
      })),
      barWidth: '50%',
    }],
    grid: { top: 10, bottom: 5, left: 5, right: 10 },
  };
});

// ─── 每日趋势折线图 ────────────────────────────────
const dailyTrendOption = computed(() => {
  const items = data.value?.daily_trend || [];
  const days = items.map(i => i.day.slice(5)); // MM-DD
  const values = items.map(i => i.count);

  return {
    tooltip: {
      trigger: 'axis',
      formatter: p => `${p[0].axisValue}<br/>消息: ${p[0].value}`,
    },
    xAxis: {
      type: 'category',
      data: days,
      axisLine: { lineStyle: { color: '#e5e5ea' } },
      axisTick: { show: false },
      axisLabel: { color: '#86868b', fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: '#f5f5f7' } },
      axisLabel: { color: '#86868b', fontSize: 12 },
    },
    series: [{
      type: 'line',
      data: values,
      smooth: true,
      symbol: 'none',
      lineStyle: { color: '#0071e3', width: 2 },
      areaStyle: { color: 'rgba(0, 113, 227, 0.08)' },
    }],
    grid: { top: 10, bottom: 5, left: 5, right: 10 },
  };
});

// ─── 小时活跃柱状图 ────────────────────────────────
const hourlyOption = computed(() => {
  const items = data.value?.hourly_activity || [];
  // 填充 0-23 所有小时
  const full = Array.from({ length: 24 }, (_, h) => {
    const found = items.find(i => i.hour === h);
    return found ? found.count : 0;
  });
  const hours = Array.from({ length: 24 }, (_, i) => `${i}时`);

  return {
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      data: hours,
      axisLine: { lineStyle: { color: '#e5e5ea' } },
      axisTick: { show: false },
      axisLabel: { color: '#86868b', fontSize: 10, interval: 2 },
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: '#f5f5f7' } },
      axisLabel: { color: '#86868b', fontSize: 12 },
    },
    series: [{
      type: 'bar',
      data: full.map(v => ({
        value: v,
        itemStyle: {
          color: v > 0 ? '#0071e3' : '#f0f0f5',
          borderRadius: v > 0 ? [3, 3, 0, 0] : 0,
        },
      })),
      barWidth: '60%',
    }],
    grid: { top: 10, bottom: 5, left: 5, right: 10 },
  };
});

// ─── 计算属性：是否有数据 ──────────────────────────
const hasData = computed(() => {
  return data.value && data.value.total_messages > 0;
});
</script>

<template>
  <main class="dashboard">
    <!-- 顶部标题栏 -->
    <header class="dashboard__header">
      <button class="dashboard__back-btn" @click="router.push('/')">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M19 12H5M12 19l-7-7 7-7" />
        </svg>
        <span>返回对话</span>
      </button>
      <h1 class="dashboard__title">数据看板</h1>
      <div class="dashboard__spacer" />
    </header>

    <!-- 加载中 -->
    <div v-if="loading" class="dashboard__state">
      <p class="dashboard__state-text">加载中...</p>
    </div>

    <!-- 错误 -->
    <div v-else-if="error" class="dashboard__state">
      <p class="dashboard__state-text dashboard__state-text--error">{{ error }}</p>
      <button class="dashboard__retry-btn" @click="fetchData">重试</button>
    </div>

    <!-- 数据展示 -->
    <template v-else>
      <!-- 统计卡片 -->
      <section class="dashboard__stat-cards">
        <div
          v-for="card in statCards"
          :key="card.label"
          class="dashboard__stat-card"
        >
          <span class="dashboard__stat-icon">{{ card.icon }}</span>
          <span class="dashboard__stat-value">{{ card.value }}</span>
          <span class="dashboard__stat-label">{{ card.label }}</span>
        </div>
      </section>

      <!-- 图表区 -->
      <div v-if="hasData" class="dashboard__charts">
        <div class="dashboard__chart-card">
          <h3 class="dashboard__chart-title">意图分布</h3>
          <VChart class="dashboard__chart" :option="intentOption" autoresize />
        </div>
        <div class="dashboard__chart-card">
          <h3 class="dashboard__chart-title">情感分布</h3>
          <VChart class="dashboard__chart" :option="sentimentOption" autoresize />
        </div>
        <div class="dashboard__chart-card">
          <h3 class="dashboard__chart-title">每日消息趋势（近30天）</h3>
          <VChart class="dashboard__chart" :option="dailyTrendOption" autoresize />
        </div>
        <div class="dashboard__chart-card">
          <h3 class="dashboard__chart-title">小时活跃分布</h3>
          <VChart class="dashboard__chart" :option="hourlyOption" autoresize />
        </div>
      </div>

      <!-- 空数据 -->
      <div v-else class="dashboard__state">
        <p class="dashboard__state-text">暂无数据</p>
        <p class="dashboard__state-hint">开始对话后，这里将展示数据分析图表</p>
      </div>
    </template>
  </main>
</template>

<style scoped>
.dashboard {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  padding: var(--space-xl) var(--space-2xl);
  background: var(--color-bg);
}

/* ─── Header ──────────────────────────────── */
.dashboard__header {
  display: flex;
  align-items: center;
  gap: var(--space-lg);
  margin-bottom: var(--space-2xl);
}

.dashboard__back-btn {
  display: flex;
  align-items: center;
  gap: var(--space-xs);
  padding: var(--space-sm) var(--space-md);
  border: 1px solid var(--color-btn-outline-border, #d2d2d7);
  border-radius: var(--radius-md);
  background: var(--color-bg);
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
  cursor: pointer;
  transition: all 0.15s ease;
  white-space: nowrap;
}

.dashboard__back-btn:hover {
  background: var(--color-card);
  color: var(--color-accent-blue);
  border-color: var(--color-accent-blue);
}

.dashboard__title {
  font-size: var(--font-size-xl);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
  margin: 0;
}

.dashboard__spacer {
  flex: 1;
}

/* ─── 状态占位 ────────────────────────────── */
.dashboard__state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-md);
}

.dashboard__state-text {
  font-size: var(--font-size-lg);
  color: var(--color-text-secondary);
}

.dashboard__state-text--error {
  color: var(--color-danger, #ff3b30);
}

.dashboard__state-hint {
  font-size: var(--font-size-sm);
  color: var(--color-text-tertiary, #aeaeb2);
}

.dashboard__retry-btn {
  padding: var(--space-sm) var(--space-xl);
  border: none;
  border-radius: var(--radius-md);
  background: var(--color-accent-blue);
  color: #fff;
  font-size: var(--font-size-md);
  cursor: pointer;
}

.dashboard__retry-btn:hover {
  opacity: 0.85;
}

/* ─── 统计卡片 ─────────────────────────────── */
.dashboard__stat-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-lg);
  margin-bottom: var(--space-2xl);
}

.dashboard__stat-card {
  background: var(--color-card);
  border: 1px solid var(--color-border-light, #e5e5ea);
  border-radius: var(--radius-lg);
  padding: var(--space-lg) var(--space-xl);
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
}

.dashboard__stat-icon {
  font-size: 20px;
  margin-bottom: var(--space-xs);
}

.dashboard__stat-value {
  font-size: 28px;
  font-weight: var(--font-weight-bold);
  color: var(--color-text-primary);
  line-height: 1.2;
}

.dashboard__stat-label {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}

/* ─── 图表网格 ─────────────────────────────── */
.dashboard__charts {
  display: grid;
  grid-template-columns: 1fr 1fr;
  grid-template-rows: auto auto;
  gap: var(--space-lg);
  flex: 1;
  min-height: 0;
}

.dashboard__chart-card {
  background: var(--color-bg);
  border: 1px solid var(--color-border-light, #e5e5ea);
  border-radius: var(--radius-lg);
  padding: var(--space-lg);
  display: flex;
  flex-direction: column;
  min-height: 320px;
}

.dashboard__chart-title {
  font-size: var(--font-size-md);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
  margin: 0 0 var(--space-md) 0;
}

.dashboard__chart {
  flex: 1;
  min-height: 0;
}

/* ─── 响应式 ────────────────────────────────── */
@media (max-width: 1024px) {
  .dashboard__stat-cards {
    grid-template-columns: repeat(2, 1fr);
  }

  .dashboard__charts {
    grid-template-columns: 1fr;
  }

  .dashboard__chart-card {
    min-height: 280px;
  }
}
</style>
