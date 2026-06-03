import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router.js'
import './assets/style.css'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')

// Global error handler — same behavior as old app
app.config.errorHandler = (err, instance, info) => {
  console.warn('Caught:', err.message, info)
}
