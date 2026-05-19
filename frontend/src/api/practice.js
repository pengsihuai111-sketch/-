import request from './request'

export function generateSheet(data) {
  return request.post('/practice/generate', data)
}

export function aiGeneratePreview(data) {
  return request.post('/practice/ai-generate-preview', data, {
    timeout: 180000,
  })
}

export function aiGenerateConfirm(data) {
  return request.post('/practice/ai-generate-confirm', data, {
    timeout: 60000,
  })
}

export function aiReplaceQuestion(data) {
  return request.post('/practice/ai-replace-question', data, {
    timeout: 30000,
  })
}

export function aiSupplementQuestion(data) {
  return request.post('/practice/ai-supplement-question', data, {
    timeout: 30000,
  })
}

export function generateWeekSheets() {
  return request.post('/practice/generate-week')
}

export function generateRedoSheet() {
  return request.post('/practice/generate-redo')
}

export function generateWrongPeriodSheet(data) {
  return request.post('/practice/generate-wrong-period', data)
}

export function generateSmartRedoSheet(data) {
  return request.post('/practice/generate-smart-redo', data)
}

export function listSheets() {
  return request.get('/practice/sheets')
}

export function getSheet(sheetId) {
  return request.get(`/practice/sheets/${sheetId}`)
}

export function deleteSheet(sheetId) {
  return request.delete(`/practice/sheets/${sheetId}`)
}

export function downloadSheet(sheetId) {
  const token = localStorage.getItem('token')
  return fetch(`/api/practice/sheets/${sheetId}/download`, {
    headers: { 'Authorization': `Bearer ${token}` },
  })
}

export function completeSheet(sheetId, data) {
  return request.post(`/practice/sheets/${sheetId}/complete`, data)
}

// 错题相关
export function listWrongQuestions(params = {}) {
  return request.get('/wrong-questions', { params })
}

export function addWrongQuestion(data) {
  return request.post('/wrong-questions', data)
}

export function deleteWrongQuestion(recordId) {
  return request.delete(`/wrong-questions/${recordId}`)
}

export function feedbackWrongQuestion(data) {
  return request.put('/wrong-questions/feedback', data)
}

export function recognizeWrongQuestionImage(formData) {
  return request.post('/wrong-questions/recognize', formData, {
    timeout: 180000,
  })
}

// 诊断
export function getDiagnosis() {
  return request.get('/wrong-questions/diagnosis')
}

export function getErrorAnalysis() {
  return request.get('/wrong-questions/error-analysis')
}

// 答案生成与去重
export function generateAnswer(data) {
  return request.post('/wrong-questions/generate-answer', data, { timeout: 60000 })
}

export function checkDuplicate(data) {
  return request.post('/wrong-questions/check-duplicate', data)
}

// 高级错题识别（带批改痕迹）
export function recognizeAdvanced(formData) {
  return request.post('/wrong-questions/recognize-advanced', formData, {
    timeout: 300000,
  })
}

// PDF 异步整卷识别（带进度轮询）
export function recognizePdf(formData) {
  return request.post('/wrong-questions/recognize-pdf', formData, {
    timeout: 60000,
  })
}

export function getRecognitionProgress(taskId) {
  return request.get(`/wrong-questions/recognition-tasks/${taskId}/progress`)
}

export function getRecognitionTask(taskId) {
  return request.get(`/wrong-questions/recognition-tasks/${taskId}`)
}

export function prepareRecognitionConfirmation(taskId) {
  return request.post(`/wrong-questions/recognition-tasks/${taskId}/prepare-confirmation`, null, {
    timeout: 180000,
  })
}

export function confirmRecognitionTask(taskId, data) {
  return request.post(`/wrong-questions/recognition-tasks/${taskId}/confirm`, data)
}

// 支付
export function createOrder(data) {
  return request.post('/payment/create-order', data)
}

export function payOrder(orderId) {
  return request.post(`/payment/pay/${orderId}`)
}

export function listOrders() {
  return request.get('/payment/orders')
}

export function getPrices() {
  return request.get('/payment/prices')
}

export function getMemberInfo() {
  return request.get('/payment/member-info')
}
