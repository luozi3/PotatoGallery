(function () {
  if (window.__galleryInit) return;
  const gallery = document.querySelector('[data-gallery-grid]');
  const cards = gallery ? Array.from(gallery.querySelectorAll('[data-image-card]')) : [];
  const empty = gallery ? gallery.querySelector('[data-empty-state]') : null;
  const tabs = Array.from(document.querySelectorAll('[data-collection-tab]'));
  const pills = Array.from(document.querySelectorAll('[data-filter-pill]'));
  const jumps = Array.from(document.querySelectorAll('[data-jump-collection]'));

  const masonryGrids = Array.from(document.querySelectorAll('[data-masonry]'));

  function relayoutMasonry() {
    masonryGrids.forEach((grid) => {
      const rowHeight = parseInt(getComputedStyle(grid).getPropertyValue('grid-auto-rows')) || 8;
      const rowGap = parseInt(getComputedStyle(grid).getPropertyValue('grid-row-gap')) || 0;
      const items = Array.from(grid.querySelectorAll('[data-masonry-item]'));
      items.forEach((item) => {
        if (item.classList.contains('hidden')) {
          return;
        }
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
      if (show) visible += 1;
    });
    if (empty) {
      empty.classList.toggle('show', visible === 0);
    }
    window.requestAnimationFrame(relayoutMasonry);
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
