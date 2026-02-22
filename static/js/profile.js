(function () {
  const page = document.querySelector('[data-profile-page]');
  if (!page) return;

  const loginHint = page.querySelector('[data-profile-login-hint]');
  const profileForm = page.querySelector('[data-profile-form]');
  const profileHint = page.querySelector('[data-profile-hint]');
  const displayNameInput = profileForm ? profileForm.querySelector("[name='display_name']") : null;
  const genderSelect = profileForm ? profileForm.querySelector("[name='gender']") : null;
  const introInput = profileForm ? profileForm.querySelector("[name='intro']") : null;
  const websiteInput = profileForm ? profileForm.querySelector("[name='website']") : null;
  const locationInput = profileForm ? profileForm.querySelector("[name='location']") : null;
  const avatarImg = page.querySelector('[data-profile-avatar-img]');
  const introText = page.querySelector('[data-profile-intro]');
  const usernameText = page.querySelector('[data-profile-username]');
  const accountTexts = page.querySelectorAll('[data-profile-account]');
  const createdTexts = page.querySelectorAll('[data-profile-created]');
  const groupWraps = page.querySelectorAll('[data-profile-groups]');
  const worksCount = page.querySelector('[data-profile-works]');
  const favoritedCount = page.querySelector('[data-profile-favorited]');
  const groupCount = page.querySelector('[data-profile-group-count]');
  const displayTitles = page.querySelectorAll('[data-profile-display]');
  const tabButtons = Array.from(page.querySelectorAll('[data-profile-tab]'));
  const tabPanels = Array.from(page.querySelectorAll('[data-profile-panel]'));
  const focusNameBtn = page.querySelector('[data-profile-focus-name]');
  const focusAvatarBtn = page.querySelector('[data-profile-focus-avatar]');
  const avatarSection = page.querySelector('[data-profile-avatar-section]');
  const nameInput = page.querySelector('[data-profile-name-input]') || displayNameInput;

  const cropper = page.querySelector('[data-avatar-cropper]');
  const preview = page.querySelector('[data-avatar-preview]');
  const avatarInput = page.querySelector('[data-avatar-input]');
  const zoomInput = page.querySelector('[data-avatar-zoom]');
  const avatarUploadBtn = page.querySelector('[data-avatar-upload]');
  const avatarResetBtn = page.querySelector('[data-avatar-reset]');
  const avatarHint = page.querySelector('[data-avatar-hint]');
  const avatarCurrent = page.querySelector('[data-avatar-current]');
  const avatarModal = page.querySelector('[data-avatar-modal]');
  const avatarOpenBtn = page.querySelector('[data-avatar-open]');
  const avatarCloseBtns = Array.from(page.querySelectorAll('[data-avatar-close]'));
  const avatarSizeInput = page.querySelector('[data-avatar-size]');
  const avatarFrame = page.querySelector('[data-avatar-frame]');
  const avatarHandles = Array.from(page.querySelectorAll('[data-avatar-handle]'));

  const topbarAvatar = document.querySelector('[data-user-avatar-img]');
  let currentUser = '';

  const cropState = {
    ready: false,
    naturalWidth: 0,
    naturalHeight: 0,
    baseScale: 1,
    zoom: 1,
    imageLeft: 0,
    imageTop: 0,
    imageWidth: 0,
    imageHeight: 0,
    frameSize: 220,
    frameX: 0,
    frameY: 0,
    frameDragging: false,
    frameResizing: false,
    dragStartX: 0,
    dragStartY: 0,
    frameStartX: 0,
    frameStartY: 0,
    resizeHandle: '',
    resizeAnchorX: 0,
    resizeAnchorY: 0,
    resizeStartSize: 0,
    loadToken: 0,
    previewLocked: false,
  };

  async function fetchJSON(url, options) {
    const resp = await fetch(url, { credentials: 'include', ...options });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      const message = data.error || '请求失败';
      throw new Error(message);
    }
    return data;
  }

  function setFormDisabled(disabled) {
    if (!profileForm) return;
    Array.from(profileForm.elements).forEach((el) => {
      el.disabled = disabled;
    });
  }

  function setAvatarControlsDisabled(disabled) {
    if (avatarInput) avatarInput.disabled = disabled;
    if (zoomInput) zoomInput.disabled = disabled || !cropState.ready;
    if (avatarSizeInput) avatarSizeInput.disabled = disabled || !cropState.ready;
    if (avatarUploadBtn) avatarUploadBtn.disabled = disabled || !cropState.ready;
    if (avatarResetBtn) avatarResetBtn.disabled = disabled || !cropState.ready;
  }

  function setText(nodes, value) {
    if (!nodes || !nodes.length) return;
    nodes.forEach((node) => {
      node.textContent = value;
    });
  }

  function renderGroups(groups) {
    if (!groupWraps.length) return;
    let html = '<span class="chip">游客</span>';
    if (groups && groups.length) {
      const labels = { admin: '管理组', user: '用户' };
      html = groups.map((group) => `<span class="chip">${labels[group] || String(group)}</span>`).join('');
    }
    groupWraps.forEach((wrap) => {
      wrap.innerHTML = html;
    });
  }

  function updateProfileText({ user, displayName, intro }) {
    const name = displayName || user || '用户';
    setText(displayTitles, name);
    if (usernameText) usernameText.textContent = user ? `账号：${user}` : '未登录';
    setText(accountTexts, user || '未登录');
    if (introText) {
      introText.textContent = intro || '完善你的头像与简介，让主页更清晰。';
    }
  }

  function updateStats(stats, groups) {
    if (worksCount) worksCount.textContent = stats && typeof stats.works === 'number' ? stats.works : 0;
    if (favoritedCount)
      favoritedCount.textContent = stats && typeof stats.favorited === 'number' ? stats.favorited : 0;
    if (groupCount) groupCount.textContent = groups ? groups.length : 0;
  }

  function setAvatar(url, bustCache = false) {
    if (!url) return;
    const resolved = bustCache ? `${url}${url.includes('?') ? '&' : '?'}v=${Date.now()}` : url;
    if (avatarImg) avatarImg.src = resolved;
    if (avatarCurrent) avatarCurrent.src = resolved;
    if (preview && !cropState.ready && !cropState.previewLocked) preview.src = resolved;
    if (topbarAvatar) topbarAvatar.src = resolved;
  }

  function openAvatarModal() {
    if (!avatarModal) return;
    avatarModal.hidden = false;
    if (cropState.ready) {
      requestAnimationFrame(() => initCropper());
    }
  }

  function closeAvatarModal() {
    if (!avatarModal) return;
    avatarModal.hidden = true;
    handleFrameDragEnd();
    handleResizeEnd();
    cropState.loadToken += 1;
    cropState.previewLocked = false;
    if (preview && avatarCurrent) {
      cropState.ready = false;
      preview.src = avatarCurrent.src;
    }
    if (avatarInput) avatarInput.value = '';
  }

  function clamp(val, min, max) {
    return Math.min(Math.max(val, min), max);
  }

  function updateImageLayout() {
    if (!cropper || !preview || !cropState.ready) return;
    const rect = cropper.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    cropState.baseScale = Math.min(rect.width / cropState.naturalWidth, rect.height / cropState.naturalHeight);
    const scale = cropState.baseScale * cropState.zoom;
    cropState.imageWidth = cropState.naturalWidth * scale;
    cropState.imageHeight = cropState.naturalHeight * scale;
    cropState.imageLeft = (rect.width - cropState.imageWidth) / 2;
    cropState.imageTop = (rect.height - cropState.imageHeight) / 2;
    preview.style.width = `${cropState.imageWidth}px`;
    preview.style.height = `${cropState.imageHeight}px`;
    preview.style.left = `${cropState.imageLeft}px`;
    preview.style.top = `${cropState.imageTop}px`;
  }

  function updateFrameConstraints() {
    if (!cropper || !avatarFrame || !cropState.ready) return;
    const maxSize = Math.min(cropState.imageWidth, cropState.imageHeight);
    if (!maxSize) return;
    const minSize = Math.min(120, maxSize);
    cropState.frameSize = clamp(cropState.frameSize, minSize, maxSize);
    cropState.frameX = clamp(
      cropState.frameX,
      cropState.imageLeft,
      cropState.imageLeft + cropState.imageWidth - cropState.frameSize
    );
    cropState.frameY = clamp(
      cropState.frameY,
      cropState.imageTop,
      cropState.imageTop + cropState.imageHeight - cropState.frameSize
    );
    if (avatarSizeInput) {
      avatarSizeInput.min = `${Math.floor(minSize)}`;
      avatarSizeInput.max = `${Math.floor(maxSize)}`;
      avatarSizeInput.value = `${Math.round(cropState.frameSize)}`;
    }
  }

  function updateFrameLayout() {
    if (!avatarFrame || !cropState.ready) return;
    avatarFrame.style.width = `${cropState.frameSize}px`;
    avatarFrame.style.height = `${cropState.frameSize}px`;
    avatarFrame.style.left = `${cropState.frameX}px`;
    avatarFrame.style.top = `${cropState.frameY}px`;
  }

  function initCropper() {
    if (!cropper || !preview || !cropState.ready) return;
    cropState.zoom = 1;
    cropState.frameResizing = false;
    cropState.resizeHandle = '';
    if (avatarFrame) avatarFrame.classList.remove('is-resizing');
    updateImageLayout();
    cropState.frameSize = Math.min(240, Math.min(cropState.imageWidth, cropState.imageHeight));
    cropState.frameX = cropState.imageLeft + (cropState.imageWidth - cropState.frameSize) / 2;
    cropState.frameY = cropState.imageTop + (cropState.imageHeight - cropState.frameSize) / 2;
    if (zoomInput) {
      zoomInput.min = "1";
      zoomInput.max = "3";
      zoomInput.value = "1";
    }
    if (avatarSizeInput) {
      avatarSizeInput.value = `${Math.round(cropState.frameSize)}`;
    }
    updateFrameConstraints();
    updateFrameLayout();
  }

  function loadAvatarFile(file) {
    if (!file || !preview) return;
    if (!file.type || !file.type.startsWith('image/')) {
      if (avatarHint) avatarHint.textContent = '请选择图片文件。';
      return;
    }
    cropState.ready = false;
    cropState.previewLocked = true;
    const loadToken = (cropState.loadToken += 1);
    openAvatarModal();
    setAvatarControlsDisabled(true);
    if (avatarHint) avatarHint.textContent = '读取图片中...';
    const reader = new FileReader();
    reader.onload = () => {
      if (loadToken !== cropState.loadToken) return;
      const result = typeof reader.result === 'string' ? reader.result : '';
      if (!result) {
        if (avatarHint) avatarHint.textContent = '读取图片失败。';
        cropState.previewLocked = false;
        return;
      }
      preview.onload = () => {
        if (loadToken !== cropState.loadToken) return;
        cropState.naturalWidth = preview.naturalWidth || 1;
        cropState.naturalHeight = preview.naturalHeight || 1;
        cropState.ready = true;
        requestAnimationFrame(() => initCropper());
        setAvatarControlsDisabled(false);
        cropState.previewLocked = false;
        if (avatarHint) avatarHint.textContent = '拖动裁切框，拖拽四角可调整大小。';
      };
      preview.onerror = () => {
        if (loadToken !== cropState.loadToken) return;
        cropState.previewLocked = false;
        if (avatarHint) avatarHint.textContent = '读取图片失败。';
      };
      preview.src = result;
    };
    reader.onerror = () => {
      if (loadToken !== cropState.loadToken) return;
      if (avatarHint) avatarHint.textContent = '读取图片失败。';
      cropState.previewLocked = false;
    };
    reader.readAsDataURL(file);
  }

  function handleFrameDragStart(event) {
    if (!cropState.ready || !avatarFrame) return;
    if (cropState.frameResizing) return;
    cropState.frameDragging = true;
    cropState.dragStartX = event.clientX;
    cropState.dragStartY = event.clientY;
    cropState.frameStartX = cropState.frameX;
    cropState.frameStartY = cropState.frameY;
    avatarFrame.classList.add('is-dragging');
  }

  function handleFrameDragMove(event) {
    if (!cropState.frameDragging || cropState.frameResizing) return;
    cropState.frameX = cropState.frameStartX + (event.clientX - cropState.dragStartX);
    cropState.frameY = cropState.frameStartY + (event.clientY - cropState.dragStartY);
    updateFrameConstraints();
    updateFrameLayout();
  }

  function handleFrameDragEnd() {
    cropState.frameDragging = false;
    if (avatarFrame) avatarFrame.classList.remove('is-dragging');
  }

  function getResizeAnchor(handle, startX, startY, size) {
    switch (handle) {
      case 'se':
        return { x: startX, y: startY };
      case 'nw':
        return { x: startX + size, y: startY + size };
      case 'ne':
        return { x: startX, y: startY + size };
      case 'sw':
        return { x: startX + size, y: startY };
      default:
        return { x: startX, y: startY };
    }
  }

  function handleResizeStart(event) {
    if (!cropState.ready || !avatarFrame) return;
    const handle = event.currentTarget.dataset.avatarHandle;
    if (!handle) return;
    event.preventDefault();
    event.stopPropagation();
    cropState.frameResizing = true;
    cropState.resizeHandle = handle;
    cropState.frameStartX = cropState.frameX;
    cropState.frameStartY = cropState.frameY;
    cropState.resizeStartSize = cropState.frameSize;
    const anchor = getResizeAnchor(handle, cropState.frameStartX, cropState.frameStartY, cropState.resizeStartSize);
    cropState.resizeAnchorX = anchor.x;
    cropState.resizeAnchorY = anchor.y;
    avatarFrame.classList.add('is-resizing');
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function handleResizeMove(event) {
    if (!cropState.frameResizing) return;
    const handle = cropState.resizeHandle;
    if (!handle) return;
    event.preventDefault();
    const dx = event.clientX - cropState.resizeAnchorX;
    const dy = event.clientY - cropState.resizeAnchorY;
    let size = 0;
    if (handle === 'se') size = Math.max(dx, dy);
    if (handle === 'nw') size = Math.max(-dx, -dy);
    if (handle === 'ne') size = Math.max(dx, -dy);
    if (handle === 'sw') size = Math.max(-dx, dy);
    size = Math.max(size, 1);
    let x = cropState.frameStartX;
    let y = cropState.frameStartY;
    if (handle === 'se') {
      x = cropState.resizeAnchorX;
      y = cropState.resizeAnchorY;
    }
    if (handle === 'nw') {
      x = cropState.resizeAnchorX - size;
      y = cropState.resizeAnchorY - size;
    }
    if (handle === 'ne') {
      x = cropState.resizeAnchorX;
      y = cropState.resizeAnchorY - size;
    }
    if (handle === 'sw') {
      x = cropState.resizeAnchorX - size;
      y = cropState.resizeAnchorY;
    }
    cropState.frameSize = size;
    cropState.frameX = x;
    cropState.frameY = y;
    updateFrameConstraints();
    updateFrameLayout();
  }

  function handleResizeEnd(event) {
    if (!cropState.frameResizing) return;
    cropState.frameResizing = false;
    cropState.resizeHandle = '';
    if (avatarFrame) avatarFrame.classList.remove('is-resizing');
    if (event && event.currentTarget && event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  }

  function buildAvatarBlob() {
    if (!cropper || !preview || !cropState.ready) return Promise.resolve(null);
    const rect = cropper.getBoundingClientRect();
    if (!rect.width || !rect.height) return Promise.resolve(null);
    const canvas = document.createElement('canvas');
    const outputSize = 256;
    canvas.width = outputSize;
    canvas.height = outputSize;
    const scaleToNatural = 1 / (cropState.baseScale * cropState.zoom);
    const sx = (cropState.frameX - cropState.imageLeft) * scaleToNatural;
    const sy = (cropState.frameY - cropState.imageTop) * scaleToNatural;
    const sSize = cropState.frameSize * scaleToNatural;
    const ctx = canvas.getContext('2d');
    if (!ctx) return Promise.resolve(null);
    ctx.drawImage(preview, sx, sy, sSize, sSize, 0, 0, outputSize, outputSize);
    return new Promise((resolve) => {
      canvas.toBlob(
        (blob) => {
          if (blob) {
            resolve({ blob, type: 'image/webp' });
          } else {
            canvas.toBlob((fallback) => resolve(fallback ? { blob: fallback, type: 'image/png' } : null), 'image/png');
          }
        },
        'image/webp',
        0.92
      );
    });
  }

  async function uploadAvatar() {
    if (!avatarUploadBtn) return;
    avatarUploadBtn.disabled = true;
    if (avatarHint) avatarHint.textContent = '上传中...';
    try {
      const payload = await buildAvatarBlob();
      if (!payload) throw new Error('头像裁切失败');
      const formData = new FormData();
      const filename = payload.type === 'image/webp' ? 'avatar.webp' : 'avatar.png';
      formData.append('avatar', payload.blob, filename);
      const data = await fetchJSON('/api/user/avatar', {
        method: 'POST',
        body: formData,
      });
      if (data.avatar_url) {
        setAvatar(data.avatar_url, true);
      }
      if (avatarHint) avatarHint.textContent = '头像已更新。';
      closeAvatarModal();
    } catch (err) {
      if (avatarHint) avatarHint.textContent = err.message || '头像更新失败';
    } finally {
      avatarUploadBtn.disabled = false;
      if (avatarInput) avatarInput.value = '';
    }
  }

  function resetAvatarCrop() {
    if (!cropState.ready) return;
    initCropper();
  }

  function setActiveTab(tabId) {
    if (!tabId) return;
    tabButtons.forEach((btn) => {
      const active = btn.dataset.profileTab === tabId;
      btn.classList.toggle('is-active', active);
      btn.setAttribute('aria-selected', active ? 'true' : 'false');
    });
    tabPanels.forEach((panel) => {
      const active = panel.dataset.profilePanel === tabId;
      panel.classList.toggle('is-active', active);
      panel.hidden = !active;
    });
  }

  function activateBasicTab() {
    if (!tabButtons.length || !tabPanels.length) return;
    setActiveTab('basic');
  }

  function focusElement(target) {
    if (!target) return;
    target.scrollIntoView({ behavior: 'smooth', block: 'center' });
    if (typeof target.focus === 'function') {
      target.focus({ preventScroll: true });
    }
  }

  async function loadProfile() {
    if (loginHint) loginHint.hidden = true;
    setFormDisabled(true);
    setAvatarControlsDisabled(true);
    try {
      const data = await fetchJSON('/api/user/profile');
      const profile = data.profile || {};
      const groups = data.groups || [];
      const user = data.user || '';
      currentUser = user;
      if (displayNameInput) displayNameInput.value = profile.display_name || '';
      if (genderSelect) genderSelect.value = profile.gender || '';
      if (introInput) introInput.value = profile.intro || '';
      if (websiteInput) websiteInput.value = profile.website || '';
      if (locationInput) locationInput.value = profile.location || '';
      updateProfileText({ user, displayName: profile.display_name, intro: profile.intro });
      renderGroups(groups);
      updateStats(data.stats || {}, groups);
      setText(createdTexts, data.account && data.account.created_at ? data.account.created_at : '--');
      if (profile.avatar_url) {
        setAvatar(profile.avatar_url);
      }
      setFormDisabled(false);
      if (avatarInput) avatarInput.disabled = false;
    } catch (err) {
      currentUser = '';
      if (loginHint) {
        loginHint.hidden = false;
        loginHint.textContent = '请先登录后管理个人主页。';
      }
      updateProfileText({ user: '', displayName: '', intro: '' });
    }
  }

  if (tabButtons.length && tabPanels.length) {
    tabButtons.forEach((btn) => {
      btn.addEventListener('click', () => setActiveTab(btn.dataset.profileTab));
    });
    const defaultTab = tabButtons.find((btn) => btn.classList.contains('is-active')) || tabButtons[0];
    setActiveTab(defaultTab ? defaultTab.dataset.profileTab : 'basic');
  }

  if (focusNameBtn) {
    focusNameBtn.addEventListener('click', () => {
      activateBasicTab();
      if (nameInput) {
        focusElement(nameInput);
      }
    });
  }

  if (focusAvatarBtn) {
    focusAvatarBtn.addEventListener('click', () => {
      activateBasicTab();
      if (avatarSection) {
        avatarSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  }

  if (profileForm) {
    profileForm.addEventListener('submit', async (event) => {
      event.preventDefault();
      if (profileHint) profileHint.textContent = '保存中...';
      const payload = {
        display_name: displayNameInput ? displayNameInput.value : '',
        gender: genderSelect ? genderSelect.value : '',
        intro: introInput ? introInput.value : '',
        website: websiteInput ? websiteInput.value : '',
        location: locationInput ? locationInput.value : '',
      };
      try {
        const data = await fetchJSON('/api/user/profile', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        updateProfileText({
          user: currentUser,
          displayName: data.profile ? data.profile.display_name : payload.display_name,
          intro: data.profile ? data.profile.intro : payload.intro,
        });
        if (profileHint) profileHint.textContent = '已保存。';
      } catch (err) {
        if (profileHint) profileHint.textContent = err.message || '保存失败';
      }
    });
  }

  if (avatarInput) {
    avatarInput.addEventListener('change', () => {
      const file = avatarInput.files && avatarInput.files[0];
      if (file) {
        loadAvatarFile(file);
      }
    });
  }

  if (avatarOpenBtn && avatarInput) {
    avatarOpenBtn.addEventListener('click', () => {
      if (avatarInput.disabled) return;
      avatarInput.value = '';
      avatarInput.click();
    });
  }

  if (avatarCloseBtns.length) {
    avatarCloseBtns.forEach((btn) => {
      btn.addEventListener('click', () => closeAvatarModal());
    });
  }

  if (avatarSizeInput) {
    avatarSizeInput.addEventListener('input', () => {
      if (!cropState.ready) return;
      cropState.frameSize = parseFloat(avatarSizeInput.value) || cropState.frameSize;
      updateFrameConstraints();
      updateFrameLayout();
    });
  }

  if (zoomInput) {
    zoomInput.addEventListener('input', () => {
      if (!cropState.ready) return;
      cropState.zoom = parseFloat(zoomInput.value) || cropState.zoom;
      updateImageLayout();
      updateFrameConstraints();
      updateFrameLayout();
    });
  }

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && avatarModal && !avatarModal.hidden) {
      closeAvatarModal();
    }
  });

  if (avatarFrame) {
    avatarFrame.addEventListener('pointerdown', (event) => {
      if (!cropState.ready) return;
      avatarFrame.setPointerCapture(event.pointerId);
      handleFrameDragStart(event);
    });
    avatarFrame.addEventListener('pointermove', (event) => handleFrameDragMove(event));
    avatarFrame.addEventListener('pointerup', handleFrameDragEnd);
    avatarFrame.addEventListener('pointerleave', handleFrameDragEnd);
  }

  if (avatarHandles.length) {
    avatarHandles.forEach((handle) => {
      handle.addEventListener('pointerdown', handleResizeStart);
      handle.addEventListener('pointermove', handleResizeMove);
      handle.addEventListener('pointerup', handleResizeEnd);
      handle.addEventListener('pointerleave', handleResizeEnd);
      handle.addEventListener('pointercancel', handleResizeEnd);
    });
  }

  if (avatarUploadBtn) {
    avatarUploadBtn.addEventListener('click', () => uploadAvatar());
  }

  if (avatarResetBtn) {
    avatarResetBtn.addEventListener('click', resetAvatarCrop);
  }

  window.addEventListener('resize', () => {
    if (!cropState.ready) return;
    updateImageLayout();
    updateFrameConstraints();
    updateFrameLayout();
  });

  loadProfile();
})();
