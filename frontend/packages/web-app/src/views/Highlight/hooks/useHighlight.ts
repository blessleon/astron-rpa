import { ref, computed, onMounted, onUnmounted } from 'vue'
import { windowManager } from '@/platform'
import { PickShortCuts, PickMode, PickStep, ShortCutKey } from '../config'
import { RpaHighlight } from '@/api/highlight'
import { message } from 'ant-design-vue'
import type { HighlightRect, MessageType } from '../types.d'
import { currentLocale, t } from '../locale'



export function useHighlight(cvMessageHandler?: (data: any) => void) {
  const highlightBox = ref<HTMLDivElement | null>(null)
  const dpr = window.devicePixelRatio || 1
  const highlightRects = ref([] as HighlightRect[])
  const mousePos = ref({ x: 0, y: 0 })
  const pickMode = ref('' as PickMode)
  const pickStep = ref('' as PickStep)
  const appName = ref('')
  const tooltipVisible = ref(false)
  let tooltipLastPos = 'leftTop'

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
    return [PickStep.CTRL, PickStep.ALT].includes(pickStep.value) && pickMode.value === PickMode.VISION
  })
  // 设置拾取步骤（仅CV模式）
  const setPickStep = (step: PickStep) => {
    pickStep.value = step
  }
  // 隐藏所有高亮和提示
  const hideAll = () => {
    tooltipVisible.value = false
    highlightRects.value = []
    setPickStep(PickStep.DEFAULT)
  }
  // 处理快捷键，CV模式下Ctrl/Alt切换截图/智能识别，Shift返回上一步
  const handleShortcutKey = (key: ShortCutKey) => {
    key = key?.toLowerCase() as ShortCutKey
    if (key === ShortCutKey.CTRL && pickMode.value === PickMode.VISION) {
      setPickStep(PickStep.CTRL)
      windowManager.setMouseIgnore(false)
    }
    if (key === ShortCutKey.ALT && pickMode.value === PickMode.VISION) {
      setPickStep(PickStep.ALT)
      windowManager.setMouseIgnore(false)
    }
    if (key === ShortCutKey.SHIFT && pickMode.value === PickMode.VISION) {
      setPickStep(PickStep.DEFAULT)
    }
  }
  // 处理高亮
  const handleDraw = (data: MessageType) => {
    mousePos.value = {
      x: data.MouseX,
      y: data.MouseY,
    }
    highlightRects.value = data.Boxes.map(box => ({
      x: box.Left / dpr,
      y: box.Top / dpr,
      width: (box.Right - box.Left) / dpr,
      height: (box.Bottom - box.Top) / dpr,
      tag: box.Msg,
    }))
  }
  // 处理消息
  const handleOperation = (op: string, data: MessageType) => {
    switch (op) {
      case 'start':
        console.log('handleOperation: ', op, data);
        windowManager.showWindow()
        windowManager.setWindowAlwaysOnTop(true)
        if (data.Type) pickMode.value = data.Type
        if (data.Language) currentLocale.value = data.Language as any
        tooltipVisible.value = data.Type !== PickMode.VALIDATE
        console.log('tooltipVisible.value: ', tooltipVisible.value);
        if (pickMode.value !== PickMode.VISION) {
          windowManager.setMouseIgnore(true)
        }
        break
      case 'hide':
        console.log('handleOperation: ', op, data);
        highlightRects.value = []
        hideAll()
        break
      case 'draw':
        console.log('handleOperation: ', op, data);
        handleDraw(data)
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

    // 如果是 CV 模式，同时传递给 CV 消息处理器
    // if (pickMode.value === PickMode.CV && cvMessageHandler) {
    //   cvMessageHandler(data)
    // }
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
  }
}
