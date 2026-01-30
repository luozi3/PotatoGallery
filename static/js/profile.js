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

  const topbarAvatar = document.querySelector('[data-user-avatar-img]');
  let currentUser = '';

  const cropState = {
    ready: false,
    naturalWidth: 0,
    naturalHeight: 0,
    scale: 1,
    minScale: 1,
    maxScale: 1,
    offsetX: 0,
    offsetY: 0,
    dragStartX: 0,
    dragStartY: 0,
    dragOffsetX: 0,
    dragOffsetY: 0,
    dragging: false,
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

  function setAvatar(url) {
    if (avatarImg && url) avatarImg.src = url;
    if (preview && url) preview.src = url;
    if (topbarAvatar && url) topbarAvatar.src = url;
  }

  function clamp(val, min, max) {
    return Math.min(Math.max(val, min), max);
  }

  function updateCropperLayout() {
    if (!cropper || !preview || !cropState.ready) return;
    const rect = cropper.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    const width = cropState.naturalWidth * cropState.scale;
    const height = cropState.naturalHeight * cropState.scale;
    const minX = rect.width - width;
    const minY = rect.height - height;
    cropState.offsetX = clamp(cropState.offsetX, minX, 0);
    cropState.offsetY = clamp(cropState.offsetY, minY, 0);
    preview.style.width = `${width}px`;
    preview.style.height = `${height}px`;
    preview.style.left = `${cropState.offsetX}px`;
    preview.style.top = `${cropState.offsetY}px`;
  }

  function initCropper() {
    if (!cropper || !preview) return;
    const rect = cropper.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    const minScale = Math.max(rect.width / cropState.naturalWidth, rect.height / cropState.naturalHeight);
    cropState.minScale = minScale;
    cropState.maxScale = minScale * 3;
    cropState.scale = minScale;
    cropState.offsetX = (rect.width - cropState.naturalWidth * cropState.scale) / 2;
    cropState.offsetY = (rect.height - cropState.naturalHeight * cropState.scale) / 2;
    if (zoomInput) {
      zoomInput.min = `${minScale}`;
      zoomInput.max = `${cropState.maxScale}`;
      zoomInput.value = `${cropState.scale}`;
    }
    updateCropperLayout();
  }

  function loadAvatarFile(file) {
    if (!file || !preview) return;
    if (!file.type || !file.type.startsWith('image/')) {
      if (avatarHint) avatarHint.textContent = '请选择图片文件。';
      return;
    }
    const url = URL.createObjectURL(file);
    preview.onload = () => {
      URL.revokeObjectURL(url);
      cropState.naturalWidth = preview.naturalWidth || 1;
      cropState.naturalHeight = preview.naturalHeight || 1;
      cropState.ready = true;
      initCropper();
      setAvatarControlsDisabled(false);
      if (avatarHint) avatarHint.textContent = '拖动图片以调整裁切区域。';
    };
    preview.src = url;
  }

  function handleDragStart(event) {
    if (!cropState.ready) return;
    cropState.dragging = true;
    cropper.classList.add('is-dragging');
    cropState.dragStartX = event.clientX;
    cropState.dragStartY = event.clientY;
    cropState.dragOffsetX = cropState.offsetX;
    cropState.dragOffsetY = cropState.offsetY;
  }

  function handleDragMove(event) {
    if (!cropState.dragging) return;
    cropState.offsetX = cropState.dragOffsetX + (event.clientX - cropState.dragStartX);
    cropState.offsetY = cropState.dragOffsetY + (event.clientY - cropState.dragStartY);
    updateCropperLayout();
  }

  function handleDragEnd() {
    cropState.dragging = false;
    if (cropper) cropper.classList.remove('is-dragging');
  }

  function buildAvatarBlob() {
    if (!cropper || !preview || !cropState.ready) return Promise.resolve(null);
    const rect = cropper.getBoundingClientRect();
    if (!rect.width || !rect.height) return Promise.resolve(null);
    const canvas = document.createElement('canvas');
    const outputSize = 256;
    canvas.width = outputSize;
    canvas.height = outputSize;
    const scaleToNatural = 1 / cropState.scale;
    const sx = -cropState.offsetX * scaleToNatural;
    const sy = -cropState.offsetY * scaleToNatural;
    const sWidth = rect.width * scaleToNatural;
    const sHeight = rect.height * scaleToNatural;
    const ctx = canvas.getContext('2d');
    if (!ctx) return Promise.resolve(null);
    ctx.drawImage(preview, sx, sy, sWidth, sHeight, 0, 0, outputSize, outputSize);
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
        setAvatar(data.avatar_url);
      }
      if (avatarHint) avatarHint.textContent = '头像已更新。';
    } catch (err) {
      if (avatarHint) avatarHint.textContent = err.message || '头像更新失败';
    } finally {
      avatarUploadBtn.disabled = false;
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

  if (zoomInput) {
    zoomInput.addEventListener('input', () => {
      if (!cropState.ready) return;
      cropState.scale = parseFloat(zoomInput.value) || cropState.scale;
      updateCropperLayout();
    });
  }

  if (cropper) {
    cropper.addEventListener('pointerdown', (event) => {
      if (!cropState.ready) return;
      cropper.setPointerCapture(event.pointerId);
      handleDragStart(event);
    });
    cropper.addEventListener('pointermove', (event) => handleDragMove(event));
    cropper.addEventListener('pointerup', handleDragEnd);
    cropper.addEventListener('pointerleave', handleDragEnd);
  }

  if (avatarUploadBtn) {
    avatarUploadBtn.addEventListener('click', () => uploadAvatar());
  }

  if (avatarResetBtn) {
    avatarResetBtn.addEventListener('click', resetAvatarCrop);
  }

  window.addEventListener('resize', () => {
    if (!cropState.ready) return;
    initCropper();
  });

  loadProfile();
})();
