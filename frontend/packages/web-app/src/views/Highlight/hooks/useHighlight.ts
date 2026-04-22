import { computed, onMounted, onUnmounted, ref } from 'vue'

import { RpaHighlight } from '@/api/highlight'
import { windowManager } from '@/platform'

import type { CvPickEvent, DrawRect, HighlightRect, MessageType } from '../config'
import { PickEvent, PickMode, PickShortCuts, PickStep, ShortCutKey } from '../config'
import { currentLocale } from '../locale'
import { captureScreen } from '../utils'

export function useHighlight() {
  const highlightBox = ref<HTMLDivElement | null>(null)
  const dpr = window.devicePixelRatio || 1
  const highlightRects = ref([] as HighlightRect[])
  const mousePos = ref({ x: 0, y: 0 })
  const pickMode = ref('' as PickMode)
  const pickStep = ref('' as PickStep)
  const pickEvent = ref('' as PickEvent)
  const appName = ref('')
  const tooltipVisible = ref(false)
  let tooltipLastPos = 'leftTop'
  let canDraw = true

  // CV state
  const targetRect = ref<HighlightRect | null>(null)
  const targetButton = ref(false)
  const anchorRect = ref<HighlightRect | null>(null)
  const cvPickEvent = ref<CvPickEvent>('')

  // tooltip位置根据鼠标位置动态调整，避免遮挡
  const tooltipPos = computed(() => {
    const margin = 350
    const mouse = mousePos.value
    if (mouse.x < margin && mouse.y < margin) {
      tooltipLastPos = 'rightBottom'
    }
    if (mouse.x > (screen.width - margin) * dpr && mouse.y > (screen.height - margin) * dpr) {
      tooltipLastPos = 'leftTop'
    }
    return tooltipLastPos
  })
  // 标签位置根据高亮区域位置动态调整，避免标签被遮挡
  const tagPosition = computed(() => {
    const rect = highlightRects.value[0]
    return rect && rect.y < 60 ? 'bottom' : 'top'
  })
  // 快捷键提示根据拾取模式动态调整
  const shortcuts = computed(() => {
    const pickKey = pickMode.value === PickMode.VISION ? (pickMode.value + pickStep.value) as PickMode : pickMode.value
    const shortCuts = PickShortCuts[pickKey]
    console.log('shortCuts: ', shortCuts)
    return shortCuts || []
  })
  // 高亮区域是否显示（CV模式下由CV组件控制）
  const highlightShow = computed(() => {
    const rect = highlightRects.value[0]
    return rect && rect.width > 0 && rect.height > 0 && pickMode.value !== PickMode.VISION
  })
  // CV模式下的截图预览是否显示
  const cvCropShow = computed(() => {
    if (pickMode.value === PickMode.DESIGNATE && pickStep.value === PickStep.ALT)
      return true
    return [PickStep.CTRL, PickStep.ALT, PickStep.ANCHOR].includes(pickStep.value) && pickMode.value === PickMode.VISION
  })

  // CV computed
  const toRectStyle = (rect: HighlightRect | null) => {
    if (!rect)
      return null
    return {
      left: `${rect.x}px`,
      top: `${rect.y}px`,
      width: `${rect.width}px`,
      height: `${rect.height}px`,
    }
  }
  const targetStyle = computed(() => toRectStyle(targetRect.value))
  const anchorStyle = computed(() => toRectStyle(anchorRect.value))
  const hasAnchor = computed(() => !!anchorRect.value)

  // 设置拾取步骤（仅CV模式）
  const setPickStep = (step: PickStep) => {
    pickStep.value = step
  }
  // 隐藏所有高亮和提示
  const hideAll = () => {
    canDraw = true
    tooltipVisible.value = false
    highlightRects.value = []
    targetButton.value = false
    setPickStep(PickStep.DEFAULT)
  }

  // CV reset
  const resetCV = () => {
    targetRect.value = null
    anchorRect.value = null
    cvPickEvent.value = ''
    targetButton.value = false
    canDraw = true
  }

  // CV feedback
  const sendFeedback = (feedbackType: string, data?: any) => {
    const payload: any = { feedback_type: feedbackType }
    if (data !== undefined)
      payload.data = data
    console.log('payload: ', payload)
    RpaHighlight.send(payload)
  }

  const confirmAnchor = () => {
    if (!anchorRect.value)
      return
    sendFeedback('confirm', { Boxes: [anchorRect.value] })
    resetCV()
  }

  const stopPicking = () => {
    sendFeedback('stop')
    resetCV()
  }

  const continuePicking = () => {
    sendFeedback('continue')
    resetCV()
  }

  const sendScreenshot = (imageBase64: string) => {
    sendFeedback('screenshot', { image: imageBase64 })
  }

  const confirmCvCtrlPick = (params: { imageDataUrl: string, position: HighlightRect }) => {
    const data = params.position
    const pos = {
      Left: Math.floor(data.x * dpr),
      Top: Math.floor(data.y * dpr),
      Right: Math.floor((data.x + data.width) * dpr),
      Bottom: Math.floor((data.y + data.height) * dpr),
    }
    sendFeedback('confirm', { Boxes: [pos] })
  }

  const confirmCvAltPick = (params) => {
    const pos = {
      Left: Math.floor(params.x * dpr),
      Top: Math.floor(params.y * dpr),
      Right: Math.floor((params.x + params.width) * dpr),
      Bottom: Math.floor((params.y + params.height) * dpr),
    }
    sendFeedback('confirm', { Boxes: [pos] })
    resetCV()
  }

  const reCvAltPick = () => {
    canDraw = true
    targetButton.value = false
    sendFeedback('continue')
    setPickStep(PickStep.ALT)
  }

  const confirmCvAnchorPick = (params) => {
    const pos = {
      Left: Math.floor(params.x * dpr),
      Top: Math.floor(params.y * dpr),
      Right: Math.floor((params.x + params.width) * dpr),
      Bottom: Math.floor((params.y + params.height) * dpr),
    }
    sendFeedback('confirm', { Boxes: [pos] })
    resetCV()
  }

  const reCvAnchorPick = () => {
    canDraw = true
    targetButton.value = false
    sendFeedback('continue')
    setPickStep(PickStep.ANCHOR)
  }

  const captureDone = () => {
    tooltipVisible.value = [PickStep.CTRL, PickStep.ALT].includes(pickStep.value)
  }

  // 处理快捷键，CV模式下Ctrl/Alt切换截图/智能识别，Shift返回上一步
  const handleShortcutKey = (key: ShortCutKey) => {
    key = key?.toLowerCase() as ShortCutKey
    if (key === ShortCutKey.CTRL && pickMode.value === PickMode.VISION) {
      setPickStep(PickStep.CTRL)
      tooltipVisible.value = false
      windowManager.setMouseIgnore(false)
    }
    if (key === ShortCutKey.ALT && pickMode.value === PickMode.VISION) {
      setPickStep(PickStep.ALT)
      tooltipVisible.value = false
      windowManager.setMouseIgnore(false)
    }
    if (key === ShortCutKey.SHIFT && pickMode.value === PickMode.VISION) {
      setPickStep(PickStep.DEFAULT)
      targetButton.value = false
      targetRect.value = null
    }
  }
  const handleRect = (data: DrawRect) => {
    return {
      x: data.Left / dpr,
      y: data.Top / dpr,
      width: (data.Right - data.Left) / dpr,
      height: (data.Bottom - data.Top) / dpr,
      tag: data.Msg,
    }
  }
  // 处理高亮
  const handleDraw = (data: MessageType) => {
    mousePos.value = {
      x: data.MouseX,
      y: data.MouseY,
    }
    highlightRects.value = data.Boxes.map(box => handleRect(box))
  }
  // 处理消息
  const handleOperation = (op: string, data: MessageType) => {
    if (op !== 'mouse_move') {
      console.log(data)
    }
    switch (op) {
      case 'start':
        windowManager.showWindow()
        windowManager.setWindowAlwaysOnTop(true)
        if (data.Type)
          pickMode.value = data.Type
        if (data.Language)
          currentLocale.value = data.Language as any
        if (data.Type !== PickMode.VALIDATE && data.mode !== 'designate' && !data.ShortcutKey) {
          tooltipVisible.value = true
        }
        windowManager.setMouseIgnore(pickMode.value !== PickMode.VISION)
        if (data.mode === 'designate' && pickMode.value === PickMode.VISION) {
          captureScreen().then((dataUrl) => {
            sendScreenshot(dataUrl)
          })
        }
        break
      case 'hide':
        highlightRects.value = []
        hideAll()
        break
      case 'draw':
        // alt click draw, anchor draw
        if (data.Type === PickMode.DESIGNATE) {
          targetRect.value = handleRect(data.TargetRect)
          targetButton.value = data.Event === PickEvent.CLICK_CONFIRM
          pickEvent.value = data.Event
          if (data.Event === PickEvent.TARGET_READY) {
            setPickStep(PickStep.ANCHOR)
          }
          if (data.Event === PickEvent.MOUSE_MOVE && data.AnchorRect) {
            anchorRect.value = handleRect(data.AnchorRect)
            tooltipVisible.value = false
          }
          if (data.Event === PickEvent.CLICK_CONFIRM && data.AnchorRect) {
            targetButton.value = true
          }
          return
        }

        if (canDraw) {
          // alt draw move
          if (data.Type === PickMode.VISION_PICK) {
            targetButton.value = false
            targetRect.value = data.Boxes?.[0] ? handleRect(data.Boxes[0]) : null
            return
          }
          // draw default
          handleDraw(data)
        }
        windowManager.setWindowAlwaysOnTop(true)
        break
      case 'mouse_move':
        mousePos.value = { x: data.MouseX, y: data.MouseY }
        break
      default:
        break
    }
  }
  // 处理websocket消息
  const handleMessage = (data: MessageType) => {
    const op = data.Operation
    const shortcut = data.ShortcutKey
    handleShortcutKey(shortcut)
    handleOperation(op, data)
  }

  onMounted(() => {
    windowManager.showWindow()
    RpaHighlight.create(() => {
      RpaHighlight.bindMessage((data) => {
        handleMessage(data)
      })
    })
    RpaHighlight.bindClose(() => {
      console.log('Highlight bindClose called')
      hideAll()
    })
  })
  onUnmounted(() => {
    RpaHighlight.destroy()
  })

  return {
    highlightBox,
    dpr,
    highlightRects,
    mousePos,
    pickMode,
    appName,
    tooltipVisible,
    tooltipPos,
    tagPosition,
    shortcuts,
    highlightShow,
    cvCropShow,
    pickStep,
    setPickStep,
    // CV
    targetRect,
    targetButton,
    anchorRect,
    cvPickEvent,
    targetStyle,
    anchorStyle,
    hasAnchor,
    confirmAnchor,
    stopPicking,
    continuePicking,
    sendScreenshot,
    confirmCvAltPick,
    reCvAltPick,
    confirmCvCtrlPick,
    resetCV,
    captureDone,
    reCvAnchorPick,
    confirmCvAnchorPick,
  }
}
