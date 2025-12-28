(function () {
  if (window.__galleryInit) return;
  const gallery = document.querySelector('[data-gallery-grid]');
  const cards = gallery ? Array.from(gallery.querySelectorAll('[data-image-card]')) : [];
  const empty = gallery ? gallery.querySelector('[data-empty-state]') : null;
  const tabs = Array.from(document.querySelectorAll('[data-collection-tab]'));
  const pills = Array.from(document.querySelectorAll('[data-filter-pill]'));
  const jumps = Array.from(document.querySelectorAll('[data-jump-collection]'));
  const summary = document.querySelector('[data-filter-summary]');
  const summaryList = summary ? summary.querySelector('[data-filter-summary-list]') : null;
  const summaryClear = summary ? summary.querySelector('[data-filter-summary-clear]') : null;

  const masonryGrids = Array.from(document.querySelectorAll('[data-masonry]'));
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

  function relayoutMasonry() {
    masonryGrids.forEach((grid) => {
      const rowHeight = parseInt(getComputedStyle(grid).getPropertyValue('grid-auto-rows')) || 8;
      const rowGap = parseInt(getComputedStyle(grid).getPropertyValue('grid-row-gap')) || 0;
      const items = Array.from(grid.querySelectorAll('[data-masonry-item]'));
      items.forEach((item) => {
        if (item.classList.contains('hidden')) {
          return;
        }
        // Reset span before measuring to avoid using an already-stretched height.
        item.style.setProperty('--row-span', '1');
        const height = item.scrollHeight || item.getBoundingClientRect().height;
        const span = Math.max(1, Math.ceil((height + rowGap) / (rowHeight + rowGap)));
        item.style.setProperty('--row-span', span);
      });
    });
  }

  if (masonryGrids.length) {
    const observer = 'ResizeObserver' in window ? new ResizeObserver(() => relayoutMasonry()) : null;
    masonryGrids.forEach((grid) => {
      grid.querySelectorAll('img').forEach((img) => {
        img.addEventListener('load', relayoutMasonry);
      });
      if (observer) {
        grid.querySelectorAll('[data-masonry-item]').forEach((item) => observer.observe(item));
      }
    });
    window.addEventListener('resize', () => {
      window.requestAnimationFrame(relayoutMasonry);
    });
    window.requestAnimationFrame(relayoutMasonry);
    masonryGrids.forEach((grid) => {
      waitForGridImages(grid).then(() => {
        window.requestAnimationFrame(() => {
          relayoutMasonry();
          grid.classList.add('masonry-ready');
        });
      });
    });
  }

  const filters = {
    collection: 'all',
    orientation: 'all',
    size: 'all',
  };

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

  function applyFilters() {
    if (!gallery) return;
    let visible = 0;
    cards.forEach((card) => {
      const matchCollection = filters.collection === 'all' || card.dataset.collection === filters.collection;
      const matchOrientation =
        filters.orientation === 'all' || card.dataset.orientation === filters.orientation;
      const matchSize = filters.size === 'all' || card.dataset.size === filters.size;
      const show = matchCollection && matchOrientation && matchSize;
      card.classList.toggle('hidden', !show);
      if (show) {
        card.style.setProperty('--row-span', '1');
      }
      if (show) visible += 1;
    });
    if (empty) {
      empty.classList.toggle('show', visible === 0);
    }
    window.requestAnimationFrame(() => window.requestAnimationFrame(relayoutMasonry));
    updateFilterSummary();
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
          `<button class="filter-chip" type="button" data-filter-chip="${item.filter}" aria-label="移除筛选 ${item.label}">${item.label} ×</button>`
      )
      .join('');
    summary.hidden = active.length === 0;
  }

  tabs.forEach((tab) => {
    tab.addEventListener('click', () => {
      filters.collection = tab.dataset.collection || 'all';
      setActive(tabs, tab);
      applyFilters();
    });
  });

  pills.forEach((pill) => {
    pill.addEventListener('click', () => {
      const filter = pill.dataset.filter;
      if (!filter) return;
      filters[filter] = pill.dataset.value || 'all';
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

  applyFilters();
  window.__galleryInit = true;
})();
