<template>
  <div>
    <el-row :gutter="20">
      <el-col :span="14">
        <el-card shadow="hover">
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center">
              <span style="font-weight: bold">错题本</span>
              <div>
                <el-button type="danger" size="small" :disabled="!selectedWrongIds.size" @click="handleBatchDelete">批量删除</el-button>
                <el-button type="primary" size="small" @click="showAddDialog">录入错题</el-button>
              </div>
            </div>
          </template>
          <el-table ref="wrongTableRef" :data="wrongList" stripe v-loading="loading" style="width: 100%" row-key="record_id" @selection-change="onWrongSelectionChange">
            <el-table-column type="selection" width="40" reserve-selection />
            <el-table-column label="题目" min-width="250">
              <template #default="{ row }">
                <div style="max-height: 50px; overflow: hidden" v-html="renderMath(row.question?.question_text || '')"></div>
              </template>
            </el-table-column>
            <el-table-column prop="exam_name" label="考试" width="100" />
            <el-table-column label="录入时间" width="110">
              <template #default="{ row }">
                {{ formatCreatedDate(row.created_date || row.created_at || row.createdDate || row.exam_date) }}
              </template>
            </el-table-column>
            <el-table-column label="错误类型" width="100">
              <template #default="{ row }">{{ row.error_type || '-' }}</template>
            </el-table-column>
            <el-table-column label="状态" width="80">
              <template #default="{ row }">
                <el-tag v-if="row.mastered" type="success" size="small">已掌握</el-tag>
                <el-tag v-else type="danger" size="small">待巩固</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="重做" width="60">
              <template #default="{ row }">{{ row.redo_count || 0 }}次</template>
            </el-table-column>
            <el-table-column label="操作" width="180" fixed="right">
              <template #default="{ row }">
                <el-button type="primary" link size="small" @click="showDetail(row)">详情</el-button>
                <el-button type="primary" link size="small" @click="showFeedback(row)">反馈</el-button>
                <el-button type="danger" link size="small" @click="handleDelete(row.record_id)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <div style="display: flex; justify-content: center; margin-top: 16px" v-if="totalCount > pageSize">
            <el-pagination
              v-model:current-page="pageNum"
              :page-size="pageSize"
              :total="totalCount"
              layout="prev, pager, next, total"
              @current-change="onPageChange"
            />
          </div>
          <el-empty v-if="!wrongList.length && !loading" description="暂无错题" />
        </el-card>
      </el-col>
      <el-col :span="10">
        <el-card shadow="hover">
          <template #header><span style="font-weight: bold">错题统计</span></template>
          <div style="margin-bottom: 12px">
            <span>总错题数：<strong>{{ wrongList.length }}</strong></span>
          </div>
          <div style="margin-bottom: 12px">
            <span>已掌握：<strong style="color: #67c23a">{{ wrongList.filter(w => w.mastered).length }}</strong></span>
            <span style="margin-left: 20px">待巩固：<strong style="color: #f56c6c">{{ wrongList.filter(w => !w.mastered).length }}</strong></span>
          </div>
          <el-divider />
          <div><strong>错误类型分布</strong></div>
          <div v-for="(count, type) in errorStats" :key="type" style="margin-top: 8px; display: flex; align-items: center">
            <span style="width: 80px">{{ type }}</span>
            <el-progress :percentage="Math.round(count / wrongList.length * 100)" :stroke-width="16" style="flex: 1" />
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 录入错题对话框（双模式） -->
    <el-dialog v-model="addVisible" title="录入错题" width="800px" destroy-on-close>
      <el-tabs v-model="addMode">
        <!-- 模式1：手动选择 -->
        <el-tab-pane label="手动选择" name="manual">
          <div style="display: flex; gap: 8px; margin-bottom: 12px">
            <el-select v-model="searchFilters.category" placeholder="分类" clearable size="small" style="width: 120px">
              <el-option v-for="c in categories" :key="c" :label="c" :value="c" />
            </el-select>
            <el-select v-model="searchFilters.difficulty" placeholder="难度" clearable size="small" style="width: 100px">
              <el-option label="基础" value="基础" />
              <el-option label="中等" value="中等" />
              <el-option label="挑战" value="挑战" />
            </el-select>
            <el-input v-model="searchFilters.keyword" placeholder="搜索题目关键字" clearable size="small" style="width: 200px" @keyup.enter="searchQuestions" />
            <el-button type="primary" size="small" @click="searchQuestions">搜索</el-button>
          </div>

          <el-table :data="searchResults" stripe v-loading="searchLoading" max-height="250" style="width: 100%; cursor: pointer" @row-click="selectQuestion">
            <el-table-column label="ID" width="60" prop="question_id" />
            <el-table-column label="知识点" width="100" prop="knowledge_point" show-overflow-tooltip />
            <el-table-column label="题型" width="70" prop="question_type" />
            <el-table-column label="难度" width="70">
              <template #default="{ row }">
                <el-tag :type="row.difficulty === '基础' ? 'success' : row.difficulty === '中等' ? 'warning' : 'danger'" size="small">{{ row.difficulty }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="题目" min-width="200">
              <template #default="{ row }">{{ row.question_text?.slice(0, 60) }}{{ row.question_text?.length > 60 ? '...' : '' }}</template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!searchResults.length && !searchLoading" description="请搜索题目" style="padding: 16px" />

          <div style="display: flex; justify-content: center; margin-top: 8px" v-if="searchTotal > searchPageSize">
            <el-pagination
              v-model:current-page="searchPage"
              :page-size="searchPageSize"
              :total="searchTotal"
              layout="prev, pager, next"
              small
              @current-change="searchQuestions"
            />
          </div>

          <div v-if="selectedQuestion" style="margin-top: 12px; padding: 12px; background: #f5f7fa; border-radius: 6px; border: 1px solid #e4e7ed">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px">
              <strong>已选题目 #{{ selectedQuestion.question_id }}</strong>
              <el-button type="danger" link size="small" @click="clearSelection">取消选择</el-button>
            </div>
            <div style="white-space: pre-wrap; font-size: 13px">{{ selectedQuestion.question_text }}</div>
          </div>
        </el-tab-pane>

        <!-- 模式2：图片上传识别（支持上传文件和截图粘贴） -->
        <el-tab-pane label="图片上传" name="image">
          <!-- 上传 + 粘贴混合区 -->
          <div v-if="!capturedImage && !ocrLoading && !recognizedQuestions.length" style="border:2px dashed #dcdfe6;border-radius:8px;padding:40px 20px;text-align:center;cursor:pointer;transition:border-color .2s" @click="triggerFileSelect" @dragover.prevent @drop.prevent="onDropImage">
            <el-icon size="48" color="#c0c4cc"><UploadFilled /></el-icon>
            <p style="margin-top:12px;color:#666;font-size:14px">点击选择图片，或拖拽图片到此处</p>

            <!-- 截图技巧提示 -->
            <div style="margin-top:16px;padding:12px;background:#f0f9ff;border:1px solid #b3d8ff;border-radius:6px;text-align:left;max-width:420px;margin-left:auto;margin-right:auto">
              <div style="font-weight:bold;color:#409eff;margin-bottom:8px;font-size:13px">📸 截图技巧（提高识别速度和准确率）</div>
              <ul style="margin:0;padding-left:20px;font-size:12px;color:#606266;line-height:2">
                <li>包含<strong>完整题目</strong>（题号、题干、选项、图表）</li>
                <li>确保文字<strong>清晰可读</strong>，避免模糊、倾斜</li>
                <li>可一次截取<strong>多道题</strong>，系统会按题号拆分识别</li>
                <li>留出适当边距，不要紧贴边缘裁剪</li>
              </ul>
            </div>

            <p style="margin-top:12px;color:#909399;font-size:12px">
              按 <kbd style="padding:1px 6px;background:#f0f0f0;border:1px solid #ddd;border-radius:3px">Ctrl+V</kbd> 粘贴截图 · 支持 Win+Shift+S 截图后直接粘贴
            </p>
            <el-button size="small" style="margin-top:12px" @click.stop="triggerScreenshot">启动屏幕截图</el-button>
            <input ref="fileInputRef" type="file" accept="image/*" style="display:none" @change="onFileSelected" />
          </div>

          <!-- 图片预览 + 裁剪 -->
          <div v-if="capturedImage && !ocrLoading" style="margin-top:16px;text-align:center">
            <div style="margin-bottom:8px;color:#909399;font-size:13px">可裁剪单题区域，也可以直接识别整张多题图片</div>
            <div style="max-height:360px;overflow:hidden;border:1px solid #dcdfe6;border-radius:4px;display:inline-block">
              <img :src="capturedImage" style="max-width:100%;max-height:360px;display:block" />
            </div>
            <div style="margin-top:12px">
              <el-button @click="openCropper">裁剪题目区域</el-button>
              <el-button @click="skipCropAndRecognize">跳过裁剪，识别整张图片</el-button>
              <el-button @click="clearCapturedImage">重新选择</el-button>
            </div>
          </div>

          <!-- 加载中 -->
          <div v-if="ocrLoading" style="text-align:center;padding:40px">
            <el-icon class="is-loading" size="32"><Loading /></el-icon>
            <p style="margin-top:12px;color:#666">正在整图识别并拆分题目，请稍候...</p>
          </div>

          <!-- 识别结果（普通模式） -->
          <div v-if="recognizedQuestions.length && !ocrLoading" style="margin-top:20px">
            <!-- 原图预览 -->
            <div v-if="capturedImage" style="margin-bottom:16px;padding:12px;background:#fafafa;border:1px solid #e4e7ed;border-radius:8px">
              <div style="font-size:13px;color:#666;margin-bottom:8px;font-weight:500">📷 原图预览（对照检查识别结果是否完整准确）</div>
              <img :src="capturedImage" style="max-width:100%;max-height:200px;border:1px solid #dcdfe6;border-radius:4px;cursor:pointer" @click="previewOriginalImage" />
            </div>

            <!-- 选择栏 -->
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
              <strong>识别结果（共 {{ recognizedQuestions.length }} 题）</strong>
              <div style="display:flex;align-items:center;gap:12px">
                <span style="font-size:13px;color:#666">已选 {{ selectedQuestionCount }} 题</span>
                <el-checkbox v-model="allSelectedFlag" :indeterminate="selectionIndeterminate" @change="toggleAllSelected" size="small">全选</el-checkbox>
              </div>
            </div>
            <div v-for="(q, qi) in recognizedQuestions" :key="qi" :style="{ marginBottom: '16px', padding: '12px', background: '#fafafa', borderRadius: '8px', border: q._selected ? '1px solid #409eff' : '1px solid #eee', opacity: q._selected ? 1 : 0.55 }">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
                <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
                  <el-checkbox v-model="q._selected" @change="onSelectionChange" />
                  <strong v-if="recognizedQuestions.length > 1">第 {{ qi + 1 }} 题</strong>
                  <!-- 质量警告 -->
                  <el-tag v-if="q.question_text && q.question_text.length < 15" type="warning" size="small">⚠️ 题目较短，请检查</el-tag>
                  <el-tag v-if="q.question_text && !q.question_text.match(/^[\d一二三四五六七八九十]+[.、)）]/)" type="info" size="small">💡 建议补充题号</el-tag>
                  <el-tag v-if="q._matched_question_id" type="info" size="small">已匹配题库 #{{ q._matched_question_id }}</el-tag>
                </div>
              </div>
              <el-row :gutter="12">
                <el-col :span="8">
                  <el-form-item label="知识点">
                    <el-input v-model="q.knowledge_point" size="small" />
                  </el-form-item>
                </el-col>
                <el-col :span="6">
                  <el-form-item label="分类">
                    <el-select v-model="q.knowledge_category" size="small" style="width:100%">
                      <el-option v-for="c in categories" :key="c" :label="c" :value="c" />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :span="5">
                  <el-form-item label="题型">
                    <el-select v-model="q.question_type" size="small" style="width:100%">
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
                    <el-select v-model="q.difficulty" size="small" style="width:100%">
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
              <el-form-item label="答案">
                <el-input v-model="q.answer" type="textarea" :rows="2" />
                <div v-if="q.answer" style="margin-top:4px;padding:6px 10px;background:#fff;border:1px dashed #d9d9d9;border-radius:4px;white-space:pre-wrap;font-size:13px;line-height:1.7" v-html="renderMath(q.answer)"></div>
              </el-form-item>
              <el-form-item label="解析">
                <el-input v-model="q.solution" type="textarea" :rows="2" />
              </el-form-item>
              <el-form-item label="配图">
                <div style="width:100%">
                  <div v-if="q._image_preview" style="position:relative;display:inline-block;margin-bottom:4px">
                    <img :src="q._image_preview" style="max-width:200px;max-height:150px;border:1px solid #dcdfe6;border-radius:4px;display:block" />
                    <el-button size="small" type="danger" circle style="position:absolute;top:-6px;right:-6px;width:18px;height:18px;min-height:18px;font-size:10px" @click="removeQuestionImage(q)">×</el-button>
                  </div>
                  <div v-if="!q._image_uploading" style="display:flex;gap:6px;align-items:center">
                    <el-button size="small" @click="triggerQuestionImageSelect(qi)">选择配图</el-button>
                    <span v-if="!q._image_preview" style="font-size:11px;color:#909399">图形、图表等</span>
                  </div>
                  <div v-else style="display:flex;align-items:center;gap:6px">
                    <el-icon class="is-loading" size="14"><Loading /></el-icon>
                    <span style="font-size:12px;color:#666">上传中...</span>
                  </div>
                  <input :ref="el => registerImageInputRef(qi, el)" type="file" accept="image/*" style="display:none" @change="e => onQuestionImageSelected(e, qi)" />
                </div>
              </el-form-item>
            </div>

            <div v-if="ocrMatches.length" style="margin-top:16px">
              <h4>题库中可能匹配的题目（点击选中即可关联）</h4>
              <el-table :data="ocrMatches" stripe max-height="200" style="width:100%;cursor:pointer" @row-click="selectOcrMatch">
                <el-table-column label="ID" width="60" prop="question_id" />
                <el-table-column label="知识点" width="120" prop="knowledge_point" show-overflow-tooltip />
                <el-table-column label="题目" min-width="200">
                  <template #default="{ row }">{{ row.question_text?.slice(0, 60) }}{{ row.question_text?.length > 60 ? '...' : '' }}</template>
                </el-table-column>
              </el-table>
            </div>

            <div v-if="selectedMatch" style="margin-top:8px;padding:8px 12px;background:#e6f7ff;border-radius:4px;border:1px solid #91d5ff">
              已关联题库题目 #{{ selectedMatch.question_id }}
              <el-button type="primary" link size="small" @click="clearOcrMatch">取消</el-button>
            </div>
          </div>
        </el-tab-pane>

        <!-- 模式3：PDF上传识别（整卷识别） -->
        <el-tab-pane label="PDF上传" name="pdf">
          <!-- 上传区（未选择文件） -->
          <div v-if="!pdfFile && !pdfRecognizing && !pdfResult"
               style="border:2px dashed #dcdfe6;border-radius:8px;padding:40px 20px;text-align:center;cursor:pointer"
               @click="triggerPdfSelect" @dragover.prevent @drop.prevent="onDropPdf">
            <el-icon size="48" color="#c0c4cc"><UploadFilled /></el-icon>
            <p style="margin-top:12px;color:#666;font-size:14px">点击选择 PDF 文件，或拖拽 PDF 到此处</p>
            <p style="margin-top:6px;color:#909399;font-size:12px">支持电子版 PDF、扫描版 PDF · 建议 ≤ 50MB · ≤ 30 页</p>
            <p style="margin-top:4px;color:#c0c4cc;font-size:12px">将自动识别整张试卷的所有题目</p>
            <input ref="pdfInputRef" type="file" accept=".pdf,application/pdf" style="display:none" @change="onPdfFileSelected" />
          </div>

          <!-- 已选文件，待识别 -->
          <div v-if="pdfFile && !pdfRecognizing && !pdfResult" style="text-align:center;padding:20px">
            <div style="padding:24px;background:#f5f7fa;border-radius:8px;margin-bottom:16px">
              <p style="font-size:16px;font-weight:bold;color:#303133;word-break:break-all">{{ pdfFile.name }}</p>
              <p style="color:#909399;font-size:13px;margin-top:4px">{{ formatFileSize(pdfFile.size) }}</p>
            </div>
            <el-button type="primary" size="large" @click="startPdfRecognition">开始识别整张试卷</el-button>
            <el-button @click="clearPdfFile">重新选择</el-button>
          </div>

          <!-- 识别中（进度条） -->
          <div v-if="pdfRecognizing" style="padding:20px">
            <PdfRecognitionProgress
              :current-page="pdfProgress.current_page || 0"
              :total-pages="pdfProgress.total_pages || 0"
              :questions-found="pdfProgress.questions_found || 0"
              :message="pdfProgress.message || '正在准备识别...'"
              title="正在识别整张试卷"
              subtitle="AI 正在逐页分析题目，请耐心等待"
            />
          </div>

          <!-- 识别完成 -->
          <div v-if="pdfResult && !pdfRecognizing" style="text-align:center;padding:20px">
            <div style="padding:24px;background:#f0f9eb;border-radius:8px;margin-bottom:16px">
              <p style="font-size:20px;color:#67c23a;margin:0">✓ 识别完成</p>
              <p style="color:#606266;font-size:14px;margin-top:8px">
                共 <strong>{{ pdfResult.page_count }}</strong> 页，
                识别出 <strong>{{ totalPdfQuestions }}</strong> 道题目
              </p>
              <div v-if="pdfResult.file_type" style="margin-top:4px">
                <el-tag size="small">{{ pdfResult.file_type === 'pdf' ? 'PDF文件' : '图片文件' }}</el-tag>
              </div>
            </div>
            <el-button type="primary" size="large" @click="openPdfConfirmDialog">
              查看题目和答案
            </el-button>
            <el-button @click="clearPdfFile">重新上传</el-button>
          </div>
        </el-tab-pane>
      </el-tabs>

      <!-- ScreenshotCropper -->
      <ScreenshotCropper :visible="cropperVisible" :image-src="capturedImage" @confirm="onCropConfirm" @cancel="onCropCancel" />

      <!-- 公共表单部分（PDF模式由确认对话框处理） -->
      <template v-if="addMode !== 'pdf'">
        <el-divider />
        <el-form :model="addForm" label-width="80px">
          <el-form-item label="考试日期">
            <el-date-picker v-model="addForm.exam_date" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" style="width: 100%" />
          </el-form-item>
          <el-form-item label="考试名称">
            <el-input v-model="addForm.exam_name" placeholder="如：二外真题第2套" />
          </el-form-item>
          <el-form-item label="错误类型">
            <el-select v-model="addForm.error_type" placeholder="选择错误类型" style="width: 100%">
              <el-option label="概念错误" value="概念错误" />
              <el-option label="计算错误" value="计算错误" />
              <el-option label="审题错误" value="审题错误" />
              <el-option label="方法错误" value="方法错误" />
              <el-option label="其他" value="其他" />
            </el-select>
          </el-form-item>
          <el-form-item label="备注">
            <el-input v-model="addForm.notes" type="textarea" rows="2" />
          </el-form-item>
        </el-form>
      </template>
      <template #footer>
        <el-button @click="addVisible = false">取消</el-button>
        <el-button type="primary" @click="handleAdd" :loading="addLoading" :disabled="!hasSelectedQuestion">确认录入{{ addMode === 'image' && selectedQuestionCount > 0 ? `（${selectedQuestionCount} 题）` : '' }}</el-button>
      </template>
    </el-dialog>

    <!-- 反馈对话框 -->
    <el-dialog v-model="feedbackVisible" title="答题反馈" width="400px">
      <el-form :model="feedbackForm" label-width="80px">
        <el-form-item label="是否做对">
          <el-radio-group v-model="feedbackForm.is_correct">
            <el-radio :value="true">做对了</el-radio>
            <el-radio :value="false">还是错了</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="错误类型" v-if="!feedbackForm.is_correct">
          <el-select v-model="feedbackForm.error_type" placeholder="选择错误类型" style="width: 100%">
            <el-option label="概念错误" value="概念错误" />
            <el-option label="计算错误" value="计算错误" />
            <el-option label="审题错误" value="审题错误" />
            <el-option label="方法错误" value="方法错误" />
            <el-option label="其他" value="其他" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="feedbackVisible = false">取消</el-button>
        <el-button type="primary" @click="handleFeedback">确认</el-button>
      </template>
    </el-dialog>

    <!-- 题目详情对话框 -->
    <el-dialog v-model="detailVisible" title="错题详情" width="700px">
      <div v-if="currentDetailQuestion">
        <div style="margin-bottom: 16px">
          <el-tag size="small">#{{ currentDetailQuestion.question_id }}</el-tag>
          <el-tag size="small" type="info" style="margin-left: 4px">{{ currentDetailQuestion.q_id }}</el-tag>
          <el-tag size="small" type="success" style="margin-left: 8px">{{ currentDetailQuestion.knowledge_point }}</el-tag>
          <el-tag size="small" :type="currentDetailQuestion.difficulty === '基础' ? 'success' : currentDetailQuestion.difficulty === '中等' ? 'warning' : 'danger'" style="margin-left: 4px">{{ currentDetailQuestion.difficulty }}</el-tag>
          <el-tag v-if="currentDetailQuestion.grade_level" size="small" type="primary" style="margin-left: 4px">{{ currentDetailQuestion.grade_level }}</el-tag>
        </div>
        <div style="background: #f5f7fa; padding: 16px; border-radius: 6px; margin-bottom: 16px; white-space: pre-wrap" v-html="renderMath(currentDetailQuestion.question_text)"></div>
        <div v-if="currentDetailQuestion.has_image && currentDetailQuestion.image_path" style="margin-bottom: 16px; text-align: center">
          <el-image :src="encodeURI(currentDetailQuestion.image_path)" style="max-width: 500px" fit="contain" :preview-src-list="[encodeURI(currentDetailQuestion.image_path)]" preview-teleported />
        </div>
        <el-divider />
        <div>
          <strong>答案：</strong>
          <span v-html="renderMath((currentDetailRow?.ai_answer || currentDetailQuestion.answer) || '待补充')" />
          <el-tag v-if="currentDetailRow?.ai_answer" type="success" size="small" style="margin-left: 8px">AI生成</el-tag>
        </div>
        <div style="margin-top: 8px">
          <strong>解析：</strong>
          <span v-html="renderMath((currentDetailRow?.ai_solution || currentDetailQuestion.solution) || '待补充')" />
          <el-tag v-if="currentDetailRow?.ai_solution" type="success" size="small" style="margin-left: 8px">AI生成</el-tag>
        </div>
        <div style="margin-top: 8px">
          <strong>错误信息：</strong>
          类型：{{ currentDetailRow?.error_type || '-' }} ·
          考试：{{ currentDetailRow?.exam_name || '-' }} ·
          重做 {{ currentDetailRow?.redo_count || 0 }} 次
        </div>
      </div>
    </el-dialog>

    <!-- PDF 识别结果确认对话框 -->
    <RecognitionConfirmDialog
      :visible="pdfConfirmVisible"
      :result="pdfResult"
      @close="pdfConfirmVisible = false"
      @confirmed="onPdfConfirmed"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { listWrongQuestions, addWrongQuestion, deleteWrongQuestion, feedbackWrongQuestion, recognizeWrongQuestionImage, recognizeAdvanced, recognizePdf, getRecognitionProgress, getRecognitionTask, generateAnswer, checkDuplicate } from '../api/practice'
import { listQuestions, listCategories, createQuestion, uploadQuestionImage } from '../api/question'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UploadFilled, Loading } from '@element-plus/icons-vue'
import { renderMath } from '../utils/math'
import ScreenshotCropper from '../components/ScreenshotCropper.vue'
import RecognitionConfirmDialog from '../components/RecognitionConfirmDialog.vue'
import PdfRecognitionProgress from '../components/PdfRecognitionProgress.vue'

const wrongList = ref([])
const loading = ref(false)
const selectedWrongIds = ref(new Set())
const wrongTableRef = ref(null)
const pageNum = ref(1)
const pageSize = ref(15)
const totalCount = ref(0)

// ===== Detail dialog state =====
const detailVisible = ref(false)
const currentDetailQuestion = ref(null)
const currentDetailRow = ref(null)
const answerBackfillRefreshTimers = []

function showDetail(row) {
  currentDetailQuestion.value = row.question || row
  currentDetailRow.value = row
  detailVisible.value = true
}

function syncCurrentDetailRow() {
  const recordId = currentDetailRow.value?.record_id
  if (!recordId) return
  const latest = wrongList.value.find(item => item.record_id === recordId)
  if (!latest) return
  currentDetailRow.value = latest
  currentDetailQuestion.value = latest.question || latest
}

function clearAnswerBackfillRefreshTimers() {
  while (answerBackfillRefreshTimers.length) {
    clearTimeout(answerBackfillRefreshTimers.pop())
  }
}

function scheduleAnswerBackfillRefresh() {
  clearAnswerBackfillRefreshTimers()
  const delays = [4000, 12000, 25000]
  delays.forEach((delay) => {
    const timerId = setTimeout(async () => {
      try {
        await loadData()
      } catch (e) {
        // ignore background refresh errors
      }
    }, delay)
    answerBackfillRefreshTimers.push(timerId)
  })
}

// ===== Add dialog state =====
const addVisible = ref(false)
const addLoading = ref(false)
const addMode = ref('manual')
const addForm = ref({ question_id: '', exam_name: '', error_type: '', notes: '', exam_date: new Date().toISOString().split('T')[0] })

// ===== Manual select state =====
const categories = ref([])
const searchFilters = ref({ category: '', difficulty: '', keyword: '' })
const searchResults = ref([])
const searchLoading = ref(false)
const searchPage = ref(1)
const searchPageSize = ref(10)
const searchTotal = ref(0)
const selectedQuestion = ref(null)

// ===== Image upload state (merged file + screenshot) =====
const fileInputRef = ref(null)
const ocrLoading = ref(false)
const recognizedQuestions = ref([])
const ocrMatches = ref([])
const selectedMatch = ref(null)

// ===== Screenshot & crop state =====
const capturedImage = ref(null)
const capturedFile = ref(null) // original File/Blob from paste/drop/select
const cropperVisible = ref(false)
const dedupStatus = ref('')

// ===== PDF upload state =====
const pdfInputRef = ref(null)
const pdfFile = ref(null)
const pdfRecognizing = ref(false)
const pdfResult = ref(null)
const pdfConfirmVisible = ref(false)
const pdfPreparingConfirm = ref(false)
const pdfTaskId = ref(null)
const pdfProgress = ref({ current_page: 0, total_pages: 0, questions_found: 0, message: '' })
let progressTimer = null

// ===== Per-question image upload =====
const questionImageInputRefs = ref({})

function registerImageInputRef(index, el) {
  if (el) {
    questionImageInputRefs.value[index] = el
  }
}

function triggerQuestionImageSelect(index) {
  questionImageInputRefs.value[index]?.click()
}

function onQuestionImageSelected(e, index) {
  const file = e.target.files?.[0]
  if (!file || !file.type.startsWith('image/')) {
    ElMessage.warning('请选择图片文件')
    return
  }
  const q = recognizedQuestions.value[index]
  if (!q) return

  // Show local preview immediately
  const reader = new FileReader()
  reader.onload = () => { q._image_preview = reader.result }
  reader.readAsDataURL(file)

  // Upload to server
  q._image_uploading = true
  const fd = new FormData()
  fd.append('file', file)
  console.log('开始上传图片:', file.name, file.type, file.size)
  uploadQuestionImage(fd)
    .then(res => {
      console.log('图片上传成功:', res)
      q._image_url = res.url
      ElMessage.success('图片上传成功')
    })
    .catch(err => {
      console.error('图片上传失败:', err)
      console.error('错误详情:', err.response?.data)
      const errorMsg = err.response?.data?.detail || err.message || '图片上传失败'
      ElMessage.error(errorMsg)
    })
    .finally(() => { q._image_uploading = false })
  // Reset input
  e.target.value = ''
}

function removeQuestionImage(q) {
  q._image_preview = ''
  q._image_url = ''
}

// ===== Computed =====
const hasSelectedQuestion = computed(() => {
  if (addMode.value === 'manual') return selectedQuestion.value !== null
  if (addMode.value === 'image') return recognizedQuestions.value.some(q => q._selected)
  return false
})

const selectedQuestionCount = computed(() => {
  if (addMode.value !== 'image') return 0
  return recognizedQuestions.value.filter(q => q._selected).length
})

const totalPdfQuestions = computed(() => {
  if (!pdfResult.value) return 0
  let count = 0
  for (const page of pdfResult.value.pages || []) {
    count += page.questions?.length || 0
  }
  return count
})

const allSelectedFlag = ref(true)
const selectionIndeterminate = ref(false)

function toggleAllSelected(checked) {
  recognizedQuestions.value.forEach(q => { q._selected = checked })
  selectionIndeterminate.value = false
  allSelectedFlag.value = checked
}

function onSelectionChange() {
  const selected = recognizedQuestions.value.filter(q => q._selected)
  if (selected.length === 0) {
    allSelectedFlag.value = false
    selectionIndeterminate.value = false
  } else if (selected.length === recognizedQuestions.value.length) {
    allSelectedFlag.value = true
    selectionIndeterminate.value = false
  } else {
    allSelectedFlag.value = false
    selectionIndeterminate.value = true
  }
}

const errorStats = computed(() => {
  const stats = {}
  wrongList.value.forEach(w => {
    const type = w.error_type || '其他'
    stats[type] = (stats[type] || 0) + 1
  })
  return stats
})

// ===== Data loading =====
function formatCreatedDate(value) {
  if (!value) return '-'
  const text = String(value)
  if (text.length >= 16) {
    return text.slice(0, 16).replace('T', ' ')
  }
  return text.replace('T', ' ')
}

async function loadData() {
  loading.value = true
  try {
    const res = await listWrongQuestions({ page: pageNum.value, page_size: pageSize.value })
    wrongList.value = (res.wrong_questions || []).map(item => ({
      ...item,
      created_date: item.created_date || item.created_at || item.createdDate || item.exam_date || null,
    }))
    totalCount.value = res.total || 0
    syncCurrentDetailRow()
  } finally {
    loading.value = false
  }
}

function onPageChange(p) {
  pageNum.value = p
  loadData()
}

async function loadCategories() {
  try {
    const res = await listCategories()
    categories.value = res.categories || []
  } catch (e) { /* ignore */ }
}

// ===== Manual select: search questions =====
async function searchQuestions() {
  searchLoading.value = true
  searchResults.value = []
  try {
    const params = { page: searchPage.value, page_size: searchPageSize.value }
    if (searchFilters.value.category) params.knowledge_category = searchFilters.value.category
    if (searchFilters.value.difficulty) params.difficulty = searchFilters.value.difficulty
    if (searchFilters.value.keyword) params.keyword = searchFilters.value.keyword
    const res = await listQuestions(params)
    searchResults.value = res.questions || []
    searchTotal.value = res.total || 0
  } catch (e) {
    ElMessage.error('搜索题目失败')
  } finally {
    searchLoading.value = false
  }
}

function selectQuestion(row) {
  selectedQuestion.value = row
  addForm.value.question_id = row.question_id
}

function clearSelection() {
  selectedQuestion.value = null
  addForm.value.question_id = ''
}

// ===== Image handling (upload + paste + screenshot) =====

function triggerFileSelect() {
  fileInputRef.value?.click()
}

function onFileSelected(e) {
  const file = e.target.files?.[0]
  if (!file) return
  if (!file.type.startsWith('image/')) {
    ElMessage.warning('请选择图片文件')
    return
  }
  const reader = new FileReader()
  reader.onload = () => {
    capturedImage.value = reader.result
  }
  reader.readAsDataURL(file)
  capturedFile.value = file
  // Reset input so same file can be re-selected
  e.target.value = ''
}

function onDropImage(e) {
  const file = e.dataTransfer?.files?.[0]
  if (!file || !file.type.startsWith('image/')) {
    ElMessage.warning('请拖拽图片文件')
    return
  }
  const reader = new FileReader()
  reader.onload = () => {
    capturedImage.value = reader.result
  }
  reader.readAsDataURL(file)
  capturedFile.value = file
}

function clearCapturedImage() {
  capturedImage.value = null
  capturedFile.value = null
  recognizedQuestions.value = []
  ocrMatches.value = []
  selectedMatch.value = null
  dedupStatus.value = ''
  allSelectedFlag.value = true
  selectionIndeterminate.value = false
}

function openCropper() {
  if (capturedImage.value) {
    cropperVisible.value = true
  }
}

function skipCropAndRecognize() {
  if (!capturedImage.value) return
  if (capturedFile.value) {
    // Use original file to avoid re-encoding large images
    startRecognition(capturedFile.value)
  } else {
    // Fallback: convert data URL to Blob
    const blob = dataURLToBlob(capturedImage.value)
    const file = new File([blob], 'image.png', { type: 'image/png' })
    startRecognition(file)
  }
}

function dataURLToBlob(dataURL) {
  const parts = dataURL.split(',')
  const mime = parts[0].match(/:(.*?);/)[1]
  const bytes = atob(parts[1])
  const arr = new Uint8Array(bytes.length)
  for (let i = 0; i < bytes.length; i++) arr[i] = bytes.charCodeAt(i)
  return new Blob([arr], { type: mime })
}

// ===== Recognition flow =====

function startRecognition(file) {
  ocrLoading.value = true
  recognizedQuestions.value = []
  ocrMatches.value = []
  selectedMatch.value = null
  dedupStatus.value = ''

  const formData = new FormData()
  formData.append('file', file)

  recognizeWrongQuestionImage(formData)
    .then(res => {
      const qs = res.questions || (res.recognized ? [res.recognized] : [])
      const validQs = qs.filter(q => q.question_text?.trim())
      recognizedQuestions.value = validQs.map(q => ({
        ...q,
        _selected: true,
        knowledge_category: q.knowledge_category || '',
      })) || []
      allSelectedFlag.value = recognizedQuestions.value.length > 0
      selectionIndeterminate.value = false
      ocrMatches.value = res.matches || []

      dedupStatus.value = res.dedup_status || ''

      // 图像质量警告
      if (res.quality_score !== undefined) {
        const score = res.quality_score
        if (score < 0.5) {
          ElMessage.warning({
            message: `图像质量较差（${(score * 100).toFixed(0)}分），识别可能不准确。建议重新截图：确保清晰、光线充足、无模糊`,
            duration: 5000
          })
        } else if (score < 0.7) {
          ElMessage.info({
            message: `图像质量一般（${(score * 100).toFixed(0)}分），已自动增强处理`,
            duration: 3000
          })
        }
      }

      if (res.matched_question_id) {
        const matched = (res.matches || []).find(m => m.question_id === res.matched_question_id)
        if (matched) {
          selectedMatch.value = matched
          addForm.value.question_id = matched.question_id
        } else {
          addForm.value.question_id = res.matched_question_id
        }
        if (res.dedup_status === 'in_wrong') {
          ElMessage.info('该题已在错题本中')
        } else if (res.dedup_status === 'in_bank') {
          ElMessage.info('已在题库找到匹配题目，将仅加入错题本')
        }
      } else if (res.matches && res.matches.length === 1) {
        selectedMatch.value = res.matches[0]
        addForm.value.question_id = res.matches[0].question_id
        ElMessage.info('已自动匹配到题库中的题目')
      }

      if (!qs.length) {
        ElMessage.warning('AI 未能识别出题目，请确保图片清晰或重试')
      } else if (qs.length > 0 && !validQs.length) {
        ElMessage.warning('识别结果为空文本，请裁剪更大区域或使用更清晰的图片')
      } else if (res.generated_answer && !res.matched_question_id) {
        ElMessage.success('识别完成，答案已自动生成')
      } else {
        ElMessage.success('识别完成')
      }
    })
    .catch(e => {
      const detail = e.response?.data?.detail
      ElMessage.error(detail || '识别失败，请重试')
    })
    .finally(() => {
      ocrLoading.value = false
    })
}

function selectOcrMatch(row) {
  selectedMatch.value = row
  addForm.value.question_id = row.question_id
}

function clearOcrMatch() {
  selectedMatch.value = null
  addForm.value.question_id = ''
}

function previewOriginalImage() {
  if (!capturedImage.value) return
  // Use Element Plus image preview
  const viewer = document.createElement('div')
  viewer.innerHTML = `<el-image src="${capturedImage.value}" :preview-src-list="['${capturedImage.value}']" preview-teleported style="display:none" />`
  document.body.appendChild(viewer)
  viewer.querySelector('.el-image')?.click()
  setTimeout(() => document.body.removeChild(viewer), 100)
}

// ===== Screenshot & Clipboard =====
function triggerScreenshot() {
  if (!navigator.mediaDevices?.getDisplayMedia) {
    ElMessage.info('当前浏览器不支持截图，请使用 Ctrl+V 粘贴截图')
    return
  }
  navigator.mediaDevices.getDisplayMedia({ video: true })
    .then(stream => {
      const video = document.createElement('video')
      video.srcObject = stream
      video.onloadedmetadata = () => {
        video.play()
        const canvas = document.createElement('canvas')
        canvas.width = video.videoWidth
        canvas.height = video.videoHeight
        canvas.getContext('2d').drawImage(video, 0, 0)
        stream.getTracks().forEach(t => t.stop())
        capturedImage.value = canvas.toDataURL('image/png')
        canvas.toBlob(blob => { capturedFile.value = blob }, 'image/png')
        cropperVisible.value = true
      }
    })
    .catch(() => {
      // User cancelled or API unavailable
    })
}

function handlePaste(e) {
  if (!addVisible.value || addMode.value !== 'image' || ocrLoading.value) return
  const items = e.clipboardData?.items
  if (!items) return
  for (const item of items) {
    if (item.type.startsWith('image/')) {
      const blob = item.getAsFile()
      if (blob) {
        capturedFile.value = blob
        const reader = new FileReader()
        reader.onload = () => {
          capturedImage.value = reader.result
        }
        reader.readAsDataURL(blob)
        e.preventDefault()
      }
      break
    }
  }
}

function onCropConfirm(blob) {
  cropperVisible.value = false
  const file = new File([blob], 'cropped.png', { type: 'image/png' })
  startRecognition(file)
}

function onCropCancel() {
  cropperVisible.value = false
  // Don't clear capturedImage — user might want to re-crop or skip-crop
}

// ===== Show dialog =====
function showAddDialog() {
  const today = new Date().toISOString().split('T')[0]
  addForm.value = { question_id: '', exam_name: '', error_type: '', notes: '', exam_date: today }
  selectedQuestion.value = null
  recognizedQuestions.value = []
  ocrMatches.value = []
  selectedMatch.value = null
  searchResults.value = []
  searchFilters.value = { category: '', difficulty: '', keyword: '' }
  searchPage.value = 1
  addMode.value = 'manual'
  capturedImage.value = null
  capturedFile.value = null
  cropperVisible.value = false
  dedupStatus.value = ''
  allSelectedFlag.value = true
  selectionIndeterminate.value = false
  // PDF state reset
  stopProgressPolling()
  pdfFile.value = null
  pdfResult.value = null
  pdfRecognizing.value = false
  pdfConfirmVisible.value = false
  pdfPreparingConfirm.value = false
  pdfTaskId.value = null
  pdfProgress.value = { current_page: 0, total_pages: 0, questions_found: 0, message: '' }
  addVisible.value = true
}

// ===== Submit =====
async function handleAdd() {
  addLoading.value = true
  try {
    // Manual select mode: single question
    if (addMode.value === 'manual') {
      if (!addForm.value.question_id) {
        ElMessage.warning('请先选择题目')
        addLoading.value = false
        return
      }
      await addWrongQuestion(addForm.value)
      ElMessage.success('录入成功')
      addVisible.value = false
      await loadData()
      return
    }

    // Image upload mode: process only SELECTED questions
    const qs = recognizedQuestions.value.filter(q => q.question_text?.trim() && q._selected)
    if (!qs.length) {
      ElMessage.warning('请先勾选要录入的题目')
      addLoading.value = false
      return
    }

    let created = 0
    let added = 0
    let skipped = 0

    for (const q of qs) {
      let questionId = q._matched_question_id

      // If no match in bank, create a new question
      if (!questionId) {
        const qData = { ...q }
        // Use per-question image if uploaded
        if (q._image_url) {
          qData.image_path = q._image_url
        }
        try {
          const newQ = await createQuestion(qData)
          questionId = newQ.question_id
          created++
        } catch (e) {
          continue // skip this question if creation fails
        }
      }

      // Add to wrong question bank
      try {
        await addWrongQuestion({
          question_id: questionId,
          exam_name: addForm.value.exam_name,
          exam_date: addForm.value.exam_date,
          error_type: addForm.value.error_type,
          notes: addForm.value.notes,
        })
        added++
      } catch (e) {
        if (e.response?.status === 400) {
          // Already in wrong question bank
          skipped++
        }
      }
    }

    const parts = []
    if (created > 0) parts.push(`新建 ${created} 题`)
    if (added > 0) parts.push(`加入错题本 ${added} 题`)
    if (skipped > 0) parts.push(`${skipped} 题已在错题本中`)
    ElMessage.success(parts.join('，'))
    addVisible.value = false
    await loadData()
  } catch (e) {
    // interceptor handles 400 messages
  } finally {
    addLoading.value = false
  }
}

// ===== Feedback =====
const feedbackVisible = ref(false)
const feedbackForm = ref({ record_id: null, is_correct: true, error_type: '' })

function showFeedback(row) {
  feedbackForm.value = { record_id: row.record_id, is_correct: true, error_type: '' }
  feedbackVisible.value = true
}

async function handleFeedback() {
  try {
    await feedbackWrongQuestion(feedbackForm.value)
    ElMessage.success('反馈已记录')
    feedbackVisible.value = false
    await loadData()
  } catch (e) { /* ignore */ }
}

function onWrongSelectionChange(selection) {
  selectedWrongIds.value = new Set(selection.map(w => w.record_id))
}

async function handleBatchDelete() {
  const ids = [...selectedWrongIds.value]
  if (!ids.length) return
  try {
    await ElMessageBox.confirm(`确定删除选中的 ${ids.length} 条错题记录吗？`, '批量删除', { type: 'warning' })
  } catch { return }
  let success = 0
  for (const id of ids) {
    try { await deleteWrongQuestion(id); success++ } catch { /* continue */ }
  }
  ElMessage.success(`已删除 ${success} 条错题记录`)
  selectedWrongIds.value = new Set()
  wrongTableRef.value?.clearSelection()
  await loadData()
}

async function handleDelete(id) {
  try {
    await ElMessageBox.confirm('确定删除该错题记录吗？')
    await deleteWrongQuestion(id)
    ElMessage.success('已删除')
    await loadData()
  } catch (e) { /* ignore */ }
}

// ===== PDF upload functions =====

function triggerPdfSelect() {
  pdfInputRef.value?.click()
}

function onPdfFileSelected(e) {
  const file = e.target.files?.[0]
  if (!file) return
  if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
    ElMessage.warning('请选择 PDF 文件')
    return
  }
  if (file.size > 50 * 1024 * 1024) {
    ElMessage.warning('PDF 文件不能超过 50MB')
    return
  }
  pdfFile.value = file
  pdfResult.value = null
  pdfPreparingConfirm.value = false
  // Reset input so same file can be re-selected
  e.target.value = ''
}

function onDropPdf(e) {
  const file = e.dataTransfer?.files?.[0]
  if (!file) return
  if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
    ElMessage.warning('请拖拽 PDF 文件')
    return
  }
  if (file.size > 50 * 1024 * 1024) {
    ElMessage.warning('PDF 文件不能超过 50MB')
    return
  }
  pdfFile.value = file
  pdfResult.value = null
  pdfPreparingConfirm.value = false
}

function formatFileSize(bytes) {
  if (!bytes) return ''
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1024 / 1024).toFixed(1) + ' MB'
}

async function startPdfRecognition() {
  if (!pdfFile.value) return

  pdfRecognizing.value = true
  pdfResult.value = null
  pdfPreparingConfirm.value = false
  pdfProgress.value = { current_page: 0, total_pages: 0, questions_found: 0, message: '正在上传...' }

  const formData = new FormData()
  formData.append('file', pdfFile.value)
  formData.append('use_markdown', 'false')
  formData.append('recognition_mode', 'auto')
  formData.append('match_question_bank', 'true')
  formData.append('remove_correction_marks', 'true')

  try {
    // Step 1: Start async recognition
    const res = await recognizePdf(formData)
    pdfTaskId.value = res.task_id
    pdfProgress.value = {
      current_page: 0,
      total_pages: res.page_count,
      questions_found: 0,
      message: res.message || '识别任务已创建...',
    }

    // Step 2: Start polling for progress
    startProgressPolling()
  } catch (e) {
    const detail = e.response?.data?.detail
    // 显示错误信息
    if (detail) {
      ElMessage.error(detail)
    } else {
      ElMessage.error('PDF 识别请求失败，请重试')
    }
    pdfRecognizing.value = false
    pdfProgress.value = { current_page: 0, total_pages: 0, questions_found: 0, message: '' }
  }
}

function startProgressPolling() {
  stopProgressPolling() // Clear any existing timer
  progressTimer = setInterval(async () => {
    if (!pdfTaskId.value) return
    try {
      const progress = await getRecognitionProgress(pdfTaskId.value)
      pdfProgress.value = {
        current_page: progress.current_page || 0,
        total_pages: progress.total_pages || 0,
        questions_found: progress.questions_found || 0,
        message: progress.message || '',
        status: progress.status,
      }

      // Terminal states
      if (progress.status === 'need_confirm' || progress.status === 'partial_failed' || progress.status === 'failed' || progress.status === 'confirmed') {
        stopProgressPolling()
        pdfRecognizing.value = false

        if (progress.status === 'need_confirm' || progress.status === 'partial_failed') {
          // Fetch full result
          try {
            const fullResult = await getRecognitionTask(pdfTaskId.value)
            pdfResult.value = fullResult
            if (!fullResult.pages?.length || !fullResult.pages.some(p => p.questions?.length)) {
              ElMessage.warning('未能从 PDF 中识别出题目，请确认 PDF 清晰可读')
            } else if (progress.status === 'partial_failed') {
              ElMessage.warning(`部分页面识别失败，已识别 ${totalPdfQuestions.value} 道题，可先确认结果`)
            } else {
              ElMessage.success(`识别完成，共 ${fullResult.page_count} 页 ${totalPdfQuestions.value} 道题，答案已生成`)
            }
          } catch (e) {
            ElMessage.error('获取识别结果失败')
          }
        } else if (progress.status === 'failed') {
          ElMessage.error(progress.message || '识别失败')
        }
      }
    } catch (e) {
      // Silently ignore polling errors; will retry on next interval
    }
  }, 1500)
}

function stopProgressPolling() {
  if (progressTimer) {
    clearInterval(progressTimer)
    progressTimer = null
  }
}

function clearPdfFile() {
  stopProgressPolling()
  pdfFile.value = null
  pdfResult.value = null
  pdfConfirmVisible.value = false
  pdfPreparingConfirm.value = false
  pdfTaskId.value = null
  pdfProgress.value = { current_page: 0, total_pages: 0, questions_found: 0, message: '' }
  pdfRecognizing.value = false
}

async function openPdfConfirmDialog() {
  if (!pdfResult.value?.task_id || pdfPreparingConfirm.value) return
  pdfConfirmVisible.value = true
}

function onPdfConfirmed() {
  pdfConfirmVisible.value = false
  ElMessage.success('错题已加入错题本')
  addVisible.value = false
  loadData()
  scheduleAnswerBackfillRefresh()
}

onMounted(() => {
  loadData()
  loadCategories()
  document.addEventListener('paste', handlePaste)
})

onUnmounted(() => {
  document.removeEventListener('paste', handlePaste)
  stopProgressPolling()
  clearAnswerBackfillRefreshTimers()
})
</script>
