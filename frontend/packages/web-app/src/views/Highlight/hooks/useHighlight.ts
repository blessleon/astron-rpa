import { ref, computed, onMounted, onUnmounted } from 'vue'
import { windowManager } from '@/platform'
import { PickShortCuts, PickMode, PickStep, ShortCutKey, MessageType, HighlightRect } from '../config'
import { RpaHighlight } from '@/api/highlight'
import { message } from 'ant-design-vue'



export function useHighlight() {
  const dpr = window.devicePixelRatio || 1
  const highlightRects = ref([] as HighlightRect[])
  const mousePos = ref({ x: 0, y: 0 })
  const pickMode = ref('' as PickMode)
  const pickStep = ref('' as PickStep)
  const appName = ref('')
  const tooltipVisible = ref(false)

  const tooltipPos = computed(() => {
    const margin = 300
    const mouse = mousePos.value
    if (mouse.x < margin && mouse.y < margin) {
      return 'rightBottom'
    }
    if (mouse.x > (screen.width - margin) * dpr && mouse.y > (screen.height - margin) * dpr) {
      return 'leftTop'
    }
    return 'rightBottom'
  })

  const tagPosition = computed(() => {
    const rect = highlightRects.value[0]
    return rect && rect.y < 60 ? 'bottom' : 'top'
  })

  const shortcuts = computed(() => PickShortCuts[pickMode.value] || [])

  const highlightShow = computed(() => {
    const rect = highlightRects.value[0]
    return rect && rect.width > 0 && rect.height > 0 && pickMode.value !== PickMode.CV
  })

  const cvCropShow = computed(() => {
    return pickMode.value === PickMode.CV && pickStep.value === PickStep.CROPPED
  })

  const setPickStep = (step: PickStep) => {
    pickStep.value = step
  }
  const hideAll = () => {
    tooltipVisible.value = false
    highlightRects.value = []
  }
  onUnmounted(() => {

  })

  const handleShortcutKey = (key: ShortCutKey) => {
    if (key === ShortCutKey.CTRL && pickMode.value === PickMode.CV) {
      setPickStep(PickStep.CROPPED)
    }
    if (key === ShortCutKey.ALT && pickMode.value === PickMode.CV) {
      setPickStep(PickStep.SMART)
    }
    if (key === ShortCutKey.SHIFT && pickMode.value === PickMode.CV) {
      setPickStep(PickStep.PICKING)
    }
  }

  const handleDraw = (data: MessageType) => {
    mousePos.value = {
      x: data.MouseX,
      y: data.MouseY,
    }
    const boxes = data.Boxes
    if (boxes && boxes.length > 0) {
      highlightRects.value = boxes.map((box: any) => ({
        x: box.Left,
        y: box.Top,
        width: (box.Right - box.Left) / dpr,
        height: (box.Bottom - box.Top) / dpr,
        tag: box.Msg,
      }))
    }
  }

  const handleOperation = (op: string, data: MessageType) => {
    switch (op) {
      case 'start':
        windowManager.showWindow()
        if (data.Type) pickMode.value = data.Type
        tooltipVisible.value = data.Type !== PickMode.VALIDATE
        break
      case 'hide':
        highlightRects.value = []
        hideAll()
        windowManager.hideWindow()
        break
      case 'draw':
        handleDraw(data)
        break
      default:
        break
    }
  }

  onMounted(() => {
    const pickModeFromUrl = new URLSearchParams(window.location.search).get('pickMode') as PickMode
    if (pickModeFromUrl) {
      pickMode.value = pickModeFromUrl
      if (pickMode.value === PickMode.CV) {
        windowManager.setMouseIgnore(false)
      }
    }
    windowManager.showWindow()
    RpaHighlight.create(() => {
      RpaHighlight.bindMessage((data) => {
        console.log('bindMessage data: ', data);
        const op = data.Operation
        const shortcut = data.ShortcutKey
        handleShortcutKey(shortcut)
        handleOperation(op, data)
        windowManager.setWindowAlwaysOnTop(true)
      })
    })
    RpaHighlight.bindClose(() => {
      tooltipVisible.value = false
      highlightRects.value = []
      message.warning('Highlight WebSocket closed')
    })
    RpaHighlight.bindError(() => {
      message.error('Highlight WebSocket is unavailable')
    })
  })

  return {
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
    setPickStep,
  }
}
