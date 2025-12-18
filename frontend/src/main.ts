import {createApp} from 'vue';
import ElementPlus from 'element-plus';
import 'element-plus/dist/index.css';
// Element Plus 暗色变量（通过 html.dark 激活）
import 'element-plus/theme-chalk/dark/css-vars.css';
// 覆盖 Element Plus 变量与全局浅色主题
import './styles/theme.css'
import { plugin, defaultConfig } from '@formkit/vue'
import formKitConfig from './formkit.config' // 推荐将配置分离到单独文件
import '@formkit/themes/genesis'
import { registerIcons } from './icons'
import { initTheme } from './store/theme'

import App from './App.vue';
import router from './router';

const app = createApp(App);

// 尽早应用主题，避免页面闪烁
initTheme()

// 预加载系统设置（时区、java命令等）
import('./store/settings').then(m => m.loadSettings()).catch(() => {})

registerIcons(app)

app.use(router);
app.use(ElementPlus);
app.use(plugin, defaultConfig(formKitConfig))

app.mount('#app');
