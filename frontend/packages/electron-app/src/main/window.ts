import path from 'node:path'

import type { CreateWindowOptions } from '@rpa/shared/platform'
import { BrowserWindow, screen } from 'electron'
import { isUndefined } from 'lodash'

import { APP_ICON_PATH, MAIN_WINDOW_LABEL, electronInfo } from './config'
import logger from './log'

export const WindowStack: Map<string, BrowserWindow> = new Map()

export function getWindowFromLabel(label: string) {
  return WindowStack.get(label)
}

export function getMainWindow() {
  return getWindowFromLabel(MAIN_WINDOW_LABEL)
}

export function sendElectronInfo(win: BrowserWindow) {
  win.webContents.send('electron-info', JSON.stringify(electronInfo))
}

function createWindow(options: Electron.BrowserWindowConstructorOptions, label?: string) {
  if (label && WindowStack.has(label)) {
    logger.warn(`Window with label ${label} already exists, focusing it instead of creating a new one.`)
    const win = WindowStack.get(label)
    if (win) {
      win.show()
      return win
    }
  }
  const win = new BrowserWindow(options)
  if (label) {
    WindowStack.set(label, win)
  }

  return win
}

export function createMainWindow() {
  const mainWindowOptions: Electron.BrowserWindowConstructorOptions = {
    title: 'iflyrpa',
    autoHideMenuBar: true,
    width: 1280,
    height: 750,
    icon: APP_ICON_PATH,
    resizable: true,
    center: true,
    show: false,
    frame: false,
    webPreferences: {
      preload: path.join(__dirname, '../preload/index.js'),
      contextIsolation: true,
    },
  }

  return createWindow(mainWindowOptions, MAIN_WINDOW_LABEL)
}

function resolvePositionOnDisplay(
  display: Electron.Display,
  position: string | undefined,
  width: number,
  height: number,
  offset: number,
  _x?: number,
  _y?: number,
): { x: number | undefined; y: number | undefined; width: number; height: number } {
  const { x: dx, y: dy, width: sw, height: sh } = display.workArea
  let x: number | undefined = _x
  let y: number | undefined = _y
  let w = width
  let h = height

  switch (position) {
    case 'left_top':
      x = dx + 2; y = dy + 2; break
    case 'right_top':
      x = dx + sw - w - 2; y = dy + 2; break
    case 'left_bottom':
      x = dx + 2; y = dy + sh - h - 2; break
    case 'right_bottom':
      x = dx + sw - w - 2; y = dy + sh - h - 2; break
    case 'top_center':
      x = dx + Math.round((sw - w) / 2); y = dy + 2; break
    case 'center':
      x = dx + Math.round((sw - w) / 2); y = dy + Math.round((sh - h) / 2); break
    case 'right_center':
      x = dx + sw - w - offset; y = dy + Math.round((sh - h) / 2); break
    case 'fullscreen':
      x = dx; y = dy; w = sw; h = sh; break
    default:
      break
  }

  return { x, y, width: w, height: h }
}

export function createSubWindow(options: CreateWindowOptions) {
  logger.info('createSubWindow', JSON.stringify(options))
  let {
    width = 800,
    height = 600,
    url,
    offset = 0,
    position,
    x: _x,
    y: _y,
    followCursor,
    ...restOptions
  } = options

  const display = screen.getPrimaryDisplay()
  const resolved = resolvePositionOnDisplay(display, position, width, height, offset, _x, _y)
  let x: number | undefined = resolved.x
  let y: number | undefined = resolved.y
  width = resolved.width
  height = resolved.height

  const subWindowOptions: Electron.BrowserWindowConstructorOptions = {
    ...restOptions,
    ...(isUndefined(x) && isUndefined(y) ? { center: true } : { x, y }),
    width,
    height,
    webPreferences: {
      preload: path.join(__dirname, '../preload/index.js'),
      contextIsolation: true,
    },
    icon: APP_ICON_PATH,
    frame: false,
  }

  const window = createWindow(subWindowOptions, options.label)
  if (window.webContents.getURL() === url) {
    window.show()
  } else {
    window.loadURL(url).then(() => sendElectronInfo(window)).catch(() => logger.error('Failed to load URL'))
  }
  if (options.mouseIgnore) {
    window.setIgnoreMouseEvents(true, { forward: true })
  }
  window.on('ready-to-show', () => {
    if (options?.show !== false) {
      window.show()
    }
    window.focus()
  })

  if (followCursor) {
    let lastDisplayId: number | null = null
    const timer = setInterval(() => {
      if (window.isDestroyed()) {
        clearInterval(timer)
        return
      }
      const cursor = screen.getCursorScreenPoint()
      const currentDisplay = screen.getDisplayNearestPoint(cursor)
      if (currentDisplay.id === lastDisplayId) return
      lastDisplayId = currentDisplay.id
      const { x: nx, y: ny, width: nw, height: nh } = resolvePositionOnDisplay(
        currentDisplay, position, options.width ?? 800, options.height ?? 600, offset,
      )
      window.setBounds({
        x: nx ?? currentDisplay.workArea.x,
        y: ny ?? currentDisplay.workArea.y,
        width: nw,
        height: nh,
      })
      logger.info(`followCursor: moved window to display ${currentDisplay.id}`)
    }, 300)

    window.on('closed', () => clearInterval(timer))
  }

  window.on('closed', () => {
    if (options.label) {
      WindowStack.delete(options.label)
    }
  })

  return window
}


