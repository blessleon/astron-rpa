  import { utilsManager } from '@/platform'
  export const captureScreen = async () => {
    return await utilsManager.invoke('capture-screen')
  }