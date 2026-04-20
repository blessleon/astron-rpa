import { ref, computed, onMounted, onUnmounted } from 'vue'
import { windowManager } from '@/platform'
import { PickShortCuts, PickMode, PickStep, ShortCutKey, MessageType, HighlightRect } from '../config'
import { RpaHighlight } from '@/api/highlight'
import { message } from 'ant-design-vue'



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
  let rafId: number | null = null
  let pendingDrawData: MessageType | null = null

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

  const tagPosition = computed(() => {
    const rect = highlightRects.value[0]
    return rect && rect.y < 60 ? 'bottom' : 'top'
  })

  const shortcuts = computed(() => {
    const pickKey = pickMode.value === PickMode.CV ? (pickMode.value + pickStep.value) as PickMode : pickMode.value
    console.log('pickKey: ', pickKey);
    const shortCuts = PickShortCuts[pickKey]
    console.log('shortCuts: ', shortCuts);
    return PickShortCuts[pickKey] || []
  })

  const highlightShow = computed(() => {
    const rect = highlightRects.value[0]
    return rect && rect.width > 0 && rect.height > 0 && pickMode.value !== PickMode.CV
  })

  const cvCropShow = computed(() => {
    return pickStep.value === PickStep.CV_CTRL || pickStep.value === PickStep.CV_ALT
  })

  const setPickStep = (step: PickStep) => {
    pickStep.value = step
  }
  const hideAll = () => {
    tooltipVisible.value = false
    highlightRects.value = []
    highlightBox.value && (highlightBox.value.innerHTML = '')
    setPickStep(PickStep.DEFAULT)
    window.location.reload()
  }
  onUnmounted(() => {
    if (rafId !== null) {
      cancelAnimationFrame(rafId)
      rafId = null
    }
  })

  const handleShortcutKey = (key: ShortCutKey) => {
    key = key?.toLowerCase() as ShortCutKey
    if (key === ShortCutKey.CTRL && pickMode.value === PickMode.CV) {
      setPickStep(PickStep.CV_CTRL)
      windowManager.setMouseIgnore(false)
    }
    if (key === ShortCutKey.ALT && pickMode.value === PickMode.CV) {
      setPickStep(PickStep.CV_ALT)
      windowManager.setMouseIgnore(false)
    }
    if (key === ShortCutKey.SHIFT && pickMode.value === PickMode.CV) {
      setPickStep(PickStep.DEFAULT)
    }
  }

  const renderFrame = () => {
    rafId = null
    if (!pendingDrawData) return

    const data = pendingDrawData
    pendingDrawData = null

    const boxes = data.Boxes
    if (!boxes || boxes.length === 0) return

    const container = highlightBox.value
    if (!container) return

    const isValidateMode = pickMode.value === PickMode.VALIDATE
    const firstBox = boxes[0]
    const tagPos = firstBox && (firstBox.Top < 60) ? 'bottom' : 'top'

    if (isValidateMode) {
      container.innerHTML = ''
      const fragment = document.createDocumentFragment()
      boxes.forEach((box: any) => {
        const div = document.createElement('div')
        div.className = 'highlight-box highlight-box-validate'
        const x = box.Left / dpr
        const y = box.Top / dpr
        const width = (box.Right - box.Left) / dpr
        const height = (box.Bottom - box.Top) / dpr
        div.style.cssText = `transform:translate(${x}px,${y}px);width:${width}px;height:${height}px`
        if (box.Msg) {
          const span = document.createElement('span')
          span.className = tagPos === 'top' ? 'highlight-tag highlight-tag-top' : 'highlight-tag highlight-tag-bottom'
          span.textContent = box.Msg
          div.appendChild(span)
        }
        fragment.appendChild(div)
      })
      container.appendChild(fragment)
      return
    }

    // non-validate modes always have a single box — reuse existing element
    const box = firstBox
    const x = box.Left / dpr
    const y = box.Top / dpr
    const width = (box.Right - box.Left) / dpr
    const height = (box.Bottom - box.Top) / dpr
    const cssText = `transform:translate(${x}px,${y}px);width:${width}px;height:${height}px`

    let div = container.firstElementChild as HTMLDivElement | null
    if (!div) {
      div = document.createElement('div')
      div.className = 'highlight-box'
      container.appendChild(div)
    }
    div.style.cssText = cssText

    if (box.Msg) {
      let span = div.firstElementChild as HTMLSpanElement | null
      if (!span) {
        span = document.createElement('span')
        div.appendChild(span)
      }
      span.className = tagPos === 'top' ? 'highlight-tag highlight-tag-top' : 'highlight-tag highlight-tag-bottom'
      span.textContent = box.Msg
    } else {
      const span = div.firstElementChild
      if (span) div.removeChild(span)
    }
  }

  const handleDraw = (data: MessageType) => {
    mousePos.value = {
      x: data.MouseX,
      y: data.MouseY,
    }
    highlightRects.value = data.Boxes.map(box => ({
      x: box.Left,
      y: box.Top,
      width: box.Right - box.Left,
      height: box.Bottom - box.Top,
      tag: box.Msg,
    }))
    pendingDrawData = data
    if (rafId === null) {
      rafId = requestAnimationFrame(renderFrame)
    }
  }

  const handleOperation = (op: string, data: MessageType) => {
    switch (op) {
      case 'start':
        windowManager.showWindow()
        if (data.Type) pickMode.value = data.Type
        console.log('start: ', data);
        tooltipVisible.value = data.Type !== PickMode.VALIDATE
        break
      case 'hide':
        console.log('hide: ', data);
        highlightRects.value = []
        hideAll()
        break
      case 'draw':
        handleDraw(data)
        break
      case 'mouse_move':
        mousePos.value = { x: data.MouseX, y: data.MouseY }
        break
      default:
        break
    }
  }

  const handleMessage = (data: MessageType) => {
    // console.log('bindMessage data: ', data);
    const op = data.Operation
    const shortcut = data.ShortcutKey
    handleShortcutKey(shortcut)
    handleOperation(op, data)

    // 如果是 CV 模式，同时传递给 CV 消息处理器
    if (pickMode.value === PickMode.CV && cvMessageHandler) {
      cvMessageHandler(data)
    }

    windowManager.setWindowAlwaysOnTop(true)
  }

  onMounted(() => {
    const pickModeFromUrl = new URLSearchParams(window.location.search).get('pickMode') as PickMode
    if (pickModeFromUrl) {
      pickMode.value = pickModeFromUrl
      if (pickMode.value === PickMode.CV) {
        windowManager.setMouseIgnore(false)
      } else {
        windowManager.setMouseIgnore(true)
      }
    }
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
    RpaHighlight.bindError(() => {
      message.error('Highlight WebSocket is unavailable')
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
