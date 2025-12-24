(function () {
  const root = document.documentElement;
  const body = document.body;
  const themeToggle = document.querySelector('[data-theme-toggle]');
  const themeMeta = document.querySelector('meta[name=theme-color]');
  const savedTheme = localStorage.getItem('theme');
  const initialTheme = savedTheme || 'light';

  function applyTheme(theme, animate) {
    if (animate) {
      body.classList.add('theme-transition');
      window.setTimeout(() => body.classList.remove('theme-transition'), 360);
    }
    root.dataset.theme = theme;
    localStorage.setItem('theme', theme);
    if (themeMeta) {
      themeMeta.setAttribute('content', theme === 'dark' ? '#1c1e24' : '#3f6bff');
    }
    if (themeToggle) {
      themeToggle.setAttribute('aria-label', theme === 'dark' ? '切换到亮色' : '切换到暗色');
    }
  }

  applyTheme(initialTheme, false);

  if (themeToggle) {
    themeToggle.addEventListener('click', () => {
      const next = root.dataset.theme === 'dark' ? 'light' : 'dark';
      applyTheme(next, true);
    });
  }

  const overlay = document.querySelector('[data-search-overlay]');
  const openButtons = document.querySelectorAll('[data-search-open]');
  const closeButtons = document.querySelectorAll('[data-search-close]');
  const overlayInput = overlay ? overlay.querySelector('[data-search-input]') : null;

  function openOverlay() {
    if (!overlay) return;
    overlay.classList.add('is-open');
    overlay.setAttribute('aria-hidden', 'false');
    if (overlayInput) {
      overlayInput.focus();
      const q = new URLSearchParams(window.location.search).get('q');
      if (q && !overlayInput.value) overlayInput.value = q;
    }
  }

  function closeOverlay() {
    if (!overlay) return;
    overlay.classList.remove('is-open');
    overlay.setAttribute('aria-hidden', 'true');
  }

  openButtons.forEach((btn) => {
    btn.addEventListener('click', openOverlay);
  });
  closeButtons.forEach((btn) => btn.addEventListener('click', closeOverlay));
  if (overlay) {
    overlay.addEventListener('click', (event) => {
      if (event.target === overlay) closeOverlay();
    });
  }
  window.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') closeOverlay();
  });

  function getCookie(name) {
    const match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
    return match ? decodeURIComponent(match[2]) : '';
  }

  function setCookie(name, value, days) {
    const maxAge = days * 24 * 60 * 60;
    document.cookie =
      name + '=' + encodeURIComponent(value) + ';path=/;max-age=' + maxAge + ';SameSite=Lax';
  }

  const live2dRoot = document.getElementById('landlord');
  const live2dToggle = document.querySelector('[data-live2d-toggle]');
  if (live2dRoot && live2dToggle) {
    const pref = getCookie('live2d');
    if (pref === '0') {
      live2dRoot.classList.add('live2d-hidden');
    }
    function updateLive2dLabel() {
      const hidden = live2dRoot.classList.contains('live2d-hidden');
      live2dToggle.textContent = hidden ? 'Live2D 关' : 'Live2D 开';
    }
    updateLive2dLabel();
    live2dToggle.addEventListener('click', () => {
      live2dRoot.classList.toggle('live2d-hidden');
      const hidden = live2dRoot.classList.contains('live2d-hidden');
      setCookie('live2d', hidden ? '0' : '1', 365);
      updateLive2dLabel();
    });
  }

  const adminEntry = document.querySelector('[data-admin-entry]');
  if (adminEntry) {
    fetch('/upload/admin/me', { credentials: 'include' })
      .then((resp) => {
        if (!resp.ok) return null;
        return resp.json();
      })
      .then((data) => {
        if (data && data.ok) {
          adminEntry.hidden = false;
        }
      })
      .catch(() => undefined);
  }
})();
