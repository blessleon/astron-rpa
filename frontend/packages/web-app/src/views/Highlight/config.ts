import { computed } from 'vue'
import { t } from './locale'

export enum PickMode {
  "" = 'normal',
  NORMAL = 'normal',
  SMART = 'smart',
  CV = 'vision',
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
  CV_CTRL = 'cv_ctrl',
  CV_ALT = 'cv_alt',
  PICKED = 'picked',
}

export enum ShortCutKey {
  CTRL = 'ctrl',
  ALT = 'alt',
  SHIFT = 'shift',
  ESC = 'esc',
}

export const PickTip = computed(() => ({
  [PickMode.NORMAL]: t('elementPick'),
  [PickMode.SMART]: t('smartRecognition'),
  [PickMode.CV]: t('cvRecognition'),
  [PickMode.WINDOW]: t('windowPick'),
  [PickMode.ELEMENT]: t('elementPick'),
  [PickMode.POINT]: t('coordinatePick'),
  [PickMode.SIMILAR]: t('similarElementPick'),
  [PickMode.BATCH]: t('batchCapture'),
}))

export const PickShortCuts = computed(() => {
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

  return {
    [PickMode.NORMAL]: defaultShortCuts,
    [PickMode.SMART]: defaultShortCuts,
    [PickMode.CV]: cvShortCuts,
    [PickMode.CV + PickStep.CV_CTRL]: cvCtrlShortCuts,
    [PickMode.CV + PickStep.CV_ALT]: cvAltShortCuts,
    [PickMode.WINDOW]: defaultShortCuts,
    [PickMode.ELEMENT]: defaultShortCuts,
    [PickMode.POINT]: defaultShortCuts,
    [PickMode.SIMILAR]: defaultShortCuts,
    [PickMode.BATCH]: defaultShortCuts,
  }
})

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
