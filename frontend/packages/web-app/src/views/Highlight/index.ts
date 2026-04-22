import { createApp } from 'vue'

import '@/assets/css/default.css'
import '@/assets/css/main.scss'

import '@/utils/event'

import Index from './Index.vue'

const app = createApp(Index)

app.mount('#app')
