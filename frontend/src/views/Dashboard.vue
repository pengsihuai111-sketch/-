<template>
  <div>
    <el-row :gutter="20">
      <el-col :span="6">
        <el-card shadow="hover" class="warm-stat-card">
          <div style="text-align: center; padding: 10px">
            <div style="font-size: 36px; color: var(--brand-primary, #10B981); font-weight: bold">{{ stats.total_questions || '-' }}</div>
            <div style="color: var(--text-secondary); margin-top: 8px">题库总题数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="warm-stat-card">
          <div style="text-align: center; padding: 10px">
            <div style="font-size: 36px; color: var(--color-success, #5db872); font-weight: bold">{{ stats.verified_answers || '-' }}</div>
            <div style="color: var(--text-secondary); margin-top: 8px">已验证答案</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="warm-stat-card">
          <div style="text-align: center; padding: 10px">
            <div style="font-size: 36px; color: var(--color-warning, #e8a55a); font-weight: bold">{{ stats.with_image || '-' }}</div>
            <div style="color: var(--text-secondary); margin-top: 8px">带图题目</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="warm-stat-card">
          <div style="text-align: center; padding: 10px">
            <div style="font-size: 36px; color: var(--color-danger, #c64545); font-weight: bold">{{ diagnosis.total_wrong || 0 }}</div>
            <div style="color: var(--text-secondary); margin-top: 8px">待巩固错题</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header><span style="font-weight: bold">难度分布</span></template>
          <div v-if="stats.by_difficulty">
            <div v-for="(count, key) in stats.by_difficulty" :key="key" style="margin-bottom: 12px; display: flex; align-items: center">
              <span style="width: 60px">{{ key === 'basic' ? '基础' : key === 'medium' ? '中等' : key === 'hard' ? '挑战' : key }}</span>
              <el-progress :percentage="Math.round(count / stats.total_questions * 100)" :stroke-width="16" style="flex: 1" />
              <span style="width: 50px; text-align: right; margin-left: 10px">{{ count }}题</span>
            </div>
          </div>
          <el-empty v-else description="暂无数据" />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header><span style="font-weight: bold">学情速览</span></template>
          <div v-if="diagnosis.total_knowledge_points > 0">
            <div style="margin-bottom: 12px">
              <span>知识点覆盖率：</span>
              <el-tag type="primary">{{ diagnosis.total_knowledge_points }} 个知识点</el-tag>
            </div>
            <div style="margin-bottom: 12px">
              <span>平均掌握率：</span>
              <el-progress :percentage="diagnosis.average_mastery_rate || 0" :stroke-width="20" />
            </div>
            <div v-if="diagnosis.weak_points?.length">
              <span>薄弱知识点：</span>
              <el-tag v-for="kp in diagnosis.weak_points" :key="kp" type="danger" style="margin: 2px">{{ kp }}</el-tag>
            </div>
            <div v-else style="color: #67c23a">✅ 暂无薄弱知识点</div>
          </div>
          <el-empty v-else description="开始练习后生成诊断报告" />
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="hover" style="margin-top: 20px">
      <template #header><span style="font-weight: bold">快捷操作</span></template>
      <el-row :gutter="20">
        <el-col :span="6">
          <el-button class="warm-action-btn warm-action-primary" style="width: 100%; height: 80px" @click="$router.push('/practice')">
            <div style="display: flex; flex-direction: column; align-items: center">
              <el-icon size="24"><EditPen /></el-icon>
              <span style="margin-top: 4px">生成练习单</span>
            </div>
          </el-button>
        </el-col>
        <el-col :span="6">
          <el-button class="warm-action-btn warm-action-warning" style="width: 100%; height: 80px" @click="$router.push('/wrong-questions')">
            <div style="display: flex; flex-direction: column; align-items: center">
              <el-icon size="24"><WarningFilled /></el-icon>
              <span style="margin-top: 4px">错题管理</span>
            </div>
          </el-button>
        </el-col>
        <el-col :span="6">
          <el-button class="warm-action-btn warm-action-success" style="width: 100%; height: 80px" @click="$router.push('/diagnosis')">
            <div style="display: flex; flex-direction: column; align-items: center">
              <el-icon size="24"><DataAnalysis /></el-icon>
              <span style="margin-top: 4px">学情诊断</span>
            </div>
          </el-button>
        </el-col>
        <el-col :span="6">
          <el-button class="warm-action-btn warm-action-danger" style="width: 100%; height: 80px" @click="$router.push('/questions')">
            <div style="display: flex; flex-direction: column; align-items: center">
              <el-icon size="24"><Reading /></el-icon>
              <span style="margin-top: 4px">浏览题库</span>
            </div>
          </el-button>
        </el-col>
      </el-row>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { EditPen, WarningFilled, DataAnalysis, Reading } from '@element-plus/icons-vue'
import { getQuestionStats } from '../api/question'
import { getDiagnosis } from '../api/practice'

const stats = ref({})
const diagnosis = ref({})

onMounted(async () => {
  try {
    const statsRes = await getQuestionStats()
    stats.value = statsRes

    diagnosis.value = await getDiagnosis()
  } catch (e) {
    // ignore
  }
})
</script>
