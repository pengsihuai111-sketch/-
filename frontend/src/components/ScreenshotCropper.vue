<template>
  <el-dialog :model-value="visible" title="裁剪题目区域" width="960px" top="3vh" :close-on-click-modal="false" @close="handleCancel" append-to-body>
    <div style="text-align:center;margin-bottom:8px;color:#909399;font-size:13px">
      鼠标拖拽选择题目区域，按 <kbd>Enter</kbd> 确认，<kbd>Esc</kbd> 取消
    </div>
    <div ref="containerRef" style="position:relative;max-height:700px;overflow:hidden;border:1px solid #dcdfe6;border-radius:4px;cursor:crosshair;background:#f5f5f5">
      <canvas
        ref="canvasRef"
        style="display:block;max-width:100%"
        @mousedown="onMouseDown"
        @mousemove="onMouseMove"
        @mouseup="onMouseUp"
        @mouseleave="onMouseUp"
      />
    </div>
    <template #footer>
      <el-button @click="handleCancel">取消</el-button>
      <el-button type="primary" @click="handleConfirm" :disabled="!hasSelection">确认裁剪</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch, nextTick, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  visible: Boolean,
  imageSrc: { type: String, default: '' },
})

const emit = defineEmits(['confirm', 'cancel'])

const canvasRef = ref(null)
const containerRef = ref(null)

// Selection state (canvas pixel coords)
let isDragging = false
let startX = 0, startY = 0
let selX = 0, selY = 0, selW = 0, selH = 0
let image = null
let scale = 1          // originalImageWidth / canvasWidth
let imgW = 0, imgH = 0 // canvas pixel dimensions

const hasSelection = ref(false)

function draw() {
  const canvas = canvasRef.value
  if (!canvas || !image) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  canvas.width = imgW
  canvas.height = imgH

  // Draw image (scaled to fit canvas)
  ctx.drawImage(image, 0, 0, imgW, imgH)

  if (selW > 0 && selH > 0) {
    // Draw 4 dim rectangles AROUND the selection (so image shows through inside)
    ctx.fillStyle = 'rgba(0,0,0,0.35)'
    // Top
    ctx.fillRect(0, 0, imgW, selY)
    // Bottom
    ctx.fillRect(0, selY + selH, imgW, imgH - selY - selH)
    // Left
    ctx.fillRect(0, selY, selX, selH)
    // Right
    ctx.fillRect(selX + selW, selY, imgW - selX - selW, selH)

    // Selection border
    ctx.strokeStyle = '#409eff'
    ctx.lineWidth = 2.5
    ctx.setLineDash([6, 4])
    ctx.strokeRect(selX, selY, selW, selH)

    // Corner handles
    ctx.setLineDash([])
    ctx.fillStyle = '#409eff'
    const hs = 8
    const corners = [
      [selX, selY],
      [selX + selW, selY],
      [selX, selY + selH],
      [selX + selW, selY + selH],
    ]
    for (const [cx, cy] of corners) {
      ctx.fillRect(cx - hs / 2, cy - hs / 2, hs, hs)
    }
  } else {
    // No selection yet
    ctx.fillStyle = 'rgba(0,0,0,0.06)'
    ctx.fillRect(0, 0, imgW, imgH)
  }
}

function getMousePos(e) {
  const rect = canvasRef.value.getBoundingClientRect()
  // In canvas pixel coords (canvas handles CSS scaling internally)
  return {
    x: (e.clientX - rect.left) * (canvasRef.value.width / rect.width),
    y: (e.clientY - rect.top) * (canvasRef.value.height / rect.height),
  }
}

function onMouseDown(e) {
  if (e.button !== 0) return
  isDragging = true
  const pos = getMousePos(e)
  startX = pos.x
  startY = pos.y
  selX = startX
  selY = startY
  selW = 0
  selH = 0
  hasSelection.value = false
}

function onMouseMove(e) {
  if (!isDragging) return
  e.preventDefault()
  const pos = getMousePos(e)
  const curX = Math.max(0, Math.min(pos.x, imgW))
  const curY = Math.max(0, Math.min(pos.y, imgH))

  selX = Math.min(startX, curX)
  selY = Math.min(startY, curY)
  selW = Math.abs(curX - startX)
  selH = Math.abs(curY - startY)

  hasSelection.value = selW > 5 && selH > 5
  draw()
}

const MIN_CROP = 40

function onMouseUp() {
  isDragging = false
  if (selW > 0 && selW < MIN_CROP) selW = MIN_CROP
  if (selH > 0 && selH < MIN_CROP) selH = MIN_CROP
  if (selW > 0 && selH > 0) hasSelection.value = true
}

function onKeyDown(e) {
  if (!props.visible) return
  if (e.key === 'Enter' && hasSelection.value) {
    e.preventDefault()
    handleConfirm()
  } else if (e.key === 'Escape') {
    e.preventDefault()
    handleCancel()
  }
}

function handleConfirm() {
  if (!hasSelection.value || !image) return
  // Convert canvas pixels to original image pixels
  const cropX = Math.round(selX * scale)
  const cropY = Math.round(selY * scale)
  const cropW = Math.round(selW * scale)
  const cropH = Math.round(selH * scale)

  const c = document.createElement('canvas')
  c.width = cropW
  c.height = cropH
  const ctx = c.getContext('2d')
  ctx.drawImage(image, cropX, cropY, cropW, cropH, 0, 0, cropW, cropH)
  c.toBlob((blob) => {
    if (blob) {
      emit('confirm', blob)
    }
  }, 'image/png')
}

function handleCancel() {
  emit('cancel')
}

function loadImage() {
  if (!props.imageSrc || !canvasRef.value) return
  const img = new Image()
  img.onload = () => {
    image = img
    const container = containerRef.value
    if (!container) return
    const maxW = container.clientWidth - 2
    const maxH = Math.min(700, container.clientHeight - 2)
    const ratio = Math.min(maxW / img.width, maxH / img.height, 1)
    imgW = Math.round(img.width * ratio)
    imgH = Math.round(img.height * ratio)
    scale = img.width / imgW

    selX = 0; selY = 0; selW = 0; selH = 0
    hasSelection.value = false
    draw()
  }
  img.src = props.imageSrc
}

watch(() => props.visible, (v) => {
  if (v) nextTick(() => loadImage())
})

onMounted(() => {
  window.addEventListener('keydown', onKeyDown)
  if (props.visible) nextTick(() => loadImage())
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeyDown)
})
</script>
