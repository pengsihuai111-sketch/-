<template>
  <el-dialog
    :model-value="modelValue"
    title="AI 智能生成练习单"
    width="1080px"
    top="4vh"
    destroy-on-close
    @close="handleClose"
  >
    <div style="display:flex;flex-direction:column;gap:16px">
      <div style="padding:14px 16px;background:#f7f8fa;border:1px solid #ebeef5;border-radius:8px">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
          <div style="font-weight:600;color:#303133">描述你的练习需求</div>
          <div style="display:flex;gap:6px;flex-wrap:wrap">
            <el-button size="small" @click="applyExample('给我一份分数应用题练习，8题，中等偏难，30分钟左右')">专题示例</el-button>
            <el-button size="small" @click="applyExample('根据我最近错题出一份查漏补缺练习，应用题多一点，10题')">错题示例</el-button>
            <el-button size="small" @click="applyExample('根据我最近一周的错题出三份查漏补缺练习，每张试卷计算题保证4个，每套12题')">多套示例</el-button>
          </div>
        </div>

        <el-input
          v-model="prompt"
          type="textarea"
          :rows="4"
          resize="none"
          placeholder="例如：根据我最近一周的错题出三份查漏补缺练习，每张试卷计算题保证4个，每套12题"
        />

        <div style="display:flex;justify-content:space-between;align-items:center;margin-top:10px">
          <div style="font-size:12px;color:#909399">
            AI 会先理解需求，再从题库候选题里挑题。支持一次出多套草稿，并且可以补一题、换一题。
          </div>
          <div style="display:flex;gap:8px">
            <el-button @click="handleClose">取消</el-button>
            <el-button type="primary" :loading="previewLoading" @click="handlePreview">生成预览</el-button>
          </div>
        </div>
      </div>

      <template v-if="previewData && variants.length">
        <div style="display:grid;grid-template-columns:1.1fr 1.2fr;gap:16px;align-items:start">
          <div style="padding:14px 16px;background:#fff;border:1px solid #ebeef5;border-radius:8px">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
              <div style="font-weight:600;color:#303133">AI 理解结果</div>
              <div style="display:flex;gap:8px;align-items:center">
                <el-tag type="success" size="small">{{ variants.length }} 套草稿</el-tag>
                <el-tag size="small">{{ activeVariant?.selected_questions.length || 0 }} 题 / 约 {{ activeVariant?.estimated_time || 0 }} 分钟</el-tag>
              </div>
            </div>

            <el-form label-width="96px" size="small">
              <el-form-item label="练习单名称">
                <el-input v-model="sheetName" />
              </el-form-item>
              <el-form-item label="练习类型">
                <el-tag>{{ sheetTypeLabel(previewData.parsed_requirement.sheet_type) }}</el-tag>
              </el-form-item>
              <el-form-item label="生成套数">
                <span>{{ previewData.parsed_requirement.sheet_count || variants.length }} 套</span>
              </el-form-item>
              <el-form-item label="每套题量">
                <span>{{ previewData.parsed_requirement.target_count }} 题</span>
              </el-form-item>
              <el-form-item label="目标时长">
                <span>{{ previewData.parsed_requirement.target_minutes || activeVariant?.estimated_time || 0 }} 分钟</span>
              </el-form-item>
              <el-form-item label="知识点">
                <div style="display:flex;flex-wrap:wrap;gap:6px">
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
                  <span
                    v-if="!previewData.parsed_requirement.knowledge_points.length && !previewData.parsed_requirement.knowledge_categories.length"
                    style="color:#909399"
                  >AI 会结合你的描述和近期薄弱点自动平衡覆盖</span>
                </div>
              </el-form-item>
              <el-form-item label="难度">
                <div style="display:flex;flex-wrap:wrap;gap:6px">
                  <el-tag
                    v-for="difficulty in previewData.parsed_requirement.difficulties"
                    :key="difficulty"
                    size="small"
                    type="warning"
                    effect="plain"
                  >{{ difficulty }}</el-tag>
                </div>
              </el-form-item>
              <el-form-item label="题型">
                <div style="display:flex;flex-wrap:wrap;gap:6px">
                  <el-tag
                    v-for="type in previewData.parsed_requirement.question_types"
                    :key="type"
                    size="small"
                    type="info"
                    effect="plain"
                  >{{ questionTypeLabel(type) }}</el-tag>
                  <span v-if="!previewData.parsed_requirement.question_types.length" style="color:#909399">不限</span>
                </div>
              </el-form-item>
              <el-form-item v-if="Object.keys(previewData.parsed_requirement.question_type_counts || {}).length" label="题型配额">
                <div style="display:flex;flex-wrap:wrap;gap:6px">
                  <el-tag
                    v-for="(count, type) in previewData.parsed_requirement.question_type_counts"
                    :key="`${type}-${count}`"
                    size="small"
                    type="success"
                    effect="plain"
                  >{{ questionTypeLabel(type) }} {{ count }} 题</el-tag>
                </div>
              </el-form-item>
            </el-form>

            <div style="padding:12px;background:#f7f8fa;border-radius:8px;margin-top:8px">
              <div style="font-size:13px;color:#303133;font-weight:600;margin-bottom:6px">AI 建议</div>
              <div style="font-size:13px;color:#606266;line-height:1.7">{{ previewData.suggestion.summary || '已按你的需求从题库中筛选并组合题目。' }}</div>
              <div v-if="previewData.suggestion.selection_reason" style="font-size:12px;color:#909399;margin-top:8px">
                选题思路：{{ previewData.suggestion.selection_reason }}
              </div>
              <div v-if="previewData.suggestion.coverage_summary" style="font-size:12px;color:#909399;margin-top:4px">
                覆盖说明：{{ previewData.suggestion.coverage_summary }}
              </div>
            </div>
          </div>

          <div style="padding:14px 16px;background:#fff;border:1px solid #ebeef5;border-radius:8px">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;gap:12px;flex-wrap:wrap">
              <div style="display:flex;align-items:center;gap:8px">
                <div style="font-weight:600;color:#303133">题目预览</div>
                <el-tag size="small" effect="plain">候选池 {{ previewData.candidate_count }} 题</el-tag>
              </div>
              <div style="display:flex;gap:8px;align-items:center">
                <el-button
                  size="small"
                  :disabled="!activeVariant || activeVariant.selected_questions.length >= targetCount"
                  :loading="supplementLoading"
                  @click="handleSupplement"
                >补一题</el-button>
                <span style="font-size:12px;color:#909399">
                  当前第 {{ activeVariantIndex + 1 }} 套，共 {{ activeVariant?.selected_questions.length || 0 }}/{{ targetCount }} 题
                </span>
              </div>
            </div>

            <el-tabs v-model="activeVariantId" stretch>
              <el-tab-pane
                v-for="(variant, index) in variants"
                :key="variant.variant_id"
                :name="variant.variant_id"
                :label="`第 ${index + 1} 套`"
              >
                <div style="display:flex;flex-direction:column;gap:10px;max-height:460px;overflow:auto;padding-right:4px">
                  <div
                    v-for="(question, qIndex) in variant.selected_questions"
                    :key="question.question_id"
                    style="padding:12px;border:1px solid #ebeef5;border-radius:8px;background:#fafafa"
                  >
                    <div style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start;margin-bottom:8px">
                      <div>
                        <div style="font-weight:600;color:#303133;margin-bottom:6px">第 {{ qIndex + 1 }} 题</div>
                        <div style="display:flex;gap:6px;flex-wrap:wrap">
                          <el-tag size="small">{{ question.knowledge_point }}</el-tag>
                          <el-tag size="small" type="info" effect="plain">{{ questionTypeLabel(question.question_type) }}</el-tag>
                          <el-tag size="small" type="warning" effect="plain">{{ question.difficulty || '未标注难度' }}</el-tag>
                          <el-tag v-if="question.has_image" size="small" type="success" effect="plain">含图</el-tag>
                        </div>
                      </div>
                      <div style="display:flex;gap:4px;flex-wrap:wrap;justify-content:flex-end">
                        <el-button
                          size="small"
                          :loading="replaceLoadingId === `${variant.variant_id}-${question.question_id}`"
                          @click="handleReplace(question.question_id)"
                        >换一题</el-button>
                        <el-button type="danger" link size="small" @click="removeQuestion(question.question_id)">移除</el-button>
                      </div>
                    </div>
                    <div style="font-size:13px;line-height:1.7;color:#303133;white-space:pre-wrap">
                      {{ truncateText(question.question_text) }}
                    </div>
                    <div style="font-size:12px;color:#909399;margin-top:8px">
                      入选原因：{{ question.selected_reason || '与当前需求匹配' }}
                    </div>
                  </div>
                </div>
              </el-tab-pane>
            </el-tabs>
          </div>
        </div>
      </template>
    </div>

    <template #footer>
      <div style="display:flex;justify-content:space-between;align-items:center">
        <div style="font-size:12px;color:#909399">
          确认后会把当前草稿里的每一套都生成成练习单。多套时会自动按序号命名。
        </div>
        <div style="display:flex;gap:8px">
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
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  aiGenerateConfirm,
  aiGeneratePreview,
  aiReplaceQuestion,
  aiSupplementQuestion,
} from '../api/practice'

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

watch(
  () => props.modelValue,
  (visible) => {
    if (!visible) {
      resetState()
    }
  }
)

const activeVariantIndex = computed(() => variants.value.findIndex(item => item.variant_id === activeVariantId.value))
const activeVariant = computed(() => variants.value.find(item => item.variant_id === activeVariantId.value) || null)
const targetCount = computed(() => Number(previewData.value?.parsed_requirement?.target_count || 0))
const allVariantsReady = computed(() => variants.value.length > 0 && variants.value.every(item => item.selected_questions.length > 0))

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

function handleClose() {
  emit('update:modelValue', false)
}

function applyExample(text) {
  prompt.value = text
}

function sheetTypeLabel(type) {
  return {
    daily: '每日训练',
    wrong_redo: '错题重练',
    special_topic: '专题练习',
    exam: '模拟卷',
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
      }]

  variants.value = incoming.map((item, index) => ({
    variant_id: item.variant_id || `variant-${index + 1}`,
    sheet_name: item.sheet_name || `AI练习单 ${index + 1}`,
    selected_questions: Array.isArray(item.selected_questions) ? [...item.selected_questions] : [],
    estimated_time: Number(item.estimated_time || 0),
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
  return Math.min(total, 60)
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

async function handlePreview() {
  if (!prompt.value.trim()) {
    ElMessage.warning('先告诉我你想要什么样的练习单')
    return
  }

  previewLoading.value = true
  try {
    const res = await aiGeneratePreview({ prompt: prompt.value.trim() })
    previewData.value = res
    sheetName.value = res.parsed_requirement?.sheet_name || `AI练习单 ${new Date().toISOString().slice(0, 10)}`
    normalizeVariants(res)
    if (!variants.value.length) {
      ElMessage.warning('AI 这次没有选出题目，换一种描述再试试')
      return
    }
    ElMessage.success(`已为你准备 ${variants.value.length} 套草稿`)
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '生成 AI 预览失败')
  } finally {
    previewLoading.value = false
  }
}

async function handleReplace(questionId) {
  if (!activeVariant.value || !previewData.value) return
  replaceLoadingId.value = `${activeVariant.value.variant_id}-${questionId}`
  try {
    const res = await aiReplaceQuestion({
      parsed_requirement: previewData.value.parsed_requirement,
      current_question_ids: activeVariant.value.selected_questions.map(item => item.question_id),
      replace_question_id: questionId,
    })
    updateActiveVariant((variant) => {
      const index = variant.selected_questions.findIndex(item => item.question_id === questionId)
      if (index >= 0) {
        variant.selected_questions.splice(index, 1, res.question)
      }
      variant.estimated_time = res.estimated_time || variant.estimated_time
    })
    ElMessage.success('已帮你换了一题')
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
    ElMessage.success('已补进一题')
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
