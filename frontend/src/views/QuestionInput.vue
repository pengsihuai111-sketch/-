<template>
  <div>
    <el-tabs v-model="activeTab">
      <el-tab-pane label="单题录入" name="single">
        <el-card shadow="hover">
          <template #header><span style="font-weight: bold">录入新题目</span></template>
          <el-form :model="form" label-width="120px" :rules="rules" ref="formRef">
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="知识点分类" prop="knowledge_category">
                  <el-select v-model="form.knowledge_category" placeholder="选择分类" clearable style="width: 100%" @change="onCategoryChange">
                    <el-option v-for="c in categories" :key="c" :label="c" :value="c" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="知识点" prop="knowledge_point">
                  <el-select v-model="form.knowledge_point" placeholder="选择或输入" allow-create filterable style="width: 100%">
                    <el-option v-for="kp in filteredKps" :key="kp" :label="kp" :value="kp" />
                  </el-select>
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="20">
              <el-col :span="8">
                <el-form-item label="题型">
                  <el-select v-model="form.question_type" placeholder="选择题型" clearable style="width: 100%">
                    <el-option label="填空题" value="fill_blank" />
                    <el-option label="选择题" value="choice" />
                    <el-option label="计算题" value="calculation" />
                    <el-option label="应用题" value="problem_solving" />
                    <el-option label="其他" value="other" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="难度">
                  <el-select v-model="form.difficulty" style="width: 100%">
                    <el-option label="基础" value="基础" />
                    <el-option label="中等" value="中等" />
                    <el-option label="挑战" value="挑战" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="考试年份">
                  <el-input v-model="form.exam_year" placeholder="2025" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="20">
              <el-col :span="8">
                <el-form-item label="来源学校">
                  <el-input v-model="form.source_school" placeholder="可选" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="来源考试">
                  <el-input v-model="form.source_exam" placeholder="可选" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="题号">
                  <el-input v-model="form.source_number" placeholder="可选" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-form-item label="题目编号" prop="q_id">
              <el-input v-model="form.q_id" placeholder="留空自动生成" />
            </el-form-item>
            <el-form-item label="题目内容" prop="question_text">
              <el-input v-model="form.question_text" type="textarea" :rows="5" placeholder="请输入题目内容，支持 LaTeX 公式" />
              <div v-if="form.question_text" style="margin-top:4px;padding:8px 12px;background:#f5f7fa;border:1px solid #e4e7ed;border-radius:4px;white-space:pre-wrap;font-size:13px;line-height:1.7" v-html="renderMath(form.question_text)"></div>
            </el-form-item>
            <el-form-item label="答案" prop="answer">
              <el-input v-model="form.answer" type="textarea" :rows="2" placeholder="正确答案" />
              <div v-if="form.answer" style="margin-top:4px;padding:8px 12px;background:#f5f7fa;border:1px solid #e4e7ed;border-radius:4px;white-space:pre-wrap;font-size:13px;line-height:1.7" v-html="renderMath(form.answer)"></div>
            </el-form-item>
            <el-form-item label="解析">
              <el-input v-model="form.solution" type="textarea" :rows="3" placeholder="解题思路（可选）" />
              <div v-if="form.solution" style="margin-top:4px;padding:8px 12px;background:#f5f7fa;border:1px solid #e4e7ed;border-radius:4px;white-space:pre-wrap;font-size:13px;line-height:1.7" v-html="renderMath(form.solution)"></div>
            </el-form-item>
            <el-form-item label="标记">
              <el-checkbox v-model="form.is_key_point">重点题</el-checkbox>
              <el-checkbox v-model="form.is_difficult" style="margin-left: 16px">难题</el-checkbox>
              <el-checkbox v-model="form.is_high_freq" style="margin-left: 16px">高频题</el-checkbox>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="handleSubmit" :loading="submitting">保存题目</el-button>
              <el-button @click="resetForm">重置</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="批量导入" name="batch">
        <el-card shadow="hover">
          <template #header><span style="font-weight: bold">批量导入题目</span></template>

          <el-alert title="支持 JSON 格式批量导入" type="info" show-icon :closable="false" style="margin-bottom: 16px">
            <template #default>
              <p>JSON 格式：<code>{ "questions": [{ "question_text": "...", "knowledge_point": "...", ... }] }</code></p>
              <p>必填字段：<code>question_text</code>、<code>knowledge_point</code></p>
            </template>
          </el-alert>

          <el-upload
            ref="batchUploadRef"
            accept=".json"
            :auto-upload="false"
            :on-change="handleFileChange"
            :limit="1"
          >
            <el-button type="primary">选择 JSON 文件</el-button>
            <template #tip><div style="color:#999;font-size:12px;margin-top:4px">选择包含题目数组的 JSON 文件</div></template>
          </el-upload>

          <div v-if="previewQuestions.length" style="margin-top: 20px">
            <h4>预览（共 {{ previewQuestions.length }} 题）</h4>
            <el-table :data="previewQuestions" stripe border max-height="400" style="margin-top: 8px">
              <el-table-column label="#" type="index" width="50" />
              <el-table-column label="知识点" prop="knowledge_point" width="150" />
              <el-table-column label="难度" prop="difficulty" width="60" />
              <el-table-column label="题目" min-width="300">
                <template #default="{ row }">{{ row.question_text?.slice(0, 80) }}{{ row.question_text?.length > 80 ? '...' : '' }}</template>
              </el-table-column>
            </el-table>
            <div style="margin-top: 16px">
              <el-checkbox v-model="autoGenerateId">自动生成编号（忽略已有编号）</el-checkbox>
            </div>
            <el-button type="success" style="margin-top: 12px" @click="handleBatchImport" :loading="batchLoading">确认导入 {{ previewQuestions.length }} 题</el-button>
          </div>
        </el-card>

        <el-card v-if="batchResult" shadow="hover" style="margin-top: 16px">
          <template #header><span style="font-weight: bold">导入结果</span></template>
          <el-alert
            :title="`成功 ${batchResult.success_count} 题，失败 ${batchResult.error_count} 题`"
            :type="batchResult.error_count === 0 ? 'success' : 'warning'"
            show-icon
          />
          <el-table v-if="batchResult.errors?.length" :data="batchResult.errors" stripe style="margin-top: 12px">
            <el-table-column label="序号" prop="index" width="60" />
            <el-table-column label="编号" prop="q_id" width="150" />
            <el-table-column label="错误原因" prop="error" />
          </el-table>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="PDF识别" name="upload">
        <el-card shadow="hover">
          <template #header><span style="font-weight: bold">上传PDF自动识别题目</span></template>

          <el-alert title="通过 AI 自动识别PDF中的题目" type="info" show-icon :closable="false" style="margin-bottom: 16px">
            <template #default>
              <p>支持：PDF 格式的试卷（电子版或扫描件）</p>
              <p>AI 会自动提取文本并识别题目、答案和解析</p>
              <p>如果题目包含图形，可以在识别后为每道题单独上传配图</p>
            </template>
          </el-alert>

          <el-upload
            ref="uploadRef"
            accept=".pdf"
            :auto-upload="false"
            :on-change="handleFileUpload"
            :limit="1"
            drag
          >
            <el-icon size="48"><UploadFilled /></el-icon>
            <div style="margin-top: 8px">点击或拖拽PDF文件到此处</div>
            <template #tip><div style="color:#999;font-size:12px;margin-top:4px">支持 PDF 文件，不超过 50MB（最多 30 页）</div></template>
          </el-upload>

          <div v-if="uploadLoading" style="margin-top: 20px">
            <PdfRecognitionProgress
              :current-page="uploadProgress.current"
              :total-pages="uploadProgress.total"
              :questions-found="0"
              :message="uploadProgress.message || '正在处理中...'"
              title="正在识别 PDF"
              subtitle="请稍候，这可能需要 30-60 秒"
            />
          </div>

          <div v-if="recognizedQuestions.length && !uploadLoading" style="margin-top: 20px">
            <h4>识别结果（共 {{ recognizedQuestions.length }} 题）</h4>
            <p style="color: #999; font-size: 12px; margin-bottom: 12px">请检查并修改识别结果，确认后点击下方按钮导入</p>

            <el-alert v-if="imageWarning" :title="imageWarning" type="warning" show-icon :closable="false" style="margin-bottom: 16px" />

            <div v-for="(q, i) in recognizedQuestions" :key="i" style="margin-bottom: 20px; padding: 16px; background: #fafafa; border-radius: 8px; border: 1px solid #eee">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px">
                <div style="display: flex; align-items: center; gap: 8px">
                  <strong>第 {{ i + 1 }} 题</strong>
                  <el-tag v-if="q.is_complete === false" type="warning" size="small" effect="dark">题目可能不完整</el-tag>
                  <el-tag v-if="q.has_image" type="info" size="small">包含图形</el-tag>
                </div>
                <el-button type="danger" link size="small" @click="removeRecognized(i)">删除</el-button>
              </div>
              <el-row :gutter="12">
                <el-col :span="8">
                  <el-form-item label="知识点">
                    <el-input v-model="q.knowledge_point" size="small" />
                  </el-form-item>
                </el-col>
                <el-col :span="6">
                  <el-form-item label="分类">
                    <el-select v-model="q.knowledge_category" size="small" style="width: 100%">
                      <el-option v-for="c in categories" :key="c" :label="c" :value="c" />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :span="5">
                  <el-form-item label="题型">
                    <el-select v-model="q.question_type" size="small" style="width: 100%">
                      <el-option label="填空题" value="fill_blank" />
                      <el-option label="选择题" value="choice" />
                      <el-option label="计算题" value="calculation" />
                      <el-option label="应用题" value="problem_solving" />
                      <el-option label="其他" value="other" />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :span="5">
                  <el-form-item label="难度">
                    <el-select v-model="q.difficulty" size="small" style="width: 100%">
                      <el-option label="基础" value="基础" />
                      <el-option label="中等" value="中等" />
                      <el-option label="挑战" value="挑战" />
                    </el-select>
                  </el-form-item>
                </el-col>
              </el-row>
              <el-form-item label="题目">
                <el-input v-model="q.question_text" type="textarea" :rows="3" />
                <div v-if="q.question_text" style="margin-top:4px;padding:6px 10px;background:#fff;border:1px dashed #d9d9d9;border-radius:4px;white-space:pre-wrap;font-size:13px;line-height:1.7" v-html="renderMath(q.question_text)"></div>
              </el-form-item>

              <!-- 题目配图上传 -->
              <el-form-item v-if="q.has_image || q.question_image" label="题目配图">
                <div style="display: flex; align-items: center; gap: 12px">
                  <el-upload
                    :ref="el => questionImageUploadRefs[i] = el"
                    accept="image/*"
                    :auto-upload="false"
                    :show-file-list="false"
                    :on-change="(file) => handleQuestionImageUpload(file, i)"
                  >
                    <el-button size="small" type="primary" plain>
                      <el-icon style="margin-right: 4px"><Upload /></el-icon>
                      {{ q.question_image ? '更换配图' : '上传配图' }}
                    </el-button>
                  </el-upload>
                  <span v-if="q.question_image" style="color: #67c23a; font-size: 12px">
                    <el-icon><Check /></el-icon> 已上传
                  </span>
                  <el-button v-if="q.question_image" size="small" type="danger" link @click="removeQuestionImage(i)">删除配图</el-button>
                </div>
                <div v-if="q.question_image" style="margin-top: 8px">
                  <el-image
                    :src="q.question_image_preview"
                    fit="contain"
                    style="max-width: 300px; max-height: 200px; border: 1px solid #ddd; border-radius: 4px"
                    :preview-src-list="[q.question_image_preview]"
                  />
                </div>
                <div v-if="q.has_image && !q.question_image" style="margin-top: 4px; color: #e6a23c; font-size: 12px">
                  <el-icon><Warning /></el-icon> 题目包含"如图"等字样，建议上传配图
                </div>
              </el-form-item>

              <el-form-item label="答案">
                <el-input v-model="q.answer" type="textarea" :rows="2" placeholder="正确答案" />
                <div v-if="q.answer" style="margin-top:4px;padding:6px 10px;background:#fff;border:1px dashed #d9d9d9;border-radius:4px;white-space:pre-wrap;font-size:13px;line-height:1.7" v-html="renderMath(q.answer)"></div>
              </el-form-item>
              <el-form-item label="解析">
                <el-input v-model="q.solution" type="textarea" :rows="2" placeholder="解析（可选）" />
                <div v-if="q.solution" style="margin-top:4px;padding:6px 10px;background:#fff;border:1px dashed #d9d9d9;border-radius:4px;white-space:pre-wrap;font-size:13px;line-height:1.7" v-html="renderMath(q.solution)"></div>
              </el-form-item>
            </div>

            <el-button type="success" @click="handleImportRecognized" :loading="importLoading">确认导入 {{ recognizedQuestions.length }} 题</el-button>
            <el-button @click="clearResults">重新识别</el-button>
          </div>

          <div v-if="uploadPageErrors.length && !uploadLoading" style="margin-top: 16px">
            <el-alert title="部分页面识别异常" type="warning" show-icon :closable="false">
              <template #default>
                <p v-for="e in uploadPageErrors" :key="e.page">第 {{ e.page }} 页：{{ e.error }}</p>
              </template>
            </el-alert>
          </div>
        </el-card>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { createQuestion, batchImport, listKnowledgePoints, listCategories, recognizePdf, uploadQuestionImage } from '../api/question'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UploadFilled, Loading, Upload, Check, Warning } from '@element-plus/icons-vue'
import { renderMath } from '../utils/math'
import PdfRecognitionProgress from '../components/PdfRecognitionProgress.vue'

const activeTab = ref('single')
const formRef = ref(null)
const submitting = ref(false)

// 分类 & 知识点
const categories = ref([])
const allKps = ref({})
const filteredKps = computed(() => {
  if (!form.knowledge_category) return []
  return allKps.value[form.knowledge_category] || []
})

async function loadMeta() {
  try {
    const [catRes, kpRes] = await Promise.all([listCategories(), listKnowledgePoints()])
    categories.value = catRes.categories || []
    // 加载所有知识点
    const kps = kpRes.knowledge_points || {}
    allKps.value = kps
  } catch (e) { /* ignore */ }
}

function onCategoryChange() {
  form.knowledge_point = ''
}

// 表单
const form = reactive({
  q_id: '',
  knowledge_point: '',
  knowledge_category: '',
  question_type: '',
  difficulty: '中等',
  question_text: '',
  answer: '',
  solution: '',
  source_school: '',
  source_exam: '',
  source_number: '',
  exam_year: '2025',
  is_key_point: false,
  is_difficult: false,
  is_high_freq: false,
})

const rules = {
  knowledge_point: [{ required: true, message: '请选择知识点', trigger: 'change' }],
  question_text: [{ required: true, message: '请输入题目内容', trigger: 'blur' }],
  answer: [{ required: true, message: '请输入答案', trigger: 'blur' }],
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    const res = await createQuestion(form)
    ElMessage.success(`题目已保存！编号：${res.q_id}`)
    resetForm()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  } finally {
    submitting.value = false
  }
}

function resetForm() {
  form.q_id = ''
  form.knowledge_point = ''
  form.knowledge_category = ''
  form.question_type = ''
  form.difficulty = '中等'
  form.question_text = ''
  form.answer = ''
  form.solution = ''
  form.source_school = ''
  form.source_exam = ''
  form.source_number = ''
  form.exam_year = '2025'
  form.is_key_point = false
  form.is_difficult = false
  form.is_high_freq = false
  formRef.value?.clearValidate()
}

// 批量导入
const batchUploadRef = ref(null)
const previewQuestions = ref([])
const autoGenerateId = ref(true)
const batchLoading = ref(false)
const batchResult = ref(null)

function handleFileChange(file) {
  const reader = new FileReader()
  reader.onload = (e) => {
    try {
      const data = JSON.parse(e.target.result)
      const questions = data.questions || (Array.isArray(data) ? data : [data])
      if (!questions.length) {
        ElMessage.warning('文件中未找到题目数据')
        return
      }
      previewQuestions.value = questions
      ElMessage.success(`已解析 ${questions.length} 道题目`)
    } catch (err) {
      ElMessage.error('JSON 解析失败，请检查文件格式')
    }
  }
  reader.readAsText(file.raw)
}

async function handleBatchImport() {
  if (!previewQuestions.value.length) {
    ElMessage.warning('请先选择文件')
    return
  }

  try {
    await ElMessageBox.confirm(`确认导入 ${previewQuestions.value.length} 道题目？`, '确认')
  } catch { return }

  batchLoading.value = true
  try {
    const res = await batchImport({
      questions: previewQuestions.value,
      auto_generate_id: autoGenerateId.value,
    })
    batchResult.value = res
    if (res.success_count > 0) {
      ElMessage.success(`成功导入 ${res.success_count} 道题目`)
      previewQuestions.value = []
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '批量导入失败')
  } finally {
    batchLoading.value = false
  }
}

// ===== 文件上传识别 =====
const uploadRef = ref(null)
const uploadLoading = ref(false)
const recognizedQuestions = ref([])
const importLoading = ref(false)
const uploadProgress = ref({ current: 0, total: 0, percent: 0 })
const uploadPageErrors = ref([])
const imageWarning = ref('')
const questionImageUploadRefs = ref([])

function handleFileUpload(file) {
  const isPdf = file.raw.type === 'application/pdf' || file.raw.name?.toLowerCase().endsWith('.pdf')

  if (!isPdf) {
    ElMessage.warning('请上传PDF文件')
    return false
  }

  uploadLoading.value = true
  recognizedQuestions.value = []
  uploadPageErrors.value = []
  uploadProgress.value = { current: 0, total: 0, percent: 0, message: '正在上传文件...' }
  imageWarning.value = ''

  const formData = new FormData()
  formData.append('file', file.raw)

  // 模拟进度更新（因为这是同步API，没有实时进度）
  const progressInterval = setInterval(() => {
    if (uploadProgress.value.total === 0) {
      uploadProgress.value.message = '正在解析 PDF 文件...'
    } else if (uploadProgress.value.current < uploadProgress.value.total) {
      uploadProgress.value.current++
      uploadProgress.value.message = `正在识别第 ${uploadProgress.value.current} 页...`
    }
  }, 500)

  recognizePdf(formData)
    .then(res => {
      clearInterval(progressInterval)
      recognizedQuestions.value = (res.questions || []).map(q => ({
        ...q,
        knowledge_category: q.knowledge_category || '',
        question_image: null,  // 配图文件
        question_image_preview: null,  // 配图预览URL
      }))
      if (res.image_info?.warning) {
        imageWarning.value = res.image_info.warning
      }
      uploadProgress.value = {
        current: res.total_pages || 0,
        total: res.total_pages || 0,
        percent: 100,
        message: '识别完成！'
      }
      if (res.page_results) {
        uploadPageErrors.value = res.page_results
          .filter(p => p.status !== 'ok')
          .map(p => ({ page: p.page, error: p.error || '识别失败' }))
      }
      ElMessage.success(res.message || '识别完成')
    })
    .catch(e => {
      clearInterval(progressInterval)
      const status = e.response?.status
      const detail = e.response?.data?.detail
      let msg = detail || '识别失败'
      if (status === 502) {
        msg = `AI 服务调用失败: ${detail || 'API 可能超时'}`
      } else if (!e.response) {
        msg = `网络错误: ${e.message}，请检查连接`
      }
      console.error('Upload Error:', { status, detail, message: e.message })
      ElMessage.error(msg)
    })
    .finally(() => {
      clearInterval(progressInterval)
      uploadLoading.value = false
    })

  return false
}

function handleQuestionImageUpload(file, index) {
  const q = recognizedQuestions.value[index]
  if (!q) return

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
  q.question_image = file.raw
  q.question_image_preview = URL.createObjectURL(file.raw)

  ElMessage.success('配图已添加')
}

function removeQuestionImage(index) {
  const q = recognizedQuestions.value[index]
  if (!q) return

  // 释放预览URL
  if (q.question_image_preview) {
    URL.revokeObjectURL(q.question_image_preview)
  }

  q.question_image = null
  q.question_image_preview = null

  ElMessage.info('配图已删除')
}

function removeRecognized(index) {
  const q = recognizedQuestions.value[index]

  // 释放预览URL
  if (q?.question_image_preview) {
    URL.revokeObjectURL(q.question_image_preview)
  }

  recognizedQuestions.value.splice(index, 1)
}

function clearResults() {
  // 释放所有预览URL
  recognizedQuestions.value.forEach(q => {
    if (q.question_image_preview) {
      URL.revokeObjectURL(q.question_image_preview)
    }
  })

  recognizedQuestions.value = []
  uploadPageErrors.value = []
  uploadProgress.value = { current: 0, total: 0, percent: 0 }
  imageWarning.value = ''
  uploadRef.value?.clearFiles()
}

async function handleImportRecognized() {
  if (!recognizedQuestions.value.length) {
    ElMessage.warning('没有可导入的题目')
    return
  }

  try {
    await ElMessageBox.confirm(`确认导入 ${recognizedQuestions.value.length} 道识别后的题目？`, '确认')
  } catch { return }

  importLoading.value = true
  try {
    // 准备题目数据，处理配图
    const questionsToImport = []

    for (const q of recognizedQuestions.value) {
      const questionData = {
        question_text: q.question_text,
        answer: q.answer,
        solution: q.solution,
        knowledge_point: q.knowledge_point,
        knowledge_category: q.knowledge_category,
        question_type: q.question_type,
        difficulty: q.difficulty,
      }

      // 如果有配图，需要先上传图片
      if (q.question_image) {
        try {
          const formData = new FormData()
          formData.append('file', q.question_image)

          // 上传图片并获取URL
          const uploadRes = await uploadQuestionImage(formData)
          questionData.image_path = uploadRes.url
          questionData.has_image = true
        } catch (e) {
          console.error('Failed to upload image:', e)
          ElMessage.warning(`题目"${q.question_text.slice(0, 20)}..."的配图上传失败，将跳过配图`)
        }
      }

      questionsToImport.push(questionData)
    }

    const res = await batchImport({
      questions: questionsToImport,
      auto_generate_id: true,
    })
    if (res.success_count > 0) {
      ElMessage.success(`成功导入 ${res.success_count} 道题目`)
      clearResults()
    }
    if (res.errors?.length) {
      ElMessage.warning(`${res.errors.length} 道题导入失败（可能重复）`)
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '批量导入失败')
  } finally {
    importLoading.value = false
  }
}

onMounted(loadMeta)
</script>
