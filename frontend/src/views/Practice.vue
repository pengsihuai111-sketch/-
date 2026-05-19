<template>
  <div>
    <!-- 列表模式 -->
    <template v-if="!currentMode">
      <el-row :gutter="20">
        <el-col :span="8">
          <!-- 本周练习单 -->
          <el-card shadow="hover" style="margin-bottom:16px">
            <template #header>
              <div style="display:flex;justify-content:space-between;align-items:center">
                <span style="font-weight: bold">📅 本周练习单（周一到周四）</span>
                <el-button v-if="weekData && !weekLoading" type="primary" size="small" @click="downloadAllWeekPdf">批量下载</el-button>
              </div>
            </template>
            <div v-if="weekLoading" style="text-align:center;padding:20px">
              <el-icon class="is-loading" :size="24"><Loading /></el-icon>
              <div style="margin-top:8px;color:#999;font-size:13px">正在生成本周4天练习单...</div>
            </div>
            <div v-else-if="weekData" style="max-height:400px;overflow-y:auto">
              <div v-for="ds in weekData.sheets" :key="ds.day_label" style="margin-bottom:10px;padding:10px 12px;background:#f9f9f9;border-radius:8px;border:1px solid #eee">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
                  <span style="font-weight:bold;font-size:14px">{{ ds.day_label }}</span>
                  <el-button type="primary" link size="small" @click="downloadDayPdf(ds)">下载</el-button>
                </div>
                <div style="font-size:12px;color:#666;margin-bottom:4px">
                  {{ ds.sheet.total_questions }} 题 · 约 {{ ds.sheet.estimated_time }} 分钟
                </div>
                <div style="display:flex;flex-wrap:wrap;gap:3px">
                  <el-tag
                    v-for="kp in getDayKps(ds.sheet)" :key="kp"
                    size="small"
                    type="info"
                    style="font-size:10px"
                  >{{ kp }}</el-tag>
                </div>
              </div>
              <div style="text-align:center;margin-top:8px">
                <el-tag size="small" type="success">
                  共 {{ weekData.total_questions }} 题 · 约 {{ weekData.total_time }} 分钟
                </el-tag>
              </div>
            </div>
            <div v-else style="text-align:center;padding:10px 0">
              <el-button type="success" @click="handleGenerateWeek" :loading="weekLoading">生成本周练习单</el-button>
              <div style="margin-top:8px;color:#999;font-size:12px">基于掌握度和遗忘曲线生成4天练习</div>
            </div>
          </el-card>

          <el-card shadow="hover">
            <template #header>
              <div style="display:flex;justify-content:space-between;align-items:center">
                <span style="font-weight: bold">生成练习单</span>
                <el-button type="primary" size="small" plain @click="aiDialogVisible = true">AI 智能生成</el-button>
              </div>
            </template>
            <el-form label-width="90px">
              <el-form-item label="练习单名称">
                <el-input v-model="form.sheet_name" placeholder="留空自动生成" />
              </el-form-item>
              <el-form-item label="练习类型">
                <el-select v-model="form.sheet_type" style="width: 100%">
                  <el-option label="每日训练" value="daily" />
                  <el-option label="错题重练" value="wrong_redo" />
                </el-select>
              </el-form-item>
              <el-form-item label="难度筛选">
                <el-checkbox-group v-model="form.difficulties">
                  <el-checkbox label="基础" />
                  <el-checkbox label="中等" />
                  <el-checkbox label="挑战" />
                </el-checkbox-group>
              </el-form-item>

              <el-divider border-style="dashed" />

              <div style="margin-bottom: 12px;font-weight:bold;font-size:14px;color:#606266">按知识类别选题</div>

              <div style="max-height: 360px; overflow-y: auto; padding-right: 4px">
                <div v-for="(kps, cat) in groupedKps" :key="cat" style="margin-bottom:10px;padding:8px 10px;background:#f9f9f9;border-radius:6px;border:1px solid #eee">
                  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
                    <span style="font-weight:bold;font-size:13px">{{ cat }}</span>
                    <el-input-number v-model="categoryCounts[cat]" :min="0" :max="10" size="small" controls-position="right" style="width:100px" />
                  </div>
                  <div style="display:flex;flex-wrap:wrap;gap:3px;margin-top:4px">
                    <el-tag
                      v-for="kp in kps" :key="kp"
                      size="small"
                      :type="(selectedCategoryKps[cat] || []).includes(kp) ? 'primary' : 'info'"
                      style="cursor:pointer"
                      @click="toggleCategoryKp(cat, kp)"
                    >{{ kp }}</el-tag>
                  </div>
                </div>
              </div>

              <div style="text-align:center;margin:12px 0">
                <el-tag :type="totalSelectedQuestions > 0 ? 'primary' : 'info'" size="medium">
                  {{ totalSelectedQuestions > 0 ? `共 ${totalSelectedQuestions} 题，预计 ${Math.max(20, Math.round(totalSelectedQuestions * 3.5))} 分钟` : '请设置各类别题数' }}
                </el-tag>
              </div>

              <el-form-item>
                <el-button type="primary" style="width: 100%" :disabled="totalSelectedQuestions === 0" @click="handleGenerate" :loading="genLoading">生成练习单</el-button>
              </el-form-item>
              <template v-if="form.sheet_type === 'wrong_redo'">
                <el-divider border-style="dashed" />

                <!-- 按时间段生成多卷错题练习 -->
                <div style="margin-bottom: 12px;font-weight:bold;font-size:14px;color:#E67E22">按时间段生成错题卷</div>

                <div style="margin-bottom: 12px;padding:10px 12px;background:#f9f9f9;border-radius:6px;border:1px solid #eee">
                  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
                    <span style="font-weight:bold;font-size:13px">时间范围</span>
                    <div style="display:flex;gap:4px">
                      <el-button :type="periodPreset === 3 ? 'primary' : 'default'" size="small" @click="setPeriodPreset(3)">近3天</el-button>
                      <el-button :type="periodPreset === 7 ? 'primary' : 'default'" size="small" @click="setPeriodPreset(7)">近7天</el-button>
                      <el-button :type="periodPreset === 30 ? 'primary' : 'default'" size="small" @click="setPeriodPreset(30)">近30天</el-button>
                      <el-button :type="periodPreset === 0 ? 'primary' : 'default'" size="small" @click="setPeriodPreset(0)">全部</el-button>
                    </div>
                  </div>
                  <div style="display:flex;gap:8px;align-items:center;margin-bottom:8px">
                    <el-date-picker v-model="periodStartDate" type="date" placeholder="开始日期" size="small" value-format="YYYY-MM-DD" style="width:140px" />
                    <span>至</span>
                    <el-date-picker v-model="periodEndDate" type="date" placeholder="结束日期" size="small" value-format="YYYY-MM-DD" style="width:140px" />
                  </div>
                  <div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap">
                    <div style="display:flex;align-items:center;gap:6px">
                      <span style="font-size:13px;color:#606266">生成份数：</span>
                      <el-input-number v-model="periodSheetCount" :min="1" :max="10" size="small" controls-position="right" style="width:100px" />
                    </div>
                    <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap">
                      <span style="font-size:13px;color:#606266">每卷各题型数量：</span>
                      <div style="display:flex;gap:8px;align-items:center">
                        <div><span style="font-size:12px">计算</span><el-input-number v-model="periodTypeCounts.calculation" :min="0" :max="20" size="small" controls-position="right" style="width:90px" /></div>
                        <div><span style="font-size:12px">填空</span><el-input-number v-model="periodTypeCounts.fill_blank" :min="0" :max="20" size="small" controls-position="right" style="width:90px" /></div>
                        <div><span style="font-size:12px">选择</span><el-input-number v-model="periodTypeCounts.choice" :min="0" :max="20" size="small" controls-position="right" style="width:90px" /></div>
                        <div><span style="font-size:12px">应用</span><el-input-number v-model="periodTypeCounts.problem_solving" :min="0" :max="20" size="small" controls-position="right" style="width:90px" /></div>
                      </div>
                      <span v-if="periodTypeTotal > 0 && periodSheetCount > 0" style="font-size:12px;color:#909399">每卷 {{ periodTypeTotal }} 题，共 {{ periodSheetCount * periodTypeTotal }} 题</span>
                    </div>
                    <div style="display:flex;align-items:center;gap:6px">
                      <span style="font-size:13px;color:#606266">题型筛选：</span>
                      <el-checkbox-group v-model="periodQuestionTypes" size="small">
                        <el-checkbox label="calculation">计算</el-checkbox>
                        <el-checkbox label="fill_blank">填空</el-checkbox>
                        <el-checkbox label="choice">选择</el-checkbox>
                        <el-checkbox label="problem_solving">应用</el-checkbox>
                      </el-checkbox-group>
                    </div>
                    <div style="display:flex;align-items:center;gap:6px">
                      <span style="font-size:13px;color:#606266">难度：</span>
                      <el-checkbox-group v-model="periodDifficulties" size="small">
                        <el-checkbox label="基础" />
                        <el-checkbox label="中等" />
                        <el-checkbox label="挑战" />
                      </el-checkbox-group>
                    </div>
                  </div>
                  <div style="margin-top:10px">
                    <el-button type="warning" size="small" @click="handleGenerateWrongPeriod" :loading="periodLoading">生成错题卷（共 {{ periodSheetCount }} 份）</el-button>
                    <span v-if="periodLastResult" style="margin-left:12px;font-size:12px;color:#909399">
                      上次：{{ periodLastResult.total_count }} 题，生成 {{ periodLastResult.sheet_count }} 卷
                    </span>
                  </div>
                </div>

                <el-divider border-style="dashed" />

                <div style="margin-bottom: 12px;font-weight:bold;font-size:14px;color:#10B981">智慧推荐错题重练</div>

                <!-- 时间段筛选 -->
                <div style="margin-bottom: 12px;padding:10px 12px;background:#f9f9f9;border-radius:6px;border:1px solid #eee">
                  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
                    <span style="font-weight:bold;font-size:13px">错题时间范围</span>
                    <div style="display:flex;gap:4px">
                      <el-button :type="smartRedoPeriod === 7 ? 'primary' : 'default'" size="small" @click="setSmartRedoPeriod(7)">近7天</el-button>
                      <el-button :type="smartRedoPeriod === 30 ? 'primary' : 'default'" size="small" @click="setSmartRedoPeriod(30)">近30天</el-button>
                      <el-button :type="smartRedoPeriod === 0 ? 'primary' : 'default'" size="small" @click="setSmartRedoPeriod(0)">全部</el-button>
                    </div>
                  </div>
                  <div style="display:flex;gap:8px;align-items:center">
                    <el-date-picker v-model="smartRedoStartDate" type="date" placeholder="开始日期" size="small" value-format="YYYY-MM-DD" style="width:140px" />
                    <span>至</span>
                    <el-date-picker v-model="smartRedoEndDate" type="date" placeholder="结束日期" size="small" value-format="YYYY-MM-DD" style="width:140px" />
                  </div>
                </div>

                <!-- 数量配置 -->
                <div style="margin-bottom: 12px;padding:10px 12px;background:#f9f9f9;border-radius:6px;border:1px solid #eee">
                  <div style="font-weight:bold;font-size:13px;margin-bottom:8px">题目数量配置</div>
                  <el-row :gutter="12">
                    <el-col :span="8">
                      <el-form-item label="计算题">
                        <el-input-number v-model="smartRedoCalcCount" :min="0" :max="10" size="small" controls-position="right" style="width:100%" />
                      </el-form-item>
                    </el-col>
                    <el-col :span="8">
                      <el-form-item label="原错题">
                        <el-input-number v-model="smartRedoWrongCount" :min="0" :max="20" size="small" controls-position="right" style="width:100%" />
                      </el-form-item>
                    </el-col>
                    <el-col :span="8">
                      <el-form-item label="举一反三">
                        <el-input-number v-model="smartRedoSimilarCount" :min="0" :max="10" size="small" controls-position="right" style="width:100%" />
                      </el-form-item>
                    </el-col>
                  </el-row>
                </div>

                <!-- 题型筛选 -->
                <div style="margin-bottom: 12px;padding:10px 12px;background:#f9f9f9;border-radius:6px;border:1px solid #eee">
                  <div style="font-weight:bold;font-size:13px;margin-bottom:6px">题型筛选（留空表示不限）</div>
                  <el-checkbox-group v-model="smartRedoQuestionTypes">
                    <el-checkbox label="calculation">计算题</el-checkbox>
                    <el-checkbox label="fill_blank">填空题</el-checkbox>
                    <el-checkbox label="choice">选择题</el-checkbox>
                    <el-checkbox label="problem_solving">应用题</el-checkbox>
                  </el-checkbox-group>
                </div>

                <!-- 推荐策略 -->
                <div style="margin-bottom: 12px;padding:10px 12px;background:#f9f9f9;border-radius:6px;border:1px solid #eee">
                  <div style="font-weight:bold;font-size:13px;margin-bottom:6px">推荐策略</div>
                  <el-radio-group v-model="smartRedoStrategy" size="small">
                    <el-radio value="smart">智慧推荐</el-radio>
                    <el-radio value="latest">最新错题</el-radio>
                    <el-radio value="weak_knowledge">薄弱知识点</el-radio>
                    <el-radio value="forgetting_risk">遗忘风险</el-radio>
                  </el-radio-group>
                </div>

                <el-form-item>
                  <el-button type="warning" style="width: 100%" @click="handleGenerateSmartRedo" :loading="smartLoading">生成智慧错题重练</el-button>
                </el-form-item>
              </template>
            </el-form>
          </el-card>

          <!-- 生成后的操作 -->
          <el-card v-if="lastSheet" shadow="hover" style="margin-top: 16px">
            <template #header><span style="font-weight: bold">刚刚生成的练习单</span></template>
            <template v-if="periodLastResult">
              <p style="font-size:13px;color:#E67E22;margin-bottom:8px">
                错题卷：共 {{ periodLastResult.total_count }} 题，{{ periodLastResult.sheet_count }} 张卷子
                <span v-if="periodLastResult.supplement_count > 0" style="margin-left:8px;color:#909399">（其中 {{ periodLastResult.supplement_count }} 题从题库补充）</span>
              </p>
              <div v-for="(s, si) in periodLastResult.sheets" :key="s.sheet_id" style="display:flex;justify-content:space-between;align-items:center;padding:4px 0;border-bottom:1px solid #f5f5f5">
                <span style="font-size:13px">第 {{ si + 1 }} 卷：{{ s.total_questions }} 题 · 约 {{ s.estimated_time }} 分钟</span>
                <div style="display:flex;gap:4px">
                  <el-button type="primary" link size="small" @click="downloadOneSheet(s)">PDF</el-button>
                  <el-button size="small" link @click="openView(s)">预览</el-button>
                </div>
              </div>
            </template>
            <template v-else>
              <p><strong>{{ lastSheet.sheet_name }}</strong></p>
              <p>{{ lastSheet.total_questions }} 题，预计 {{ lastSheet.estimated_time }} 分钟</p>
              <div style="margin-top: 12px; display: flex; gap: 8px">
                <el-button type="primary" size="small" @click="downloadCurrent">下载PDF(学生+答案)</el-button>
                <el-button size="small" @click="openView(lastSheet)">预览题目</el-button>
              </div>
            </template>
          </el-card>
        </el-col>
        <el-col :span="16">
          <el-card shadow="hover">
            <template #header>
              <div style="display:flex;justify-content:space-between;align-items:center">
                <span style="font-weight: bold">已有练习单</span>
                <el-button type="danger" size="small" :disabled="!selectedSheetIds.size" @click="handleBatchDeleteSheets">批量删除</el-button>
              </div>
            </template>
            <el-table ref="sheetsTableRef" :data="sheets" stripe style="width: 100%" row-key="sheet_id" @selection-change="onSheetSelectionChange">
              <el-table-column type="selection" width="40" reserve-selection />
              <el-table-column prop="sheet_name" label="名称" min-width="160" />
              <el-table-column label="类型" width="80">
                <template #default="{ row }">{{ {'daily':'每日','wrong_redo':'错题','special_topic':'专题','custom':'自定义'}[row.sheet_type] || row.sheet_type }}</template>
              </el-table-column>
              <el-table-column prop="total_questions" label="题数" width="50" />
              <el-table-column prop="estimated_time" label="用时" width="50"><template #default="{row}">{{row.estimated_time}}分</template></el-table-column>
              <el-table-column label="状态" width="70">
                <template #default="{ row }">
                  <template v-if="row.completed">
                    <el-tag v-if="row.score !== null && row.score !== undefined" :type="(row.score||0)>=60?'success':'danger'" size="small" effect="dark">{{ row.score }}分</el-tag>
                    <el-tag v-else type="success" size="small" effect="plain">已做</el-tag>
                  </template>
                  <el-tag v-else type="info" size="small" effect="plain">未做</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="200" fixed="right">
                <template #default="{ row }">
                  <el-button type="primary" link size="small" @click="downloadSheetAction(row)">PDF下载</el-button>
                  <el-button type="success" link size="small" @click="openView(row)">查看</el-button>
                  <el-button type="danger" link size="small" @click="handleDelete(row)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
            <el-empty v-if="!sheets.length" description="暂无练习单" />
          </el-card>
        </el-col>
      </el-row>

    </template>

    <!-- 查看模式（统一对错标记） -->
    <template v-if="currentMode === 'view'">
      <el-card shadow="hover">
        <template #header>
          <div style="display: flex; justify-content: space-between; align-items: center">
            <span style="font-weight: bold">📄 {{ viewData?.sheet_name }}</span>
            <div>
              <el-button type="primary" size="small" @click="downloadCurrent">下载PDF(学生+答案)</el-button>
              <el-button size="small" @click="exitView">返回列表</el-button>
            </div>
          </div>
        </template>

        <div v-for="(q, i) in viewQuestions" :key="q.question_id" style="margin-bottom: 20px; padding: 16px; background: #fafafa; border-radius: 8px; border: 1px solid #eee">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px">
            <div>
              <strong>第 {{ i + 1 }} 题</strong>
              <el-tag size="small" style="margin-left: 8px">{{ q.knowledge_point }}</el-tag>
              <el-tag size="small" :type="q.difficulty==='基础'?'success':q.difficulty==='中等'?'warning':'danger'" style="margin-left: 4px">{{ q.difficulty }}</el-tag>
              <div v-if="q._wrongInfo" style="margin-top:4px;font-size:12px;color:#e6a23c">
                已错 <strong>{{ q._wrongInfo.wrong_count }}</strong> 次 ·
                上次错误：{{ q._wrongInfo.last_wrong_date }}
                <el-tag v-if="q._wrongInfo.mastered" size="small" type="success" style="margin-left:4px">已掌握</el-tag>
                <el-tag v-else size="small" type="warning" style="margin-left:4px">待巩固</el-tag>
              </div>
            </div>
            <div>
              <el-radio-group v-model="q._marked" size="small">
                <el-radio value="correct" style="margin-right:12px">
                  <span style="color:#67c23a">正确</span>
                </el-radio>
                <el-radio value="wrong">
                  <span style="color:#f56c6c">错误</span>
                </el-radio>
              </el-radio-group>
              <div v-if="q._marked === 'wrong'" style="margin-top: 6px">
                <el-select v-model="q._errorType" placeholder="选择错误类型" size="small" style="width: 150px" clearable>
                  <el-option label="概念错误" value="概念错误" />
                  <el-option label="计算错误" value="计算错误" />
                  <el-option label="审题错误" value="审题错误" />
                  <el-option label="方法错误" value="方法错误" />
                  <el-option label="其他" value="其他" />
                </el-select>
              </div>
            </div>
          </div>
          <div style="background: #fff; padding: 12px; border-radius: 4px; white-space: pre-wrap; line-height: 1.6" v-html="renderMath(q.question_text)"></div>
          <div v-if="q.has_image && q.image_path" style="margin-top: 8px">
            <el-image :src="encodeURI(q.image_path)" style="max-width: 400px" fit="contain" />
          </div>
          <div style="margin-top: 8px; color: #909399; font-size: 13px">
            <strong>答案：</strong><span v-html="renderMath(q.answer || '待补充')" />
          </div>
        </div>

        <div style="text-align:center;padding:16px 0 8px;border-top:1px solid #eee;margin-top:16px">
          <el-button type="primary" size="large" @click="submitMarking" :loading="submitting">
            统一提交批改（正确 {{ markedCorrectCount }} 题，错误 {{ markedWrongCount }} 题）
          </el-button>
          <el-button size="large" @click="clearMarking" style="margin-left:12px">清空所有标记</el-button>
        </div>
      </el-card>
    </template>

    <AIPracticeDialog
      v-model="aiDialogVisible"
      @created="handleAICreated"
    />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { generateSheet, listSheets, getSheet, deleteSheet, generateWeekSheets, completeSheet, generateSmartRedoSheet, generateWrongPeriodSheet } from '../api/practice'
import { listKnowledgePoints } from '../api/question'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Loading } from '@element-plus/icons-vue'
import html2canvas from 'html2canvas'
import { jsPDF } from 'jspdf'
import { renderMath } from '../utils/math'
import AIPracticeDialog from '../components/AIPracticeDialog.vue'

// ===== 列表模式 =====
const form = reactive({ sheet_name: '', sheet_type: 'daily', difficulties: ['基础', '中等', '挑战'] })
const groupedKps = ref({})        // { "几何": ["几何面积", ...], ... }
const categoryCounts = reactive({})  // { "几何": 2, "计算": 1, ... }
const selectedCategoryKps = reactive({}) // { "几何": ["几何面积", ...], ... } 默认全选
const sheets = ref([])
const genLoading = ref(false)
const lastSheet = ref(null)
const weekData = ref(null)
const weekLoading = ref(false)
const smartLoading = ref(false)
const aiDialogVisible = ref(false)

// 按时间段生成错题卷配置
const periodPreset = ref(3)
const periodStartDate = ref(new Date(Date.now() - 3 * 86400000).toISOString().split('T')[0])
const periodEndDate = ref(new Date().toISOString().split('T')[0])
const periodSheetCount = ref(3)
const periodTypeCounts = reactive({ calculation: 4, fill_blank: 3, choice: 0, problem_solving: 3 })
const periodQuestionTypes = ref([])
const periodDifficulties = ref([])
const periodTypeTotal = computed(() => Object.values(periodTypeCounts).reduce((a, b) => a + (b || 0), 0))
const periodLoading = ref(false)
const periodLastResult = ref(null)

function setPeriodPreset(days) {
  periodPreset.value = days
  if (days === 0) {
    periodStartDate.value = null
    periodEndDate.value = null
  } else {
    const end = new Date()
    const start = new Date()
    start.setDate(start.getDate() - days)
    periodStartDate.value = start.toISOString().split('T')[0]
    periodEndDate.value = end.toISOString().split('T')[0]
  }
}

async function handleGenerateWrongPeriod() {
  if (!periodStartDate.value || !periodEndDate.value) {
    ElMessage.warning('请选择时间范围')
    return
  }
  periodLoading.value = true
  try {
    const params = {
      start_date: periodStartDate.value,
      end_date: periodEndDate.value,
      sheet_count: periodSheetCount.value,
      only_unmastered: true,
    }
    // 传按题型数量配置（过滤掉数量为0的题型）
    const activeTypes = Object.fromEntries(
      Object.entries(periodTypeCounts).filter(([_, v]) => v > 0)
    )
    if (Object.keys(activeTypes).length) {
      params.type_counts = activeTypes
    }
    if (periodQuestionTypes.value.length) params.question_types = periodQuestionTypes.value
    if (periodDifficulties.value.length) params.difficulty = periodDifficulties.value

    const res = await generateWrongPeriodSheet(params)
    periodLastResult.value = res
    ElMessage.success(`已生成 ${res.sheet_count} 张错题卷，共 ${res.total_count} 题`)
    // 设置最后一张为当前下载目标（取第一卷）
    if (res.sheets?.length) {
      lastSheet.value = res.sheets[0]
    }
    await loadSheets()
  } catch (e) {
    // handled by interceptor
  } finally {
    periodLoading.value = false
  }
}

// 智慧推荐错题重练配置
const smartRedoPeriod = ref(30)
const smartRedoStartDate = ref(new Date(Date.now() - 30 * 86400000).toISOString().split('T')[0])
const smartRedoEndDate = ref(new Date().toISOString().split('T')[0])
const smartRedoCalcCount = ref(2)
const smartRedoWrongCount = ref(3)
const smartRedoSimilarCount = ref(2)
const smartRedoStrategy = ref('smart')
const smartRedoQuestionTypes = ref([])

function setSmartRedoPeriod(days) {
  smartRedoPeriod.value = days
  if (days === 0) {
    smartRedoStartDate.value = null
    smartRedoEndDate.value = null
  } else {
    const end = new Date()
    const start = new Date()
    start.setDate(start.getDate() - days)
    smartRedoStartDate.value = start.toISOString().split('T')[0]
    smartRedoEndDate.value = end.toISOString().split('T')[0]
  }
}

async function handleGenerateSmartRedo() {
  const total = smartRedoCalcCount.value + smartRedoWrongCount.value + smartRedoSimilarCount.value
  if (total === 0) {
    ElMessage.warning('请至少设置一种题目的数量')
    return
  }
  smartLoading.value = true
  try {
    const params = {
      name: form.sheet_name || undefined,
      calculation_count: smartRedoCalcCount.value,
      wrong_question_count: smartRedoWrongCount.value,
      similar_question_count: smartRedoSimilarCount.value,
      strategy: smartRedoStrategy.value,
      only_unmastered: true,
    }
    if (smartRedoQuestionTypes.value.length) params.question_types = smartRedoQuestionTypes.value
    if (smartRedoStartDate.value) params.start_date = smartRedoStartDate.value
    if (smartRedoEndDate.value) params.end_date = smartRedoEndDate.value

    const res = await generateSmartRedoSheet(params)
    lastSheet.value = res
    ElMessage.success(`智慧推荐题单已生成！共 ${res.total_questions} 题，预计 ${res.estimated_time} 分钟`)
    await loadSheets()
  } catch (e) {
    // handled by interceptor
  } finally {
    smartLoading.value = false
  }
}

function getDayKps(sheet) {
  const kps = new Set()
  if (sheet.questions) {
    sheet.questions.forEach(q => { if (q.knowledge_point) kps.add(q.knowledge_point) })
  }
  return [...kps]
}

async function handleGenerateWeek() {
  weekLoading.value = true
  try {
    weekData.value = await generateWeekSheets()
    ElMessage.success(`本周练习单已生成！共 ${weekData.value.total_questions} 题`)
    await loadSheets()
  } catch (e) {
    weekData.value = null
  } finally {
    weekLoading.value = false
  }
}

async function downloadDayPdf(ds) {
  try {
    await generatePdf(ds.sheet.sheet_name || ds.day_label, ds.sheet.questions || [])
  } catch (e) {
    ElMessage.error('PDF生成失败')
  }
}

async function downloadAllWeekPdf() {
  if (!weekData.value) return
  for (const ds of weekData.value.sheets) {
    try {
      await generatePdf(ds.sheet.sheet_name || ds.day_label, ds.sheet.questions || [])
    } catch (e) {
      console.error(e)
    }
  }
  ElMessage.success('本周练习单PDF已全部下载')
}

// 计算总题数
const totalSelectedQuestions = computed(() => Object.values(categoryCounts).reduce((a, b) => a + (b || 0), 0))

function toggleCategoryKp(cat, kp) {
  if (!selectedCategoryKps[cat]) {
    // 首次点击该类别：初始化为只选这一个
    selectedCategoryKps[cat] = [kp]
  } else {
    const arr = selectedCategoryKps[cat]
    const idx = arr.indexOf(kp)
    if (idx >= 0) arr.splice(idx, 1)
    else arr.push(kp)
  }
}

async function loadSheets() {
  try {
    const res = await listSheets()
    sheets.value = (res.sheets || []).map(s => ({ ...s, score: s.score ? parseFloat(s.score) : null }))
  } catch (e) { /* ignore */ }
}

async function handleAICreated(sheet) {
  const createdSheets = Array.isArray(sheet?.sheets) ? sheet.sheets : []
  lastSheet.value = createdSheets.length ? createdSheets[0] : sheet
  periodLastResult.value = null
  aiDialogVisible.value = false
  await loadSheets()
}

async function handleGenerate() {
  genLoading.value = true
  try {
    // 构建分组选题参数
    const knowledge_group_counts = Object.entries(categoryCounts)
      .filter(([_, count]) => count > 0 && (selectedCategoryKps[_] === undefined || selectedCategoryKps[_].length > 0))
      .map(([cat, count]) => ({
        knowledge_category: cat,
        // undefined = 未点击过任何考点 → 用该类别全部考点
        knowledge_points: selectedCategoryKps[cat] !== undefined ? selectedCategoryKps[cat] : groupedKps.value[cat] || [],
        count,
      }))
    const params = { ...form, knowledge_group_counts }
    if (!params.sheet_name) params.sheet_name = undefined
    const res = await generateSheet(params)
    lastSheet.value = res
    ElMessage.success(`练习单已生成！共 ${res.total_questions} 题，预计 ${res.estimated_time} 分钟`)
    await loadSheets()
  } finally { genLoading.value = false }
}

	// ===== PDF 下载 =====
async function downloadSheetAction(row) {
  try {
    ElMessage.info('正在生成PDF...')
    let sheetData, questions, sections, wrongInfo
    if (viewData.value && viewData.value.sheet_id === row.sheet_id) {
      sheetData = viewData.value
      questions = viewQuestions.value
      wrongInfo = sheetData._wrong_question_info || {}
    } else {
      const res = await getSheet(row.sheet_id)
      sheetData = res
      questions = res.questions || []
      wrongInfo = res._wrong_question_info || {}
    }
    sections = sheetData._sections || null
    // 附加错题信息
    if (wrongInfo) {
      questions = questions.map(q => ({
        ...q,
        _wrongInfo: wrongInfo[q.question_id] || null,
      }))
    }
    await generatePdf(sheetData.sheet_name || `练习单_${row.sheet_id}`, questions, sections)
  } catch (e) {
    ElMessage.error('PDF生成失败')
    console.error(e)
  }
}

function downloadCurrent() {
  if (viewData.value) downloadSheetAction(viewData.value)
  else if (lastSheet.value) downloadSheetAction(lastSheet.value)
}

async function downloadOneSheet(sheetData) {
  try {
    ElMessage.info('正在生成PDF...')
    await generatePdf(sheetData.sheet_name || '练习单', sheetData.questions || [], sheetData._sections || null)
  } catch (e) {
    ElMessage.error('PDF生成失败')
  }
}

// ===== 删除 =====
const selectedSheetIds = ref(new Set())
const sheetsTableRef = ref(null)

function onSheetSelectionChange(selection) {
  selectedSheetIds.value = new Set(selection.map(s => s.sheet_id))
}

async function handleBatchDeleteSheets() {
  const ids = [...selectedSheetIds.value]
  if (!ids.length) return
  try {
    await ElMessageBox.confirm(`确定删除选中的 ${ids.length} 个练习单吗？删除后不可恢复。`, '批量删除', { type: 'warning' })
  } catch { return }
  let success = 0
  for (const id of ids) {
    try { await deleteSheet(id); success++ } catch { /* continue */ }
  }
  ElMessage.success(`已删除 ${success} 个练习单`)
  selectedSheetIds.value = new Set()
  sheetsTableRef.value?.clearSelection()
  await loadSheets()
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(`确定删除练习单「${row.sheet_name}」吗？删除后不可恢复。`, '确认删除', { type: 'warning' })
  } catch { return }

  try {
    await deleteSheet(row.sheet_id)
    ElMessage.success('已删除')
    await loadSheets()
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

// ===== PDF 生成 =====
const FRACTION_CSS = `
.frac { display:inline-block; vertical-align:middle; text-align:center; font-size:0.78em; line-height:1; margin:0 1px; }
.frac .num { display:block; border-bottom:1px solid #333; padding:0 2px; line-height:1.15; }
.frac .den { display:block; padding:0 2px; line-height:1.15; }
.mixed-frac { display:inline-block; vertical-align:middle; white-space:nowrap; }
.mixed-frac .frac { font-size:0.72em; }
`

function escapeHtml(text) {
  if (!text) return ''
  return String(text).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
}

// 将题目文本中的分数替换为 CSS 上下结构
function renderFractions(text) {
  if (!text) return ''
  // 带分数: 数字+又+分子/分母 (如 "1又1/2")
  let result = String(text).replace(/(\d+)又(\d+)\/(\d+)/g, (_, a, b, c) => {
    return `${a}<span class="mixed-frac"><span class="frac"><span class="num">${b}</span><span class="den">${c}</span></span></span>`
  })
  // 真分数: 分子/分母 (如 "5/9") — 只替换独立分数，不替换日期等
  result = result.replace(/(?<!\d|>)(\d+)\/(\d+)(?!\d|%)/g, (match, a, b) => {
    return `<span class="frac"><span class="num">${a}</span><span class="den">${b}</span></span>`
  })
  return result
}

function getTypeLabel(q) {
  if (!q.question_type) return ''
  const map = { 'fill_blank': '填空', 'choice': '选择', 'calculation': '计算', 'problem_solving': '解决问题', 'other': '其他' }
  return map[q.question_type] || ''
}

function buildQuestionHtml(q, index) {
  const typeLabel = getTypeLabel(q)
  const diffColor = q.difficulty === '基础' ? '#67c23a' : q.difficulty === '中等' ? '#e6a23c' : '#f56c6c'
  const difficultyTag = q.difficulty ? `<span style="font-size:11px;color:${diffColor};font-weight:normal;border:1px solid ${diffColor};border-radius:3px;padding:0 6px;margin-left:4px">${escapeHtml(q.difficulty)}</span>` : ''

  // 题型标签
  const typeTag = typeLabel ? `<span style="font-size:11px;color:#666;font-weight:normal;border:1px solid #ddd;border-radius:3px;padding:0 6px;margin-left:4px">${typeLabel}</span>` : ''
  // 知识点标签
  const kpTag = q.knowledge_point
    ? `<span style="font-size:11px;color:#409eff;font-weight:normal;border:1px solid #409eff;border-radius:3px;padding:0 6px;margin-left:4px">${escapeHtml(q.knowledge_point)}</span>`
    : ''
  // 来源标签
  const sourceTag = q.source_school
    ? `<span style="font-size:10px;color:#999;font-weight:normal;margin-left:8px">来源：${escapeHtml(q.source_school)}</span>`
    : ''

  // 题目标题
  let html = `<div style="padding-bottom:28px">`
  html += `<div style="font-size:14px;font-weight:bold;margin-bottom:6px;padding-bottom:4px;border-bottom:1px solid #eee">`
  html += `第 ${index + 1} 题 ${typeTag} ${kpTag} ${difficultyTag} ${sourceTag}`
  html += `</div>`

  // 错题信息
  if (q._wrongInfo) {
    html += `<div style="font-size:11px;color:#e6a23c;margin-bottom:4px">`
    html += `已错 <strong>${q._wrongInfo.wrong_count}</strong> 次 · 上次错误：${q._wrongInfo.last_wrong_date || '未知'}`
    if (q._wrongInfo.mastered) html += ` · <span style="color:#67c23a">已掌握</span>`
    else html += ` · <span style="color:#e6a23c">待巩固</span>`
    html += `</div>`
  }

  // 题目正文（带公式渲染）
  const renderedText = renderFractions(renderMath(q.question_text))
  html += `<div style="white-space:pre-wrap;padding:10px 14px;background:#fafafa;border-radius:4px;line-height:1.8;font-size:15px">${renderedText}</div>`

  // 图片
  if (q.has_image && q.image_path) {
    html += `<div style="margin-top:10px;text-align:center"><img src="${encodeURI(q.image_path)}" style="max-width:480px;max-height:360px;object-fit:contain;border:1px solid #eee;border-radius:4px" crossOrigin="anonymous" /></div>`
  }

  // 根据题型添加答题留空
  if (q.question_type === 'fill_blank') {
    // 填空题：留少量空白
    html += `<div style="margin-top:6px"><div style="height:0.8cm"></div></div>`
  } else if (q.question_type === 'choice') {
    // 选择题：留推理空白
    html += `<div style="margin-top:6px"><div style="height:0.6cm"></div></div>`
  } else if (q.question_type === 'problem_solving') {
    // 解决问题：留大量空白写过程
    html += `<div style="margin-top:8px">`
    html += `<div style="font-size:12px;color:#999">解：</div>`
    html += `<div style="height:8cm;border:1px dashed #eee;border-radius:4px;margin:4px 0"></div>`
    html += `<div style="font-size:12px;color:#999">答：______________________</div>`
    html += `</div>`
  } else if (q.question_type === 'calculation') {
    // 计算题：留计算空白
    html += `<div style="margin-top:8px"><div style="height:3cm;border:1px dashed #eee;border-radius:4px"></div></div>`
  } else {
    // 默认留空
    html += `<div style="margin-top:6px"><div style="height:1cm;border:1px dashed #f5f5f5;border-radius:4px"></div></div>`
  }

  html += `</div>`
  return html
}

function buildAnswerHtml(q, index) {
  let html = `<div style="padding:10px 14px 26px;background:#fafafa;border-radius:4px;border-left:3px solid #409eff">`
  html += `<div style="font-weight:bold;font-size:13.5px;margin-bottom:4px">第 ${index + 1} 题`
  if (q.knowledge_point) html += ` <span style="font-weight:normal;font-size:12px;color:#666">[${escapeHtml(q.knowledge_point)}]</span>`
  html += `</div>`
  html += `<div style="font-size:13px;line-height:1.7">`
  html += `<strong>答案：</strong>${renderFractions(renderMath(q.answer || '待补充'))}`
  if (q.solution) {
    html += `<br><strong>解析：</strong>${renderFractions(renderMath(q.solution))}`
  }
  html += `</div></div>`
  return html
}

async function renderSegment(htmlContent) {
  const container = document.createElement('div')
  container.style.cssText = `
    width: 794px;
    padding: 0 56px;
    font-family: 'SimSun', 'STSong', 'Noto Serif CJK SC', serif;
    font-size: 14px;
    line-height: 1.8;
    color: #333;
    background: #fff;
    position: absolute;
    left: -9999px;
    top: 0;
  `
  container.innerHTML = `<style>${FRACTION_CSS}</style>${htmlContent}`
  document.body.appendChild(container)

  const imgs = container.querySelectorAll('img')
  await Promise.all(Array.from(imgs).map(img => {
    if (img.complete && img.naturalWidth) return Promise.resolve()
    return new Promise(resolve => { img.onload = resolve; img.onerror = resolve })
  }))

  await new Promise(r => setTimeout(r, 300))

  const canvas = await html2canvas(container, {
    scale: 2,
    useCORS: true,
    logging: false,
    windowHeight: container.scrollHeight,
  })

  document.body.removeChild(container)
  return canvas
}

async function renderToPdf(segments, filename) {
  const pdf = new jsPDF('p', 'mm', 'a4')
  const pdfW = pdf.internal.pageSize.getWidth()
  const pdfH = pdf.internal.pageSize.getHeight()
  const TOP_MARGIN = 20
  const BOTTOM_MARGIN = 15

  let yPos = TOP_MARGIN

  for (const html of segments) {
    const canvas = await renderSegment(html)
    const imgData = canvas.toDataURL('image/png')

    const ratio = pdfW / canvas.width
    const segH = canvas.height * ratio

    // 如果当前段超出底部边距，换页
    if (yPos + segH > pdfH - BOTTOM_MARGIN && yPos > TOP_MARGIN) {
      pdf.addPage()
      yPos = TOP_MARGIN
    }

    pdf.addImage(imgData, 'PNG', 0, yPos, pdfW, segH)
    yPos += segH
  }

  pdf.save(`${filename}.pdf`)
}

async function generatePdf(sheetName, questions, sections) {
  if (!questions || !questions.length) {
    ElMessage.warning('没有题目可供生成PDF')
    return
  }

  const safeName = sheetName.replace(/[/\\?%*:|"<>]/g, '_')

  // 按题型统计
  const typeCounts = {}
  const typeTime = { fill_blank: 2.5, choice: 2.5, calculation: 3, problem_solving: 8 }
  const typeLabels = { fill_blank: '填空', choice: '选择', calculation: '计算', problem_solving: '解决问题' }
  let totalTime = 0
  questions.forEach(q => {
    const t = q.question_type || 'other'
    typeCounts[t] = (typeCounts[t] || 0) + 1
    totalTime += typeTime[t] || 3
  })
  totalTime = Math.max(20, Math.round(totalTime))

  const timeDetailHtml = Object.entries(typeCounts)
    .map(([type, count]) => {
      const label = typeLabels[type] || type
      const min = typeTime[type] || 3
      return `<span style="margin:0 8px">${label} <strong>${count}</strong> 题（约 <strong>${Math.round(count * min)}</strong> 分钟）</span>`
    })
    .join('')

  function secHeaderHtml(sec, fontSize) {
    return `<div style="margin:0;padding:8px 14px;background:#f0f5ff;border-radius:6px;border-left:4px solid #409eff;font-size:${fontSize};font-weight:bold;color:#303133">${escapeHtml(sec.label)}（共 ${sec.count} 题）</div><div style="height:12px"></div>`
  }

  // ===== 学生卷分段 =====
  const studentSegments = []

  // 标题段：去掉margin-bottom防止html2canvas裁剪丢失
  studentSegments.push(`
    <div style="text-align:center;padding-bottom:24px;border-bottom:3px double #333">
      <h1 style="font-size:24px;margin:0 0 12px;font-weight:bold;letter-spacing:2px">${escapeHtml(sheetName)}</h1>
      <div style="font-size:13px;color:#666;margin-bottom:6px">
        <span>共 <strong>${questions.length}</strong> 题，建议用时：<strong>${totalTime}</strong> 分钟</span>
      </div>
      <div style="font-size:12px;color:#999;margin-bottom:14px">
        ${timeDetailHtml}
      </div>
      <table style="margin:0 auto;font-size:13px;border-collapse:collapse">
        <tr>
          <td style="padding:4px 16px">姓名：<u style="display:inline-block;width:80px">&nbsp;</u></td>
          <td style="padding:4px 16px">日期：<u style="display:inline-block;width:80px">${new Date().toLocaleDateString('zh-CN')}</u></td>
          <td style="padding:4px 16px">用时：<u style="display:inline-block;width:60px">&nbsp;</u>分钟</td>
        </tr>
      </table>
    </div>
  `)

  let sectionIdx = 0
  questions.forEach((q, i) => {
    let html = ''
    if (sections && sectionIdx < sections.length && i === sections[sectionIdx].start) {
      html += secHeaderHtml(sections[sectionIdx], '15px')
      sectionIdx++
    }
    html += buildQuestionHtml(q, i)
    studentSegments.push(html)
  })

  // ===== 答案卷分段 =====
  const answerSegments = []

  answerSegments.push(`
    <div style="text-align:center;padding-bottom:16px;border-bottom:2px solid #333">
      <h1 style="font-size:20px;margin:0;font-weight:bold">${escapeHtml(sheetName)} — 参考答案</h1>
    </div>
  `)

  sectionIdx = 0
  questions.forEach((q, i) => {
    let html = ''
    if (sections && sectionIdx < sections.length && i === sections[sectionIdx].start) {
      html += secHeaderHtml(sections[sectionIdx], '15px')
      sectionIdx++
    }
    html += buildAnswerHtml(q, i)
    answerSegments.push(html)
  })

  try {
    ElMessage.info('正在生成学生卷PDF...')
    await renderToPdf(studentSegments, `${safeName}_学生卷`)
    ElMessage.success('学生卷下载完成')
    ElMessage.info('正在生成答案卷PDF...')
    await renderToPdf(answerSegments, `${safeName}_答案卷`)
    ElMessage.success('答案卷下载完成')
  } catch (e) {
    ElMessage.error('PDF生成失败')
    console.error(e)
  }
}

// ===== 查看模式 =====
const currentMode = ref(null)
const viewData = ref(null)
const viewQuestions = ref([])

async function openView(row) {
  try {
    const res = await getSheet(row.sheet_id)
    viewData.value = res
    const wrongInfo = res._wrong_question_info || {}
    viewQuestions.value = (res.questions || []).map(q => ({
      ...q,
      _marked: null,
      _errorType: '',
      _wrongInfo: wrongInfo[q.question_id] || null,
    }))
    currentMode.value = 'view'
  } catch (e) { /* ignore */ }
}

function exitView() {
  currentMode.value = null
  viewData.value = null
  viewQuestions.value = []
}

// ===== 统一对错标记 =====
const submitting = ref(false)

const markedCorrectCount = computed(() => viewQuestions.value.filter(q => q._marked === 'correct').length)
const markedWrongCount = computed(() => viewQuestions.value.filter(q => q._marked === 'wrong').length)

function clearMarking() {
  viewQuestions.value.forEach(q => { q._marked = null; q._errorType = '' })
}

async function submitMarking() {
  const marked = viewQuestions.value.filter(q => q._marked !== null && q._marked !== undefined)
  if (marked.length === 0) {
    ElMessage.warning('请先标记题目对错')
    return
  }

  submitting.value = true
  try {
    const marks = viewQuestions.value.map(q => ({
      question_id: q.question_id,
      is_correct: q._marked === 'correct',
      error_type: q._marked === 'wrong' ? (q._errorType || null) : null,
    }))

    await completeSheet(viewData.value.sheet_id, { marks })

    const correct = markedCorrectCount.value
    const wrong = markedWrongCount.value
    ElMessage.success(`提交完成！正确 ${correct} 题，错误 ${wrong} 题`)

    await loadSheets()
    exitView()
  } catch (e) {
    if (e.response?.status === 400) {
      ElMessage.warning('该练习单已提交过')
    } else {
      ElMessage.error('提交失败，请重试')
    }
  } finally {
    submitting.value = false
  }
}

// ===== 初始化 =====
onMounted(async () => {
  try {
    const res = await listKnowledgePoints()
    groupedKps.value = res.knowledge_points || {}
    // 默认：所有类别选1题，不预选具体考点（未点击时使用全部考点）
    for (const cat of Object.keys(groupedKps.value)) {
      categoryCounts[cat] = 1
      // 不预选考点，留空 = 使用该类别全部知识点
    }
  } catch (e) { /* ignore */ }
  await loadSheets()
})
</script>
