<template>
  <div class="action-card">
    <template v-if="action.type === 'show_practice_preview'">
      <div class="card-head">
        <strong>练习单预览</strong>
        <el-tag size="small" type="success">AI 组卷</el-tag>
      </div>
      <div v-if="practiceVariants.length" class="variant-list">
        <div v-for="(variant, index) in practiceVariants" :key="index" class="variant-item">
          <div class="variant-title">{{ variant.sheet_name || variant.title || `第 ${index + 1} 套练习` }}</div>
          <div class="variant-meta">
            {{ getVariantQuestions(variant).length }} 题
            <span v-if="variant.estimated_minutes"> · 约 {{ variant.estimated_minutes }} 分钟</span>
            <span v-else-if="variant.estimated_time"> · 约 {{ variant.estimated_time }} 分钟</span>
          </div>
          <div v-if="getVariantQuestions(variant).length" class="question-preview">
            <div
              v-for="question in getVariantQuestions(variant)"
              :key="question.question_id || question.id || question.stem"
              class="question-line"
            >
              <div class="question-text" v-html="formatMath(question.stem || question.question_text || question.title)" />
              <div class="question-actions">
                <el-tag size="small" effect="plain">{{ question.knowledge_point || '未标注知识点' }}</el-tag>
                <el-button
                  size="small"
                  link
                  type="primary"
                  :loading="replaceLoadingKey === `${variant.variant_id || index}-${question.question_id}`"
                  @click="replaceQuestion(variant, question.question_id)"
                >
                  换一题
                </el-button>
              </div>
            </div>
          </div>
          <div class="variant-actions">
            <el-button
              size="small"
              :disabled="getVariantQuestions(variant).length >= targetCount"
              :loading="supplementLoadingKey === (variant.variant_id || index)"
              @click="supplementQuestion(variant)"
            >
              补一题
            </el-button>
          </div>
        </div>
      </div>
      <el-alert
        v-else
        type="info"
        show-icon
        :closable="false"
        title="已经生成预览，但暂时没有可展示的题目摘要。"
      />
      <div v-if="practiceVariants.length" class="confirm-row">
        <el-button type="primary" :loading="confirmLoading" @click="confirmPracticeSheets">
          确认生成练习单
        </el-button>
        <el-button v-if="createdSheets.length" type="success" plain @click="goPractice">
          去练习单查看
        </el-button>
      </div>
      <el-alert
        v-if="createdSheets.length"
        type="success"
        show-icon
        :closable="false"
        :title="`已生成 ${createdSheets.length} 套练习单，可以到练习单页面查看。`"
      />
    </template>

    <template v-else-if="action.type === 'show_weak_points'">
      <div class="card-head">
        <strong>薄弱知识点</strong>
        <el-tag size="small" type="warning">诊断</el-tag>
      </div>
      <div v-if="weakPoints.length" class="tag-grid">
        <el-tag v-for="item in weakPoints" :key="item.knowledge_point || item.name" effect="plain">
          {{ item.knowledge_point || item.name }}
          <span v-if="item.mastery_level !== undefined"> · 掌握 {{ percent(item.mastery_level) }}</span>
        </el-tag>
      </div>
      <el-empty v-else description="暂时没有明显薄弱点，继续保持。" :image-size="80" />
    </template>

    <template v-else-if="action.type === 'show_wrong_question_list'">
      <div class="card-head">
        <strong>最近错题</strong>
        <el-tag size="small">{{ action.data?.recent_days || 7 }} 天</el-tag>
      </div>
      <div v-if="wrongQuestions.length" class="wrong-list">
        <div v-for="item in wrongQuestions.slice(0, 8)" :key="item.record_id || item.question_id" class="wrong-item">
          <div class="wrong-title" v-html="formatMath(item.stem || item.question_text)" />
          <div class="wrong-meta">
            {{ item.knowledge_point || '未标注知识点' }}
            <span v-if="item.error_type"> · {{ item.error_type }}</span>
          </div>
        </div>
      </div>
      <el-empty v-else description="这段时间没有找到错题记录。" :image-size="80" />
    </template>

    <template v-else-if="action.type === 'show_question_explanation'">
      <div class="card-head">
        <strong>题目讲解</strong>
        <div class="card-tools">
          <el-tag v-if="isWrongBookAdded(question)" size="small" type="success">
            {{ wrongBookText(question) }}
          </el-tag>
          <el-tag v-else size="small" type="success">解析</el-tag>
          <el-button
            size="small"
            type="primary"
            plain
            :loading="isAddingWrong(question)"
            :disabled="isWrongBookAdded(question)"
            @click="addQuestionToWrongBook(question)"
          >
            加入错题本
          </el-button>
        </div>
      </div>
      <div class="explain-block">
        <div v-if="question.stem || question.question_text" class="explain-section">
          <b>题目</b>
          <p v-html="formatMath(question.stem || question.question_text)" />
        </div>
        <div v-for="section in question.explain_sections || []" :key="section.title" class="explain-section">
          <b>{{ section.title }}</b>
          <p v-html="formatMath(section.content)" />
        </div>
        <div v-if="question.answer" class="explain-section">
          <b>答案</b>
          <p v-html="formatMath(question.answer)" />
        </div>
        <div v-if="(question.solution || question.analysis) && !(question.explain_sections || []).length" class="explain-section">
          <b>解析</b>
          <p v-html="formatMath(question.solution || question.analysis)" />
        </div>
        <div v-if="question.easy_mistakes?.length" class="tips-box">
          <b>易错点</b>
          <p v-for="tip in question.easy_mistakes" :key="tip">{{ tip }}</p>
        </div>
      </div>
    </template>

    <template v-else-if="action.type === 'show_similar_questions'">
      <div class="card-head">
        <strong>相关题目</strong>
        <el-tag size="small" type="success">语义检索</el-tag>
      </div>
      <div v-if="similarItems.length" class="wrong-list">
        <div v-for="item in similarItems" :key="item.question_id" class="wrong-item">
          <div class="wrong-title" v-html="formatMath(item.question_text)" />
          <div class="wrong-meta">
            {{ item.knowledge_point || '未标注知识点' }}
            <span v-if="item.question_type"> · {{ item.question_type }}</span>
            <span v-if="item.difficulty"> · {{ item.difficulty }}</span>
            <span v-if="item.score"> · 匹配度 {{ Math.round(item.score * 100) }}%</span>
          </div>
        </div>
      </div>
      <el-empty v-else description="暂时没有找到足够相近的题。" :image-size="80" />
    </template>

    <template v-else-if="action.type === 'show_study_plan'">
      <div class="card-head">
        <strong>学习计划</strong>
        <el-tag size="small" type="warning">{{ studyPlan.days || 7 }} 天</el-tag>
      </div>
      <div v-if="studyPlan.wrong_focus?.length || studyPlan.weak_points?.length" class="focus-block">
        <div class="summary-title">优先关注</div>
        <div class="tag-grid">
          <el-tag v-for="item in studyPlan.wrong_focus || []" :key="`wrong-${item.knowledge_point}`" type="danger" effect="plain">
            {{ item.knowledge_point }} · 错 {{ item.wrong_count }} 次
          </el-tag>
          <el-tag v-for="item in studyPlan.weak_points || []" :key="`weak-${item.knowledge_point}`" effect="plain">
            {{ item.knowledge_point }} · 掌握 {{ item.mastery_rate || 0 }}%
          </el-tag>
        </div>
      </div>
      <div class="study-task-list">
        <div v-for="task in studyPlan.tasks || []" :key="task.day" class="study-task">
          <div class="task-day">第 {{ task.day }} 天</div>
          <div class="task-main">
            <b>{{ task.focus }}</b>
            <span>{{ task.minutes }} 分钟</span>
          </div>
          <ul>
            <li v-for="line in task.tasks" :key="line">{{ line }}</li>
          </ul>
        </div>
      </div>
      <div v-if="studyPlan.parent_tips?.length" class="tips-box">
        <b>家长陪练建议</b>
        <p v-for="tip in studyPlan.parent_tips" :key="tip">{{ tip }}</p>
      </div>
    </template>

    <template v-else-if="action.type === 'show_parent_report'">
      <div class="card-head">
        <strong>{{ parentReport.title || '家长视角学习报告' }}</strong>
        <el-tag size="small" type="warning">家长报告</el-tag>
      </div>
      <div class="parent-judgement">
        {{ parentReport.overall_judgement || '当前数据还不够完整，建议先稳定记录练习和错题。' }}
      </div>
      <div class="metric-grid">
        <div class="metric-card">
          <span>练习题数</span>
          <b>{{ parentReport.stats?.total_practiced || 0 }}</b>
          <em>{{ trendText('practice') }}</em>
        </div>
        <div class="metric-card">
          <span>正确率</span>
          <b>{{ parentReport.stats?.accuracy ?? '-' }}%</b>
          <em>{{ trendText('accuracy') }}</em>
        </div>
        <div class="metric-card">
          <span>活跃天数</span>
          <b>{{ parentReport.stats?.active_days || 0 }}</b>
          <em>最近 {{ parentReport.days || 7 }} 天</em>
        </div>
        <div class="metric-card">
          <span>完成练习单</span>
          <b>{{ parentReport.sheets?.completed || 0 }}</b>
          <em>生成 {{ parentReport.sheets?.generated || 0 }} 套</em>
        </div>
      </div>

      <div v-if="parentReport.wrong_focus?.length" class="focus-block">
        <div class="summary-title">错题集中在哪里</div>
        <div class="parent-focus-list">
          <div v-for="item in parentReport.wrong_focus" :key="item.knowledge_point" class="parent-focus-item">
            <div>
              <b>{{ item.knowledge_point }}</b>
              <span>{{ item.knowledge_category }} · 错 {{ item.wrong_count }} 次</span>
            </div>
            <p>{{ item.parent_explanation }}</p>
          </div>
        </div>
      </div>

      <div v-else-if="parentReport.weak_points?.length" class="focus-block">
        <div class="summary-title">需要优先补的薄弱点</div>
        <div class="parent-focus-list">
          <div v-for="item in parentReport.weak_points" :key="item.knowledge_point" class="parent-focus-item">
            <div>
              <b>{{ item.knowledge_point }}</b>
              <span>掌握 {{ item.mastery_rate || 0 }}%</span>
            </div>
            <p>{{ item.parent_explanation }}</p>
          </div>
        </div>
      </div>

      <div v-if="parentReport.parent_tasks?.length" class="study-task-list">
        <div class="summary-title">可执行陪练任务</div>
        <div v-for="task in parentReport.parent_tasks" :key="task.day" class="study-task">
          <div class="task-day">第 {{ task.day }} 天 · {{ task.minutes }} 分钟</div>
          <div class="task-main">
            <b>{{ task.focus }}</b>
          </div>
          <p>{{ task.parent_action }}</p>
          <small>{{ task.check_result }}</small>
        </div>
      </div>

      <div v-if="parentReport.parent_tips?.length" class="tips-box">
        <b>家长提醒</b>
        <p v-for="tip in parentReport.parent_tips" :key="tip">{{ tip }}</p>
      </div>
    </template>

    <template v-else-if="action.type === 'show_study_summary'">
      <div class="card-head">
        <strong>学习总结</strong>
        <el-tag size="small" type="success">最近 {{ studySummary.days || 7 }} 天</el-tag>
      </div>
      <div class="metric-grid">
        <div class="metric-card">
          <span>练习题数</span>
          <b>{{ studySummary.stats?.total_practiced || 0 }}</b>
        </div>
        <div class="metric-card">
          <span>正确率</span>
          <b>{{ studySummary.stats?.accuracy ?? '-' }}%</b>
        </div>
        <div class="metric-card">
          <span>新增错题</span>
          <b>{{ studySummary.stats?.wrong_count || 0 }}</b>
        </div>
        <div class="metric-card">
          <span>完成练习单</span>
          <b>{{ studySummary.stats?.completed_sheets || 0 }}</b>
        </div>
      </div>
      <div class="summary-list">
        <p v-for="line in studySummary.highlights || []" :key="line">{{ line }}</p>
      </div>
      <div v-if="studySummary.wrong_focus?.length" class="focus-block">
        <div class="summary-title">错题集中点</div>
        <div class="tag-grid">
          <el-tag v-for="item in studySummary.wrong_focus" :key="item.knowledge_point" type="danger" effect="plain">
            {{ item.knowledge_point }} · {{ item.wrong_count }} 次
          </el-tag>
        </div>
      </div>
      <div class="tips-box">
        <b>下一步建议</b>
        <p v-for="line in studySummary.next_actions || []" :key="line">{{ line }}</p>
      </div>
    </template>

    <template v-else-if="action.type === 'system_help'">
      <div class="card-head">
        <strong>功能说明</strong>
        <el-tag size="small" type="info">帮助</el-tag>
      </div>
      <p class="help-text">{{ action.data?.content || '你可以让我查看错题、分析薄弱点、讲解题目或生成练习单。' }}</p>
    </template>

    <template v-else-if="action.type === 'show_attachment_questions'">
      <div class="card-head">
        <strong>附件识别结果</strong>
        <el-tag size="small" type="success">{{ attachmentData.question_count || attachmentQuestions.length }} 题</el-tag>
      </div>
      <p class="help-text">
        {{ attachmentData.file_name || '上传文件' }}
        <span v-if="attachmentData.file_type"> · {{ attachmentTypeText }}</span>
      </p>
      <div v-if="attachmentQuestions.length" class="wrong-list">
        <div v-for="item in attachmentQuestions.slice(0, 8)" :key="`${item.page_no || 1}-${item.question_no}`" class="wrong-item">
          <div class="wrong-meta">
            第 {{ item.question_no || '?' }} 题
            <span v-if="item.page_no"> · 第 {{ item.page_no }} 页</span>
            <span v-if="item.knowledge_point"> · {{ item.knowledge_point }}</span>
            <span v-if="item.question_type"> · {{ item.question_type }}</span>
          </div>
          <div class="wrong-title" v-html="formatMath(item.question_text)" />
          <div v-if="item.answer" class="attachment-answer">
            <b>答案：</b><span v-html="formatMath(item.answer)" />
          </div>
          <div class="wrong-action-row">
            <el-tag v-if="isWrongBookAdded(item)" size="small" type="success">
              {{ wrongBookText(item) }}
            </el-tag>
            <el-button
              v-else
              size="small"
              type="primary"
              plain
              :loading="isAddingWrong(item)"
              @click="addQuestionToWrongBook(item)"
            >
              加入错题本
            </el-button>
          </div>
        </div>
      </div>
      <el-empty v-else description="暂时没有识别出明确题目，可以换更清晰的图片或文件再试。" :image-size="80" />
    </template>

    <template v-else>
      <pre>{{ action }}</pre>
    </template>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { aiGenerateConfirm, aiReplaceQuestion, aiSupplementQuestion } from '../../api/practice'
import { addAssistantWrongQuestion } from '../../api/assistant'
import { renderMath } from '../../utils/math'

const props = defineProps({
  action: {
    type: Object,
    required: true,
  },
})

const router = useRouter()
const localData = ref(cloneData(props.action.data || {}))
const confirmLoading = ref(false)
const replaceLoadingKey = ref('')
const supplementLoadingKey = ref('')
const createdSheets = ref([])
const addWrongLoadingKey = ref('')
const wrongBookResults = ref({})

watch(
  () => props.action.data,
  (value) => {
    localData.value = cloneData(value || {})
    createdSheets.value = []
    wrongBookResults.value = {}
  }
)

const practiceVariants = computed(() => {
  const data = localData.value || {}
  return data.variants || data.preview?.variants || []
})

const parsedRequirement = computed(() => localData.value?.parsed_requirement || {})

const targetCount = computed(() => {
  const count = Number(parsedRequirement.value?.target_count)
  return Number.isFinite(count) && count > 0 ? count : 24
})

const weakPoints = computed(() => {
  const data = props.action.data || {}
  return data.weak_points || data.items || []
})

const wrongQuestions = computed(() => {
  const data = props.action.data || {}
  return data.wrong_questions || data.items || []
})

const question = computed(() => props.action.data?.question || props.action.data || {})

const similarItems = computed(() => {
  const data = props.action.data || {}
  return data.items || data.questions || []
})

const studyPlan = computed(() => props.action.data || {})

const studySummary = computed(() => props.action.data || {})

const parentReport = computed(() => props.action.data || {})

const attachmentData = computed(() => props.action.data || {})

const attachmentQuestions = computed(() => attachmentData.value.questions || [])

const attachmentTypeText = computed(() => {
  const type = attachmentData.value.file_type
  return {
    image: '图片',
    pdf: 'PDF',
    markdown: '文本文件',
  }[type] || '文件'
})

function cloneData(data) {
  return JSON.parse(JSON.stringify(data || {}))
}

function getVariantQuestions(variant) {
  return variant?.selected_questions || variant?.questions || []
}

function setVariantQuestions(variant, questions) {
  if (Array.isArray(variant.selected_questions)) {
    variant.selected_questions = questions
  } else {
    variant.questions = questions
  }
}

function formatMath(text) {
  return renderMath(text || '')
}

function questionKey(item = {}) {
  return [
    item.question_id || '',
    item.page_no || '',
    item.question_no || '',
    String(item.question_text || item.stem || '').slice(0, 80),
  ].join('|')
}

function getWrongBookResult(item = {}) {
  return item.wrong_book_result || wrongBookResults.value[questionKey(item)] || null
}

function isWrongBookAdded(item = {}) {
  const result = getWrongBookResult(item)
  return Boolean(result?.record_id || result?.created || result?.already_exists)
}

function wrongBookText(item = {}) {
  const result = getWrongBookResult(item)
  return result?.already_exists ? '已在错题本' : '已加入错题本'
}

function isAddingWrong(item = {}) {
  return addWrongLoadingKey.value === questionKey(item)
}

function buildWrongQuestionPayload(item = {}) {
  return {
    question_text: String(item.question_text || item.stem || '').trim(),
    answer: String(item.answer || '').trim(),
    solution: String(item.solution || item.analysis || '').trim(),
    question_type: item.question_type || 'other',
    difficulty: item.difficulty || '中等',
    knowledge_point: item.knowledge_point || '',
    knowledge_category: item.knowledge_category || '',
    exam_name: 'AI助手识别',
    error_type: '其他',
    notes: '由 AI 学习助手识别添加',
  }
}

async function addQuestionToWrongBook(item = {}) {
  const key = questionKey(item)
  const payload = buildWrongQuestionPayload(item)
  if (!payload.question_text) {
    ElMessage.warning('这道题缺少题干，暂时不能加入错题本')
    return
  }
  addWrongLoadingKey.value = key
  try {
    const result = await addAssistantWrongQuestion(payload)
    wrongBookResults.value = {
      ...wrongBookResults.value,
      [key]: result,
    }
    if (result.already_exists) {
      ElMessage.info(result.message || '这道题已经在错题本里了')
    } else {
      ElMessage.success(result.message || '已加入错题本')
    }
  } finally {
    addWrongLoadingKey.value = ''
  }
}

function percent(value) {
  const number = Number(value)
  if (Number.isNaN(number)) return value
  return `${Math.round(number * 100)}%`
}

function trendText(type) {
  const trend = parentReport.value?.trend || {}
  if (type === 'accuracy') {
    const delta = trend.accuracy_delta
    if (delta === null || delta === undefined) return '暂无对比'
    return delta >= 0 ? `较上期 +${delta}%` : `较上期 ${delta}%`
  }
  if (type === 'practice') {
    const delta = trend.practice_delta
    if (delta === null || delta === undefined) return '暂无对比'
    return delta >= 0 ? `较上期 +${delta} 题` : `较上期 ${delta} 题`
  }
  return ''
}

async function replaceQuestion(variant, questionId) {
  const questions = getVariantQuestions(variant)
  if (!parsedRequirement.value || !questionId || !questions.length) return
  replaceLoadingKey.value = `${variant.variant_id || practiceVariants.value.indexOf(variant)}-${questionId}`
  try {
    const res = await aiReplaceQuestion({
      parsed_requirement: parsedRequirement.value,
      current_question_ids: questions.map(item => item.question_id),
      replace_question_id: questionId,
      replace_mode: 'balanced',
    })
    const nextQuestions = questions.map(item => item.question_id === questionId ? res.question : item)
    setVariantQuestions(variant, nextQuestions)
    variant.estimated_time = res.estimated_time || variant.estimated_time
    ElMessage.success(res.review_hint || '已经帮你换好一题')
  } finally {
    replaceLoadingKey.value = ''
  }
}

async function supplementQuestion(variant) {
  const questions = getVariantQuestions(variant)
  if (!parsedRequirement.value || !questions.length) return
  if (questions.length >= targetCount.value) {
    ElMessage.info('这套练习已经达到目标题量')
    return
  }
  supplementLoadingKey.value = variant.variant_id || practiceVariants.value.indexOf(variant)
  try {
    const res = await aiSupplementQuestion({
      parsed_requirement: parsedRequirement.value,
      current_question_ids: questions.map(item => item.question_id),
    })
    setVariantQuestions(variant, [...questions, res.question])
    variant.estimated_time = res.estimated_time || variant.estimated_time
    ElMessage.success(res.review_hint || '已经补进一题')
  } finally {
    supplementLoadingKey.value = ''
  }
}

async function confirmPracticeSheets() {
  const variants = practiceVariants.value
    .filter(item => getVariantQuestions(item).length)
    .map((item, index) => ({
      variant_id: item.variant_id || `variant-${index + 1}`,
      sheet_name: item.sheet_name || (
        practiceVariants.value.length > 1
          ? `${parsedRequirement.value?.sheet_name || 'AI 练习单'} ${index + 1}`
          : parsedRequirement.value?.sheet_name || 'AI 练习单'
      ),
      question_ids: getVariantQuestions(item).map(question => question.question_id),
    }))

  if (createdSheets.value.length) {
    ElMessage.info('这组练习单已经生成过了，可以去练习单页面查看')
    return
  }

  if (!variants.length) {
    ElMessage.warning('当前没有可生成的练习单')
    return
  }

  confirmLoading.value = true
  try {
    const res = await aiGenerateConfirm({
      sheet_name: parsedRequirement.value?.sheet_name || 'AI 练习单',
      sheet_type: parsedRequirement.value?.sheet_type || 'special_topic',
      variants,
    })
    createdSheets.value = res.sheets || []
    ElMessage.success(`已生成 ${res.created_count || createdSheets.value.length} 套练习单`)
  } finally {
    confirmLoading.value = false
  }
}

function goPractice() {
  router.push('/practice')
}
</script>

<style scoped>
.action-card {
  padding: 14px;
  border-radius: 16px;
  background: #f8fafc;
  border: 1px solid #dbeafe;
}

.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
  color: #0f172a;
}

.card-tools,
.wrong-action-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.wrong-action-row {
  justify-content: flex-end;
  margin-top: 10px;
}

.variant-list,
.wrong-list {
  display: grid;
  gap: 10px;
}

.variant-item,
.wrong-item {
  padding: 12px;
  border-radius: 12px;
  background: #fff;
  border: 1px solid #e2e8f0;
}

.variant-title,
.wrong-title {
  color: #1e293b;
  font-weight: 700;
  line-height: 1.6;
}

.variant-meta,
.wrong-meta {
  margin-top: 4px;
  color: #64748b;
  font-size: 12px;
}

.attachment-answer {
  margin-top: 8px;
  padding: 8px 10px;
  border-radius: 10px;
  background: #f0fdf4;
  color: #047857;
  line-height: 1.55;
}

.question-preview {
  margin-top: 10px;
  display: grid;
  gap: 6px;
}

.question-line {
  padding: 10px;
  border-radius: 10px;
  background: #f8fafc;
  color: #475569;
  font-size: 13px;
  line-height: 1.55;
}

.question-text {
  margin-bottom: 8px;
}

.question-actions,
.variant-actions,
.confirm-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.variant-actions {
  justify-content: flex-end;
  margin-top: 10px;
}

.confirm-row {
  margin-top: 14px;
}

.tag-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.focus-block {
  margin-bottom: 12px;
  padding: 12px;
  border-radius: 12px;
  background: #fff;
  border: 1px solid #e2e8f0;
}

.study-task-list {
  display: grid;
  gap: 10px;
}

.study-task {
  padding: 12px;
  border-radius: 12px;
  background: #fff;
  border: 1px solid #e2e8f0;
}

.task-day {
  color: #0f9f6e;
  font-weight: 700;
  font-size: 13px;
}

.task-main {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 6px;
  color: #0f172a;
}

.task-main span {
  color: #64748b;
  font-size: 12px;
}

.study-task ul {
  margin: 8px 0 0;
  padding-left: 18px;
  color: #475569;
  line-height: 1.7;
}

.tips-box {
  margin-top: 12px;
  padding: 12px;
  border-radius: 12px;
  background: #ecfdf5;
  color: #065f46;
}

.tips-box b {
  display: block;
  margin-bottom: 6px;
}

.tips-box p,
.summary-list p {
  margin: 4px 0;
  line-height: 1.7;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.metric-card {
  padding: 12px;
  border-radius: 12px;
  background: #fff;
  border: 1px solid #e2e8f0;
}

.metric-card span {
  display: block;
  color: #64748b;
  font-size: 12px;
}

.metric-card b {
  display: block;
  margin-top: 4px;
  color: #0f172a;
  font-size: 20px;
}

.summary-list {
  margin: 12px 0;
  padding: 12px;
  border-radius: 12px;
  background: #fff;
  border: 1px solid #e2e8f0;
}

.parent-judgement {
  margin-bottom: 12px;
  padding: 14px;
  border-radius: 14px;
  color: #064e3b;
  background: linear-gradient(135deg, #ecfdf5, #f0fdfa);
  border: 1px solid #bbf7d0;
  line-height: 1.7;
  font-weight: 700;
}

.metric-card em {
  display: block;
  margin-top: 4px;
  color: #94a3b8;
  font-size: 12px;
  font-style: normal;
}

.parent-focus-list {
  display: grid;
  gap: 10px;
}

.parent-focus-item {
  padding: 12px;
  border-radius: 12px;
  background: #fff;
  border: 1px solid #e2e8f0;
}

.parent-focus-item div {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.parent-focus-item span {
  color: #ef4444;
  font-size: 12px;
}

.parent-focus-item p,
.study-task p,
.study-task small {
  display: block;
  margin: 8px 0 0;
  color: #475569;
  line-height: 1.7;
}

.study-task small {
  color: #0f766e;
}

.explain-block {
  display: grid;
  gap: 10px;
}

.explain-section {
  padding: 12px;
  border-radius: 12px;
  background: #fff;
}

.explain-section b {
  display: block;
  margin-bottom: 6px;
  color: #047857;
}

.explain-section p,
.help-text {
  margin: 0;
  line-height: 1.75;
}

pre {
  white-space: pre-wrap;
  word-break: break-word;
}

@media (max-width: 760px) {
  .metric-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
