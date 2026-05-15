<template>
  <div>
    <el-card shadow="hover">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span style="font-weight: bold">题库浏览</span>
          <div style="display: flex; gap: 8px">
            <el-select v-model="sortBy" placeholder="排序" size="small" style="width: 100px" @change="loadQuestions">
              <el-option label="默认ID" value="question_id" />
              <el-option label="题号" value="q_id" />
            </el-select>
            <el-select v-model="sortOrder" placeholder="顺序" size="small" style="width: 80px" @change="loadQuestions">
              <el-option label="升序" value="asc" />
              <el-option label="降序" value="desc" />
            </el-select>
            <el-select v-model="filters.grade" placeholder="年级" clearable size="small" style="width: 110px">
              <el-option v-for="g in grades" :key="g" :label="g" :value="g" />
            </el-select>
            <el-select v-model="filters.category" placeholder="分类" clearable size="small" style="width: 110px">
              <el-option v-for="c in categories" :key="c" :label="c" :value="c" />
            </el-select>
            <el-select v-model="filters.difficulty" placeholder="难度" clearable size="small" style="width: 100px">
              <el-option label="基础" value="基础" />
              <el-option label="中等" value="中等" />
              <el-option label="挑战" value="挑战" />
            </el-select>
            <el-input v-model="filters.keyword" placeholder="搜索题目" clearable size="small" style="width: 180px" @keyup.enter="loadQuestions" />
            <el-button type="primary" size="small" @click="loadQuestions">搜索</el-button>
            <el-button type="danger" size="small" :disabled="!selectedIds.length" @click="handleBatchDelete">批量删除</el-button>
          </div>
        </div>
      </template>

      <el-table ref="questionsTableRef" :data="questions" row-key="question_id" stripe v-loading="loading" style="width: 100%" @selection-change="onSelectionChange" @select="onRowSelect" @select-all="onSelectAll">
        <el-table-column type="selection" width="40" reserve-selection />
        <el-table-column label="ID" width="80">
          <template #default="{ row }">
            <span style="color: #999; font-size: 12px">{{ row.question_id }}</span>
          </template>
        </el-table-column>
        <el-table-column label="题号" width="180">
          <template #default="{ row }">
            <span style="font-weight: 500; font-size: 13px">{{ row.q_id }}</span>
            <el-icon v-if="row.has_image" style="margin-left: 4px; color: #409eff; vertical-align: middle"><Picture /></el-icon>
          </template>
        </el-table-column>
        <el-table-column prop="knowledge_point" label="知识点" width="120" />
        <el-table-column prop="difficulty" label="难度" width="70">
          <template #default="{ row }">
            <el-tag :type="row.difficulty === '基础' ? 'success' : row.difficulty === '中等' ? 'warning' : 'danger'" size="small">{{ row.difficulty }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="question_type" label="题型" width="80" />
        <el-table-column label="题目" min-width="300">
          <template #default="{ row }">
            <div style="max-height: 60px; overflow: hidden; text-overflow: ellipsis" v-html="renderMath(row.question_text)"></div>
          </template>
        </el-table-column>
        <el-table-column label="年级" width="70" align="center">
          <template #default="{ row }">
            <span style="font-size: 12px">{{ row.grade_level || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="source_school" label="来源" width="140" />
        <el-table-column label="状态" width="65">
          <template #default="{ row }">
            <el-tag v-if="row.verification_status === 'verified'" type="success" size="small">已验</el-tag>
            <el-tag v-else type="info" size="small">待验</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="110" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="showDetail(row)">详情</el-button>
            <el-button type="danger" link size="small" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div style="display: flex; justify-content: center; margin-top: 20px">
        <el-pagination
          v-model:current-page="page"
          :page-size="pageSize"
          :total="total"
          layout="total, prev, pager, next"
          @current-change="loadQuestions"
        />
      </div>
    </el-card>

    <!-- 题目详情对话框 -->
    <el-dialog v-model="detailVisible" title="题目详情" width="700px">
      <div v-if="currentQuestion">
        <div style="margin-bottom: 16px">
          <el-tag size="small">#{{ currentQuestion.question_id }}</el-tag>
          <el-tag size="small" type="info" style="margin-left: 4px">{{ currentQuestion.q_id }}</el-tag>
          <el-tag size="small" type="success" style="margin-left: 8px">{{ currentQuestion.knowledge_point }}</el-tag>
          <el-tag size="small" :type="currentQuestion.difficulty === '基础' ? 'success' : currentQuestion.difficulty === '中等' ? 'warning' : 'danger'" style="margin-left: 4px">{{ currentQuestion.difficulty }}</el-tag>
          <el-tag v-if="currentQuestion.grade_level" size="small" type="primary" style="margin-left: 4px">{{ currentQuestion.grade_level }}</el-tag>
        </div>
        <div style="background: #f5f7fa; padding: 16px; border-radius: 6px; margin-bottom: 16px; white-space: pre-wrap" v-html="renderMath(currentQuestion.question_text)"></div>
        <div v-if="currentQuestion.has_image && currentQuestion.image_path" style="margin-bottom: 16px; text-align: center">
          <el-image :src="encodeURI(currentQuestion.image_path)" style="max-width: 500px" fit="contain" :preview-src-list="[encodeURI(currentQuestion.image_path)]" preview-teleported />
        </div>
        <el-divider />
        <div><strong>答案：</strong><span v-html="renderMath(currentQuestion.answer || '待补充')" /></div>
        <div style="margin-top: 8px"><strong>解析：</strong><span v-html="renderMath(currentQuestion.solution || '待补充')" /></div>
        <div style="margin-top: 8px"><strong>来源：</strong>{{ currentQuestion.source_school }} {{ currentQuestion.source_exam }} {{ currentQuestion.source_number }}</div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { listQuestions, listCategories, listGrades, deleteQuestion, batchDeleteQuestions } from '../api/question'
import { Picture } from '@element-plus/icons-vue'
import { renderMath } from '../utils/math'
import { ElMessageBox, ElMessage } from 'element-plus'

const questions = ref([])
const categories = ref([])
const grades = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const detailVisible = ref(false)
const currentQuestion = ref(null)
const questionsTableRef = ref(null)
const selectedIdsSet = ref(new Set())
const sortBy = ref('question_id')
const sortOrder = ref('asc')

const selectedIds = computed(() => [...selectedIdsSet.value])

const filters = reactive({
  grade: '',
  category: '',
  difficulty: '',
  keyword: '',
})

async function loadQuestions() {
  loading.value = true
  try {
    const params = {
      page: page.value,
      page_size: pageSize.value,
      sort_by: sortBy.value,
      sort_order: sortOrder.value,
    }
    if (filters.grade) params.grade_level = filters.grade
    if (filters.category) params.knowledge_category = filters.category
    if (filters.difficulty) params.difficulty = filters.difficulty
    if (filters.keyword) params.keyword = filters.keyword

    const res = await listQuestions(params)
    questions.value = res.questions
    total.value = res.total
  } finally {
    loading.value = false
  }
}

function showDetail(row) {
  currentQuestion.value = row
  detailVisible.value = true
}

function onRowSelect(selection, row) {
  // 单行选择/取消时更新持久化集合
  const set = selectedIdsSet.value
  if (selection.some(r => r.question_id === row.question_id)) {
    set.add(row.question_id)
  } else {
    set.delete(row.question_id)
  }
  // 触发 computed 更新
  selectedIdsSet.value = new Set(set)
}

function onSelectAll(selection) {
  // 全选/取消全选时更新当前页所有行
  const set = selectedIdsSet.value
  const currentIds = new Set(questions.value.map(q => q.question_id))
  if (selection.length > 0) {
    // 全选了当前页 — 添加所有当前页ID
    currentIds.forEach(id => set.add(id))
  } else {
    // 取消了全选 — 移除所有当前页ID
    currentIds.forEach(id => set.delete(id))
  }
  selectedIdsSet.value = new Set(set)
}

function onSelectionChange(selection) {
  // 仅用于更新 UI 状态（如禁用按钮），跨页选择由 @select/@select-all 维护
  // 但翻页时 selection 只含当前页，所以用 selectedIdsSet 判断禁用状态
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(`确定删除题目「${row.q_id}」吗？`, '确认删除', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await deleteQuestion(row.question_id)
    ElMessage.success('删除成功')
    await loadQuestions()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败: ' + (e.message || e))
    }
  }
}

async function handleBatchDelete() {
  const ids = [...selectedIdsSet.value]
  if (!ids.length) return
  try {
    await ElMessageBox.confirm(
      `确定删除选中的 ${ids.length} 道题目吗？此操作不可撤销。`,
      '批量删除',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
    await batchDeleteQuestions({ question_ids: ids })
    ElMessage.success('批量删除成功')
    selectedIdsSet.value = new Set()
    questionsTableRef.value?.clearSelection()
    await loadQuestions()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('批量删除失败: ' + (e.message || e))
    }
  }
}

onMounted(async () => {
  try {
    const [catRes, gradeRes] = await Promise.all([
      listCategories(),
      listGrades(),
    ])
    categories.value = catRes.categories
    grades.value = gradeRes.grades || []
  } catch (e) { /* ignore */ }
  await loadQuestions()
})
</script>
