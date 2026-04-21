
import { ref, computed } from 'vue'
import { RpaHighlight } from '@/api/highlight'
import { DrawRect, HighlightRect } from '../types.d'

type CvPickEvent = 'target_ready' | 'mouse_move' | 'click_confirm' | ''

export function useCV() {
  const dpr = window.devicePixelRatio || 1

  // CV拾取状态
  const targetRect = ref<DrawRect | null>(null)
  const anchorRect = ref<DrawRect | null>(null)
  const mousePos = ref({ x: 0, y: 0 })
  const cvPickEvent = ref<CvPickEvent>('')

  // 将DrawRect转换为CSS样式
  const toRectStyle = (rect: DrawRect | null) => {
    if (!rect) return null
    return {
      left: `${rect.Left / dpr}px`,
      top: `${rect.Top / dpr}px`,
      width: `${(rect.Right - rect.Left) / dpr}px`,
      height: `${(rect.Bottom - rect.Top) / dpr}px`,
    }
  }

  const targetStyle = computed(() => toRectStyle(targetRect.value))
  const anchorStyle = computed(() => toRectStyle(anchorRect.value))
  const hasAnchor = computed(() => !!anchorRect.value)

  // 处理designate_pick类型的draw消息
  const handleDesignatePick = (data: any) => {
    mousePos.value = { x: data.MouseX, y: data.MouseY }
    if (data.TargetRect) targetRect.value = data.TargetRect
    anchorRect.value = data.AnchorRect ?? null
    cvPickEvent.value = data.Event as CvPickEvent
  }

  // 处理来自picker的消息（由useHighlight调用）
  const handleMessage = (data: any) => {
    const { Operation, Type } = data
    if (Operation === 'draw' && Type === 'designate_pick') {
      handleDesignatePick(data)
    }
  }

  // 重置状态
  const reset = () => {
    targetRect.value = null
    anchorRect.value = null
    cvPickEvent.value = ''
  }

  // 发送反馈到picker
  const sendFeedback = (feedbackType: string, data?: any) => {
    const payload: any = { feedback_type: feedbackType }
    if (data !== undefined) payload.data = data
    RpaHighlight.send(payload)
  }

  // 确认选择锚点
  const confirmAnchor = () => {
    if (!anchorRect.value) return
    sendFeedback('confirm', { Boxes: [anchorRect.value] })
    reset()
  }

  // 停止拾取
  const stopPicking = () => {
    sendFeedback('stop')
    reset()
  }

  // 继续拾取（重选）
  const continuePicking = () => {
    sendFeedback('continue')
    reset()
  }

  // 发送截图
  const sendScreenshot = (imageBase64: string) => {
    console.log('sendScreenshot: ', imageBase64);
    sendFeedback('screenshot', { image: imageBase64 })
  }

  const confirmCvAltPick = () => {
    sendFeedback('confirm')
    reset()
  }
  const confirmCvCtrlPick = (params: { imageDataUrl: string, position: HighlightRect}) => {
    const data = params.position
    const pos = {
      "Left": Math.floor(data.x * dpr),
      "Top": Math.floor(data.y * dpr),
      "Right": Math.floor((data.x + data.width) * dpr),
      "Bottom": Math.floor((data.y + data.height) * dpr),
    }
    console.log('confirmCvCtrlPick: ', pos);
    sendFeedback('confirm', { Boxes: [pos] })
  }

  const reCvAltPick = () => {
    sendFeedback('recapture')
    reset()
  }

  return {
    // 状态
    targetRect,
    anchorRect,
    mousePos,
    cvPickEvent,
    // 计算属性
    targetStyle,
    anchorStyle,
    hasAnchor,
    // 方法
    handleMessage,
    confirmAnchor,
    stopPicking,
    continuePicking,
    sendScreenshot,
    reset,
    confirmCvAltPick,
    reCvAltPick,
    confirmCvCtrlPick,
  }
}
