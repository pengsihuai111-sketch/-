<template>
  <el-dialog
    :model-value="modelValue"
    title="AI 智能生成练习单"
    width="1120px"
    top="4vh"
    destroy-on-close
    @close="handleClose"
  >
    <div class="ai-practice-dialog">
      <div class="request-panel">
        <div class="section-header">
          <div>
            <div class="section-title">先告诉我你想练什么</div>
            <div class="section-subtitle">先选结构化条件，再补一句自然语言，系统会更稳定地理解你的需求。</div>
          </div>
          <div class="example-actions">
            <el-button size="small" @click="applyExample('topic')">专题示例</el-button>
            <el-button size="small" @click="applyExample('wrong')">错题示例</el-button>
            <el-button size="small" @click="applyExample('multi')">多套示例</el-button>
          </div>
        </div>

        <el-form label-width="92px" class="structured-form">
          <div class="form-grid">
            <el-form-item label="练习单名称">
              <el-input v-model="structured.sheet_name" placeholder="例如：分数应用题专项" />
            </el-form-item>
            <el-form-item label="练习类型">
              <el-select v-model="structured.sheet_type" placeholder="请选择">
                <el-option label="专题练习" value="special_topic" />
                <el-option label="错题重练" value="wrong_redo" />
                <el-option label="每日训练" value="daily" />
                <el-option label="模拟试卷" value="exam" />
              </el-select>
            </el-form-item>
            <el-form-item label="生成套数">
              <el-input-number v-model="structured.sheet_count" :min="1" :max="5" controls-position="right" />
            </el-form-item>
            <el-form-item label="每套题量">
              <el-input-number v-model="structured.target_count" :min="4" :max="24" controls-position="right" />
            </el-form-item>
            <el-form-item label="目标时长">
              <el-input-number v-model="structured.target_minutes" :min="10" :max="120" controls-position="right" />
              <span class="unit-label">分钟</span>
            </el-form-item>
            <el-form-item label="难度安排">
              <el-select v-model="structured.difficulties" multiple collapse-tags collapse-tags-tooltip placeholder="可多选">
                <el-option label="基础" value="基础" />
                <el-option label="中等" value="中等" />
                <el-option label="挑战" value="挑战" />
              </el-select>
            </el-form-item>
          </div>

          <el-form-item label="知识类别">
            <el-select v-model="structured.knowledge_categories" multiple collapse-tags collapse-tags-tooltip placeholder="可多选">
              <el-option v-for="category in categories" :key="category" :label="category" :value="category" />
            </el-select>
          </el-form-item>

          <el-form-item label="知识点">
            <el-select v-model="structured.knowledge_points" multiple filterable collapse-tags collapse-tags-tooltip placeholder="可多选">
              <el-option
                v-for="point in filteredKnowledgePoints"
                :key="point"
                :label="point"
                :value="point"
              />
            </el-select>
          </el-form-item>

          <el-form-item label="题型要求">
            <div class="type-counts">
              <div v-for="type in questionTypeOptions" :key="type.value" class="type-count-item">
                <span class="type-label">{{ type.label }}</span>
                <el-input-number
                  v-model="structured.question_type_counts[type.value]"
                  :min="0"
                  :max="20"
                  controls-position="right"
                />
              </div>
            </div>
          </el-form-item>

          <el-form-item label="额外偏好">
            <div class="toggle-row">
              <el-checkbox v-model="structured.must_include_wrong_questions">优先包含错题</el-checkbox>
              <el-checkbox v-model="structured.avoid_recent_questions">尽量避开最近做过的题</el-checkbox>
              <el-checkbox v-model="structured.difficulty_progression">按先易后难排序</el-checkbox>
            </div>
          </el-form-item>

          <el-form-item label="补充描述">
            <el-input
              v-model="prompt"
              type="textarea"
              :rows="4"
              resize="none"
              placeholder="例如：应用题多一点，最后两题稍难；优先覆盖浓度和工程问题。"
            />
          </el-form-item>
        </el-form>

        <div class="request-footer">
          <div class="request-hint">
            当前是“AI 理解需求 + 程序从题库选题”的模式，系统会先理解你的要求，再从题库中挑更合适的题。
          </div>
          <div class="request-actions">
            <el-button @click="handleClose">取消</el-button>
            <el-button type="primary" :loading="previewLoading" @click="handlePreview">生成预览</el-button>
          </div>
        </div>
      </div>

      <template v-if="previewData && variants.length">
        <div class="preview-layout">
          <div class="understanding-panel">
            <div class="panel-title-row">
              <div class="section-title">系统理解结果</div>
              <div class="tag-row">
                <el-tag type="success" size="small">{{ variants.length }} 套草稿</el-tag>
                <el-tag size="small">候选池 {{ previewData.candidate_count }} 题</el-tag>
              </div>
            </div>

            <div class="summary-card">
              <div class="summary-title">准备生成什么</div>
              <div class="summary-lines">
                <div>名称：{{ sheetName }}</div>
                <div>类型：{{ sheetTypeLabel(previewData.parsed_requirement.sheet_type) }}</div>
                <div>套数：{{ previewData.parsed_requirement.sheet_count || variants.length }} 套</div>
                <div>题量：每套 {{ previewData.parsed_requirement.target_count }} 题</div>
                <div>时长：目标 {{ previewData.parsed_requirement.target_minutes || activeVariant?.estimated_time || 0 }} 分钟</div>
              </div>
            </div>

            <div class="summary-card">
              <div class="summary-title">筛题条件</div>
              <div class="token-block">
                <el-tag
                  v-for="kp in previewData.parsed_requirement.knowledge_points"
                  :key="kp"
                  size="small"
                  effect="plain"
                >{{ kp }}</el-tag>
                <el-tag
                  v-for="cat in previewData.parsed_requirement.knowledge_categories"
                  :key="`cat-${cat}`"
                  type="info"
                  size="small"
                  effect="plain"
                >{{ cat }}</el-tag>
                <span v-if="!previewData.parsed_requirement.knowledge_points.length && !previewData.parsed_requirement.knowledge_categories.length" class="muted-text">
                  本次没有明确指定知识点，系统会结合你的描述、错题和薄弱点综合选题。
                </span>
              </div>
              <div class="token-block">
                <el-tag
                  v-for="difficulty in previewData.parsed_requirement.difficulties"
                  :key="difficulty"
                  type="warning"
                  size="small"
                  effect="plain"
                >{{ difficulty }}</el-tag>
              </div>
              <div class="token-block">
                <el-tag
                  v-for="type in previewData.parsed_requirement.question_types"
                  :key="type"
                  type="info"
                  size="small"
                  effect="plain"
                >{{ questionTypeLabel(type) }}</el-tag>
              </div>
              <div class="token-block" v-if="Object.keys(previewData.parsed_requirement.question_type_counts || {}).length">
                <el-tag
                  v-for="(count, type) in previewData.parsed_requirement.question_type_counts"
                  :key="`${type}-${count}`"
                  type="success"
                  size="small"
                  effect="plain"
                >{{ questionTypeLabel(type) }} {{ count }} 题</el-tag>
              </div>
            </div>

            <div class="summary-card">
              <div class="summary-title">AI 说明</div>
              <div class="summary-paragraph">{{ previewData.suggestion.summary || '系统已经按照你的需求挑选出一批候选题。' }}</div>
              <div class="summary-helper">选题思路：{{ previewData.suggestion.selection_reason || '系统会优先满足明确条件。' }}</div>
              <div class="summary-helper">排序逻辑：{{ previewData.suggestion.ordering_reason || '默认按先易后难排列。' }}</div>
              <div class="summary-helper">覆盖说明：{{ previewData.suggestion.coverage_summary || '系统会兼顾题型、难度和知识点覆盖。' }}</div>
              <div v-if="previewData.suggestion.review_summary" class="summary-helper">复核结论：{{ previewData.suggestion.review_summary }}</div>
              <div v-if="previewData.parsed_requirement.learning_advice" class="summary-helper">练习建议：{{ previewData.parsed_requirement.learning_advice }}</div>
            </div>

            <div v-if="previewData.suggestion.explanation_lines?.length" class="summary-card">
              <div class="summary-title">为什么这样组卷</div>
              <div class="explanation-list">
                <div v-for="line in previewData.suggestion.explanation_lines" :key="line" class="explanation-item">
                  {{ line }}
                </div>
              </div>
            </div>
          </div>

          <div class="question-panel">
            <div class="panel-title-row">
              <div class="section-title">题目预览</div>
              <div class="tag-row">
                <span class="muted-text">当前第 {{ activeVariantIndex + 1 }} 套，共 {{ activeVariant?.selected_questions.length || 0 }}/{{ targetCount }} 题</span>
              </div>
            </div>

            <div class="preview-top-actions">
              <el-button
                size="small"
                :disabled="!activeVariant || activeVariant.selected_questions.length >= targetCount"
                :loading="supplementLoading"
                @click="handleSupplement"
              >补一题</el-button>
            </div>

            <el-tabs v-model="activeVariantId" stretch>
              <el-tab-pane
                v-for="(variant, index) in variants"
                :key="variant.variant_id"
                :name="variant.variant_id"
                :label="`第 ${index + 1} 套`"
              >
                <div class="variant-summary-grid">
                  <div class="summary-card compact-card">
                    <div class="summary-title">结构说明</div>
                    <div class="summary-helper strong-text">{{ variant.composition_summary || '系统已为这套题做题型和难度平衡。' }}</div>
                  </div>
                  <div class="summary-card compact-card">
                    <div class="summary-title">覆盖说明</div>
                    <div class="summary-helper strong-text">{{ variant.coverage_summary || '系统已尽量保证知识点覆盖。' }}</div>
                  </div>
                  <div class="summary-card compact-card">
                    <div class="summary-title">复核意见</div>
                    <div class="summary-helper strong-text">{{ variant.review_summary || '这套题整体结构较协调。' }}</div>
                  </div>
                </div>

                <div class="question-list">
                  <div
                    v-for="(question, qIndex) in variant.selected_questions"
                    :key="question.question_id"
                    class="question-card"
                  >
                    <div class="question-head">
                      <div>
                        <div class="question-index">第 {{ qIndex + 1 }} 题</div>
                        <div class="tag-row">
                          <el-tag size="small">{{ question.knowledge_point }}</el-tag>
                          <el-tag size="small" type="info" effect="plain">{{ questionTypeLabel(question.question_type) }}</el-tag>
                          <el-tag size="small" type="warning" effect="plain">{{ question.difficulty || '未标注难度' }}</el-tag>
                          <el-tag v-if="question.has_image" size="small" type="success" effect="plain">含图</el-tag>
                        </div>
                      </div>
                      <div class="question-actions">
                        <el-button
                          size="small"
                          :loading="replaceLoadingId === `${variant.variant_id}-${question.question_id}-balanced`"
                          @click="handleReplace(question.question_id, 'balanced')"
                        >换一题</el-button>
                        <el-dropdown @command="(mode) => handleReplace(question.question_id, mode)">
                          <el-button size="small">
                            精细替换
                          </el-button>
                          <template #dropdown>
                            <el-dropdown-menu>
                              <el-dropdown-item command="easier">换简单一点</el-dropdown-item>
                              <el-dropdown-item command="harder">换难一点</el-dropdown-item>
                              <el-dropdown-item command="same_type">换同题型</el-dropdown-item>
                              <el-dropdown-item command="same_knowledge">换同知识点</el-dropdown-item>
                              <el-dropdown-item command="wrong_focused">更贴近错题</el-dropdown-item>
                            </el-dropdown-menu>
                          </template>
                        </el-dropdown>
                        <el-button type="danger" link size="small" @click="removeQuestion(question.question_id)">移除</el-button>
                      </div>
                    </div>
                    <div class="question-text">{{ truncateText(question.question_text) }}</div>
                    <div class="question-reason">入选原因：{{ question.selected_reason || '与当前需求匹配' }}</div>
                  </div>
                </div>
              </el-tab-pane>
            </el-tabs>
          </div>
        </div>
      </template>
    </div>

    <template #footer>
      <div class="dialog-footer">
        <div class="request-hint">
          确认后会把当前草稿中的每一套都生成成练习单，多套时会自动按序号命名。
        </div>
        <div class="request-actions">
          <el-button @click="handleClose">关闭</el-button>
          <el-button
            type="primary"
            :disabled="!previewData || !variants.length || !allVariantsReady"
            :loading="confirmLoading"
            @click="handleConfirm"
          >
            确认生成 {{ variants.length || 0 }} 套练习单
          </el-button>
        </div>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  aiGenerateConfirm,
  aiGeneratePreview,
  aiReplaceQuestion,
  aiSupplementQuestion,
} from '../api/practice'
import { listKnowledgePoints } from '../api/question'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['update:modelValue', 'created'])

const prompt = ref('')
const previewLoading = ref(false)
const confirmLoading = ref(false)
const supplementLoading = ref(false)
const replaceLoadingId = ref('')
const previewData = ref(null)
const sheetName = ref('')
const variants = ref([])
const activeVariantId = ref('')
const groupedKnowledgePoints = ref({})
const knowledgeLoading = ref(false)

const questionTypeOptions = [
  { label: '计算题', value: 'calculation' },
  { label: '填空题', value: 'fill_blank' },
  { label: '选择题', value: 'choice' },
  { label: '应用题', value: 'problem_solving' },
]

const structuredDefaults = () => ({
  sheet_name: '',
  sheet_type: 'special_topic',
  sheet_count: 1,
  target_count: 8,
  target_minutes: 30,
  knowledge_categories: [],
  knowledge_points: [],
  question_type_counts: {
    calculation: 0,
    fill_blank: 0,
    choice: 0,
    problem_solving: 0,
  },
  difficulties: ['基础', '中等'],
  must_include_wrong_questions: false,
  avoid_recent_questions: true,
  difficulty_progression: true,
})

const structured = reactive(structuredDefaults())
const STORAGE_KEY = 'ai_practice_dialog_draft_v1'

watch(
  () => props.modelValue,
  async (visible) => {
    if (visible) {
      restoreDraft()
      await loadKnowledgePoints()
      return
    }
  }
)

watch(
  [prompt, structured],
  () => saveDraft(),
  { deep: true }
)

const categories = computed(() => Object.keys(groupedKnowledgePoints.value || {}))
const filteredKnowledgePoints = computed(() => {
  const groups = groupedKnowledgePoints.value || {}
  if (!structured.knowledge_categories.length) {
    return Object.values(groups).flat()
  }
  return structured.knowledge_categories.flatMap(category => groups[category] || [])
})
const selectedQuestionTypes = computed(() =>
  questionTypeOptions
    .filter(item => Number(structured.question_type_counts[item.value] || 0) > 0)
    .map(item => item.value)
)
const activeVariantIndex = computed(() => variants.value.findIndex(item => item.variant_id === activeVariantId.value))
const activeVariant = computed(() => variants.value.find(item => item.variant_id === activeVariantId.value) || null)
const targetCount = computed(() => Number(previewData.value?.parsed_requirement?.target_count || 0))
const allVariantsReady = computed(() => variants.value.length > 0 && variants.value.every(item => item.selected_questions.length > 0))

async function loadKnowledgePoints() {
  if (knowledgeLoading.value || Object.keys(groupedKnowledgePoints.value).length) return
  knowledgeLoading.value = true
  try {
    const res = await listKnowledgePoints()
    groupedKnowledgePoints.value = res.knowledge_points || {}
  } catch (error) {
    ElMessage.warning(error?.response?.data?.detail || '知识点加载失败，仍可继续输入自然语言描述')
  } finally {
    knowledgeLoading.value = false
  }
}

function resetStructured() {
  const defaults = structuredDefaults()
  Object.keys(defaults).forEach((key) => {
    if (typeof defaults[key] === 'object' && defaults[key] !== null) {
      structured[key] = Array.isArray(defaults[key]) ? [...defaults[key]] : { ...defaults[key] }
      return
    }
    structured[key] = defaults[key]
  })
}

function resetState() {
  previewLoading.value = false
  confirmLoading.value = false
  supplementLoading.value = false
  replaceLoadingId.value = ''
  previewData.value = null
  sheetName.value = ''
  variants.value = []
  activeVariantId.value = ''
}

function saveDraft() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      prompt: prompt.value,
      structured: JSON.parse(JSON.stringify(structured)),
    }))
  } catch {
    // localStorage may be unavailable in private browsing.
  }
}

function restoreDraft() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return
    const parsed = JSON.parse(raw)
    if (typeof parsed.prompt === 'string') {
      prompt.value = parsed.prompt
    }
    if (parsed.structured && typeof parsed.structured === 'object') {
      const defaults = structuredDefaults()
      Object.keys(defaults).forEach((key) => {
        if (parsed.structured[key] === undefined) return
        if (typeof defaults[key] === 'object' && defaults[key] !== null) {
          structured[key] = Array.isArray(defaults[key])
            ? [...parsed.structured[key]]
            : { ...defaults[key], ...parsed.structured[key] }
          return
        }
        structured[key] = parsed.structured[key]
      })
    }
  } catch {
    // Ignore malformed drafts.
  }
}

function handleClose() {
  resetState()
  emit('update:modelValue', false)
}

function applyExample(type) {
  resetStructured()
  if (type === 'topic') {
    structured.sheet_name = '分数应用题专项'
    structured.sheet_type = 'special_topic'
    structured.target_count = 10
    structured.target_minutes = 30
    structured.difficulties = ['中等', '挑战']
    structured.question_type_counts.problem_solving = 4
    structured.question_type_counts.calculation = 3
    structured.question_type_counts.fill_blank = 2
    structured.question_type_counts.choice = 1
    prompt.value = '重点练分数应用题，最后两题稍难一些。'
    return
  }
  if (type === 'wrong') {
    structured.sheet_name = '错题查漏补缺'
    structured.sheet_type = 'wrong_redo'
    structured.target_count = 10
    structured.target_minutes = 25
    structured.must_include_wrong_questions = true
    structured.difficulties = ['基础', '中等']
    structured.question_type_counts.problem_solving = 3
    structured.question_type_counts.calculation = 3
    structured.question_type_counts.fill_blank = 2
    prompt.value = '优先覆盖我最近的错题，应用题多一点。'
    return
  }
  structured.sheet_name = '一周错题强化'
  structured.sheet_type = 'wrong_redo'
  structured.sheet_count = 3
  structured.target_count = 12
  structured.target_minutes = 35
  structured.must_include_wrong_questions = true
  structured.difficulties = ['基础', '中等', '挑战']
  structured.question_type_counts.calculation = 4
  structured.question_type_counts.fill_blank = 3
  structured.question_type_counts.problem_solving = 3
  prompt.value = '根据我最近一周的错题生成三套练习，整体先易后难。'
}

function sheetTypeLabel(type) {
  return {
    daily: '每日训练',
    wrong_redo: '错题重练',
    special_topic: '专题练习',
    exam: '模拟试卷',
  }[type] || type || '未设置'
}

function questionTypeLabel(type) {
  return {
    calculation: '计算题',
    fill_blank: '填空题',
    choice: '选择题',
    problem_solving: '应用题',
  }[type] || type || '未标注'
}

function truncateText(text) {
  if (!text) return ''
  return text.length <= 180 ? text : `${text.slice(0, 180)}...`
}

function normalizeVariants(response) {
  const incoming = Array.isArray(response?.variants) && response.variants.length
    ? response.variants
    : [{
        variant_id: 'variant-1',
        sheet_name: response?.parsed_requirement?.sheet_name || 'AI练习单',
        selected_questions: Array.isArray(response?.selected_questions) ? response.selected_questions : [],
        estimated_time: response?.estimated_time || 0,
        composition_summary: '',
        coverage_summary: '',
        review_summary: '',
      }]

  variants.value = incoming.map((item, index) => ({
    variant_id: item.variant_id || `variant-${index + 1}`,
    sheet_name: item.sheet_name || `AI练习单${index + 1}`,
    selected_questions: Array.isArray(item.selected_questions) ? [...item.selected_questions] : [],
    estimated_time: Number(item.estimated_time || 0),
    composition_summary: item.composition_summary || '',
    coverage_summary: item.coverage_summary || '',
    review_summary: item.review_summary || '',
  }))
  activeVariantId.value = variants.value[0]?.variant_id || ''
}

function estimateTimeLocally(questions) {
  const typeMap = { fill_blank: 2, choice: 2, problem_solving: 8, calculation: 3 }
  const diffMap = { 基础: 2, 中等: 3, 挑战: 5 }
  const total = questions.reduce((sum, question) => {
    const typeTime = typeMap[question.question_type] || 3
    const diffTime = diffMap[question.difficulty] || 3
    return sum + Math.max(typeTime, diffTime)
  }, 0)
  return Math.min(total, 120)
}

function updateActiveVariant(mutator) {
  const idx = variants.value.findIndex(item => item.variant_id === activeVariantId.value)
  if (idx < 0) return
  const clone = {
    ...variants.value[idx],
    selected_questions: [...variants.value[idx].selected_questions],
  }
  mutator(clone)
  clone.estimated_time = estimateTimeLocally(clone.selected_questions)
  variants.value.splice(idx, 1, clone)
}

function removeQuestion(questionId) {
  updateActiveVariant((variant) => {
    variant.selected_questions = variant.selected_questions.filter(item => item.question_id !== questionId)
  })
}

function buildPreviewPayload() {
  return {
    prompt: prompt.value.trim(),
    sheet_name: structured.sheet_name.trim(),
    sheet_type: structured.sheet_type,
    sheet_count: structured.sheet_count,
    target_count: structured.target_count,
    target_minutes: structured.target_minutes,
    knowledge_categories: [...structured.knowledge_categories],
    knowledge_points: [...structured.knowledge_points],
    question_types: selectedQuestionTypes.value,
    question_type_counts: Object.fromEntries(
      Object.entries(structured.question_type_counts).filter(([, count]) => Number(count) > 0)
    ),
    difficulties: [...structured.difficulties],
    must_include_wrong_questions: structured.must_include_wrong_questions,
    avoid_recent_questions: structured.avoid_recent_questions,
    difficulty_progression: structured.difficulty_progression,
  }
}

async function handlePreview() {
  const payload = buildPreviewPayload()
  const hasStructuredCondition = [
    payload.sheet_name,
    payload.knowledge_categories.length,
    payload.knowledge_points.length,
    payload.question_types.length,
    Object.keys(payload.question_type_counts).length,
    payload.difficulties.length,
    payload.must_include_wrong_questions,
  ].some(Boolean)

  if (!payload.prompt && !hasStructuredCondition) {
    ElMessage.warning('先描述需求，或者至少选择一项结构化条件')
    return
  }

  previewLoading.value = true
  try {
    const res = await aiGeneratePreview(payload)
    previewData.value = res
    sheetName.value = res.parsed_requirement?.sheet_name || structured.sheet_name || `AI练习单${new Date().toISOString().slice(0, 10)}`
    normalizeVariants(res)
    if (!variants.value.length) {
      ElMessage.warning('这次没有选出合适的题目，换一种描述再试试')
      return
    }
    ElMessage.success(`已为你准备 ${variants.value.length} 套练习草稿`)
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '生成 AI 预览失败')
  } finally {
    previewLoading.value = false
  }
}

async function handleReplace(questionId, replaceMode = 'balanced') {
  if (!activeVariant.value || !previewData.value) return
  replaceLoadingId.value = `${activeVariant.value.variant_id}-${questionId}-${replaceMode}`
  try {
    const res = await aiReplaceQuestion({
      parsed_requirement: previewData.value.parsed_requirement,
      current_question_ids: activeVariant.value.selected_questions.map(item => item.question_id),
      replace_question_id: questionId,
      replace_mode: replaceMode,
    })
    updateActiveVariant((variant) => {
      const index = variant.selected_questions.findIndex(item => item.question_id === questionId)
      if (index >= 0) {
        variant.selected_questions.splice(index, 1, res.question)
      }
      variant.estimated_time = res.estimated_time || variant.estimated_time
    })
    ElMessage.success(res.review_hint || '已经帮你换了一题')
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '换题失败')
  } finally {
    replaceLoadingId.value = ''
  }
}

async function handleSupplement() {
  if (!activeVariant.value || !previewData.value) return
  if (activeVariant.value.selected_questions.length >= targetCount.value) {
    ElMessage.info('这套题已经达到目标题量了')
    return
  }
  supplementLoading.value = true
  try {
    const res = await aiSupplementQuestion({
      parsed_requirement: previewData.value.parsed_requirement,
      current_question_ids: activeVariant.value.selected_questions.map(item => item.question_id),
    })
    updateActiveVariant((variant) => {
      variant.selected_questions.push(res.question)
      variant.estimated_time = res.estimated_time || variant.estimated_time
    })
    ElMessage.success(res.review_hint || '已经补进一题')
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '补题失败')
  } finally {
    supplementLoading.value = false
  }
}

async function handleConfirm() {
  if (!variants.value.length) {
    ElMessage.warning('当前没有可生成的练习单')
    return
  }

  confirmLoading.value = true
  try {
    const baseName = sheetName.value.trim() || 'AI练习单'
    const payload = {
      sheet_name: baseName,
      sheet_type: previewData.value?.parsed_requirement?.sheet_type || 'special_topic',
      variants: variants.value
        .filter(item => item.selected_questions.length)
        .map((item, index) => ({
          variant_id: item.variant_id,
          sheet_name: variants.value.length > 1 ? `${baseName} ${index + 1}` : baseName,
          question_ids: item.selected_questions.map(question => question.question_id),
        })),
    }
    const res = await aiGenerateConfirm(payload)
    ElMessage.success(`AI 练习单已生成 ${res.created_count || res.sheets?.length || 0} 套`)
    emit('created', res)
    emit('update:modelValue', false)
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '生成练习单失败')
  } finally {
    confirmLoading.value = false
  }
}
</script>

<style scoped>
.ai-practice-dialog {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.request-panel,
.understanding-panel,
.question-panel {
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 12px;
  padding: 16px 18px;
}

.section-header,
.panel-title-row,
.request-footer,
.dialog-footer,
.preview-top-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.section-subtitle,
.request-hint,
.muted-text,
.summary-helper,
.question-reason {
  font-size: 12px;
  color: #909399;
}

.structured-form {
  margin-top: 14px;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px 16px;
}

.unit-label {
  margin-left: 8px;
  color: #909399;
  font-size: 12px;
}

.type-counts {
  width: 100%;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.type-count-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border: 1px solid #ebeef5;
  border-radius: 10px;
  background: #fafafa;
}

.type-label {
  min-width: 48px;
  color: #606266;
}

.toggle-row,
.token-block,
.tag-row,
.explanation-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.request-actions,
.example-actions,
.question-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.preview-layout {
  display: grid;
  grid-template-columns: minmax(320px, 0.95fr) minmax(420px, 1.15fr);
  gap: 16px;
  align-items: start;
}

.summary-card {
  margin-top: 12px;
  padding: 12px;
  border-radius: 10px;
  background: #f7f8fa;
}

.compact-card {
  margin-top: 0;
}

.summary-title {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 8px;
}

.summary-lines,
.summary-paragraph,
.strong-text {
  font-size: 13px;
  color: #606266;
  line-height: 1.7;
}

.strong-text {
  color: #303133;
}

.explanation-item {
  width: 100%;
  font-size: 13px;
  color: #606266;
  line-height: 1.7;
}

.variant-summary-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 12px;
}

.question-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 500px;
  overflow: auto;
  padding-right: 4px;
}

.question-card {
  padding: 12px;
  border: 1px solid #ebeef5;
  border-radius: 10px;
  background: #fafafa;
}

.question-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 8px;
}

.question-index {
  font-weight: 600;
  color: #303133;
  margin-bottom: 6px;
}

.question-text {
  white-space: pre-wrap;
  line-height: 1.7;
  color: #303133;
  font-size: 13px;
}

@media (max-width: 960px) {
  .form-grid,
  .preview-layout,
  .type-counts,
  .variant-summary-grid {
    grid-template-columns: 1fr;
  }
}
</style>
