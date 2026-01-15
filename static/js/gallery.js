(function () {
  if (window.__galleryInit) return;
  const gallery = document.querySelector('[data-gallery-grid]');
  if (!gallery) return;

  const empty = gallery.querySelector('[data-empty-state]');
  const tabs = Array.from(document.querySelectorAll('[data-collection-tab]'));
  const pills = Array.from(document.querySelectorAll('[data-filter-pill]'));
  const jumps = Array.from(document.querySelectorAll('[data-jump-collection]'));
  const summary = document.querySelector('[data-filter-summary]');
  const summaryList = summary ? summary.querySelector('[data-filter-summary-list]') : null;
  const summaryClear = summary ? summary.querySelector('[data-filter-summary-clear]') : null;
  const masonry = window.GalleryMasonry ? window.GalleryMasonry.init(gallery) : null;

  const ORIENTATION_LABELS = {
    portrait: '竖屏',
    landscape: '横屏',
    square: '方形',
    unknown: '未标',
  };
  const SIZE_LABELS = {
    ultra: '超清',
    large: '高清',
    medium: '中等',
    compact: '轻量',
    unknown: '未标',
  };

  const state = {
    collection: 'all',
    orientation: 'all',
    size: 'all',
    cursor: null,
    hasMore: true,
    loading: false,
  };
  const requestState = { seq: 0 };
  const pageLimit = parseInt(gallery.dataset.homeLimit || '40', 10) || 40;

  function initStateFromDom() {
    const cards = Array.from(gallery.querySelectorAll('[data-image-card]'));
    const last = cards[cards.length - 1];
    if (last && last.dataset.createdAt && last.dataset.imageId) {
      state.cursor = `${last.dataset.createdAt}|${last.dataset.imageId}`;
    }
    const total = parseInt(gallery.dataset.total || '0', 10);
    if (total && cards.length >= total) {
      state.hasMore = false;
    }
  }

  const sentinel = document.createElement('div');
  sentinel.className = 'gallery-sentinel';
  sentinel.dataset.gallerySentinel = '1';
  gallery.insertAdjacentElement('afterend', sentinel);

  const loader = document.createElement('div');
  loader.className = 'gallery-loader';
  loader.textContent = '加载中…';
  loader.hidden = true;
  sentinel.insertAdjacentElement('afterend', loader);

  const errorBox = document.createElement('div');
  errorBox.className = 'gallery-error';
  errorBox.hidden = true;
  const errorText = document.createElement('span');
  errorText.textContent = '加载失败';
  const retryButton = document.createElement('button');
  retryButton.type = 'button';
  retryButton.className = 'btn ghost';
  retryButton.textContent = '重试';
  errorBox.append(errorText, retryButton);
  loader.insertAdjacentElement('afterend', errorBox);

  function setLoading(value) {
    state.loading = value;
    loader.hidden = !value;
  }

  function setError(message) {
    if (!message) {
      errorBox.hidden = true;
      return;
    }
    errorText.textContent = message;
    errorBox.hidden = false;
  }

  function escapeText(value) {
    return String(value || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/\"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function createCard(item) {
    const article = document.createElement('article');
    article.className = 'illust-card';
    article.dataset.imageCard = '1';
    article.dataset.masonryItem = '1';
    if (item.detail_path) {
      article.dataset.cardLink = item.detail_path;
    }
    if (item.id) {
      article.dataset.imageId = String(item.id);
    }
    if (item.created_at) {
      article.dataset.createdAt = item.created_at;
    }
    article.dataset.collection = item.collection || 'all';
    article.dataset.orientation = item.orientation || 'unknown';
    article.dataset.size = item.size_bucket || 'unknown';
    article.tabIndex = 0;
    article.setAttribute('role', 'link');
    article.setAttribute('aria-label', escapeText(item.title || ''));

    const link = document.createElement('a');
    link.className = 'thumb-link';
    link.href = item.detail_path || '/';
    link.setAttribute('aria-label', escapeText(item.title || ''));

    const shell = document.createElement('div');
    shell.className = 'thumb-shell';
    const ratio = item.thumb_width && item.thumb_height ? `${item.thumb_width}/${item.thumb_height}` : '1/1';
    shell.style.setProperty('--thumb-ratio', ratio);

    const img = document.createElement('img');
    img.className = 'thumb';
    img.alt = item.title || '';
    img.loading = 'lazy';
    if (item.thumb_width) img.width = item.thumb_width;
    if (item.thumb_height) img.height = item.thumb_height;
    img.src = item.thumb_filename ? `/thumb/${item.thumb_filename}` : '';
    if (item.raw_filename) {
      img.onerror = () => {
        img.onerror = null;
        img.src = `/raw/${item.raw_filename}`;
      };
    }

    shell.appendChild(img);
    link.appendChild(shell);
    article.appendChild(link);

    const body = document.createElement('div');
    body.className = 'card-body';

    const title = document.createElement('div');
    title.className = 'title';
    title.textContent = item.title || '';
    body.appendChild(title);

    if (item.description) {
      const desc = document.createElement('p');
      desc.className = 'desc';
      desc.textContent = item.description;
      body.appendChild(desc);
    }

    const meta = document.createElement('div');
    meta.className = 'meta';
    const sizeText = item.width && item.height ? `${item.width}×${item.height}` : '-';
    const bytesText = item.bytes_human || '-';
    const collectionText = item.collection_title || item.collection || '-';
    [sizeText, bytesText, collectionText].forEach((text) => {
      const span = document.createElement('span');
      span.textContent = text;
      meta.appendChild(span);
    });
    body.appendChild(meta);

    const tags = document.createElement('div');
    tags.className = 'tags';
    const orientationTag = document.createElement('span');
    orientationTag.className = 'tag accent';
    orientationTag.textContent = ORIENTATION_LABELS[item.orientation] || ORIENTATION_LABELS.unknown;
    tags.appendChild(orientationTag);

    const sizeTag = document.createElement('span');
    sizeTag.className = 'tag';
    sizeTag.textContent = SIZE_LABELS[item.size_bucket] || SIZE_LABELS.unknown;
    tags.appendChild(sizeTag);

    (item.tags || []).slice(0, 3).forEach((tag) => {
      const tagLink = document.createElement('a');
      tagLink.className = 'tag ghost';
      tagLink.href = `/tags/${encodeURIComponent(tag.slug || tag.tag || '')}/`;
      if (tag.style) tagLink.setAttribute('style', tag.style);
      tagLink.textContent = `#${tag.tag || ''}`;
      tags.appendChild(tagLink);
    });

    body.appendChild(tags);
    article.appendChild(body);
    return article;
  }

  function updateEmptyState() {
    if (!empty) return;
    const cards = gallery.querySelectorAll('[data-image-card]');
    empty.classList.toggle('show', cards.length === 0 && !state.loading);
  }

  function appendItems(items) {
    if (!items.length) return;
    const fragment = document.createDocumentFragment();
    const newCards = [];
    items.forEach((item) => {
      const card = createCard(item);
      newCards.push(card);
      fragment.appendChild(card);
    });
    gallery.appendChild(fragment);
    if (window.GalleryCardLinks) {
      window.GalleryCardLinks.init(newCards);
    }
    if (masonry && masonry.refresh) {
      masonry.refresh({ soft: true, items: newCards });
    }
  }

  function clearCards() {
    gallery.querySelectorAll('[data-image-card]').forEach((node) => node.remove());
    updateEmptyState();
  }

  function buildQuery(cursor) {
    const params = new URLSearchParams();
    params.set('limit', String(pageLimit));
    if (cursor) {
      params.set('cursor', cursor);
    }
    if (state.collection !== 'all') {
      params.set('collection', state.collection);
    }
    if (state.orientation !== 'all') {
      params.set('orientation', state.orientation);
    }
    if (state.size !== 'all') {
      params.set('size', state.size);
    }
    return params.toString();
  }

  function resolveCursorFromItem(item) {
    if (!item || !item.created_at || !item.id) return null;
    return `${item.created_at}|${item.id}`;
  }

  function loadNextPage(reset = false) {
    if (state.loading) return;
    if (!state.hasMore && !reset) return;
    setError('');
    if (reset) {
      clearCards();
      state.cursor = null;
      state.hasMore = true;
    }
    setLoading(true);
    updateEmptyState();
    const requestId = (requestState.seq += 1);
    const query = buildQuery(reset ? null : state.cursor);
    fetch(`/api/home/images?${query}`)
      .then((resp) => {
        if (!resp.ok) throw new Error('bad response');
        return resp.json();
      })
      .then((data) => {
        if (requestId !== requestState.seq) return;
        const items = Array.isArray(data.items) ? data.items : [];
        appendItems(items);
        const nextCursor = data.next_cursor || resolveCursorFromItem(items[items.length - 1]);
        state.cursor = nextCursor || state.cursor;
        state.hasMore = Boolean(data.has_more) && Boolean(nextCursor);
        setLoading(false);
        updateEmptyState();
      })
      .catch(() => {
        if (requestId !== requestState.seq) return;
        setLoading(false);
        setError('加载失败');
        updateEmptyState();
      });
  }

  retryButton.addEventListener('click', () => loadNextPage(false));

  function setActive(buttons, activeEl) {
    buttons.forEach((btn) => {
      btn.classList.toggle('active', btn === activeEl);
      if (btn.hasAttribute('data-collection-tab')) {
        btn.setAttribute('aria-selected', btn === activeEl);
      }
      if (btn.hasAttribute('data-filter-pill')) {
        btn.setAttribute('aria-pressed', btn === activeEl);
      }
    });
  }

  function getButtonLabel(button) {
    if (!button) return '';
    const textNode = Array.from(button.childNodes).find(
      (node) => node.nodeType === Node.TEXT_NODE && node.textContent.trim()
    );
    return (textNode ? textNode.textContent : button.textContent || '').trim();
  }

  function resetFilter(filter) {
    if (filter === 'collection') {
      const defaultTab = tabs.find((tab) => (tab.dataset.collection || 'all') === 'all') || tabs[0];
      if (defaultTab) defaultTab.click();
      return;
    }
    const defaultPill =
      pills.find((pill) => pill.dataset.filter === filter && (pill.dataset.value || 'all') === 'all') ||
      null;
    if (defaultPill) defaultPill.click();
  }

  function updateFilterSummary() {
    if (!summary || !summaryList) return;
    const active = [];
    const activeTab = tabs.find((tab) => tab.classList.contains('active'));
    if (activeTab && (activeTab.dataset.collection || 'all') !== 'all') {
      active.push({ filter: 'collection', label: `分区: ${getButtonLabel(activeTab)}` });
    }
    const activeOrientation = pills.find(
      (pill) => pill.dataset.filter === 'orientation' && pill.classList.contains('active')
    );
    if (activeOrientation && (activeOrientation.dataset.value || 'all') !== 'all') {
      active.push({ filter: 'orientation', label: `方向: ${getButtonLabel(activeOrientation)}` });
    }
    const activeSize = pills.find(
      (pill) => pill.dataset.filter === 'size' && pill.classList.contains('active')
    );
    if (activeSize && (activeSize.dataset.value || 'all') !== 'all') {
      active.push({ filter: 'size', label: `清晰度: ${getButtonLabel(activeSize)}` });
    }
    summaryList.innerHTML = active
      .map(
        (item) =>
          `<button class=\"filter-chip\" type=\"button\" data-filter-chip=\"${item.filter}\" aria-label=\"移除筛选 ${item.label}\">${item.label} ×</button>`
      )
      .join('');
    summary.hidden = active.length === 0;
  }

  function applyFilters() {
    updateFilterSummary();
    loadNextPage(true);
  }

  tabs.forEach((tab) => {
    tab.addEventListener('click', () => {
      state.collection = tab.dataset.collection || 'all';
      setActive(tabs, tab);
      applyFilters();
    });
  });

  pills.forEach((pill) => {
    pill.addEventListener('click', () => {
      const filter = pill.dataset.filter;
      if (!filter) return;
      state[filter] = pill.dataset.value || 'all';
      const siblings = pills.filter((p) => p.dataset.filter === filter);
      setActive(siblings, pill);
      applyFilters();
    });
  });

  if (summaryList) {
    summaryList.addEventListener('click', (event) => {
      const chip = event.target.closest('[data-filter-chip]');
      if (!chip) return;
      resetFilter(chip.dataset.filter);
    });
  }

  if (summaryClear) {
    summaryClear.addEventListener('click', () => {
      resetFilter('collection');
      resetFilter('orientation');
      resetFilter('size');
    });
  }

  jumps.forEach((jump) => {
    jump.addEventListener('click', (e) => {
      const target = jump.dataset.jumpCollection;
      if (!target) return;
      e.preventDefault();
      const tab = tabs.find((t) => (t.dataset.collection || 'all') === target) || tabs[0];
      if (tab) {
        tab.click();
      }
      const controls = document.querySelector('.controls');
      if (controls) {
        controls.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  });

  const observer = new IntersectionObserver(
    (entries) => {
      if (entries.some((entry) => entry.isIntersecting)) {
        loadNextPage(false);
      }
    },
    { rootMargin: '200px 0px' }
  );
  observer.observe(sentinel);

  initStateFromDom();
  updateFilterSummary();
  updateEmptyState();
  if (masonry && masonry.refresh) {
    masonry.refresh();
  }
  window.__galleryInit = true;
})();
