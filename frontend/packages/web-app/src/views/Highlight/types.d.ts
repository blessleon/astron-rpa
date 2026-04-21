
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
}