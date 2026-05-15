import request from './request'

export function listQuestions(params) {
  return request.get('/questions', { params })
}

export function getQuestion(id) {
  return request.get(`/questions/${id}`)
}

export function listKnowledgePoints() {
  return request.get('/questions/knowledge-points/list')
}

export function listCategories() {
  return request.get('/questions/categories/list')
}

export function createQuestion(data) {
  return request.post('/questions', data)
}

export function batchImport(data) {
  return request.post('/questions/batch', data)
}

export function getQuestionStats() {
  return request.get('/questions/stats')
}

export function listGrades() {
  return request.get('/questions/grades/list')
}

export function recognizeQuestions(formData) {
  return request.post('/questions/recognize', formData, {
    timeout: 180000,
  })
}

export function recognizePdf(formData) {
  return request.post('/questions/recognize-pdf', formData, {
    timeout: 600000,
  })
}

export function uploadQuestionImage(formData) {
  return request.post('/questions/upload-image', formData, {
    timeout: 60000,
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  })
}

export function deleteQuestion(questionId) {
  return request.delete(`/questions/${questionId}`)
}

export function batchDeleteQuestions(data) {
  return request.post('/questions/batch-delete', data)
}
