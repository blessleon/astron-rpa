import { utilsManager } from '@/platform'

export async function captureScreen() {
  return await utilsManager.invoke('capture-screen')
}
