import request from './request'

export function chatWithAssistant(data) {
  return request.post('/assistant/chat', data, {
    timeout: 180000,
  })
}

export function uploadAssistantAttachment(formData) {
  return request.post('/assistant/upload', formData, {
    timeout: 240000,
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })
}

export function listAssistantSessions() {
  return request.get('/assistant/sessions')
}

export function listAssistantMessages(sessionId) {
  return request.get(`/assistant/sessions/${sessionId}/messages`)
}

export function deleteAssistantSession(sessionId) {
  return request.delete(`/assistant/sessions/${sessionId}`)
}
