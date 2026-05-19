<template>
  <el-dialog :model-value="visible" title="确认识别结果" width="820px" top="5vh" destroy-on-close @close="handleCancel">
    <div v-if="!result" style="text-align:center;padding:40px;color:#999">暂无识别结果</div>

    <template v-else>
      <!-- Task info -->
      <div style="margin-bottom:16px;display:flex;align-items:center;gap:12px;flex-wrap:wrap;justify-content:space-between">
        <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap">
          <el-tag>{{ result.file_type === 'pdf' ? 'PDF' : '图片' }}</el-tag>
          <el-tag type="info">{{ result.page_count }} 页</el-tag>
          <el-tag :type="result.status === 'partial_failed' ? 'danger' : result.status === 'need_confirm' ? 'warning' : 'success'">
            {{ result.status === 'partial_failed' ? '部分成功' : result.status === 'need_confirm' ? '待确认' : '已完成' }}
          </el-tag>
          <span style="font-size:13px;color:#999">任务 #{{ result.task_id }}</span>
        </div>
        <div style="display:flex;align-items:center;gap:12px">
          <span style="font-size:13px;color:#666">已选 {{ selectedCount }} / {{ totalCount }} 题</span>
          <el-checkbox v-model="allSelected" :indeterminate="selectionIndeterminate" @change="toggleAllSelection">全选</el-checkbox>
        </div>
      </div>

      <!-- Questions -->
      <div v-for="page in result.pages" :key="page.page_no" style="margin-bottom:20px">
        <div style="font-weight:bold;margin-bottom:8px;color:#409eff">第 {{ page.page_no }} 页</div>

        <div v-for="(block, bi) in page.questions" :key="block.block_id"
             style="margin-bottom:16px;border:1px solid #e4e7ed;border-radius:8px;overflow:hidden">

          <!-- Block header -->
          <div style="display:flex;justify-content:space-between;align-items:center;padding:8px 12px;background:#f5f7fa;border-bottom:1px solid #e4e7ed">
            <div style="display:flex;align-items:center;gap:8px">
              <el-checkbox :model-value="isBlockSelected(block.block_id)" @update:model-value="(val) => setBlockSelection(block.block_id, val)" />
              <strong>第 {{ block.question_no || bi + 1 }} 题</strong>
            </div>
            <div style="display:flex;gap:8px;align-items:center">
              <el-tag v-if="block.need_manual_confirm" type="warning" size="small">需确认</el-tag>
              <el-tag v-else type="success" size="small">自动匹配</el-tag>
            </div>
          </div>

          <div style="display:flex;gap:16px;padding:12px">
            <!-- Crop image (only show for screenshot recognition) -->
            <div v-if="block.crop_image_url" style="flex-shrink:0;width:200px">
              <div style="font-size:12px;color:#999;margin-bottom:4px">题目截图</div>
              <el-image :src="block._showClean && block.clean_crop_image_url ? block.clean_crop_image_url : block.crop_image_url"
                        fit="contain"
                        style="width:200px;max-height:160px;border:1px solid #eee;border-radius:4px;background:#fafafa;cursor:pointer"
                        :preview-src-list="[block._showClean && block.clean_crop_image_url ? block.clean_crop_image_url : block.crop_image_url]"
                        preview-teleported>
                <template #error>
                  <div style="padding:20px;text-align:center;color:#ccc;font-size:12px">无图片</div>
                </template>
              </el-image>
              <!-- Original vs cleaned toggle -->
              <div v-if="block.clean_crop_image_url && block.clean_crop_image_url !== block.crop_image_url"
                   style="margin-top:4px">
                <el-button link size="small" @click="toggleClean(block)">
                  {{ block._showClean ? '查看原图' : '查看清洗图' }}
                </el-button>
              </div>
            </div>

            <!-- AI result -->
            <div style="flex:1;min-width:0">
              <el-form label-width="60px" size="small">
                <el-form-item label="题干">
                  <el-input v-model="block._editedText" type="textarea" :rows="2"
                            @input="onEditBlock(block)" />
                </el-form-item>
                <el-form-item label="题型">
                  <el-select v-model="block._editedType" style="width:140px" @change="onEditBlock(block)">
                    <el-option label="填空题" value="fill_blank" />
                    <el-option label="选择题" value="choice" />
                    <el-option label="计算题" value="calculation" />
                    <el-option label="应用题" value="problem_solving" />
                  </el-select>
                </el-form-item>
                <el-form-item label="知识点">
                  <el-input v-model="block._editedKps" placeholder="逗号分隔"
                            @input="onEditBlock(block)" />
                </el-form-item>
                <el-form-item label="答案" v-if="block.ai_answer">
                  <div style="padding:8px;background:#f0f9ff;border-radius:4px;color:#0369a1;white-space:pre-wrap">
                    {{ block.ai_answer }}
                  </div>
                </el-form-item>
                <el-form-item label="解析" v-if="block.ai_solution">
                  <div style="padding:8px;background:#f0fdf4;border-radius:4px;color:#15803d;white-space:pre-wrap;max-height:120px;overflow-y:auto">
                    {{ block.ai_solution }}
                  </div>
                </el-form-item>
                <el-form-item label="配图">
                  <div style="display:flex;gap:8px;align-items:center">
                    <el-upload
                      v-if="!block._questionImage"
                      :auto-upload="false"
                      :show-file-list="false"
                      accept="image/*"
                      :on-change="(file) => handleQuestionImageUpload(file, block)">
                      <el-button size="small" type="primary" plain>上传配图</el-button>
                    </el-upload>
                    <div v-if="block._questionImagePreview" style="display:flex;gap:8px;align-items:center">
                      <el-image
                        :src="block._questionImagePreview"
                        fit="cover"
                        style="width:60px;height:60px;border-radius:4px;border:1px solid #dcdfe6"
                        :preview-src-list="[block._questionImagePreview]"
                        preview-teleported />
                      <el-button size="small" type="danger" link @click="removeQuestionImage(block)">删除</el-button>
                    </div>
                  </div>
                </el-form-item>
              </el-form>

              <!-- Matched candidates -->
              <div v-if="block.matched_questions && block.matched_questions.length" style="margin-top:8px">
                <div style="font-size:12px;color:#666;margin-bottom:4px">题库匹配（点击选中）</div>
                <div v-for="mq in block.matched_questions" :key="mq.question_id"
                     :class="['match-item', { selected: block._selectedMatchId === mq.question_id }]"
                     @click="selectMatch(block, mq)"
                     style="padding:6px 10px;margin-bottom:4px;border:1px solid #eee;border-radius:4px;cursor:pointer;font-size:13px">
                  <div style="display:flex;justify-content:space-between;align-items:center">
                    <span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">
                      #{{ mq.question_id }} — {{ mq.question_text?.slice(0, 60) }}
                    </span>
                    <el-tag :type="mq.similarity >= 0.85 ? 'success' : mq.similarity >= 0.7 ? 'warning' : 'info'"
                            size="small" style="margin-left:8px;flex-shrink:0">
                      {{ Math.round(mq.similarity * 100) }}%
                    </el-tag>
                  </div>
                  <div style="color:#999;font-size:12px;margin-top:2px">
                    {{ mq.knowledge_point }} · {{ mq.difficulty }}
                  </div>
                </div>
              </div>

              <div v-else style="margin-top:8px;padding:8px;background:#fff7e6;border-radius:4px;font-size:12px;color:#d46b08">
                题库中未找到匹配题目，确认后将作为新题录入
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Common form -->
      <el-divider />
      <el-form :model="confirmForm" label-width="80px" size="small">
        <el-form-item label="考试名称">
          <el-input v-model="confirmForm.exam_name" placeholder="如：二外真题第2套" />
        </el-form-item>
      </el-form>
    </template>

    <template #footer>
      <el-button @click="handleCancel">取消</el-button>
      <el-button type="primary" @click="handleConfirm" :loading="confirmLoading" :disabled="!canConfirm">
        确认加入错题本 ({{ selectedCount }})
      </el-button>
    </template>

  </el-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { confirmRecognitionTask } from '../api/practice'
import { createQuestion, uploadQuestionImage } from '../api/question'
import { ElMessage } from 'element-plus'

const props = defineProps({
  visible: Boolean,
  result: { type: Object, default: null },
})

const emit = defineEmits(['close', 'confirmed'])

const confirmLoading = ref(false)
const confirmForm = ref({ exam_name: '' })
const allSelected = ref(true)
const selectionIndeterminate = ref(false)

// Store block selection state separately for reactivity
const blockSelections = ref(new Map())

// Initialize editable fields when result changes
watch(() => props.result, (val) => {
  if (!val) return
  blockSelections.value.clear()
  for (const page of val.pages || []) {
    for (const block of page.questions || []) {
      // Initialize block properties if not exists
      if (!('_editedText' in block)) {
        block._editedText = block.ai_result?.question_text || ''
        block._editedType = block.ai_result?.question_type || 'problem_solving'
        block._editedKps = (block.ai_result?.knowledge_points || []).join(', ')
        block._selectedMatchId = block.matched_questions?.[0]?.question_id || null
        block._showClean = false
        block._asNewQuestion = !block._selectedMatchId
        block._questionImage = null
        block._questionImagePreview = null
      }
      // Store selection state separately
      blockSelections.value.set(block.block_id, true)
    }
  }
  updateSelectionState()
}, { deep: true, immediate: true })

// Helper to check if block is selected
function isBlockSelected(blockId) {
  return blockSelections.value.get(blockId) ?? true
}

// Helper to set block selection
function setBlockSelection(blockId, selected) {
  blockSelections.value.set(blockId, selected)
  updateSelectionState()
}

const selectedCount = computed(() => {
  let count = 0
  for (const selected of blockSelections.value.values()) {
    if (selected) count++
  }
  return count
})

const totalCount = computed(() => {
  if (!props.result) return 0
  let count = 0
  for (const page of props.result.pages || []) {
    count += page.questions.length
  }
  return count
})

const canConfirm = computed(() => selectedCount.value > 0)

function updateSelectionState() {
  const selected = selectedCount.value
  const total = totalCount.value
  if (selected === 0) {
    allSelected.value = false
    selectionIndeterminate.value = false
  } else if (selected === total) {
    allSelected.value = true
    selectionIndeterminate.value = false
  } else {
    allSelected.value = false
    selectionIndeterminate.value = true
  }
}

function toggleAllSelection(checked) {
  if (!props.result) return
  for (const page of props.result.pages || []) {
    for (const block of page.questions || []) {
      blockSelections.value.set(block.block_id, checked)
    }
  }
  updateSelectionState()
}

function onBlockSelectionChange() {
  updateSelectionState()
}

function toggleClean(block) {
  block._showClean = !block._showClean
  const temp = block.crop_image_url
  block.crop_image_url = block.clean_crop_image_url
  block.clean_crop_image_url = temp
}

function selectMatch(block, mq) {
  block._selectedMatchId = mq.question_id
  block._asNewQuestion = false
}

function onEditBlock(block) {
  // User edited something — mark for re-evaluation
}

function handleQuestionImageUpload(file, block) {
  if (!file.raw) return

  // 验证文件类型
  if (!file.raw.type.startsWith('image/')) {
    ElMessage.warning('请上传图片文件')
    return
  }

  // 验证文件大小（最大5MB）
  if (file.raw.size > 5 * 1024 * 1024) {
    ElMessage.warning('图片大小不能超过5MB')
    return
  }

  // 保存文件和预览URL
  block._questionImage = file.raw
  block._questionImagePreview = URL.createObjectURL(file.raw)

  ElMessage.success('配图已添加')
}

function removeQuestionImage(block) {
  if (block._questionImagePreview) {
    URL.revokeObjectURL(block._questionImagePreview)
  }
  block._questionImage = null
  block._questionImagePreview = null
}

async function handleConfirm() {
  confirmLoading.value = true
  try {
    const items = []
    const newQuestions = []

    for (const page of props.result.pages || []) {
      for (const block of page.questions || []) {
        // Skip unselected blocks
        if (!isBlockSelected(block.block_id)) continue

        const text = block._editedText?.trim()
        if (!text) continue

        if (block._selectedMatchId) {
          items.push({
            block_id: block.block_id,
            matched_question_id: block._selectedMatchId,
            error_type: '',
            remark: '',
            exam_name: confirmForm.value.exam_name || '',
          })
        } else {
          // Will be created as new question
          newQuestions.push(block)
        }
      }
    }

    // Create new questions first
    for (const block of newQuestions) {
      const kps = block._editedKps?.split(/[,，、]/).map(s => s.trim()).filter(Boolean) || []
      try {
        // 先上传配图（如果有）
        let imageUrl = null
        if (block._questionImage) {
          try {
            const formData = new FormData()
            formData.append('file', block._questionImage)
            const uploadRes = await uploadQuestionImage(formData)
            imageUrl = uploadRes.url
          } catch (uploadErr) {
            ElMessage.warning(`配图上传失败: ${block._editedText?.slice(0, 20)}`)
          }
        }

        const qData = {
          q_id: '',
          knowledge_point: kps[0] || block.ai_result?.knowledge_points?.[0] || '未知',
          knowledge_category: block.ai_result?.knowledge_category || '',
          question_type: block._editedType || 'problem_solving',
          difficulty: block.ai_result?.difficulty || '中等',
          question_text: block._editedText || '',
          answer: block.ai_answer || '',
          solution: block.ai_solution || '',
          image_path: imageUrl || '',
          has_image: !!imageUrl,
        }
        const newQ = await createQuestion(qData)
        block._selectedMatchId = newQ.question_id
        items.push({
          block_id: block.block_id,
          matched_question_id: newQ.question_id,
          error_type: '',
          remark: '',
          exam_name: confirmForm.value.exam_name || '',
        })
      } catch (e) {
        ElMessage.error(`创建题目失败: ${block._editedText?.slice(0, 30)}`)
      }
    }

    if (items.length === 0) {
      ElMessage.warning('没有可确认的题目')
      confirmLoading.value = false
      return
    }

    await confirmRecognitionTask(props.result.task_id, { items })
    ElMessage.success(`已加入 ${items.length} 道题到错题本`)
    emit('confirmed')
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '确认失败')
  } finally {
    confirmLoading.value = false
  }
}

function handleCancel() {
  emit('close')
}
</script>

<style scoped>
.match-item:hover {
  border-color: #409eff;
  background: #f0f7ff;
}
.match-item.selected {
  border-color: #409eff;
  background: #e6f7ff;
}
</style>
