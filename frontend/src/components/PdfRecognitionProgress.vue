<template>
  <div class="pdf-progress-container">
    <div class="progress-header">
      <div class="status-icon">
        <el-icon class="rotating" size="48" color="#409eff">
          <Loading />
        </el-icon>
      </div>
      <h3 class="progress-title">{{ title }}</h3>
      <p class="progress-subtitle">{{ subtitle }}</p>
    </div>

    <div class="progress-stats">
      <div class="stat-item">
        <div class="stat-label">当前页</div>
        <div class="stat-value">{{ currentPage }}</div>
      </div>
      <div class="stat-divider">/</div>
      <div class="stat-item">
        <div class="stat-label">总页数</div>
        <div class="stat-value">{{ totalPages }}</div>
      </div>
      <div class="stat-item" v-if="questionsFound > 0">
        <div class="stat-label">已发现</div>
        <div class="stat-value highlight">{{ questionsFound }} 题</div>
      </div>
    </div>

    <div class="progress-bar-wrapper">
      <div class="progress-bar-container">
        <div
          class="progress-bar-fill"
          :style="{ width: percentage + '%' }"
        >
          <div class="progress-bar-shine"></div>
        </div>
        <div class="progress-percentage">{{ percentage }}%</div>
      </div>
    </div>

    <div class="progress-details">
      <div class="detail-row">
        <el-icon><Document /></el-icon>
        <span>{{ message || '正在处理中...' }}</span>
      </div>
      <div class="detail-row" v-if="estimatedTime">
        <el-icon><Clock /></el-icon>
        <span>预计剩余时间：{{ estimatedTime }}</span>
      </div>
      <div class="detail-row" v-if="speed">
        <el-icon><Odometer /></el-icon>
        <span>处理速度：{{ speed }}</span>
      </div>
    </div>

    <div class="progress-tips">
      <el-icon><InfoFilled /></el-icon>
      <span>识别完成后结果将自动展示，请耐心等待</span>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Loading, Document, Clock, Odometer, InfoFilled } from '@element-plus/icons-vue'

const props = defineProps({
  currentPage: {
    type: Number,
    default: 0
  },
  totalPages: {
    type: Number,
    default: 0
  },
  questionsFound: {
    type: Number,
    default: 0
  },
  progressPercent: {
    type: Number,
    default: null
  },
  message: {
    type: String,
    default: ''
  },
  title: {
    type: String,
    default: '正在识别 PDF'
  },
  subtitle: {
    type: String,
    default: '请稍候，这可能需要 30-60 秒'
  }
})

const percentage = computed(() => {
  if (props.progressPercent !== null && props.progressPercent !== undefined) {
    return Math.max(0, Math.min(100, Math.round(props.progressPercent)))
  }
  if (props.totalPages === 0) return 0
  return Math.round((props.currentPage / props.totalPages) * 100)
})

// 计算处理速度和预计剩余时间
const startTime = ref(Date.now())
const speed = computed(() => {
  if (props.progressPercent !== null && props.progressPercent !== undefined) {
    const elapsed = (Date.now() - startTime.value) / 1000
    if (elapsed <= 0 || props.progressPercent <= 0) return ''
    return `${(props.progressPercent / elapsed).toFixed(1)}%/秒`
  }
  if (props.currentPage === 0) return ''
  const elapsed = (Date.now() - startTime.value) / 1000 // 秒
  const pagesPerSecond = props.currentPage / elapsed
  if (pagesPerSecond < 0.1) return ''
  return `${pagesPerSecond.toFixed(1)} 页/秒`
})

const estimatedTime = computed(() => {
  if (props.progressPercent !== null && props.progressPercent !== undefined) {
    if (props.progressPercent <= 0 || props.progressPercent >= 100) return ''
    const elapsed = (Date.now() - startTime.value) / 1000
    const remainingSeconds = Math.ceil((elapsed / props.progressPercent) * (100 - props.progressPercent))
    if (remainingSeconds < 60) return `${remainingSeconds} 秒`
    return `${Math.floor(remainingSeconds / 60)} 分 ${remainingSeconds % 60} 秒`
  }
  if (props.currentPage === 0 || props.totalPages === 0) return ''
  const elapsed = (Date.now() - startTime.value) / 1000 // 秒
  const pagesPerSecond = props.currentPage / elapsed
  if (pagesPerSecond < 0.1) return ''

  const remainingPages = props.totalPages - props.currentPage
  const remainingSeconds = Math.ceil(remainingPages / pagesPerSecond)

  if (remainingSeconds < 60) {
    return `${remainingSeconds} 秒`
  } else {
    const minutes = Math.floor(remainingSeconds / 60)
    const seconds = remainingSeconds % 60
    return `${minutes} 分 ${seconds} 秒`
  }
})

// 重置开始时间当页面重新开始时
watch(() => props.currentPage, (newVal, oldVal) => {
  if (newVal === 0 || (oldVal > 0 && newVal === 1)) {
    startTime.value = Date.now()
  }
})
</script>

<style scoped>
.pdf-progress-container {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 16px;
  padding: 48px 40px;
  color: white;
  box-shadow: 0 8px 32px rgba(102, 126, 234, 0.3);
  position: relative;
  overflow: hidden;
}

.pdf-progress-container::before {
  content: '';
  position: absolute;
  top: -50%;
  left: -50%;
  width: 200%;
  height: 200%;
  background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%);
  animation: pulse 3s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { transform: scale(1); opacity: 0.5; }
  50% { transform: scale(1.1); opacity: 0.8; }
}

.progress-header {
  text-align: center;
  margin-bottom: 32px;
  position: relative;
  z-index: 1;
}

.status-icon {
  margin-bottom: 16px;
}

.rotating {
  animation: rotate 2s linear infinite;
}

@keyframes rotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.progress-title {
  font-size: 24px;
  font-weight: 600;
  margin: 0 0 8px 0;
  text-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.progress-subtitle {
  font-size: 14px;
  margin: 0;
  opacity: 0.9;
}

.progress-stats {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 24px;
  margin-bottom: 32px;
  position: relative;
  z-index: 1;
}

.stat-item {
  text-align: center;
}

.stat-label {
  font-size: 12px;
  opacity: 0.8;
  margin-bottom: 4px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.stat-value {
  font-size: 32px;
  font-weight: 700;
  line-height: 1;
  text-shadow: 0 2px 8px rgba(0,0,0,0.2);
}

.stat-value.highlight {
  color: #ffd700;
  animation: glow 2s ease-in-out infinite;
}

@keyframes glow {
  0%, 100% { text-shadow: 0 0 10px rgba(255, 215, 0, 0.5); }
  50% { text-shadow: 0 0 20px rgba(255, 215, 0, 0.8); }
}

.stat-divider {
  font-size: 28px;
  font-weight: 300;
  opacity: 0.5;
}

.progress-bar-wrapper {
  margin-bottom: 24px;
  position: relative;
  z-index: 1;
}

.progress-bar-container {
  position: relative;
  height: 32px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 16px;
  overflow: hidden;
  backdrop-filter: blur(10px);
  box-shadow: inset 0 2px 4px rgba(0,0,0,0.1);
}

.progress-bar-fill {
  position: absolute;
  left: 0;
  top: 0;
  height: 100%;
  background: linear-gradient(90deg, #4facfe 0%, #00f2fe 100%);
  border-radius: 16px;
  transition: width 0.5s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(79, 172, 254, 0.4);
}

.progress-bar-shine {
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent);
  animation: shine 2s infinite;
}

@keyframes shine {
  0% { left: -100%; }
  100% { left: 200%; }
}

.progress-percentage {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  font-size: 14px;
  font-weight: 600;
  text-shadow: 0 1px 2px rgba(0,0,0,0.3);
  z-index: 1;
}

.progress-details {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 20px;
  position: relative;
  z-index: 1;
}

.detail-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  background: rgba(255, 255, 255, 0.1);
  padding: 10px 16px;
  border-radius: 8px;
  backdrop-filter: blur(10px);
}

.detail-row .el-icon {
  font-size: 16px;
  opacity: 0.9;
}

.progress-tips {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-size: 13px;
  opacity: 0.8;
  padding: 12px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  backdrop-filter: blur(10px);
  position: relative;
  z-index: 1;
}

.progress-tips .el-icon {
  font-size: 16px;
}
</style>
