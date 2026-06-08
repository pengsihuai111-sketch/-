<template>
  <div class="assistant-page">
    <section class="assistant-hero">
      <div>
        <p class="eyebrow">AI Learning Agent</p>
        <h1>AI 学习助手</h1>
        <p class="hero-desc">
          可以帮你看错题、找薄弱点、讲题，也可以按你的描述生成练习单预览。
        </p>
      </div>
      <el-button type="primary" plain @click="startNewSession">开启新对话</el-button>
    </section>

    <section class="assistant-shell">
      <aside class="assistant-side">
        <div class="session-section">
          <div class="side-header">
            <div class="side-title">我的对话</div>
            <el-button size="small" type="primary" plain @click="startNewSession">新建</el-button>
          </div>
          <div v-if="sessions.length" class="session-list">
            <div
              v-for="session in sessions"
              :key="session.session_id"
              :class="['session-item', { active: session.session_id === sessionId }]"
            >
              <button class="session-open" type="button" @click="selectSession(session.session_id)">
                <span class="session-main">
                  <span class="session-title">{{ session.title || 'AI 学习助手' }}</span>
                  <span class="session-meta">
                    <span :class="['session-type', `type-${session.session_type || 'chat'}`]">
                      {{ getSessionTypeLabel(session.session_type) }}
                    </span>
                    <span v-if="session.summary" class="session-summary">{{ session.summary }}</span>
                  </span>
                  <span class="session-time">{{ formatSessionTime(session.updated_at || session.created_at) }}</span>
                </span>
              </button>
              <button
                class="session-delete"
                type="button"
                title="删除对话"
                @click.stop="removeSession(session.session_id)"
              >
                ×
              </button>
            </div>
          </div>
          <div v-else class="empty-session">还没有历史对话，发送第一条消息后会自动保存。</div>
        </div>

        <div class="prompt-section">
          <div class="side-title">可以这样问</div>
          <button
            v-for="item in quickPrompts"
            :key="item"
            class="prompt-chip"
            type="button"
            @click="sendMessage(item)"
          >
            {{ item }}
          </button>
        </div>
      </aside>

      <main class="chat-panel">
        <div v-if="currentSession" class="current-task-bar">
          <div>
            <span :class="['session-type', `type-${currentSession.session_type || 'chat'}`]">
              {{ getSessionTypeLabel(currentSession.session_type) }}
            </span>
            <strong>{{ currentSession.title || 'AI 学习助手' }}</strong>
          </div>
          <span>{{ currentSession.summary || '当前 AI 学习对话' }}</span>
        </div>
        <div ref="messageListRef" class="message-list">
          <div v-for="message in messages" :key="message.localId" :class="['message-row', message.role]">
            <div class="message-bubble">
              <div class="message-role">{{ message.role === 'user' ? '我' : 'AI 助手' }}</div>
              <div class="message-content" v-html="formatText(message.content)" />
              <div v-if="message.actions?.length" class="action-stack">
                <AssistantActionCard
                  v-for="(action, index) in message.actions"
                  :key="`${message.localId}-${index}`"
                  :action="action"
                />
              </div>
              <div v-if="message.suggestions?.length" class="suggestion-row">
                <el-button
                  v-for="suggestion in message.suggestions"
                  :key="suggestion"
                  size="small"
                  round
                  @click="sendMessage(suggestion)"
                >
                  {{ suggestion }}
                </el-button>
              </div>
            </div>
          </div>
          <div v-if="loading" class="message-row assistant">
            <div class="message-bubble loading-bubble">
              <span class="typing-dot" />
              <span class="typing-dot" />
              <span class="typing-dot" />
              <span>正在思考并调用学习工具...</span>
            </div>
          </div>
        </div>

        <div class="composer">
          <input
            ref="fileInputRef"
            class="hidden-file-input"
            type="file"
            accept="image/*,.pdf,.md,.markdown,.txt"
            @change="handleAttachmentChange"
          />
          <el-dropdown
            trigger="click"
            :disabled="loading"
            placement="top-start"
            @command="handleAttachmentCommand"
          >
            <el-button class="attach-plus-button" :disabled="loading" circle aria-label="添加附件">
              +
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="upload">上传附件</el-dropdown-item>
                <el-dropdown-item command="screenshot">屏幕截图</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
          <div class="composer-main">
            <div v-if="pendingAttachment" class="pending-attachment">
              <span>已选择：{{ pendingAttachment.name }}</span>
              <el-button size="small" link type="danger" @click="removePendingAttachment">移除</el-button>
            </div>
            <div v-else class="paste-tip">支持 Win+Shift+S 截图后直接 Ctrl+V 粘贴</div>
            <el-input
              v-model="input"
              type="textarea"
              :autosize="{ minRows: 2, maxRows: 5 }"
              :placeholder="pendingAttachment ? '补充你的需求，例如：帮我识别并解析图片里的全部题目 / 只讲第 1 题' : '例如：帮我分析最近 7 天错题，并生成一套计算和应用题练习'"
              resize="none"
              @keydown.enter.exact.prevent="sendMessage()"
            />
          </div>
          <el-button type="primary" :loading="loading" @click="sendMessage()">发送</el-button>
        </div>
      </main>
    </section>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import AssistantActionCard from '../components/assistant/AssistantActionCard.vue'
import {
  chatWithAssistant,
  deleteAssistantSession,
  listAssistantMessages,
  listAssistantSessions,
  uploadAssistantAttachment,
} from '../api/assistant'
import { renderMath } from '../utils/math'

const quickPrompts = [
  '生成一份家长周报',
  '生成一份家长月报',
  '看看我最近 7 天的错题',
  '分析我的薄弱知识点',
  '制定一份 7 天学习计划',
  '生成本周学习总结',
  '帮我生成一套错题举一反三练习单',
  '给我讲解一道题，我把题目发给你',
]

const SESSION_STORAGE_KEY = 'ai_assistant_current_session_id'

const sessionId = ref(localStorage.getItem(SESSION_STORAGE_KEY) || '')
const input = ref('')
const loading = ref(false)
const sessions = ref([])
const messageListRef = ref(null)
const fileInputRef = ref(null)
const pendingAttachment = ref(null)

const currentSession = computed(() => {
  if (!sessionId.value) return null
  return sessions.value.find((item) => item.session_id === sessionId.value) || null
})

function createLocalId(prefix = 'msg') {
  if (globalThis.crypto?.randomUUID) {
    return globalThis.crypto.randomUUID()
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

const createWelcomeMessage = (content = '你好，我是你的 AI 学习助手。你可以直接用自然语言告诉我想复习什么、哪里不会，或者让我根据错题生成练习。') => ({
    localId: createLocalId('welcome'),
    role: 'assistant',
    content,
    actions: [],
    suggestions: quickPrompts.slice(0, 3),
})

const messages = ref([createWelcomeMessage()])

function formatText(text) {
  return renderMath(String(text || '')).replace(/\n/g, '<br>')
}

async function scrollToBottom() {
  await nextTick()
  if (messageListRef.value) {
    messageListRef.value.scrollTop = messageListRef.value.scrollHeight
  }
}

function startNewSession() {
  sessionId.value = ''
  localStorage.removeItem(SESSION_STORAGE_KEY)
  messages.value = [createWelcomeMessage('新的对话已经开始。告诉我你的学习目标，我们从这里继续。')]
  pendingAttachment.value = null
  input.value = ''
}

function persistSession(nextSessionId) {
  sessionId.value = nextSessionId || ''
  if (sessionId.value) {
    localStorage.setItem(SESSION_STORAGE_KEY, sessionId.value)
  }
}

function normalizeHistoryMessages(rows = []) {
  return rows.map((item) => ({
    localId: `history-${item.message_id || createLocalId('history')}`,
    role: item.role,
    content: item.content || '',
    actions: item.actions || [],
    suggestions: [],
  }))
}

function formatSessionTime(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  const now = new Date()
  const sameDay = date.toDateString() === now.toDateString()
  if (sameDay) {
    return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  }
  return date.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })
}

function getSessionTypeLabel(type = 'chat') {
  const labels = {
    attachment: '文件',
    practice: '练习',
    diagnosis: '诊断',
    wrong_review: '错题',
    explanation: '讲题',
    search: '找题',
    study_plan: '计划',
    study_summary: '总结',
    parent_report: '家长',
    chat: '对话',
  }
  return labels[type] || '对话'
}

async function loadSessions() {
  try {
    sessions.value = await listAssistantSessions()
  } catch (error) {
    sessions.value = []
  }
}

async function selectSession(nextSessionId) {
  if (!nextSessionId || nextSessionId === sessionId.value || loading.value) return
  persistSession(nextSessionId)
  pendingAttachment.value = null
  input.value = ''
  try {
    const rows = await listAssistantMessages(nextSessionId)
    const historyMessages = normalizeHistoryMessages(rows || [])
    messages.value = historyMessages.length
      ? historyMessages
      : [createWelcomeMessage('这个对话还没有消息，可以从这里继续。')]
    await scrollToBottom()
  } catch (error) {
    ElMessage.error('加载对话失败')
  }
}

async function removeSession(targetSessionId) {
  try {
    await ElMessageBox.confirm('确定删除这个 AI 对话吗？删除后无法恢复。', '删除对话', {
      type: 'warning',
      closeOnClickModal: false,
      closeOnPressEscape: false,
    })
  } catch {
    return
  }
  try {
    await deleteAssistantSession(targetSessionId)
    if (targetSessionId === sessionId.value) {
      startNewSession()
    }
    await loadSessions()
    ElMessage.success('对话已删除')
  } catch (error) {
    ElMessage.error('删除对话失败')
  }
}

async function sendMessage(preset = '') {
  const text = String(preset || input.value || '').trim()
  if ((!text && !pendingAttachment.value) || loading.value) return
  if (pendingAttachment.value) {
    await sendAttachment(text)
    return
  }

  input.value = ''
  messages.value.push({
    localId: createLocalId('user'),
    role: 'user',
    content: text,
    actions: [],
    suggestions: [],
  })
  await scrollToBottom()

  loading.value = true
  try {
    const res = await chatWithAssistant({
      message: text,
      session_id: sessionId.value || undefined,
    })
    persistSession(res.session_id)
    messages.value.push({
      localId: createLocalId('assistant'),
      role: 'assistant',
      content: res.reply || '我已经处理完成。',
      actions: res.actions || [],
      suggestions: res.suggestions || [],
    })
    await loadSessions()
  } finally {
    loading.value = false
    await scrollToBottom()
  }
}

function triggerAttachmentUpload() {
  if (loading.value) return
  fileInputRef.value?.click()
}

function handleAttachmentCommand(command) {
  if (command === 'upload') {
    triggerAttachmentUpload()
    return
  }
  if (command === 'screenshot') {
    triggerScreenshot()
  }
}

async function handleAttachmentChange(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file || loading.value) return
  pendingAttachment.value = file
}

function buildScreenshotFile(blob, prefix = '截图') {
  const ext = blob.type?.includes('jpeg') ? 'jpg' : 'png'
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-')
  return new File([blob], `${prefix}-${timestamp}.${ext}`, {
    type: blob.type || 'image/png',
  })
}

function setScreenshotAttachment(blob, sourceText = '截图') {
  if (!blob || loading.value) return
  pendingAttachment.value = buildScreenshotFile(blob, sourceText)
  ElMessage.success('截图已添加为待上传附件，可以继续补充需求后发送')
}

function handlePaste(event) {
  if (loading.value) return
  const items = event.clipboardData?.items
  if (!items?.length) return

  for (const item of items) {
    if (!item.type?.startsWith('image/')) continue
    const blob = item.getAsFile()
    if (!blob) continue
    setScreenshotAttachment(blob, '粘贴截图')
    event.preventDefault()
    return
  }
}

async function triggerScreenshot() {
  if (loading.value) return
  if (!navigator.mediaDevices?.getDisplayMedia) {
    ElMessage.info('当前浏览器不支持屏幕截图，请使用 Win+Shift+S 后 Ctrl+V 粘贴截图')
    return
  }

  try {
    const stream = await navigator.mediaDevices.getDisplayMedia({ video: true })
    const video = document.createElement('video')
    video.srcObject = stream
    video.muted = true
    await new Promise((resolve) => {
      video.onloadedmetadata = resolve
    })
    await video.play()
    const canvas = document.createElement('canvas')
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    canvas.getContext('2d')?.drawImage(video, 0, 0)
    stream.getTracks().forEach((track) => track.stop())
    canvas.toBlob((blob) => {
      if (blob) {
        setScreenshotAttachment(blob, '屏幕截图')
      }
    }, 'image/png')
  } catch (error) {
    ElMessage.info('已取消截图')
  }
}

function removePendingAttachment() {
  pendingAttachment.value = null
}

async function sendAttachment(text = '') {
  const file = pendingAttachment.value
  messages.value.push({
    localId: createLocalId('upload'),
    role: 'user',
    content: text ? `上传附件：${file.name}\n需求：${text}` : `上传附件：${file.name}`,
    actions: [],
    suggestions: [],
  })
  await scrollToBottom()

  const formData = new FormData()
  formData.append('file', file)
  if (sessionId.value) {
    formData.append('session_id', sessionId.value)
  }
  if (text.trim()) {
    formData.append('message', text.trim())
  }

  input.value = ''
  pendingAttachment.value = null
  loading.value = true
  try {
    const res = await uploadAssistantAttachment(formData)
    persistSession(res.session_id)
    messages.value.push({
      localId: createLocalId('assistant'),
      role: 'assistant',
      content: res.reply || '我已经识别完附件。',
      actions: res.actions || [],
      suggestions: res.suggestions || [],
    })
    await loadSessions()
  } finally {
    loading.value = false
    await scrollToBottom()
  }
}

onMounted(async () => {
  document.addEventListener('paste', handlePaste)
  await loadSessions()
  if (!sessionId.value) return
  try {
    const rows = await listAssistantMessages(sessionId.value)
    const historyMessages = normalizeHistoryMessages(rows || [])
    if (historyMessages.length) {
      messages.value = historyMessages
      await scrollToBottom()
    }
  } catch (error) {
    sessionId.value = ''
    localStorage.removeItem(SESSION_STORAGE_KEY)
  }
})

onUnmounted(() => {
  document.removeEventListener('paste', handlePaste)
})
</script>

<style scoped>
.assistant-page {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 92px);
  min-height: 0;
  overflow: hidden;
  color: #102033;
}

.assistant-hero {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 14px;
  padding: 22px 28px;
  border-radius: 22px;
  background:
    radial-gradient(circle at 12% 18%, rgba(16, 185, 129, 0.22), transparent 30%),
    linear-gradient(135deg, #f7fff9 0%, #eef7ff 52%, #fff7e8 100%);
  border: 1px solid rgba(16, 185, 129, 0.16);
}

.assistant-hero :deep(.el-button) {
  min-width: 118px;
  color: #ffffff;
  background: #059669;
  border-color: #059669;
  font-weight: 700;
  box-shadow: 0 10px 22px rgba(5, 150, 105, 0.22);
}

.assistant-hero :deep(.el-button:hover) {
  color: #ffffff;
  background: #047857;
  border-color: #047857;
}

.eyebrow {
  margin: 0 0 8px;
  color: #0f9f6e;
  font-size: 12px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  font-weight: 700;
}

.assistant-hero h1 {
  margin: 0;
  font-size: 30px;
  line-height: 1.2;
}

.hero-desc {
  margin: 10px 0 0;
  color: #52616f;
  font-size: 15px;
}

.assistant-shell {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr);
  gap: 18px;
}

.assistant-side,
.chat-panel {
  border: 1px solid #e2e8f0;
  border-radius: 18px;
  background: #fff;
  box-shadow: 0 16px 42px rgba(15, 23, 42, 0.06);
}

.assistant-side {
  padding: 18px;
  height: fit-content;
  position: sticky;
  top: 16px;
  max-height: 100%;
  overflow-y: auto;
}

.session-section {
  padding-bottom: 16px;
  margin-bottom: 16px;
  border-bottom: 1px solid #e2e8f0;
}

.side-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 12px;
}

.side-title {
  margin-bottom: 12px;
  color: #334155;
  font-weight: 700;
}

.side-header .side-title {
  margin-bottom: 0;
}

.session-list {
  display: grid;
  gap: 8px;
}

.session-item {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 26px;
  align-items: center;
  gap: 6px;
  padding: 4px;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  background: #f8fafc;
  transition: all 0.18s ease;
}

.session-item:hover {
  border-color: #99f6e4;
  background: #f0fdfa;
}

.session-item.active {
  border-color: #10b981;
  background: linear-gradient(135deg, #ecfdf5, #f0fdfa);
  box-shadow: inset 3px 0 0 #10b981;
}

.session-open {
  min-width: 0;
  padding: 8px 6px 8px 10px;
  text-align: left;
  color: #0f172a;
  background: transparent;
  border: 0;
  cursor: pointer;
}

.session-main,
.session-title,
.session-time,
.session-meta {
  display: block;
}

.session-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
  font-weight: 700;
}

.session-time {
  margin-top: 4px;
  color: #64748b;
  font-size: 12px;
}

.session-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  margin-top: 6px;
}

.session-type {
  flex: 0 0 auto;
  padding: 2px 6px;
  border-radius: 999px;
  color: #047857;
  background: #d1fae5;
  font-size: 11px;
  font-weight: 800;
}

.session-type.type-attachment {
  color: #0369a1;
  background: #e0f2fe;
}

.session-type.type-practice {
  color: #9a3412;
  background: #ffedd5;
}

.session-type.type-diagnosis,
.session-type.type-wrong_review {
  color: #b91c1c;
  background: #fee2e2;
}

.session-type.type-explanation {
  color: #6d28d9;
  background: #ede9fe;
}

.session-type.type-parent_report,
.session-type.type-study_plan,
.session-type.type-study_summary {
  color: #0f766e;
  background: #ccfbf1;
}

.session-summary {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #64748b;
  font-size: 12px;
}

.session-delete {
  width: 24px;
  height: 24px;
  padding: 0;
  border: 0;
  border-radius: 999px;
  color: #94a3b8;
  background: transparent;
  cursor: pointer;
  font-size: 18px;
  line-height: 22px;
}

.session-delete:hover {
  color: #ef4444;
  background: #fee2e2;
}

.empty-session {
  padding: 12px;
  border: 1px dashed #bae6fd;
  border-radius: 14px;
  color: #64748b;
  background: #f8fafc;
  font-size: 13px;
  line-height: 1.6;
}

.prompt-section {
  min-height: 0;
}

.prompt-chip {
  width: 100%;
  margin-bottom: 10px;
  padding: 12px 14px;
  text-align: left;
  color: #064e3b;
  background: #f0fdfa;
  border: 1px solid #99f6e4;
  border-radius: 14px;
  cursor: pointer;
  font-weight: 700;
  line-height: 1.45;
  transition: all 0.18s ease;
}

.prompt-chip:hover {
  transform: translateY(-1px);
  border-color: #10b981;
  background: #dcfce7;
}

.chat-panel {
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

.current-task-bar {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 12px 18px;
  border-bottom: 1px solid #e2e8f0;
  color: #334155;
  background: linear-gradient(135deg, #ffffff, #f8fafc);
}

.current-task-bar > div {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.current-task-bar strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.current-task-bar > span {
  flex: 0 1 auto;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #64748b;
  font-size: 13px;
}

.message-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 22px;
  scroll-behavior: smooth;
  background:
    linear-gradient(rgba(255,255,255,0.88), rgba(255,255,255,0.92)),
    repeating-linear-gradient(135deg, rgba(16, 185, 129, 0.08) 0 1px, transparent 1px 18px);
}

.message-row {
  display: flex;
  margin-bottom: 16px;
}

.message-row.user {
  justify-content: flex-end;
}

.message-bubble {
  max-width: min(860px, 88%);
  padding: 14px 16px;
  border-radius: 18px;
  background: #fff;
  border: 1px solid #e2e8f0;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
}

.message-row.user .message-bubble {
  color: #fff;
  background: linear-gradient(135deg, #10b981, #059669);
  border-color: transparent;
}

.message-role {
  margin-bottom: 6px;
  font-size: 12px;
  font-weight: 700;
  opacity: 0.72;
}

.message-content {
  line-height: 1.75;
  word-break: break-word;
}

.suggestion-row :deep(.el-button) {
  color: #0f5132;
  background: #ffffff;
  border-color: #86efac;
  font-weight: 700;
}

.suggestion-row :deep(.el-button:hover) {
  color: #ffffff;
  background: #059669;
  border-color: #059669;
}

.action-stack {
  display: grid;
  gap: 12px;
  margin-top: 14px;
}

.suggestion-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}

.loading-bubble {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #475569;
}

.typing-dot {
  width: 7px;
  height: 7px;
  border-radius: 999px;
  background: #10b981;
  animation: typing 1s infinite ease-in-out;
}

.typing-dot:nth-child(2) {
  animation-delay: 0.15s;
}

.typing-dot:nth-child(3) {
  animation-delay: 0.3s;
}

.composer {
  position: sticky;
  bottom: 0;
  z-index: 5;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) 96px;
  align-items: end;
  gap: 12px;
  padding: 14px 16px;
  border-top: 1px solid #e2e8f0;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.96), #ffffff),
    #ffffff;
  box-shadow: 0 -12px 28px rgba(15, 23, 42, 0.08);
}

.composer :deep(.el-button) {
  min-height: 36px;
  color: #064e3b;
  border-color: #99f6e4;
  font-weight: 700;
}

.composer :deep(.el-button:hover) {
  color: #047857;
  border-color: #10b981;
  background: #ecfdf5;
}

.composer > :deep(.el-button--primary) {
  color: #ffffff;
  background: #059669;
  border-color: #059669;
}

.composer > :deep(.el-button--primary:hover) {
  color: #ffffff;
  background: #047857;
  border-color: #047857;
}

.attach-plus-button {
  width: 44px;
  height: 44px;
  padding: 0;
  font-size: 28px;
  line-height: 1;
  color: #ffffff !important;
  background: #059669 !important;
  border-color: #059669 !important;
  box-shadow: 0 10px 22px rgba(5, 150, 105, 0.22);
}

.attach-plus-button:hover,
.attach-plus-button:focus {
  color: #ffffff !important;
  background: #047857 !important;
  border-color: #047857 !important;
}

.composer-main {
  display: grid;
  gap: 8px;
}

.pending-attachment {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 10px;
  border: 1px solid #bbf7d0;
  border-radius: 12px;
  color: #047857;
  background: #ecfdf5;
  font-size: 13px;
}

.pending-attachment span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.paste-tip {
  color: #94a3b8;
  font-size: 12px;
}

.hidden-file-input {
  display: none;
}

@keyframes typing {
  0%, 80%, 100% {
    transform: translateY(0);
    opacity: 0.45;
  }
  40% {
    transform: translateY(-5px);
    opacity: 1;
  }
}

@media (max-width: 900px) {
  .assistant-shell {
    grid-template-columns: 1fr;
  }

  .assistant-side {
    position: static;
    max-height: 190px;
  }

  .assistant-hero {
    align-items: flex-start;
    flex-direction: column;
  }

  .composer {
    grid-template-columns: 1fr;
    position: sticky;
  }
}
</style>
