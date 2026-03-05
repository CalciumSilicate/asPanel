import '@fontsource/maple-mono/400.css';
import '@fontsource/maple-mono/700.css';
import { createApp } from 'vue';
import { createPinia } from 'pinia';
import ElementPlus from 'element-plus';
import 'element-plus/dist/index.css';
import 'element-plus/theme-chalk/dark/css-vars.css';
import './styles/theme.css'
import { registerIcons } from './icons'
import { initTheme } from './store/theme'

import App from './App.vue';
import router from './router';

const app = createApp(App);
const pinia = createPinia();

initTheme()

import('./store/settings').then(m => m.useSettingsStore().loadSettings()).catch(() => {})

registerIcons(app)

app.use(pinia);
app.use(router);
app.use(ElementPlus);

app.mount('#app');
