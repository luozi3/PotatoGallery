import { createApp } from 'vue';
import App from './App.vue';

function parseBootstrap() {
  const payloadEl = document.getElementById('home-bootstrap');
  if (!payloadEl) return {};
  try {
    return JSON.parse(payloadEl.textContent || '{}');
  } catch (err) {
    return {};
  }
}

const root = document.getElementById('home-app');
if (root && !window.__homeVueInit) {
  const bootstrap = parseBootstrap();
  const app = createApp(App, { bootstrap });
  app.mount(root);
  if (root.hasAttribute('v-cloak')) {
    root.removeAttribute('v-cloak');
  }
  window.__homeVueInit = true;
}
