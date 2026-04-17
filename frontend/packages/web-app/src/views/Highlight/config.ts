export enum PickMode {
  "" = 'normal',
  NORMAL = 'normal',
  SMART = 'smart',
  CV = 'vision_wait',
  WINDOW = 'window',
  ELEMENT = "element",
  POINT = "point",
  SIMILAR = "similar",
  BATCH = "batch",
  VALIDATE = "validate",
}

export enum PickStep {
  "" = 'default',
  DEFAULT = 'default',
  PICKING = 'picking',
  PICKED = 'picked',
  CROPPED = 'cropped',
  SMART = 'smart',
}

export enum ShortCutKey {
  CTRL = 'ctrl',
  ALT = 'Alt',
  SHIFT = 'Shift',
  ESC = 'Escape',
}

export const PickTip = {
  [PickMode.NORMAL]: '元素拾取',
  [PickMode.SMART]: '智能识别',
  [PickMode.CV]: 'CV识别',
  [PickMode.WINDOW]: '窗口拾取',
  [PickMode.ELEMENT]: '元素拾取',
  [PickMode.POINT]: '坐标拾取',
  [PickMode.SIMILAR]: '相似元素拾取',
  [PickMode.BATCH]: '批量抓取',
}

const defaultShortCuts = [
  {
    title: "捕获元素",
    keys: 'Ctrl + 鼠标左键',
  },
  {
    title: "退出",
    keys: 'Esc',
  }
]

const cvShortCuts = [
  {
    title: "截图拾取",
    keys: 'Ctrl',
  },
  {
    title: "智能拾取",
    keys: 'Alt',
  },
  {
    title: "退出",
    keys: 'Esc',
  }
]

export const PickShortCuts = {
  [PickMode.NORMAL]: defaultShortCuts,
  [PickMode.SMART]: defaultShortCuts,
  [PickMode.CV]: cvShortCuts,
  [PickMode.WINDOW]: defaultShortCuts,
  [PickMode.ELEMENT]: defaultShortCuts,
  [PickMode.POINT]: defaultShortCuts,
  [PickMode.SIMILAR]: defaultShortCuts,
  [PickMode.BATCH]: defaultShortCuts,
}

export const TipPosition = {
  leftTop: {
    top: '10px',
    left: '10px',
  },
  rightBottom: {
    bottom: '60px',
    right: '10px',
  }
}


export interface HighlightRect {
  x: number
  y: number
  width: number
  height: number
  tag?: string
}

export interface DrawRect {
  Left: number
  Top: number
  Right: number
  Bottom: number
  Msg?: string
}

export interface MessageType {
  MouseX?: number
  MouseY?: number
  Boxes?: DrawRect[],
  Type?: PickMode,
  Operation: string
}