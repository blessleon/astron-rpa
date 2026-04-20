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
    console.warn(`Window with label ${label} already exists, focusing it instead of creating a new one.`)
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
    ...restOptions
  } = options

  const display = screen.getPrimaryDisplay()
  const { width: screenWidth, height: screenHeight } = display.workAreaSize

  let x: number | undefined = _x
  let y: number | undefined = _y

  switch (position) {
    case 'left_top':
      x = 2
      y = 2
      break
    case 'right_top':
      x = screenWidth - width - 2
      y = 2
      break
    case 'left_bottom':
      x = 2
      y = screenHeight - height - 2
      break
    case 'right_bottom':
      x = screenWidth - width - 2
      y = screenHeight - height - 2
      break
    case 'top_center':
      x = Math.round((screenWidth - width) / 2)
      y = 2
      break
    case 'center':
      x = Math.round((screenWidth - width) / 2)
      y = Math.round((screenHeight - height) / 2)
      break
    case 'right_center':
      x = screenWidth - width - offset
      y = screenHeight / 2 - height / 2
      break
    case 'fullscreen':
      x = 0
      y = 0
      width = screenWidth
      height = screenHeight
      break
    default:
      break
  }

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
  window.loadURL(url).then(() => sendElectronInfo(window)).catch(() => logger.error('Failed to load URL'))

  if (options.mouseIgnore) {
    window.setIgnoreMouseEvents(true, { forward: true });
  }
  window.on('ready-to-show', () => {
    // window?.openDevTools()
    if (options?.show !== false) {
      window.show()
    }
    window.focus()
  })

  window.on('closed', () => {
    if (options.label) {
      WindowStack.delete(options.label)
    }
  })


  return window
}
