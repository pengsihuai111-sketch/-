<template>
  <div>
    <el-tabs v-model="activeTab">
      <el-tab-pane label="诊断概览" name="overview">
        <!-- Stat Cards -->
        <el-row :gutter="20">
          <el-col :span="6">
            <el-card shadow="hover" class="warm-stat-card">
              <div style="text-align: center; padding: 10px">
                <div style="font-size: 32px; color: var(--brand-primary, #10B981); font-weight: bold">{{ report.total_knowledge_points || 0 }}</div>
                <div style="color: var(--text-secondary); margin-top: 8px">知识点覆盖</div>
              </div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card shadow="hover" class="warm-stat-card">
              <div style="text-align: center; padding: 10px">
                <div style="font-size: 32px; color: var(--color-success, #5db872); font-weight: bold">{{ report.average_mastery_rate || 0 }}%</div>
                <div style="color: var(--text-secondary); margin-top: 8px">平均掌握率</div>
              </div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card shadow="hover" class="warm-stat-card">
              <div style="text-align: center; padding: 10px">
                <div style="font-size: 32px; color: var(--color-danger, #c64545); font-weight: bold">{{ report.weak_points?.length || 0 }}</div>
                <div style="color: var(--text-secondary); margin-top: 8px">薄弱知识点</div>
              </div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card shadow="hover" class="warm-stat-card">
              <div style="text-align: center; padding: 10px">
                <div style="font-size: 32px; color: var(--color-warning, #e8a55a); font-weight: bold">{{ report.forgetting_risks?.length || 0 }}</div>
                <div style="color: var(--text-secondary); margin-top: 8px">遗忘风险知识点</div>
              </div>
            </el-card>
          </el-col>
        </el-row>

        <el-row :gutter="20" style="margin-top: 20px">
          <!-- 薄弱知识点详情 -->
          <el-col :span="12">
            <el-card shadow="hover">
              <template #header><span style="font-weight: bold; color: var(--color-danger)">薄弱知识点诊断</span></template>
              <div v-if="report.weak_point_details?.length" style="max-height: 420px; overflow-y: auto; padding-right: 6px">
                <div v-for="wp in report.weak_point_details" :key="wp.knowledge_point" style="margin-bottom: 14px; padding: 12px; background: #fef0f0; border-radius: 8px; border: 1px solid #f5c8c8">
                  <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px">
                    <span style="font-weight: bold; font-size: 14px">{{ wp.knowledge_point }}</span>
                    <div>
                      <el-tag type="danger" size="small" style="margin-right: 4px">掌握率 {{ wp.mastery_rate }}%</el-tag>
                      <el-tag type="warning" size="small">错 {{ wp.error_count }} 题</el-tag>
                    </div>
                  </div>
                  <div style="font-size: 13px; color: var(--text-body); margin-bottom: 4px">
                    <strong>主要问题：</strong>{{ wp.main_issue }}
                  </div>
                  <div style="font-size: 12px; color: var(--text-secondary); padding: 6px 8px; background: #fff; border-radius: 4px">
                    💡 {{ wp.suggestion }}
                  </div>
                  <div v-if="wp.key_method" style="margin-top: 4px; font-size: 12px; color: var(--brand-primary)">
                    🔑 {{ wp.key_method }}
                  </div>
                </div>
              </div>
              <div v-else-if="report.weak_points?.length">
                <div v-for="kp in report.weak_points" :key="kp" style="margin-bottom: 10px; display: flex; align-items: center; justify-content: space-between; padding: 8px 12px; background: #fef0f0; border-radius: 6px">
                  <span>{{ kp }}</span>
                  <el-tag type="danger" size="small">需加强</el-tag>
                </div>
              </div>
              <el-empty v-else description="暂无薄弱知识点" />
            </el-card>
          </el-col>

          <!-- 错误类型分布 & 遗忘风险 -->
          <el-col :span="12">
            <el-card shadow="hover" style="margin-bottom: 16px">
              <template #header><span style="font-weight: bold">错误类型分布</span></template>
              <div v-if="report.error_type_stats?.length">
                <div v-for="et in report.error_type_stats" :key="et.error_type" style="margin-bottom: 10px; display: flex; align-items: center">
                  <span style="width: 80px; font-size: 13px">{{ et.error_type }}</span>
                  <el-progress :percentage="et.percentage" :stroke-width="16" style="flex: 1" />
                  <span style="width: 50px; text-align: right; margin-left: 8px; font-size: 13px; color: var(--text-secondary)">{{ et.count }}次</span>
                </div>
              </div>
              <el-empty v-else description="暂无错误数据" />
            </el-card>

            <el-card shadow="hover">
              <template #header><span style="font-weight: bold; color: var(--color-warning)">遗忘风险知识点</span></template>
              <div v-if="report.forgetting_risks?.length">
                <div v-for="kp in report.forgetting_risks" :key="kp" style="margin-bottom: 10px; display: flex; align-items: center; justify-content: space-between; padding: 8px 12px; background: #fdf6ec; border-radius: 6px">
                  <span>{{ kp }}</span>
                  <el-tag type="warning" size="small">需复习</el-tag>
                </div>
              </div>
              <el-empty v-else description="暂无遗忘风险" />
            </el-card>
          </el-col>
        </el-row>

        <!-- 诊断建议 -->
        <el-card shadow="hover" style="margin-top: 20px">
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center">
              <span style="font-weight: bold">诊断建议</span>
              <el-button type="primary" size="small" @click="$router.push('/practice')">去生成练习单</el-button>
            </div>
          </template>
          <div v-if="report.total_knowledge_points > 0">
            <div v-if="report.weak_points?.length" style="margin-bottom: 8px; color: var(--color-danger); font-size: 14px">
              🔴 你有 <strong>{{ report.weak_points.length }}</strong> 个薄弱知识点需要加强——<em>{{ report.weak_points.slice(0, 3).join('、') }}{{ report.weak_points.length > 3 ? '等' : '' }}</em>
            </div>
            <div v-if="report.forgetting_risks?.length" style="margin-bottom: 8px; color: var(--color-warning); font-size: 14px">
              🟡 <strong>{{ report.forgetting_risks.length }}</strong> 个知识点存在遗忘风险，建议安排复习
            </div>
            <div v-if="report.total_wrong > 0" style="margin-bottom: 8px; color: var(--text-body); font-size: 14px">
              📝 错题本有 <strong>{{ report.total_wrong }}</strong> 道待巩固，建议先做错题重练
            </div>
            <div v-if="report.recent_trend && report.recent_trend !== '数据不足'" style="margin-top: 6px; padding: 8px 12px; background: #f0f9eb; border-radius: 6px; font-size: 13px; color: var(--color-success)">
              📈 {{ report.recent_trend }}
            </div>
            <div v-if="!report.weak_points?.length && !report.forgetting_risks?.length && report.total_wrong === 0" style="color: var(--color-success); font-size: 14px">
              ✅ 当前状态良好，继续保持每日练习！
            </div>
          </div>
          <el-empty v-else description="暂无诊断数据，开始练习后自动生成" />
        </el-card>
      </el-tab-pane>

      <!-- 错误分析 Tab -->
      <el-tab-pane label="错误分析" name="error-analysis">
        <el-row :gutter="20">
          <el-col :span="8">
            <el-card shadow="hover">
              <template #header><span style="font-weight: bold">错误类型统计</span></template>
              <div v-if="errorReport.error_type_stats?.length">
                <div v-for="et in errorReport.error_type_stats" :key="et.error_type" style="margin-bottom: 16px">
                  <div style="display: flex; justify-content: space-between; margin-bottom: 4px; font-size: 13px">
                    <span>{{ et.error_type }}</span>
                    <span>{{ et.count }}次（{{ et.percentage }}%）</span>
                  </div>
                  <el-progress
                    :percentage="et.percentage"
                    :stroke-width="20"
                    :color="et.error_type === '概念错误' ? '#c64545' : et.error_type === '计算错误' ? '#e8a55a' : et.error_type === '审题错误' ? '#409eff' : et.error_type === '方法错误' ? '#909399' : '#67c23a'"
                  />
                </div>
              </div>
              <el-empty v-else description="暂无数据" />
            </el-card>
          </el-col>
          <el-col :span="16">
            <el-card shadow="hover">
              <template #header><span style="font-weight: bold">知识点错误热力图</span></template>
              <div v-if="errorReport.knowledge_heatmap?.length">
                <div v-for="item in errorReport.knowledge_heatmap.slice(0, 15)" :key="item.knowledge_point" style="margin-bottom: 10px">
                  <div style="display: flex; justify-content: space-between; margin-bottom: 2px; font-size: 13px">
                    <span>{{ item.knowledge_point }}</span>
                    <span style="color: var(--text-secondary)">错 {{ item.wrong_count }} 题 · 掌握率 {{ item.mastery_rate }}%</span>
                  </div>
                  <div style="height: 8px; background: #f0f0f0; border-radius: 4px; overflow: hidden">
                    <div
                      :style="{
                        width: Math.min(100, item.wrong_count * 20) + '%',
                        height: '100%',
                        background: item.mastery_rate < 40 ? '#c64545' : item.mastery_rate < 60 ? '#e8a55a' : '#5db872',
                        borderRadius: '4px',
                        transition: 'width 0.3s',
                      }"
                    />
                  </div>
                </div>
              </div>
              <el-empty v-else description="暂无数据" />
            </el-card>
          </el-col>
        </el-row>

        <!-- 薄弱知识点详细建议 -->
        <el-card v-if="errorReport.weak_point_details?.length" shadow="hover" style="margin-top: 20px">
          <template #header><span style="font-weight: bold; color: var(--color-danger)">薄弱知识点学习建议</span></template>
          <div style="max-height: 500px; overflow-y: auto; padding-right: 6px">
          <div v-for="wp in errorReport.weak_point_details" :key="wp.knowledge_point" style="margin-bottom: 16px; padding: 14px; background: #fef0f0; border-radius: 8px; border: 1px solid #f5c8c8">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px">
              <span style="font-weight: bold; font-size: 15px">{{ wp.knowledge_point }}</span>
              <div>
                <el-progress :percentage="Math.round(wp.mastery_rate)" :stroke-width="12" :width="120" type="dashboard" :color="wp.mastery_rate < 40 ? '#c64545' : '#e8a55a'" />
              </div>
            </div>
            <div style="margin-bottom: 4px; font-size: 13px"><strong>练习情况：</strong>练习 {{ wp.total_practiced }} 次，错 {{ wp.error_count }} 题</div>
            <div style="margin-bottom: 4px; font-size: 13px"><strong>主要问题：</strong>{{ wp.main_issue }}</div>
            <div style="margin-bottom: 4px; font-size: 13px; padding: 8px; background: #fff; border-radius: 4px"><strong>💡 建议：</strong>{{ wp.suggestion }}</div>
            <div style="font-size: 12px; color: var(--brand-primary)"><strong>🔑 解题要领：</strong>{{ wp.key_method }}</div>
          </div>
          </div>
        </el-card>
      </el-tab-pane>

      <!-- 掌握度明细 Tab -->
      <el-tab-pane label="掌握度明细" name="details">
        <el-card shadow="hover">
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center">
              <span style="font-weight: bold">知识点掌握度明细</span>
              <el-tag type="info" size="medium">{{ report.total_knowledge_points || 0 }} 个知识点</el-tag>
            </div>
          </template>
          <el-table v-if="report.mastery_details?.length" :data="sortedMastery" stripe style="width: 100%" @sort-change="onSortChange">
            <el-table-column prop="knowledge_point" label="知识点" min-width="150" />
            <el-table-column label="掌握度" width="180" sortable="custom" prop="mastery_rate">
              <template #default="{ row }">
                <el-progress
                  :percentage="Math.round(row.mastery_rate)"
                  :color="row.mastery_rate >= 80 ? '#5db872' : row.mastery_rate >= 60 ? '#e8a55a' : '#c64545'"
                  :stroke-width="16"
                  :text-inside="true"
                />
              </template>
            </el-table-column>
            <el-table-column label="练习次数" width="90" align="center" sortable="custom" prop="total_practiced">
              <template #default="{ row }">{{ row.total_practiced }} 次</template>
            </el-table-column>
            <el-table-column label="正确题数" width="80" align="center">
              <template #default="{ row }">{{ row.correct_count }}</template>
            </el-table-column>
            <el-table-column label="遗忘风险" width="100" align="center">
              <template #default="{ row }">
                <el-tag v-if="row.forgetting_risk_score >= 60" type="warning" size="small">高</el-tag>
                <el-tag v-else-if="row.forgetting_risk_score >= 30" type="info" size="small">中</el-tag>
                <span v-else style="color: var(--text-muted)">低</span>
              </template>
            </el-table-column>
            <el-table-column label="上次练习" width="110" align="center" sortable="custom" prop="last_practiced_date">
              <template #default="{ row }">{{ row.last_practiced_date || '-' }}</template>
            </el-table-column>
            <el-table-column label="状态" width="80" align="center">
              <template #default="{ row }">
                <el-tag v-if="row.is_weak_point" type="danger" size="small">薄弱</el-tag>
                <el-tag v-else-if="row.mastery_rate >= 80" type="success" size="small">良好</el-tag>
                <el-tag v-else type="warning" size="small">一般</el-tag>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-else description="暂无掌握度数据，开始练习后自动生成" />
        </el-card>

        <!-- 掌握度概览图 -->
        <el-row :gutter="20" style="margin-top: 20px" v-if="report.mastery_details?.length">
          <el-col :span="12">
            <el-card shadow="hover">
              <template #header><span style="font-weight: bold">掌握度分布</span></template>
              <div v-for="(item, idx) of masterySummary" :key="idx" style="margin-bottom: 14px; display: flex; align-items: center">
                <el-tag :type="item.type" size="small" style="width: 80px; text-align: center; margin-right: 12px">{{ item.label }}</el-tag>
                <el-progress :percentage="item.percentage" :stroke-width="18" :color="item.color" style="flex: 1" />
                <span style="width: 60px; text-align: right; margin-left: 8px; font-size: 13px; color: var(--text-secondary)">{{ item.count }}个</span>
              </div>
            </el-card>
          </el-col>
          <el-col :span="12">
            <el-card shadow="hover">
              <template #header><span style="font-weight: bold">趋势判断</span></template>
              <div v-if="report.recent_trend" style="text-align: center; padding: 20px">
                <el-tag :type="trendTagType" size="large" effect="dark" style="font-size: 16px; padding: 8px 20px">
                  {{ report.recent_trend }}
                </el-tag>
                <div style="margin-top: 16px; font-size: 13px; color: var(--text-secondary)">
                  平均掌握率 <strong>{{ report.average_mastery_rate }}%</strong>，
                  薄弱点 <strong>{{ report.weak_points?.length || 0 }}</strong> 个 /
                  共 <strong>{{ report.total_knowledge_points }}</strong> 个知识点
                </div>
              </div>
              <el-empty v-else description="数据不足" />
            </el-card>
          </el-col>
        </el-row>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { getDiagnosis, getErrorAnalysis } from '../api/practice'

const activeTab = ref('overview')
const report = ref({})
const errorReport = ref({})
const sortField = ref('mastery_rate')
const sortOrder = ref('ascending')

const sortedMastery = computed(() => {
  const list = [...(report.value.mastery_details || [])]
  const field = sortField.value
  const dir = sortOrder.value === 'ascending' ? 1 : -1
  list.sort((a, b) => {
    const va = a[field] ?? ''
    const vb = b[field] ?? ''
    if (typeof va === 'string') return dir * va.localeCompare(vb)
    return dir * (va - vb)
  })
  return list
})

const masterySummary = computed(() => {
  const details = report.value.mastery_details || []
  const good = details.filter(d => d.mastery_rate >= 80).length
  const medium = details.filter(d => d.mastery_rate >= 60 && d.mastery_rate < 80).length
  const weak = details.filter(d => d.mastery_rate < 60).length
  const total = details.length || 1
  return [
    { label: '良好', type: 'success', color: '#5db872', count: good, percentage: Math.round(good / total * 100) },
    { label: '一般', type: 'warning', color: '#e8a55a', count: medium, percentage: Math.round(medium / total * 100) },
    { label: '薄弱', type: 'danger', color: '#c64545', count: weak, percentage: Math.round(weak / total * 100) },
  ]
})

const trendTagType = computed(() => {
  const t = report.value.recent_trend || ''
  if (t.includes('稳步提升')) return 'success'
  if (t.includes('向好')) return 'warning'
  if (t.includes('薄弱') || t.includes('未练习')) return 'danger'
  return 'info'
})

function onSortChange({ prop, order }) {
  if (prop) sortField.value = prop
  sortOrder.value = order || 'ascending'
}

onMounted(async () => {
  try {
    report.value = await getDiagnosis()
  } catch (e) { /* ignore */ }
  try {
    errorReport.value = await getErrorAnalysis()
  } catch (e) { /* ignore */ }
})
</script>
