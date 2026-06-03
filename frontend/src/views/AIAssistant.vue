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
      </aside>

      <main class="chat-panel">
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
          <div class="attachment-actions">
            <el-button :disabled="loading" @click="triggerAttachmentUpload">上传附件</el-button>
            <el-button :disabled="loading" @click="triggerScreenshot">屏幕截图</el-button>
          </div>
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
              :placeholder="pendingAttachment ? '补充你的需求，例如：帮我识别并讲解第 1 题 / 提取题目和答案' : '例如：帮我分析最近 7 天错题，并生成一套计算和应用题练习'"
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
import { nextTick, onMounted, onUnmounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import AssistantActionCard from '../components/assistant/AssistantActionCard.vue'
import { chatWithAssistant, listAssistantMessages, uploadAssistantAttachment } from '../api/assistant'
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
const messageListRef = ref(null)
const fileInputRef = ref(null)
const pendingAttachment = ref(null)

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
  } finally {
    loading.value = false
    await scrollToBottom()
  }
}

function triggerAttachmentUpload() {
  if (loading.value) return
  fileInputRef.value?.click()
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
  if (input.value.trim()) {
    formData.append('message', input.value.trim())
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
  } finally {
    loading.value = false
    await scrollToBottom()
  }
}

onMounted(async () => {
  document.addEventListener('paste', handlePaste)
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
  min-height: calc(100vh - 92px);
  color: #102033;
}

.assistant-hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 18px;
  padding: 28px 32px;
  border-radius: 22px;
  background:
    radial-gradient(circle at 12% 18%, rgba(16, 185, 129, 0.22), transparent 30%),
    linear-gradient(135deg, #f7fff9 0%, #eef7ff 52%, #fff7e8 100%);
  border: 1px solid rgba(16, 185, 129, 0.16);
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
}

.side-title {
  margin-bottom: 12px;
  color: #334155;
  font-weight: 700;
}

.prompt-chip {
  width: 100%;
  margin-bottom: 10px;
  padding: 12px 14px;
  text-align: left;
  color: #0f5132;
  background: #ecfdf5;
  border: 1px solid #bbf7d0;
  border-radius: 14px;
  cursor: pointer;
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
  min-height: 660px;
  overflow: hidden;
}

.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 22px;
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
  max-width: min(780px, 88%);
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
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) 96px;
  align-items: end;
  gap: 12px;
  padding: 16px;
  border-top: 1px solid #e2e8f0;
  background: #fff;
}

.attachment-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
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
  }

  .assistant-hero {
    align-items: flex-start;
    flex-direction: column;
  }

  .composer {
    grid-template-columns: 1fr;
  }
}
</style>
