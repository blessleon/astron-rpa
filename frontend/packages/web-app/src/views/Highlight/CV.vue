<!-- @format -->

<script lang="ts" setup>
import { ref, computed, onMounted } from 'vue'
import { windowManager, utilsManager } from '@/platform'
import { DrawRect } from './config'

const props = defineProps<{
  cvStep: string
  targetRect?: DrawRect | null
}>()
// ─── Emits ───────────────────────────────────────────────────────────────────
const emit = defineEmits(['save', 'confirmAlt', 'reselectAlt', 'sendScreenshot'])

// ─── Screenshot state ────────────────────────────────────────────────────────
const screenshotDataUrl = ref<string>('')
const isLoading = ref(true)

// ─── Selection drag state ────────────────────────────────────────────────────
const isSelecting = ref(false)
const startPos = ref({ x: 0, y: 0 })
const currentPos = ref({ x: 0, y: 0 })
const hasSelection = ref(false)

// ─── Computed ─────────────────────────────────────────────────────────────────
const dpr = window.devicePixelRatio || 1

// cv_alt 模式：显示智能拾取的高亮位置
const isCvAltMode = computed(() => props.cvStep === 'cv_alt')
// cv_alt 模式下，有 targetRect 即视为有选区
const hasAltSelection = computed(() => isCvAltMode.value && !!props.targetRect)

const selection = computed(() => {
  // cv_alt 模式：使用后端返回的 targetRect
  if (isCvAltMode.value && props.targetRect) {
    return {
      x: props.targetRect.Left / dpr,
      y: props.targetRect.Top / dpr,
      width: (props.targetRect.Right - props.targetRect.Left) / dpr,
      height: (props.targetRect.Bottom - props.targetRect.Top) / dpr,
    }
  }

  // cv_ctrl 模式：使用用户手动选择的区域
  const x = Math.min(startPos.value.x, currentPos.value.x)
  const y = Math.min(startPos.value.y, currentPos.value.y)
  const width = Math.abs(currentPos.value.x - startPos.value.x)
  const height = Math.abs(currentPos.value.y - startPos.value.y)
  return { x, y, width, height }
})

const topOverlayStyle = computed(() => ({
  top: 0,
  left: 0,
  right: 0,
  height: `${selection.value.y}px`,
}))

const bottomOverlayStyle = computed(() => ({
  left: 0,
  right: 0,
  top: `${selection.value.y + selection.value.height}px`,
  bottom: 0,
}))

const leftOverlayStyle = computed(() => ({
  top: `${selection.value.y}px`,
  left: 0,
  width: `${selection.value.x}px`,
  height: `${selection.value.height}px`,
}))

const rightOverlayStyle = computed(() => ({
  top: `${selection.value.y}px`,
  left: `${selection.value.x + selection.value.width}px`,
  right: 0,
  height: `${selection.value.height}px`,
}))

const selectionBoxStyle = computed(() => ({
  left: `${selection.value.x}px`,
  top: `${selection.value.y}px`,
  width: `${selection.value.width}px`,
  height: `${selection.value.height}px`,
}))

// 按钮栏紧贴选区右下角，靠近屏幕边界时自动内缩
const actionBarStyle = computed(() => {
  const sel = selection.value
  const barHeight = 36
  const margin = 8
  const preferTop = sel.y + sel.height + margin
  const fallbackTop = sel.y - barHeight - margin
  const top = preferTop + barHeight <= window.innerHeight ? preferTop : Math.max(0, fallbackTop)

  const isNearLeftEdge = sel.x + sel.width + margin < 150
  if (isNearLeftEdge) {
    return {
      left: `${Math.max(0, sel.x)}px`,
      top: `${top}px`,
    }
  }

  return {
    left: `${sel.x + sel.width}px`,
    top: `${top}px`,
    transform: 'translateX(-100%)',
  }
})

// ─── Mouse event handlers ─────────────────────────────────────────────────────
function onMouseDown(e: MouseEvent) {
  // cv_alt 模式下禁用手动选择
  if (isCvAltMode.value) return
  if (e.button !== 0) return
  // 点击按钮区域时不重置选区
  if ((e.target as HTMLElement).closest('.cv-action-bar')) return
  isSelecting.value = true
  hasSelection.value = false
  startPos.value = { x: e.clientX, y: e.clientY }
  currentPos.value = { x: e.clientX, y: e.clientY }
  e.preventDefault()
}

function onMouseMove(e: MouseEvent) {
  if (!isSelecting.value) return
  currentPos.value = { x: e.clientX, y: e.clientY }
}

function onMouseUp(e: MouseEvent) {
  if (!isSelecting.value) return
  isSelecting.value = false
  currentPos.value = { x: e.clientX, y: e.clientY }
  if (selection.value.width > 5 && selection.value.height > 5) {
    hasSelection.value = true
  }
}

function onMouseLeave() {
  if (isSelecting.value) {
    isSelecting.value = false
  }
}

// ─── Actions ──────────────────────────────────────────────────────────────────
function cancelSelection() {
  hasSelection.value = false
  isSelecting.value = false
}

function saveSelection() {
  if (!screenshotDataUrl.value) return
  const img = new Image()
  img.src = screenshotDataUrl.value
  img.onload = async () => {
    const sel = selection.value
    // 用图片自然像素与视口的实际比值换算，比直接使用 dpr 更精确
    // 避免 Electron 窗口缩放或 display.scaleFactor 与 window.devicePixelRatio 的细微差异导致模糊
    const scaleX = img.naturalWidth / window.innerWidth
    const scaleY = img.naturalHeight / window.innerHeight
    const srcX = Math.round(sel.x * scaleX)
    const srcY = Math.round(sel.y * scaleY)
    const srcW = Math.round(sel.width * scaleX)
    const srcH = Math.round(sel.height * scaleY)
    const canvas = document.createElement('canvas')
    canvas.width = srcW
    canvas.height = srcH
    const ctx = canvas.getContext('2d')!
    ctx.drawImage(img, srcX, srcY, srcW, srcH, 0, 0, srcW, srcH)
    const imageDataUrl = canvas.toDataURL('image/png')

    emit('save', {
      imageDataUrl,
      position: { x: sel.x, y: sel.y, width: sel.width, height: sel.height },
    })
    console.log('Selected area:', sel)
  }
}

// cv_alt 模式的操作
function confirmAltSelection() {
  emit('confirmAlt')
}

function reselectAlt() {
  emit('reselectAlt')
}

// ─── Lifecycle ────────────────────────────────────────────────────────────────
onMounted(async () => {
  windowManager.setWindowAlwaysOnTop(true)
  try {
    const dataUrl = await utilsManager.invoke('capture-screen')
    if (dataUrl) {
      screenshotDataUrl.value = dataUrl as string
    }
    if (props.cvStep === 'cv_alt') {
      // cv_alt 模式下直接显示后端分析的选区，不允许手动选择
      hasSelection.value = false
      emit('sendScreenshot', screenshotDataUrl.value)
    }
  }
  catch (err) {
    console.error('[CV] Failed to capture screen:', err)
  }
  finally {
    windowManager.showWindow()
    isLoading.value = false
  }
})
</script>

<template>
  <div class="cv-container" @mousedown="onMouseDown" @mousemove="onMouseMove" @mouseup="onMouseUp" @mouseleave="onMouseLeave">
    <!-- 截图作为全屏背景 -->
    <img v-if="screenshotDataUrl" class="cv-screenshot" :src="screenshotDataUrl" draggable="false" alt="" />

      <!-- 无选区时：整屏黑色半透明遮罩 -->
      <div v-if="!isSelecting && !hasSelection && !isCvAltMode" class="cv-overlay cv-overlay--full" />

      <!-- 有选区时：四块遮罩围绕选区，选区内透明 -->
      <template v-if="hasSelection || isSelecting">
        <div class="cv-overlay" :style="topOverlayStyle" />
        <div class="cv-overlay" :style="bottomOverlayStyle" />
        <div class="cv-overlay" :style="leftOverlayStyle" />
        <div class="cv-overlay" :style="rightOverlayStyle" />
      </template>

      <!-- 选区边框 + 角标 -->
      <div
        v-if="isSelecting || hasSelection"
        class="cv-selection-box"
        :style="selectionBoxStyle"
      >
        <!-- <span class="cv-size-label">{{ selection.width }} × {{ selection.height }}</span> -->
        <span class="cv-corner cv-corner--tl" />
        <span class="cv-corner cv-corner--tr" />
        <span class="cv-corner cv-corner--bl" />
        <span class="cv-corner cv-corner--br" />
      </div>

    <!-- cv_alt 模式：保存 / 重新选择 -->
    <div v-if="hasAltSelection" class="cv-action-bar" :style="actionBarStyle">
      <button class="cv-btn cv-btn--cancel" @mousedown.stop @click.stop="reselectAlt">重新选择</button>
      <button class="cv-btn cv-btn--save" @mousedown.stop @click.stop="confirmAltSelection">保存</button>
    </div>

    <!-- cv_ctrl 模式：取消 / 保存 -->
    <div v-else-if="hasSelection && !isSelecting" class="cv-action-bar" :style="actionBarStyle">
      <button class="cv-btn cv-btn--cancel" @mousedown.stop @click.stop="cancelSelection">取消</button>
      <button class="cv-btn cv-btn--save" @mousedown.stop @click.stop="saveSelection">保存</button>
    </div>

    <!-- 提示信息 -->
    <div v-else-if="!hasSelection && !isSelecting && !isCvAltMode" class="cv-tip">拖动鼠标框选目标区域</div>
  </div>
</template>

<style lang="scss" scoped>
.cv-container {
  position: fixed;
  inset: 0;
  cursor: crosshair;
  user-select: none;
  overflow: hidden;
  animation: fadeIn ease-in 0.3s forwards;
}

.cv-screenshot {
  position: fixed;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  pointer-events: none;
  animation: fadeIn ease-in 0.2s forwards;
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

.cv-overlay {

  position: fixed;
  background: rgba(0, 0, 0, 0.4);
  pointer-events: none;
  &--full {
    inset: 0;
  }
}

.cv-selection-box {
  position: fixed;
  border: 1px solid rgba(255, 255, 255, 0.9);
  pointer-events: none;
  box-sizing: border-box;

  &--alt {
    border: 2px solid #1677ff;
    box-shadow: 0 0 0 2px rgba(22, 119, 255, 0.2);
  }

  .cv-size-label {
    position: absolute;
    top: -22px;
    left: 0;
    font-size: 11px;
    color: #fff;
    background: rgba(0, 0, 0, 0.65);
    padding: 1px 6px;
    border-radius: 3px;
    white-space: nowrap;
    line-height: 1.8;
  }
}

.cv-corner {
  position: absolute;
  width: 8px;
  height: 8px;
  border-color: #fff;
  border-style: solid;
  background: transparent;

  &--tl {
    top: -1px;
    left: -1px;
    border-width: 2px 0 0 2px;
  }
  &--tr {
    top: -1px;
    right: -1px;
    border-width: 2px 2px 0 0;
  }
  &--bl {
    bottom: -1px;
    left: -1px;
    border-width: 0 0 2px 2px;
  }
  &--br {
    bottom: -1px;
    right: -1px;
    border-width: 0 2px 2px 0;
  }
}

.cv-action-bar {
  position: fixed;
  display: flex;
  gap: 8px;
  z-index: 200;
  width: max-content;
}

.cv-btn {
  padding: 5px 18px;
  border: none;
  border-radius: 4px;
  font-size: 13px;
  cursor: pointer;
  line-height: 1.5;
  outline: none;

  &--cancel {
    background: rgba(177, 177, 177, 0.8);
    color: #fff;
    border: 1px solid rgba(255, 255, 255, 0.3);

    &:hover {
      background: rgba(177, 177, 177, 0.6);
    }
  }

  &--save {
    background: #1677ff;
    color: #fff;

    &:hover {
      background: #4096ff;
    }
  }
}

.cv-hint {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  color: rgba(255, 255, 255, 0.85);
  font-size: 16px;
  pointer-events: none;
}

.cv-tip {
  position: fixed;
  bottom: 40px;
  left: 50%;
  transform: translateX(-50%);
  color: rgba(255, 255, 255, 0.7);
  font-size: 13px;
  background: rgba(0, 0, 0, 0.5);
  padding: 4px 12px;
  border-radius: 4px;
  pointer-events: none;
}
</style>
