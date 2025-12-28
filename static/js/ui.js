(function () {
  const root = document.documentElement;
  const body = document.body;
  const themeToggle = document.querySelector('[data-theme-toggle]');
  const themeMeta = document.querySelector('meta[name=theme-color]');
  const savedTheme = localStorage.getItem('theme');
  const initialTheme =
    savedTheme || (body && body.classList.contains('page-home') ? 'dark' : 'light');

  function applyTheme(theme, animate) {
    if (animate) {
      body.classList.add('theme-transition');
      window.setTimeout(() => body.classList.remove('theme-transition'), 360);
    }
    root.dataset.theme = theme;
    localStorage.setItem('theme', theme);
    if (themeMeta) {
      themeMeta.setAttribute('content', theme === 'dark' ? '#1f2023' : '#2f7dd9');
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

  function syncTopbarHeight() {
    const topbar = document.querySelector('.topbar');
    if (!topbar) return;
    const height = Math.ceil(topbar.getBoundingClientRect().height);
    if (height) {
      root.style.setProperty('--topbar-height', `${height}px`);
    }
  }

  syncTopbarHeight();
  window.addEventListener('load', syncTopbarHeight);
  window.addEventListener('resize', () => {
    window.requestAnimationFrame(syncTopbarHeight);
  });

  const masonryState = new WeakMap();
  const MASONRY_READY_TIMEOUT = 1200;

  function waitForGridImages(grid) {
    const images = Array.from(grid.querySelectorAll('img'));
    if (!images.length) return Promise.resolve();
    let remaining = images.length;
    let resolved = false;
    return new Promise((resolve) => {
      const done = () => {
        if (resolved) return;
        resolved = true;
        resolve();
      };
      const tick = () => {
        remaining -= 1;
        if (remaining <= 0) done();
      };
      images.forEach((img) => {
        if (img.complete) {
          tick();
          return;
        }
        img.addEventListener('load', tick, { once: true });
        img.addEventListener('error', tick, { once: true });
      });
      window.setTimeout(done, MASONRY_READY_TIMEOUT);
    });
  }

  function relayoutGrid(grid) {
    const rowHeight = parseInt(getComputedStyle(grid).getPropertyValue('grid-auto-rows')) || 8;
    const rowGap = parseInt(getComputedStyle(grid).getPropertyValue('grid-row-gap')) || 0;
    grid.querySelectorAll('[data-masonry-item]').forEach((item) => {
      if (item.classList.contains('hidden')) return;
      item.style.setProperty('--row-span', '1');
      const height = item.scrollHeight || item.getBoundingClientRect().height;
      const span = Math.max(1, Math.ceil((height + rowGap) / (rowHeight + rowGap)));
      item.style.setProperty('--row-span', span);
    });
  }

  function initMasonry(grid) {
    if (!grid) return null;
    let state = masonryState.get(grid);
    if (!state) {
      const boundImages = typeof WeakSet !== 'undefined' ? new WeakSet() : new Set();
      const observer =
        'ResizeObserver' in window ? new ResizeObserver(() => relayoutGrid(grid)) : null;
      const resizeHandler = () => window.requestAnimationFrame(() => relayoutGrid(grid));
      window.addEventListener('resize', resizeHandler);
      state = { boundImages, observer, resizeHandler };
      masonryState.set(grid, state);
    }

    function bindImages() {
      grid.querySelectorAll('img').forEach((img) => {
        if (state.boundImages.has(img)) return;
        state.boundImages.add(img);
        img.addEventListener('load', () => window.requestAnimationFrame(() => relayoutGrid(grid)));
        img.addEventListener('error', () => window.requestAnimationFrame(() => relayoutGrid(grid)));
      });
    }

    function observeItems() {
      if (!state.observer) return;
      grid
        .querySelectorAll('[data-masonry-item]')
        .forEach((item) => state.observer.observe(item));
    }

    function refresh() {
      bindImages();
      observeItems();
      grid.classList.remove('masonry-ready');
      window.requestAnimationFrame(() => relayoutGrid(grid));
      waitForGridImages(grid).then(() => {
        window.requestAnimationFrame(() => {
          relayoutGrid(grid);
          grid.classList.add('masonry-ready');
        });
      });
    }

    return { refresh };
  }

  window.GalleryMasonry = { init: initMasonry };

  const leftSidebar = document.querySelector('[data-left-sidebar]');
  const leftToggles = Array.from(document.querySelectorAll('[data-left-toggle]'));
  const sidebarDim = document.querySelector('[data-sidebar-dim]');

  function syncToggleAria(expanded) {
    leftToggles.forEach((btn) => btn.setAttribute('aria-expanded', expanded ? 'true' : 'false'));
  }

  function setDesktopCollapsed(collapsed, persist = true) {
    if (!body) return;
    body.classList.toggle('sidebar-collapsed', collapsed);
    body.classList.remove('sidebar-open');
    root.classList.remove('sidebar-open');
    syncToggleAria(!collapsed);
    if (persist) {
      localStorage.setItem('sidebar-collapsed', collapsed ? '1' : '0');
    }
  }

  if (leftSidebar && leftToggles.length) {
    const mobileQuery = window.matchMedia('(max-width: 640px)');

    function setMobileOpen(open) {
      if (!body) return;
      body.classList.toggle('sidebar-open', open);
      root.classList.toggle('sidebar-open', open);
      body.classList.remove('sidebar-collapsed');
      syncToggleAria(open);
    }

    const applySidebarState = () => {
      if (mobileQuery.matches) {
        setMobileOpen(false);
        return;
      }
      const stored = localStorage.getItem('sidebar-collapsed');
      setDesktopCollapsed(stored === '1', false);
    };

    applySidebarState();

    const handleViewportChange = () => applySidebarState();
    if (mobileQuery.addEventListener) {
      mobileQuery.addEventListener('change', handleViewportChange);
    } else if (mobileQuery.addListener) {
      mobileQuery.addListener(handleViewportChange);
    }

    leftToggles.forEach((btn) => {
      btn.addEventListener('click', () => {
        if (mobileQuery.matches) {
          const next = !body.classList.contains('sidebar-open');
          setMobileOpen(next);
          return;
        }
        const next = !body.classList.contains('sidebar-collapsed');
        setDesktopCollapsed(next, true);
      });
    });

    if (sidebarDim) {
      sidebarDim.addEventListener('click', () => {
        if (mobileQuery.matches) {
          setMobileOpen(false);
        }
      });
    }
  }


  const tagIndexState = { promise: null, data: null };

  function normalizeTagName(input) {
    const value = String(input || '').trim().replace(/^#/, '');
    return value.replace(/\s+/g, ' ').toLowerCase();
  }

  function buildTagIndex(raw) {
    const source = raw && Array.isArray(raw.tags) ? raw.tags : [];
    const aliasMap = new Map();
    const parentMap = new Map();
    const canonicalTags = [];
    const allTags = [];
    source.forEach((item) => {
      const tag = normalizeTagName(item.tag);
      if (!tag) return;
      allTags.push(tag);
      const aliasOf = normalizeTagName(item.alias_of);
      const canonical = aliasOf || tag;
      aliasMap.set(tag, canonical);
      const aliases = Array.isArray(item.aliases) ? item.aliases : [];
      aliases.forEach((alias) => {
        const normalized = normalizeTagName(alias);
        if (normalized) aliasMap.set(normalized, canonical);
      });
      if (!aliasOf) {
        canonicalTags.push(tag);
        const parents = Array.isArray(item.parents) ? item.parents : [];
        parentMap.set(
          tag,
          parents.map((parent) => normalizeTagName(parent)).filter(Boolean)
        );
      }
    });
    canonicalTags.sort();
    return { raw, aliasMap, parentMap, canonicalTags, allTags };
  }

  function loadTagIndex() {
    if (tagIndexState.data) {
      return Promise.resolve(tagIndexState.data);
    }
    if (!tagIndexState.promise) {
      tagIndexState.promise = fetch('/static/data/tag_index.json', { cache: 'no-store' })
        .then((resp) => (resp.ok ? resp.json() : null))
        .then((raw) => {
          if (!raw) return null;
          tagIndexState.data = buildTagIndex(raw);
          return tagIndexState.data;
        })
        .catch(() => null);
    }
    return tagIndexState.promise;
  }

  function escapeHtml(text) {
    return String(text)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/\"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function parseTagInput(value) {
    if (!value) return [];
    const raw = String(value);
    const parts = raw.includes('#') ? raw.split('#') : raw.split(/[,\s|]+/);
    const tags = [];
    parts.forEach((part) => {
      const cleaned = normalizeTagName(part);
      if (cleaned && !tags.includes(cleaned)) tags.push(cleaned);
    });
    return tags;
  }

  function collectAncestors(tag, parentMap, cache) {
    if (cache.has(tag)) return cache.get(tag);
    const parents = parentMap.get(tag) || [];
    const chain = [];
    parents.forEach((parent) => {
      if (!chain.includes(parent)) chain.push(parent);
      const nested = collectAncestors(parent, parentMap, cache);
      nested.forEach((item) => {
        if (!chain.includes(item)) chain.push(item);
      });
    });
    cache.set(tag, chain);
    return chain;
  }

  function findMissingParents(tags, data) {
    const missing = [];
    if (!data) return missing;
    const aliasMap = data.aliasMap;
    const parentMap = data.parentMap;
    const cache = new Map();
    const tagSet = new Set(tags.map((tag) => aliasMap.get(tag) || tag));
    tagSet.forEach((tag) => {
      const parents = collectAncestors(tag, parentMap, cache);
      parents.forEach((parent) => {
        if (!tagSet.has(parent) && !missing.includes(parent)) {
          missing.push(parent);
        }
      });
    });
    return missing;
  }

  function suggestTags(query, data, existingTags) {
    if (!data) return [];
    const normalized = normalizeTagName(query);
    if (!normalized) return [];
    const suggestions = [];
    const aliasMap = data.aliasMap || new Map();
    const canonicalTags = data.canonicalTags || [];
    const existing = new Set(existingTags || []);
    const added = new Set();
    const pushSuggestion = (tag) => {
      if (!tag || existing.has(tag) || added.has(tag)) return;
      added.add(tag);
      suggestions.push(tag);
    };
    const canonical = aliasMap.get(normalized);
    if (canonical && canonical !== normalized) {
      pushSuggestion(canonical);
    }
    aliasMap.forEach((canonicalTag, alias) => {
      if (suggestions.length >= 8) return;
      if (alias.startsWith(normalized)) {
        pushSuggestion(canonicalTag);
      }
    });
    if (suggestions.length < 8) {
      aliasMap.forEach((canonicalTag, alias) => {
        if (suggestions.length >= 8) return;
        if (alias.includes(normalized)) {
          pushSuggestion(canonicalTag);
        }
      });
    }
    canonicalTags.forEach((tag) => {
      if (suggestions.length >= 8) return;
      if (tag.startsWith(normalized)) {
        pushSuggestion(tag);
      }
    });
    if (suggestions.length < 8) {
      canonicalTags.forEach((tag) => {
        if (suggestions.length >= 8) return;
        if (tag.includes(normalized)) {
          pushSuggestion(tag);
        }
      });
    }
    return suggestions;
  }

  let suggestPanelSeq = 0;

  function ensureSuggestPanel(input, options, anchor) {
    let withParents = false;
    let showHint = true;
    if (typeof options === 'object' && options !== null) {
      withParents = Boolean(options.withParents);
      showHint = options.showHint !== false;
    } else {
      withParents = Boolean(options);
      showHint = !withParents;
    }
    if (input.dataset.suggestPanelId) {
      const existing = document.getElementById(input.dataset.suggestPanelId);
      if (existing) return existing;
    }
    const panel = document.createElement('div');
    panel.className = 'suggest-panel';
    panel.id = `suggest-panel-${suggestPanelSeq++}`;
    panel.innerHTML = `
      <div class="suggest-section" data-suggest-tags>
        <div class="suggest-title">猜你想找</div>
        <div class="suggest-list" data-suggest-list></div>
      </div>
      ${
        withParents
          ? `<div class="suggest-section" data-suggest-parents>
        <div class="suggest-title">补全父标签</div>
        <div class="suggest-list" data-suggest-parent-list></div>
      </div>`
          : ''
      }
      ${
        !withParents && showHint
          ? `<div class="suggest-hint" data-suggest-hint>
        <span class="hint-chip">#标签</span>
        <span class="hint-chip">-排除</span>
        <span class="hint-chip">size:large</span>
        <span class="hint-chip">width>=3000</span>
      </div>`
          : ''
      }
    `;
    const host = anchor || input;
    host.insertAdjacentElement('afterend', panel);
    input.dataset.suggestPanelReady = '1';
    input.dataset.suggestPanelId = panel.id;
    return panel;
  }

  function renderSuggestButtons(container, tags, prefix) {
    container.innerHTML = tags
      .map(
        (tag) =>
          `<button class="suggest-chip" type="button" data-suggest-tag="${escapeHtml(
            tag
          )}">${escapeHtml(prefix + tag)}</button>`
      )
      .join('');
  }

  function updateTagSuggest(input, panel, data) {
    if (!panel) return;
    const requireHash = input.dataset.tagRequireHash === '1';
    const tags = parseTagInput(input.value);
    const query = input.value.includes('#')
      ? input.value.split('#').pop()
      : input.value.split(/[,\s|]+/).pop();
    const normalizedQuery = normalizeTagName(query || '');
    const aliasMap = data ? data.aliasMap : new Map();
    const canonicalTags = tags.map((tag) => aliasMap.get(tag) || tag);
    const suggestions = normalizedQuery ? suggestTags(normalizedQuery, data, canonicalTags) : [];
    const missingParents = requireHash ? findMissingParents(canonicalTags, data) : [];
    const tagSection = panel.querySelector('[data-suggest-tags]');
    const tagList = panel.querySelector('[data-suggest-list]');
    const parentSection = panel.querySelector('[data-suggest-parents]');
    const parentList = panel.querySelector('[data-suggest-parent-list]');
    if (tagSection && tagList) {
      if (suggestions.length) {
        tagSection.classList.add('show');
        renderSuggestButtons(tagList, suggestions, requireHash ? '#' : '');
      } else {
        tagSection.classList.remove('show');
      }
    }
    if (parentSection && parentList) {
      if (missingParents.length) {
        parentSection.classList.add('show');
        renderSuggestButtons(parentList, missingParents, '#');
      } else {
        parentSection.classList.remove('show');
      }
    }
    panel.classList.toggle('is-empty', !suggestions.length && !missingParents.length);
  }

  function applyMissingParents(input, data) {
    if (!data) return;
    const requireHash = input.dataset.tagRequireHash === '1';
    if (!requireHash) return;
    const tags = parseTagInput(input.value);
    if (!tags.length) return;
    const aliasMap = data.aliasMap || new Map();
    const canonicalTags = tags.map((tag) => aliasMap.get(tag) || tag);
    const missingParents = findMissingParents(canonicalTags, data);
    if (!missingParents.length) return;
    const canonicalSet = new Set(canonicalTags);
    const nextTags = tags.slice();
    missingParents.forEach((parent) => {
      if (canonicalSet.has(parent)) return;
      canonicalSet.add(parent);
      nextTags.push(parent);
    });
    input.value = nextTags.map((tag) => `#${tag}`).join(' ');
    input.dispatchEvent(new Event('input', { bubbles: true }));
  }

  function applyTagToInput(input, tag, requireHash) {
    const rawValue = input.value || '';
    const tags = parseTagInput(rawValue);
    const endsWithDelimiter = /[,\s|]$/.test(rawValue);
    if (tags.length && !endsWithDelimiter) {
      tags[tags.length - 1] = tag;
    } else if (!tags.includes(tag)) {
      tags.push(tag);
    }
    const unique = [];
    const seen = new Set();
    tags.forEach((item) => {
      if (seen.has(item)) return;
      seen.add(item);
      unique.push(item);
    });
    const prefix = requireHash ? '#' : '';
    input.value = unique.map((item) => `${prefix}${item}`).join(' ');
    input.dispatchEvent(new Event('input', { bubbles: true }));
  }

  function initTagInputs(targets) {
    const inputs = Array.from(targets || document.querySelectorAll('[data-tag-input]'));
    if (!inputs.length) return;
    loadTagIndex().then((data) => {
      if (!data) return;
      const tags = data.canonicalTags || [];
      if (!tags.length) return;
      let hashList = document.getElementById('tag-suggest-hash');
      if (!hashList) {
        hashList = document.createElement('datalist');
        hashList.id = 'tag-suggest-hash';
        document.body.appendChild(hashList);
      }
      let plainList = document.getElementById('tag-suggest');
      if (!plainList) {
        plainList = document.createElement('datalist');
        plainList.id = 'tag-suggest';
        document.body.appendChild(plainList);
      }
      hashList.innerHTML = tags
        .map((tag) => `<option value="${escapeHtml(`#${tag}`)}"></option>`)
        .join('');
      plainList.innerHTML = tags.map((tag) => `<option value="${escapeHtml(tag)}"></option>`).join('');
      inputs.forEach((input) => {
        if (input.dataset.tagSuggestReady === '1') return;
        input.dataset.tagSuggestReady = '1';
        const requireHash = input.dataset.tagRequireHash === '1';
        input.setAttribute('list', requireHash ? 'tag-suggest-hash' : 'tag-suggest');
        const panel = ensureSuggestPanel(input, { withParents: requireHash, showHint: false });
        const update = () => updateTagSuggest(input, panel, data);
        input.addEventListener('input', update);
        input.addEventListener('focus', update);
        input.addEventListener('blur', () => {
          window.setTimeout(() => {
            applyMissingParents(input, data);
            update();
          }, 80);
        });
        panel.addEventListener('click', (event) => {
          const target = event.target.closest('[data-suggest-tag]');
          if (!target) return;
          applyTagToInput(input, normalizeTagName(target.dataset.suggestTag), requireHash);
          applyMissingParents(input, data);
        });
        update();
      });
    });
  }

  function updateSearchSuggest(input, panel, data) {
    if (!panel || !data) return;
    const value = input.value || '';
    const parts = value.trim().split(/\s+/);
    const lastToken = parts.length ? parts[parts.length - 1] : '';
    const token = lastToken.trim();
    const hasHash = token.startsWith('#') || token.startsWith('-#');
    const cleaned = hasHash ? token.replace(/^-?#/, '') : '';
    const suggestions = cleaned ? suggestTags(cleaned, data, []) : [];
    const section = panel.querySelector('[data-suggest-tags]');
    const list = panel.querySelector('[data-suggest-list]');
    if (!section || !list) return;
    const isFocused = document.activeElement === input || panel.contains(document.activeElement);
    if (!hasHash || !suggestions.length) {
      section.classList.remove('show');
      panel.classList.toggle('is-empty', !isFocused);
      return;
    }
    section.classList.add('show');
    const prefix = token.startsWith('-#') ? '-#' : '#';
    renderSuggestButtons(list, suggestions, prefix);
    panel.classList.remove('is-empty');
  }

  function applySearchTag(input, tag) {
    const value = input.value || '';
    const parts = value.trim().split(/\s+/);
    const lastToken = parts.length ? parts[parts.length - 1] : '';
    const prefix = lastToken.startsWith('-') ? '-' : '';
    const hash = lastToken.startsWith('#') ? '#' : '';
    if (parts.length) {
      parts[parts.length - 1] = `${prefix}${hash}${tag}`;
    } else {
      parts.push(`${hash}${tag}`);
    }
    input.value = `${parts.join(' ')} `;
    input.dispatchEvent(new Event('input', { bubbles: true }));
  }

  function initSearchInputs(targets) {
    const inputs = Array.from(targets || document.querySelectorAll('[data-search-input]'));
    if (!inputs.length) return;
    loadTagIndex().then((data) => {
      if (!data) return;
      inputs.forEach((input) => {
        if (input.dataset.searchSuggestReady === '1') return;
        input.dataset.searchSuggestReady = '1';
        const host = input.closest('[data-search-host]') || input.closest('.search-form') || input;
        const panel = ensureSuggestPanel(input, { withParents: false, showHint: true }, host);
        const update = () => updateSearchSuggest(input, panel, data);
        input.addEventListener('input', update);
        input.addEventListener('focus', update);
        input.addEventListener('blur', () => {
          window.setTimeout(update, 80);
        });
        panel.addEventListener('click', (event) => {
          const target = event.target.closest('[data-suggest-tag]');
          if (!target) return;
          applySearchTag(input, normalizeTagName(target.dataset.suggestTag));
        });
        update();
      });
    });
  }

  window.GalleryTagSuggest = {
    loadTagIndex,
    initTagInputs,
    initSearchInputs,
    normalizeTagName,
  };

  const overlay = document.querySelector('[data-search-overlay]');
  const openButtons = document.querySelectorAll('[data-search-open]');
  const closeButtons = document.querySelectorAll('[data-search-close]');
  const overlayInput = overlay ? overlay.querySelector('[data-search-input]') : null;
  const searchInputs = Array.from(document.querySelectorAll('[data-search-input]'));

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
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
      const targetInput =
        overlay && overlay.classList.contains('is-open') ? overlayInput : topSearchInput || overlayInput;
      if (targetInput) {
        event.preventDefault();
        targetInput.focus();
        if (typeof targetInput.select === 'function') targetInput.select();
        if (targetInput === topSearchInput) setSearchFocus(true);
      }
      return;
    }
    if (event.key === 'Escape') {
      closeOverlay();
      closeAvatarMenu();
    }
  });

  initSearchInputs(searchInputs);
  initTagInputs();

  const topSearchHost = document.querySelector('[data-search-host]');
  const topSearchInput = topSearchHost ? topSearchHost.querySelector('[data-search-input]') : null;
  const searchDim = document.querySelector('[data-search-dim]');

  function setSearchFocus(active) {
    if (!body) return;
    body.classList.toggle('search-focus', active);
  }

  function getSearchPanel() {
    if (!topSearchInput) return null;
    const id = topSearchInput.dataset.suggestPanelId;
    return id ? document.getElementById(id) : null;
  }

  if (topSearchHost && topSearchInput) {
    const focusButton = topSearchHost.querySelector('.search-icon');
    if (focusButton) {
      focusButton.addEventListener('click', (event) => {
        event.preventDefault();
        topSearchInput.focus();
      });
    }
    topSearchHost.addEventListener('click', (event) => {
      if (event.target === topSearchInput) return;
      topSearchInput.focus();
    });
    topSearchInput.addEventListener('focus', () => setSearchFocus(true));
    topSearchInput.addEventListener('blur', () => {
      window.setTimeout(() => {
        const panel = getSearchPanel();
        if (panel && panel.contains(document.activeElement)) return;
        setSearchFocus(false);
      }, 80);
    });
  }

  if (searchDim) {
    searchDim.addEventListener('click', () => {
      if (topSearchInput) topSearchInput.blur();
      setSearchFocus(false);
    });
  }

  function initCardLinks(targets) {
    const cards = Array.from(targets || document.querySelectorAll('[data-card-link]'));
    if (!cards.length) return;
    cards.forEach((card) => {
      if (card.dataset.cardLinkReady === '1') return;
      card.dataset.cardLinkReady = '1';
      const url = card.dataset.cardLink;
      if (!url) return;
      card.addEventListener('click', (event) => {
        if (event.defaultPrevented) return;
        const target = event.target;
        if (target && target.closest('a, button, input, textarea, select')) return;
        window.location.href = url;
      });
      card.addEventListener('keydown', (event) => {
        if (event.key !== 'Enter' && event.key !== ' ') return;
        const target = event.target;
        if (target && target.closest('a, button, input, textarea, select')) return;
        event.preventDefault();
        window.location.href = url;
      });
    });
  }

  initCardLinks();
  window.GalleryCardLinks = { init: initCardLinks };

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
      live2dToggle.dataset.live2dState = hidden ? 'off' : 'on';
    }
    updateLive2dLabel();
    live2dToggle.addEventListener('click', () => {
      live2dRoot.classList.toggle('live2d-hidden');
      const hidden = live2dRoot.classList.contains('live2d-hidden');
      setCookie('live2d', hidden ? '0' : '1', 365);
      updateLive2dLabel();
    });
  }

  const adminEntries = Array.from(document.querySelectorAll('[data-admin-entry]'));
  const userAvatar = document.querySelector('[data-user-avatar]');
  const userAvatarImg = document.querySelector('[data-user-avatar-img]');
  const loginLinks = document.querySelectorAll('[data-auth-login-link]');
  const registerLinks = document.querySelectorAll('[data-auth-register-link]');
  const userLinks = document.querySelectorAll('[data-auth-user-link]');

  function setAuthVisibility(isLoggedIn, username, groups) {
    if (userAvatar) {
      userAvatar.hidden = !isLoggedIn;
    }
    loginLinks.forEach((link) => {
      link.hidden = isLoggedIn;
    });
    registerLinks.forEach((link) => {
      link.hidden = isLoggedIn;
    });
    userLinks.forEach((link) => {
      link.hidden = !isLoggedIn;
    });
    if (userAvatarImg && username) {
      userAvatarImg.alt = `${username} 的头像`;
    }
    if (adminEntries.length) {
      const isAdmin = Array.isArray(groups) && groups.includes('admin');
      adminEntries.forEach((entry) => {
        entry.hidden = !isAdmin;
      });
    }
  }

  const avatarMenu = document.querySelector('[data-avatar-menu]');
  const avatarToggle = document.querySelector('[data-avatar-toggle]');
  const avatarDropdown = document.querySelector('[data-avatar-dropdown]');

  function openAvatarMenu() {
    if (!avatarMenu || !avatarDropdown || !avatarToggle) return;
    avatarMenu.classList.add('is-open');
    avatarDropdown.hidden = false;
    avatarToggle.setAttribute('aria-expanded', 'true');
  }

  function closeAvatarMenu() {
    if (!avatarMenu || !avatarDropdown || !avatarToggle) return;
    avatarMenu.classList.remove('is-open');
    avatarDropdown.hidden = true;
    avatarToggle.setAttribute('aria-expanded', 'false');
  }

  if (avatarMenu && avatarToggle && avatarDropdown) {
    avatarMenu.addEventListener('mouseenter', openAvatarMenu);
    avatarMenu.addEventListener('mouseleave', closeAvatarMenu);
    avatarToggle.addEventListener('click', (event) => {
      event.stopPropagation();
      if (avatarMenu.classList.contains('is-open')) {
        closeAvatarMenu();
      } else {
        openAvatarMenu();
      }
    });

    document.addEventListener('click', (event) => {
      if (!avatarMenu.contains(event.target)) closeAvatarMenu();
    });

    window.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') closeAvatarMenu();
    });
  }

  if (userAvatar || loginLinks.length || registerLinks.length) {
    fetch('/auth/me', { credentials: 'include' })
      .then((resp) => {
        if (!resp.ok) return null;
        return resp.json();
      })
      .then((data) => {
        if (data && data.ok) {
          setAuthVisibility(true, data.user, data.groups || []);
        }
      })
      .catch(() => undefined);
  }

  const tagEditor = document.querySelector('[data-tag-editor]');
  if (tagEditor) {
    const tagName = tagEditor.dataset.tagName || '';
    const aliasOf = tagEditor.dataset.tagAliasOf || '';
    const slugField = tagEditor.querySelector('[data-tag-editor-slug]');
    const introField = tagEditor.querySelector('[data-tag-editor-intro]');
    const aliasesField = tagEditor.querySelector('[data-tag-editor-aliases]');
    const aliasToField = tagEditor.querySelector('[data-tag-editor-alias-to]');
    const parentsField = tagEditor.querySelector('[data-tag-editor-parents]');
    const saveBtn = tagEditor.querySelector('[data-tag-editor-save]');
    const hint = tagEditor.querySelector('[data-tag-editor-hint]');

    function normalizeTag(input) {
      let value = String(input || '').trim();
      if (value.includes('%')) {
        try {
          value = decodeURIComponent(value);
        } catch (e) {
          // ignore decode errors
        }
      }
      return value.replace(/\s+/g, ' ').toLowerCase();
    }

    async function fetchJSON(url, options) {
      const resp = await fetch(url, { credentials: 'include', ...options });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) {
        throw new Error(data.error || '请求失败');
      }
      return data;
    }

    fetch('/upload/admin/me', { credentials: 'include' })
      .then((resp) => (resp.ok ? resp.json() : null))
      .then((data) => {
        if (!data || !data.ok) return;
        tagEditor.hidden = false;
        return fetchJSON('/upload/admin/tags');
      })
      .then((data) => {
        if (!data || !data.tags) return;
        const target = normalizeTag(tagName);
        const item =
          data.tags.find((t) => normalizeTag(t.tag) === target) ||
          data.tags.find((t) => normalizeTag(t.tag) === normalizeTag(aliasOf));
        if (!item) return;
        if (slugField) slugField.value = item.slug || '';
        if (introField) introField.value = item.intro || '';
        if (aliasesField) aliasesField.value = (item.aliases || []).join(' | ');
        if (aliasToField) aliasToField.value = item.alias_to || aliasOf || '';
        if (parentsField) parentsField.value = (item.parents || []).join(' | ');
      })
      .catch(() => undefined);

    if (saveBtn) {
      saveBtn.addEventListener('click', async () => {
        if (hint) hint.textContent = '保存中...';
        const payload = {
          tag: tagName,
          slug: slugField ? slugField.value.trim() : '',
          intro: introField ? introField.value.trim() : '',
          aliases: aliasesField ? aliasesField.value.trim() : '',
          alias_to: aliasToField ? aliasToField.value.trim() : '',
          parents: parentsField ? parentsField.value.trim() : '',
        };
        try {
          await fetchJSON('/upload/admin/tags/meta', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
          });
          if (hint) hint.textContent = '已保存，刷新页面生效';
        } catch (err) {
          if (hint) hint.textContent = err.message;
        }
      });
    }
  }
})();
