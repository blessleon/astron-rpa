import Socket from './ws'

export const RpaHighlight = new Socket('picker/picker?tag=hl', {
  noInitCreat: true,
  port: 13159,
  isReconnect: true,
  timeout: 1000 * 10, // 10s
})