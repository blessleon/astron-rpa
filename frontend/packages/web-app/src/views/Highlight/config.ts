import { t } from './locale'

export enum PickMode {
  "" = 'normal',
  NORMAL = 'normal',
  SMART = 'smart',
  VISION = 'vision',
  VISION_PICK = 'vision_pick', // 拾取中
  DESIGNATE = 'designate_pick', // CV 模式的分割，用于区分普通CV拾取和指定区域拾取
  WINDOW = 'window',
  ELEMENT = "element",
  POINT = "point",
  SIMILAR = "similar",
  BATCH = "batch",
  VALIDATE = "validate",
}

export enum PickStep {
  DEFAULT = '',
  CTRL = 'ctrl',
  ALT = 'alt',
  PICKED = 'picked',
}

export enum ShortCutKey {
  CTRL = 'ctrl',
  ALT = 'alt',
  SHIFT = 'shift',
  ESC = 'esc',
}

const defaultShortCuts = [
  { title: t('captureElement'), keys: t('mouseLeft') },
  { title: t('exit'), keys: 'Esc' },
]

const cvShortCuts = [
  { title: t('screenshotPick'), keys: 'Ctrl' },
  { title: t('smartPick'), keys: 'Alt' },
  { title: t('exit'), keys: 'Esc' },
]

const cvCtrlShortCuts = [
  { title: t('returnPrevious'), keys: 'Shift' },
  { title: t('exit'), keys: 'Esc' },
]

const cvAltShortCuts = [
  { title: t('returnPrevious'), keys: 'Shift' },
  { title: t('exit'), keys: 'Esc' },
]
export const PickShortCuts = {
  [PickMode.NORMAL]: defaultShortCuts,
  [PickMode.SMART]: defaultShortCuts,
  [PickMode.VISION]: cvShortCuts,
  [PickMode.VISION + PickStep.CTRL]: cvCtrlShortCuts,
  [PickMode.VISION + PickStep.ALT]: cvAltShortCuts,
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
  Operation: string,
  ShortcutKey?: ShortCutKey,
  Language?: string,
  TargetRect?: DrawRect,
  mode: string
}