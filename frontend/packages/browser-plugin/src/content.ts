/** @format */
import { handle, moveListener } from './content/contentInject'

chrome.runtime.onMessage.addListener((message, _sender, senderResponse) => {
  const handleMessage = async () => {
    try {
      const result = await handle(message)
      return result
    }
    catch (error) {
      return { error: error.message }
    }
  }

  handleMessage().then(senderResponse)
  return true
})

window.addEventListener(
  'mousemove',
  (event: MouseEvent) => {
    // 1. 过滤合成事件（脚本创建的事件）
    // 如果客户代码通过postMessage转发事件并在外层重新dispatch，isTrusted会是false
    if (!event.isTrusted) {
      console.log('[Astron Debug] 检测到合成事件，已过滤（可能是客户代码转发的事件）')
      return
    }

    // 2. 检查事件的窗口来源
    if (event.view && event.view !== window) {
      console.log('[Astron Debug] 事件来自其他窗口，已过滤')
      return
    }

    // 3. 检查事件目标
    const target = event.target as HTMLElement
    if (!target || !document.contains(target)) {
      return
    }

    // 4. 检查元素所有权（确保元素真的属于当前document）
    if (target.ownerDocument !== document) {
      console.log('[Astron Debug] 元素不属于当前document，已过滤')
      return
    }
    moveListener(event, document, '')
  },
  true,
)
