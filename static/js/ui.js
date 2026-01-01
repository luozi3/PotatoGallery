(function () {
  const root = document.documentElement;
  const body = document.body;
  const themeToggle = document.querySelector('[data-theme-toggle]');
  const themeMeta = document.querySelector('meta[name=theme-color]');
  const savedTheme = localStorage.getItem('theme');
  const initialTheme =
    savedTheme || (body && body.classList.contains('page-home') ? 'dark' : 'light');
  const SIDEBAR_RESTORE_KEY = 'sidebar-restore-open';

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

  function isDetailPath(path) {
    return path && path.indexOf('/images/') === 0 && path !== '/images/' && path !== '/images';
  }

  function isDetailUrl(url) {
    if (!url) return false;
    try {
      const next = new URL(url, window.location.href);
      if (next.origin !== window.location.origin) return false;
      return isDetailPath(next.pathname || '');
    } catch (e) {
      return false;
    }
  }

  function shouldMarkSidebarRestore() {
    if (!body) return false;
    if (body.classList.contains('page-detail')) return false;
    if (body.classList.contains('sidebar-collapsed') || root.classList.contains('sidebar-collapsed')) {
      return false;
    }
    if (window.matchMedia('(max-width: 640px)').matches) return false;
    return true;
  }

  function markSidebarRestoreOpen() {
    if (!shouldMarkSidebarRestore()) return;
    try {
      localStorage.setItem(SIDEBAR_RESTORE_KEY, '1');
    } catch (e) {}
    root.dataset.sidebarRestore = '1';
  }

  function maybePrepareSidebarRestore(url) {
    if (!isDetailUrl(url)) return;
    markSidebarRestoreOpen();
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

  const tagStrip = document.querySelector('[data-tag-strip-list]');
  let tagStripRaf = 0;

  function clampTagStrip() {
    if (!tagStrip) return;
    const chips = Array.from(tagStrip.querySelectorAll('.tag-chip'));
    if (!chips.length) return;
    chips.forEach((chip) => {
      chip.hidden = false;
    });
    if (window.matchMedia('(max-width: 640px)').matches) return;
    if (!tagStrip.clientWidth) return;
    const moreChip = tagStrip.querySelector('.tag-chip-more');
    const hideTargets = chips.filter((chip) => chip !== moreChip);
    let overflow = tagStrip.scrollWidth > tagStrip.clientWidth;
    for (let i = hideTargets.length - 1; overflow && i >= 0; i -= 1) {
      hideTargets[i].hidden = true;
      overflow = tagStrip.scrollWidth > tagStrip.clientWidth;
    }
  }

  function scheduleClampTagStrip() {
    if (!tagStrip) return;
    if (tagStripRaf) {
      window.cancelAnimationFrame(tagStripRaf);
    }
    tagStripRaf = window.requestAnimationFrame(() => {
      tagStripRaf = 0;
      clampTagStrip();
    });
  }

  if (tagStrip) {
    scheduleClampTagStrip();
    window.addEventListener('load', scheduleClampTagStrip);
    window.addEventListener('resize', scheduleClampTagStrip);
  }

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
  const sidebarDefault = body ? body.getAttribute('data-sidebar-default') : null;
  let sidebarUserOverride = false;

  function syncToggleAria(expanded) {
    leftToggles.forEach((btn) => btn.setAttribute('aria-expanded', expanded ? 'true' : 'false'));
  }

  function setDesktopCollapsed(collapsed, persist = true) {
    if (!body) return;
    body.classList.toggle('sidebar-collapsed', collapsed);
    body.classList.remove('sidebar-open');
    root.classList.remove('sidebar-open');
    root.classList.toggle('sidebar-collapsed', collapsed);
    syncToggleAria(!collapsed);
    if (persist) {
      localStorage.setItem('sidebar-collapsed', collapsed ? '1' : '0');
    }
  }

  if (leftSidebar && leftToggles.length) {
    const mobileQuery = window.matchMedia('(max-width: 640px)');

    function shouldRestoreOpen() {
      if (!body) return false;
      if (body.classList.contains('page-detail')) return false;
      if (localStorage.getItem('sidebar-collapsed') === '1') return false;
      return (
        root.dataset.sidebarRestore === '1' || localStorage.getItem(SIDEBAR_RESTORE_KEY) === '1'
      );
    }

    function clearRestoreOpen() {
      root.dataset.sidebarRestore = '0';
      localStorage.removeItem(SIDEBAR_RESTORE_KEY);
    }

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
      if (shouldRestoreOpen()) {
        setDesktopCollapsed(true, false);
        return;
      }
      if (sidebarDefault === 'collapsed' && !sidebarUserOverride) {
        setDesktopCollapsed(true, false);
        return;
      }
      const stored = localStorage.getItem('sidebar-collapsed');
      setDesktopCollapsed(stored === '1', false);
    };

    applySidebarState();
    if (shouldRestoreOpen()) {
      clearRestoreOpen();
      window.requestAnimationFrame(() => setDesktopCollapsed(false, false));
    }

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
        if (sidebarDefault === 'collapsed') {
          sidebarUserOverride = true;
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

    window.addEventListener('pagehide', (event) => {
      if (!event.persisted || mobileQuery.matches) return;
      if (!shouldRestoreOpen()) return;
      setDesktopCollapsed(true, false);
    });

    window.addEventListener('pageshow', (event) => {
      if (mobileQuery.matches) return;
      const navEntry = performance.getEntriesByType
        ? performance.getEntriesByType('navigation')[0]
        : null;
      const isBackForward = navEntry
        ? navEntry.type === 'back_forward'
        : performance.navigation && performance.navigation.type === 2;
      if (!event.persisted && !isBackForward) return;
      applySidebarState();
      if (shouldRestoreOpen()) {
        clearRestoreOpen();
        window.requestAnimationFrame(() => setDesktopCollapsed(false, false));
      }
    });
  }


  const tagIndexState = { promise: null, data: null };

  function normalizeTagName(input) {
    const value = String(input || '').trim().replace(/^#/, '');
    return value.replace(/\s+/g, ' ').toLowerCase();
  }

  function normalizeTagMatch(input) {
    return normalizeTagName(input).replace(/\s+/g, '');
  }

  function buildTagIndex(raw) {
    const source = raw && Array.isArray(raw.tags) ? raw.tags : [];
    const aliasMap = new Map();
    const aliasCompactMap = new Map();
    const aliasEntries = [];
    const aliasEntryKeys = new Set();
    const parentMap = new Map();
    const canonicalTags = [];
    const allTags = [];
    const registerCompactAlias = (alias, canonical) => {
      const compact = normalizeTagMatch(alias);
      if (!compact) return;
      const existing = aliasCompactMap.get(compact);
      if (!existing) {
        aliasCompactMap.set(compact, canonical);
      } else if (existing !== canonical) {
        aliasCompactMap.set(compact, '');
      }
    };
    const registerAliasEntry = (alias, canonical, isAlias) => {
      if (!alias) return;
      aliasMap.set(alias, canonical);
      registerCompactAlias(alias, canonical);
      if (!isAlias || alias === canonical) return;
      const key = `${alias}::${canonical}`;
      if (aliasEntryKeys.has(key)) return;
      aliasEntryKeys.add(key);
      aliasEntries.push({ alias, canonical, matchKey: normalizeTagMatch(alias) });
    };
    source.forEach((item) => {
      const tag = normalizeTagName(item.tag);
      if (!tag) return;
      allTags.push(tag);
      const aliasOf = normalizeTagName(item.alias_of);
      const canonical = aliasOf || tag;
      registerAliasEntry(tag, canonical, Boolean(aliasOf));
      const aliases = Array.isArray(item.aliases) ? item.aliases : [];
      aliases.forEach((alias) => {
        const normalized = normalizeTagName(alias);
        if (normalized) registerAliasEntry(normalized, canonical, true);
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
    return { raw, aliasMap, aliasCompactMap, aliasEntries, parentMap, canonicalTags, allTags };
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

  function buildTagSuggestions(query, data, options) {
    if (!data) return [];
    const settings = options && typeof options === 'object' ? options : {};
    const limit = Number.isFinite(settings.limit) ? settings.limit : 8;
    const includeAlias = settings.includeAlias === true;
    const existing = new Set(settings.existingTags || []);
    const normalized = normalizeTagName(query);
    const matchKey = normalizeTagMatch(normalized);
    if (!matchKey) return [];
    const suggestions = [];
    const added = new Set();
    const pushSuggestion = (tag, alias) => {
      if (!tag || existing.has(tag) || added.has(tag)) return;
      added.add(tag);
      if (includeAlias) {
        suggestions.push({ tag, alias: alias || '' });
      } else {
        suggestions.push({ tag });
      }
    };
    const aliasEntries = data.aliasEntries || [];
    const canonicalTags = data.canonicalTags || [];
    aliasEntries.forEach((entry) => {
      if (suggestions.length >= limit) return;
      if (entry.matchKey && entry.matchKey.startsWith(matchKey)) {
        pushSuggestion(entry.canonical, entry.alias);
      }
    });
    if (suggestions.length < limit) {
      aliasEntries.forEach((entry) => {
        if (suggestions.length >= limit) return;
        if (entry.matchKey && entry.matchKey.includes(matchKey)) {
          pushSuggestion(entry.canonical, entry.alias);
        }
      });
    }
    canonicalTags.forEach((tag) => {
      if (suggestions.length >= limit) return;
      const tagKey = normalizeTagMatch(tag);
      if (tagKey.startsWith(matchKey)) {
        pushSuggestion(tag, '');
      }
    });
    if (suggestions.length < limit) {
      canonicalTags.forEach((tag) => {
        if (suggestions.length >= limit) return;
        const tagKey = normalizeTagMatch(tag);
        if (tagKey.includes(matchKey)) {
          pushSuggestion(tag, '');
        }
      });
    }
    return suggestions;
  }

  function suggestTags(query, data, existingTags) {
    return buildTagSuggestions(query, data, { existingTags }).map((item) => item.tag);
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
      .map((item) => {
        const tag = typeof item === 'string' ? item : item.tag;
        const alias = typeof item === 'string' ? '' : item.alias;
        const displayAlias = alias && alias !== tag ? `${prefix}${alias}` : '';
        const displayTag = `${prefix}${tag}`;
        const label = displayAlias ? `${displayAlias} -> ${displayTag}` : displayTag;
        return `<button class="suggest-chip" type="button" data-suggest-tag="${escapeHtml(
          tag
        )}">${escapeHtml(label)}</button>`;
      })
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
    const tokenInfo = parseSearchSuggestToken(value);
    const cleaned = tokenInfo.query;
    const suggestions = cleaned
      ? buildTagSuggestions(cleaned, data, { limit: 10, includeAlias: true })
      : [];
    const section = panel.querySelector('[data-suggest-tags]');
    const list = panel.querySelector('[data-suggest-list]');
    if (!section || !list) return;
    const isFocused = document.activeElement === input || panel.contains(document.activeElement);
    if (!suggestions.length) {
      section.classList.remove('show');
      panel.classList.toggle('is-empty', !isFocused);
      return;
    }
    section.classList.add('show');
    renderSuggestButtons(list, suggestions, tokenInfo.prefix);
    panel.classList.remove('is-empty');
  }

  function findLastSearchToken(value) {
    const text = String(value || '');
    let inQuote = false;
    let tokenStart = null;
    let lastStart = 0;
    let lastEnd = 0;
    for (let i = 0; i < text.length; i += 1) {
      const char = text[i];
      if (char === '"') {
        inQuote = !inQuote;
        continue;
      }
      if (!inQuote && /\s/.test(char)) {
        if (tokenStart != null) {
          lastStart = tokenStart;
          lastEnd = i;
          tokenStart = null;
        }
        continue;
      }
      if (tokenStart == null) tokenStart = i;
    }
    if (tokenStart != null) {
      lastStart = tokenStart;
      lastEnd = text.length;
    }
    return { token: text.slice(lastStart, lastEnd), start: lastStart, end: lastEnd };
  }

  function parseSearchSuggestToken(value) {
    const last = findLastSearchToken(value);
    const token = last.token || '';
    if (!token) return { token: '', query: '', prefix: '', start: 0, end: 0 };
    let working = token;
    let negPrefix = '';
    if (working.startsWith('-')) {
      negPrefix = '-';
      working = working.slice(1);
    }
    if (working.startsWith('#')) {
      return {
        token,
        query: working.slice(1).replace(/"/g, ''),
        prefix: `${negPrefix}#`,
        start: last.start,
        end: last.end,
      };
    }
    const keyMatch = working.match(/^([a-zA-Z_]+)[:=](.+)$/);
    if (keyMatch && ['tag', 'tags', 't'].includes(keyMatch[1].toLowerCase())) {
      return {
        token,
        query: keyMatch[2].replace(/"/g, ''),
        prefix: `${negPrefix}${keyMatch[1].toLowerCase()}:`,
        start: last.start,
        end: last.end,
      };
    }
    return {
      token,
      query: working.replace(/"/g, ''),
      prefix: negPrefix,
      start: last.start,
      end: last.end,
    };
  }

  function formatSearchTagToken(tag, prefix) {
    const needsQuote = /\s/.test(tag);
    const wrapped = needsQuote ? `"${tag}"` : tag;
    return `${prefix}${wrapped}`;
  }

  function applySearchTag(input, tag) {
    const value = input.value || '';
    const tokenInfo = parseSearchSuggestToken(value);
    const tokenValue = formatSearchTagToken(tag, tokenInfo.prefix);
    const before = value.slice(0, tokenInfo.start).trimEnd();
    const nextValue = before ? `${before} ${tokenValue}` : tokenValue;
    input.value = `${nextValue} `;
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
        maybePrepareSidebarRestore(url);
        window.location.href = url;
      });
      card.addEventListener('keydown', (event) => {
        if (event.key !== 'Enter' && event.key !== ' ') return;
        const target = event.target;
        if (target && target.closest('a, button, input, textarea, select')) return;
        event.preventDefault();
        maybePrepareSidebarRestore(url);
        window.location.href = url;
      });
    });
  }

  initCardLinks();
  window.GalleryCardLinks = { init: initCardLinks };
  document.addEventListener('click', (event) => {
    if (event.defaultPrevented || event.button !== 0) return;
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    const link = event.target.closest('a');
    if (!link) return;
    if (link.target && link.target !== '_self') return;
    const href = link.getAttribute('href');
    if (!href || href.startsWith('#')) return;
    if (href.startsWith('mailto:') || href.startsWith('tel:') || href.startsWith('javascript:')) {
      return;
    }
    maybePrepareSidebarRestore(href);
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
      root.classList.toggle('live2d-hidden', hidden);
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

  function initUploadProgress() {
    const STORAGE_PREFIX = 'gallery_upload_progress_v1:';
    const MAX_PROGRESS_AGE = 20 * 60 * 1000;
    const UPLOAD_STALE_AGE = 45 * 1000;
    const POLL_INTERVAL = 2000;
    const state = {
      current: null,
      shell: null,
      titleEl: null,
      percentEl: null,
      fillEl: null,
      metaEl: null,
      pollTimer: null,
      removeTimer: null,
      lastSample: { t: 0, loaded: 0 },
    };

    function buildKey(scope, user) {
      return `${STORAGE_PREFIX}${scope}:${user}`;
    }

    function hasProgressForScope(scope) {
      return Object.keys(localStorage).some((key) => key.startsWith(`${STORAGE_PREFIX}${scope}:`));
    }

    function formatBytes(value) {
      const num = Number(value || 0);
      if (!num) return '0B';
      const units = ['B', 'KB', 'MB', 'GB'];
      let idx = 0;
      let out = num;
      while (out >= 1024 && idx < units.length - 1) {
        out /= 1024;
        idx += 1;
      }
      return `${out.toFixed(out >= 100 || idx === 0 ? 0 : 1)}${units[idx]}`;
    }

    function formatSpeed(value) {
      const num = Number(value || 0);
      if (!num) return '0B/s';
      return `${formatBytes(num)}/s`;
    }

    function stageLabel(stage) {
      switch (stage) {
        case 'uploading':
          return '上传中';
        case 'queued':
          return '排队中';
        case 'processing':
          return '处理中';
        case 'processed':
          return '等待发布';
        case 'published':
          return '已完成';
        case 'failed':
          return '处理失败';
        default:
          return '准备中';
      }
    }

    function stageMetaText(current) {
      if (!current) return '';
      if (current.stage === 'uploading') {
        const loaded = formatBytes(current.loaded || 0);
        const total = formatBytes(current.total || 0);
        const speed = formatSpeed(current.speed_bps || 0);
        return `${loaded} / ${total} · ${speed}`;
      }
      if (current.stage === 'processed') {
        return '生成静态页中';
      }
      if (current.stage === 'queued') {
        return '等待处理';
      }
      if (current.stage === 'processing') {
        return '生成缩略图中';
      }
      if (current.stage === 'failed') {
        return current.message || '处理失败';
      }
      if (current.stage === 'published') {
        return '发布完成';
      }
      return current.message || '';
    }

    function getPercent(current) {
      if (!current) return 0;
      if (current.stage === 'uploading') {
        const total = Number(current.total || 0);
        if (!total) return 0;
        return Math.min(100, Math.round((Number(current.loaded || 0) / total) * 100));
      }
      return Math.max(0, Math.min(100, Math.round(Number(current.percent || 0))));
    }

    function ensureShell() {
      if (state.shell) return;
      const shell = document.createElement('div');
      shell.className = 'upload-progress';
      shell.innerHTML = `
        <div class="upload-progress-card" role="status" aria-live="polite">
          <div class="upload-progress-head">
            <span class="upload-progress-title" data-upload-progress-title></span>
            <span class="upload-progress-percent" data-upload-progress-percent></span>
          </div>
          <div class="upload-progress-bar">
            <div class="upload-progress-fill" data-upload-progress-fill></div>
          </div>
          <div class="upload-progress-meta" data-upload-progress-meta></div>
        </div>
      `;
      document.body.appendChild(shell);
      state.shell = shell;
      state.titleEl = shell.querySelector('[data-upload-progress-title]');
      state.percentEl = shell.querySelector('[data-upload-progress-percent]');
      state.fillEl = shell.querySelector('[data-upload-progress-fill]');
      state.metaEl = shell.querySelector('[data-upload-progress-meta]');
    }

    function render(current) {
      if (!current) return;
      ensureShell();
      const percent = getPercent(current);
      if (state.titleEl) state.titleEl.textContent = stageLabel(current.stage);
      if (state.percentEl) state.percentEl.textContent = `${percent}%`;
      if (state.fillEl) state.fillEl.style.width = `${percent}%`;
      if (state.metaEl) state.metaEl.textContent = stageMetaText(current);
      state.shell.classList.add('is-visible');
      if (state.removeTimer) {
        clearTimeout(state.removeTimer);
        state.removeTimer = null;
      }
    }

    function hideShell(immediate) {
      if (!state.shell) return;
      state.shell.classList.remove('is-visible');
      if (state.removeTimer) {
        clearTimeout(state.removeTimer);
      }
      const remove = () => {
        if (!state.shell) return;
        state.shell.remove();
        state.shell = null;
        state.titleEl = null;
        state.percentEl = null;
        state.fillEl = null;
        state.metaEl = null;
      };
      if (immediate) {
        remove();
        return;
      }
      state.removeTimer = window.setTimeout(remove, 240);
    }

    function stopPolling() {
      if (!state.pollTimer) return;
      clearInterval(state.pollTimer);
      state.pollTimer = null;
    }

    function saveProgress(current) {
      if (!current || !current.scope || !current.user) return;
      const payload = { ...current, updated_at: Date.now() };
      localStorage.setItem(buildKey(current.scope, current.user), JSON.stringify(payload));
    }

    function clearProgress(current) {
      if (!current || !current.scope || !current.user) return;
      localStorage.removeItem(buildKey(current.scope, current.user));
    }

    function setCurrent(current, persist = true) {
      state.current = current;
      if (persist) saveProgress(current);
      if (!current) return;
      render(current);
      if (['queued', 'processing', 'processed'].includes(current.stage)) {
        startPolling(current);
      } else {
        stopPolling();
      }
      if (['published', 'failed', 'missing'].includes(current.stage)) {
        clearProgress(current);
        window.setTimeout(() => hideShell(false), 800);
      }
    }

    function start(scope, user, file) {
      if (!scope || !user) return;
      state.lastSample = { t: Date.now(), loaded: 0 };
      setCurrent(
        {
          scope,
          user,
          uuid: null,
          stage: 'uploading',
          percent: 0,
          loaded: 0,
          total: file ? file.size : 0,
          speed_bps: 0,
          started_at: Date.now(),
          message: '',
        },
        true
      );
    }

    function updateUpload(scope, user, loaded, total) {
      if (!scope || !user) return;
      const now = Date.now();
      const delta = now - (state.lastSample.t || now);
      const deltaBytes = loaded - (state.lastSample.loaded || 0);
      const speed = delta > 0 ? (deltaBytes / delta) * 1000 : 0;
      state.lastSample = { t: now, loaded };
      setCurrent(
        {
          scope,
          user,
          uuid: state.current ? state.current.uuid : null,
          stage: 'uploading',
          loaded,
          total,
          speed_bps: speed,
          percent: 0,
          started_at: state.current ? state.current.started_at : now,
          message: '',
        },
        true
      );
    }

    function finishUpload(scope, user, uuidValue) {
      if (!scope || !user) return;
      setCurrent(
        {
          scope,
          user,
          uuid: uuidValue,
          stage: 'queued',
          percent: 25,
          loaded: state.current ? state.current.loaded : 0,
          total: state.current ? state.current.total : 0,
          speed_bps: 0,
          started_at: state.current ? state.current.started_at : Date.now(),
          message: '',
        },
        true
      );
    }

    function fail(scope, user, message) {
      if (!scope || !user) return;
      setCurrent(
        {
          scope,
          user,
          uuid: state.current ? state.current.uuid : null,
          stage: 'failed',
          percent: 100,
          loaded: state.current ? state.current.loaded : 0,
          total: state.current ? state.current.total : 0,
          speed_bps: 0,
          started_at: state.current ? state.current.started_at : Date.now(),
          message: message || '上传失败',
        },
        true
      );
    }

    function loadProgress(scope, user) {
      if (!scope || !user) return null;
      const raw = localStorage.getItem(buildKey(scope, user));
      if (!raw) return null;
      try {
        const parsed = JSON.parse(raw);
        const age = Date.now() - Number(parsed.updated_at || 0);
        if (age > MAX_PROGRESS_AGE) {
          localStorage.removeItem(buildKey(scope, user));
          return null;
        }
        if (parsed.stage === 'uploading' && age > UPLOAD_STALE_AGE) {
          localStorage.removeItem(buildKey(scope, user));
          return null;
        }
        return parsed;
      } catch (err) {
        localStorage.removeItem(buildKey(scope, user));
        return null;
      }
    }

    function restore(scope, user) {
      const existing = loadProgress(scope, user);
      if (!existing) return;
      setCurrent(existing, false);
    }

    function fetchStatus(current) {
      if (!current || !current.uuid) return Promise.resolve(null);
      const stamp = Date.now();
      const endpoint =
        current.scope === 'admin'
          ? `/upload/admin/upload/status?uuid=${current.uuid}&t=${stamp}`
          : `/api/upload/status?uuid=${current.uuid}&t=${stamp}`;
      return fetch(endpoint, { credentials: 'include', cache: 'no-store' })
        .then((resp) => (resp.ok ? resp.json() : null))
        .catch(() => null);
    }

    function startPolling(current) {
      if (state.pollTimer || !current || !current.uuid) return;
      state.pollTimer = window.setInterval(async () => {
        const latest = state.current;
        if (!latest || !latest.uuid) {
          stopPolling();
          return;
        }
        const data = await fetchStatus(latest);
        if (!data || !data.ok) return;
        if (!state.current || state.current.uuid !== latest.uuid) return;
        setCurrent(
          {
            scope: latest.scope,
            user: latest.user,
            uuid: latest.uuid,
            stage: data.stage || latest.stage,
            percent: data.percent || latest.percent,
            loaded: latest.loaded,
            total: latest.total,
            speed_bps: 0,
            started_at: latest.started_at,
            message: data.message || '',
          },
          true
        );
      }, POLL_INTERVAL);
    }

    window.addEventListener('storage', (event) => {
      if (!event.key || !event.key.startsWith(STORAGE_PREFIX)) return;
      if (!state.current) return;
      const expected = buildKey(state.current.scope, state.current.user);
      if (event.key !== expected) return;
      const next = loadProgress(state.current.scope, state.current.user);
      if (next) {
        setCurrent(next, false);
      } else {
        stopPolling();
        hideShell(false);
      }
    });

    return {
      start,
      updateUpload,
      finishUpload,
      fail,
      restore,
      hasProgressForScope,
    };
  }

  const uploadProgress = initUploadProgress();
  window.GalleryUploadProgress = uploadProgress;

  const adminEntries = Array.from(document.querySelectorAll('[data-admin-entry]'));
  const userAvatar = document.querySelector('[data-user-avatar]');
  const userAvatarImg = document.querySelector('[data-user-avatar-img]');
  const loginLinks = document.querySelectorAll('[data-auth-login-link]');
  const registerLinks = document.querySelectorAll('[data-auth-register-link]');
  const userLinks = document.querySelectorAll('[data-auth-user-link]');
  const AUTH_HINT_KEY = 'auth-hint';

  function setAuthHint(isLoggedIn) {
    try {
      if (isLoggedIn) {
        localStorage.setItem(AUTH_HINT_KEY, '1');
        root.classList.add('auth-hint-logged-in');
      } else {
        localStorage.removeItem(AUTH_HINT_KEY);
        root.classList.remove('auth-hint-logged-in');
      }
    } catch (e) {}
  }

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

  const shouldCheckUserAuth =
    userAvatar || loginLinks.length || registerLinks.length || uploadProgress.hasProgressForScope('user');
  if (shouldCheckUserAuth) {
    fetch('/auth/me', { credentials: 'include' })
      .then((resp) => {
        if (!resp.ok) return null;
        return resp.json();
      })
      .then((data) => {
        if (data && data.ok) {
          setAuthVisibility(true, data.user, data.groups || []);
          setAuthHint(true);
          uploadProgress.restore('user', data.user);
          return;
        }
        setAuthHint(false);
      })
      .catch(() => setAuthHint(false));
  }

  if (uploadProgress.hasProgressForScope('admin')) {
    fetch('/upload/admin/me', { credentials: 'include' })
      .then((resp) => (resp.ok ? resp.json() : null))
      .then((data) => {
        if (!data || !data.ok) return;
        uploadProgress.restore('admin', data.user);
      })
      .catch(() => undefined);
  }

  const detailMedia = document.querySelector('[data-detail-media]');
  if (detailMedia) {
    const image = detailMedia.querySelector('[data-detail-image]');
    const status = detailMedia.querySelector('[data-image-status]');
    if (image) {
      const thumbSrc = image.dataset.thumbSrc || image.getAttribute('src') || '';
      const fullSrc = image.dataset.fullSrc || '';
      const canToggle = thumbSrc && fullSrc && thumbSrc !== fullSrc;

      const setMode = (mode) => {
        const useFull = mode === 'full';
        detailMedia.dataset.imageMode = useFull ? 'full' : 'thumb';
        if (useFull && fullSrc) {
          image.src = fullSrc;
        } else if (thumbSrc) {
          image.src = thumbSrc;
        }
        if (status) status.textContent = useFull ? '原图' : '略缩图';
      };

      if (canToggle) {
        setMode(detailMedia.dataset.imageMode === 'full' ? 'full' : 'thumb');
        image.addEventListener('click', () => {
          const next = detailMedia.dataset.imageMode === 'full' ? 'thumb' : 'full';
          setMode(next);
        });
      } else {
        if (status) status.textContent = '原图';
        detailMedia.dataset.imageMode = 'full';
      }
    }
  }

  const tagTreeToggle = document.querySelector('[data-tag-tree-toggle]');
  const tagTreePanel = document.querySelector('[data-tag-tree-panel]');
  if (tagTreeToggle && tagTreePanel) {
    const setExpanded = (expanded) => {
      tagTreePanel.hidden = !expanded;
      tagTreeToggle.setAttribute('aria-expanded', expanded ? 'true' : 'false');
    };
    setExpanded(false);
    tagTreeToggle.addEventListener('click', () => {
      setExpanded(tagTreePanel.hidden);
    });
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
