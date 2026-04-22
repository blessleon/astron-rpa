import { ref, computed, onMounted, onUnmounted } from 'vue'
import { windowManager } from '@/platform'
import { PickShortCuts, PickMode, PickStep, ShortCutKey, HighlightRect, MessageType, DrawRect } from '../config'
import { RpaHighlight } from '@/api/highlight'
import { currentLocale } from '../locale'
import { captureScreen } from '../utils'

type CvPickEvent = 'target_ready' | 'mouse_move' | 'click_confirm' | ''

export function useHighlight() {
  const highlightBox = ref<HTMLDivElement | null>(null)
  const dpr = window.devicePixelRatio || 1
  const highlightRects = ref([] as HighlightRect[])
  const mousePos = ref({ x: 0, y: 0 })
  const pickMode = ref('' as PickMode)
  const pickStep = ref('' as PickStep)
  const appName = ref('')
  const tooltipVisible = ref(false)
  let tooltipLastPos = 'leftTop'
  let canDraw = true

  // CV state
  const targetRect = ref<HighlightRect | null>(null)
  const targetButton = ref(false)
  const anchorRect = ref<HighlightRect | null>(null)
  const cvPickEvent = ref<CvPickEvent>('')
  const screenshotDataUrl = ref('')

  // tooltip位置根据鼠标位置动态调整，避免遮挡
  const tooltipPos = computed(() => {
    const margin = 300
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
    console.log('shortCuts: ', shortCuts);
    return shortCuts || []
  })
  // 高亮区域是否显示（CV模式下由CV组件控制）
  const highlightShow = computed(() => {
    const rect = highlightRects.value[0]
    return rect && rect.width > 0 && rect.height > 0 && pickMode.value !== PickMode.VISION
  })
  // CV模式下的截图预览是否显示
  const cvCropShow = computed(() => {
    if (pickMode.value === PickMode.DESIGNATE && pickStep.value === PickStep.ALT) return true
    return [PickStep.CTRL, PickStep.ALT].includes(pickStep.value) && pickMode.value === PickMode.VISION
  })
  // targetRect 高亮是否显示（DESIGNATE 模式下，非 ALT 步骤时显示）
  const targetRectShow = computed(() => {
    return !!targetRect.value
  })

  // CV computed
  const toRectStyle = (rect: HighlightRect | null) => {
    if (!rect) return null
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
    setPickStep(PickStep.DEFAULT)
  }

  // CV reset
  const resetCV = () => {
    targetRect.value = null
    anchorRect.value = null
    cvPickEvent.value = ''
    canDraw = true
  }

  // CV feedback
  const sendFeedback = (feedbackType: string, data?: any) => {
    const payload: any = { feedback_type: feedbackType }
    if (data !== undefined) payload.data = data
    console.log('payload: ', payload);
    RpaHighlight.send(payload)
  }

  const confirmAnchor = () => {
    if (!anchorRect.value) return
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

  const confirmCvAltPick = (params) => {
    const pos =  {
      Left: Math.floor(params.x * dpr),
      Top: Math.floor(params.y * dpr),
      Right: Math.floor((params.x + params.width) * dpr),
      Bottom: Math.floor((params.y + params.height) * dpr),
    }
    sendFeedback('confirm', { Boxes: [pos] })
    resetCV()
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

  const reCvAltPick = () => {
    console.log('reCvAltPick: ');
    canDraw = true
    targetButton.value = false
    sendFeedback('continue')
    setPickStep(PickStep.ALT)
  }

  const captureDone = () => {
    tooltipVisible.value = true
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
        if (data.Type) pickMode.value = data.Type
        if (data.Language) currentLocale.value = data.Language as any
        tooltipVisible.value = data.Type !== PickMode.VALIDATE
        windowManager.setMouseIgnore(pickMode.value !== PickMode.VISION)
        if (data.mode === "designate" && pickMode.value === PickMode.VISION) {
            captureScreen().then(dataUrl => {
              sendScreenshot(dataUrl)
            })
        }
        break
      case 'hide':
        highlightRects.value = []
        hideAll()
        break
      case 'draw':
        if (data.Type === PickMode.DESIGNATE) {
          targetRect.value = handleRect(data.TargetRect)
          targetButton.value = true
          return
        }
        if (canDraw) {
          if (data.Type === PickMode.VISION_PICK) {
            targetButton.value = false
            targetRect.value = data.Boxes?.[0] ? handleRect(data.Boxes[0]) : null
            return
          }
          if (canDraw) {
            handleDraw(data)
          }
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
    targetRectShow,
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
  }
}
