import { ref, computed, onMounted, onUnmounted } from 'vue'
import { windowManager } from '@/platform'
import { PickShortCuts, PickMode, PickStep } from '../config'
import { RpaHighlight } from '@/api/highlight'
import { message } from 'ant-design-vue'

export function useHighlight() {
  const dpr = window.devicePixelRatio || 1
  const highlightRect = ref({ x: 0, y: 0, width: 0, height: 0 })
  const mousePos = ref({ x: 0, y: 0 })
  const pickMode = ref('' as PickMode)
  const pickStep = ref('' as PickStep)
  const appName = ref('')
  const tagName = ref('')
  const tooltipVisible = ref(true)

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
    const rect = highlightRect.value
    return rect.y < 60 ? 'bottom' : 'top'
  })

  const shortcuts = computed(() => PickShortCuts[pickMode.value] || [])

  const highlightShow = computed(() => {
    return highlightRect.value.width > 0 && highlightRect.value.height > 0 && pickMode.value !== PickMode.CV
  })

  const cvCropShow = computed(() => {
    return pickMode.value === PickMode.CV && pickStep.value === PickStep.CROPPED
  })

  const setPickStep = (step: PickStep) => {
    pickStep.value = step
  }

  const keyboardListener = (e: KeyboardEvent) => {
    console.log('e: ', e);
    if (e.key === 'Control' && pickMode.value === PickMode.CV) {
      pickStep.value = PickStep.CROPPED
      windowManager.setMouseIgnore(false)
      tooltipVisible.value = false
    }
    if (e.key === 'Escape' && pickStep.value !== PickStep.DEFAULT) {
      pickStep.value = PickStep.DEFAULT
      // windowManager.setMouseIgnore(true)
      tooltipVisible.value = true
    }
  }

  onUnmounted(() => {
    window.removeEventListener('keydown', keyboardListener)
  })

  onMounted(() => {
    const pickModeFromUrl = new URLSearchParams(window.location.search).get('pickMode') as PickMode
    if (pickModeFromUrl) {
      pickMode.value = pickModeFromUrl
      if (pickMode.value === PickMode.CV) {
        windowManager.setMouseIgnore(false)
      }
    }
    windowManager.showWindow()
    window.addEventListener('keydown', keyboardListener)
    RpaHighlight.create(() => {
      RpaHighlight.bindMessage((data) => {
        const op = data.Operation
        if (op === 'start') {
          tooltipVisible.value = true
          windowManager.showWindow()
          if (data.Type) pickMode.value = data.Type
        } else if (op === 'hide') {
          windowManager.hideWindow()
          highlightRect.value = { x: 0, y: 0, width: 0, height: 0 }
          tagName.value = ''
        } else if (op === 'draw') {
          mousePos.value = {
            x: data.MouseX,
            y: data.MouseY,
          }
          const boxes = data.Boxes
          if (boxes && boxes.length > 0) {
            const box = boxes[0]
            highlightRect.value = {
              x: box.Left,
              y: box.Top,
              width: (box.Right - box.Left) / dpr,
              height: (box.Bottom - box.Top) / dpr,
            }
            if (box.Msg !== undefined) tagName.value = box.Msg
          }
        }
        windowManager.setWindowAlwaysOnTop(true)
      })
    })
    RpaHighlight.bindClose(() => {
      tooltipVisible.value = false
      highlightRect.value = { x: 0, y: 0, width: 0, height: 0 }
      tagName.value = ''
      message.warning('Highlight window closed')
    })
    RpaHighlight.bindError(() => {
      message.error('Highlight service is unavailable')
    })
  })

  return {
    dpr,
    highlightRect,
    mousePos,
    pickMode,
    appName,
    tagName,
    tooltipVisible,
    tooltipPos,
    tagPosition,
    shortcuts,
    highlightShow,
    cvCropShow,
    setPickStep,
  }
}
