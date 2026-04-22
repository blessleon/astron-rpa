import { ref } from 'vue'

export type LocaleKey = 'zh_CN' | 'en_US'

export const translations = {
  zh_CN: {
    position: '位置',
    application: '应用',
    reselect: '重新选择',
    save: '保存',
    cancel: '取消',
    dragToSelect: '拖动鼠标框选目标区域',
    elementPick: '元素拾取',
    smartRecognition: '智能识别',
    cvRecognition: 'CV识别',
    windowPick: '窗口拾取',
    coordinatePick: '坐标拾取',
    similarElementPick: '相似元素拾取',
    batchCapture: '批量抓取',
    captureElement: '捕获元素',
    exit: '退出',
    screenshotPick: '截图拾取',
    smartPick: '智能拾取',
    returnPrevious: '返回上层',
    wsUnavailable: 'Highlight WebSocket 不可用',
    mouseLeft: 'Ctrl + 鼠标左键',
    targetElement: '目标元素',
    anchorElement: '锚点元素',
    cvCtrlTitle: '普通图像拾取',
    cvCtrlShortcut: '框选区域',
    cvAltTitle: '智能图像拾取',
    cvAltShortcut: '点击元素',
    screenshotFailed: '截图失败',
  },
  en_US: {
    position: 'Position',
    application: 'Application',
    reselect: 'Reselect',
    save: 'Save',
    cancel: 'Cancel',
    dragToSelect: 'Drag mouse to select target area',
    elementPick: 'Element Pick',
    smartRecognition: 'Smart Recognition',
    cvRecognition: 'CV Recognition',
    windowPick: 'Window Pick',
    coordinatePick: 'Coordinate Pick',
    similarElementPick: 'Similar Element Pick',
    batchCapture: 'Batch Capture',
    captureElement: 'Capture Element',
    exit: 'Exit',
    screenshotPick: 'Screenshot Pick',
    smartPick: 'Smart Pick',
    returnPrevious: 'Return',
    wsUnavailable: 'Highlight WebSocket is unavailable',
    mouseLeft: 'Ctrl + Left Click',
    targetElement: 'Target Element',
    anchorElement: 'Anchor Element',
    cvCtrlTitle: 'Normal Image Pick',
    cvCtrlShortcut: 'Select Area',
    cvAltTitle: 'Smart Image Pick',
    cvAltShortcut: 'Click Element',
    screenshotFailed: 'Screenshot Failed',
  },
}

export type TranslationKey = keyof typeof translations.zh_CN

// 共享的 locale 状态
export const currentLocale = ref<LocaleKey>('zh_CN')

// 翻译函数
export function t(key: TranslationKey): string {
  return translations[currentLocale.value]?.[key] ?? translations.zh_CN[key]
}
