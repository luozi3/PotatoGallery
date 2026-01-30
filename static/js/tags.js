(() => {
  const grid = document.querySelector("[data-tags-grid]");
  if (!grid) {
    return;
  }
  const cards = Array.from(grid.querySelectorAll(".tag-card"));
  const searchInput = document.querySelector("[data-tags-search]");
  const typeSelect = document.querySelector("[data-tags-type]");
  const countLabel = document.querySelector("[data-tags-count]");
  const emptyHint = document.querySelector("[data-tags-empty]");
  const desktopQuery = window.matchMedia("(min-width: 900px)");

  if (!searchInput || !typeSelect) {
    return;
  }

  const typeMap = new Map();
  for (const card of cards) {
    const typeId = card.dataset.type || "default";
    const typeLabel = card.dataset.typeLabel || typeId;
    if (!typeMap.has(typeId)) {
      typeMap.set(typeId, typeLabel);
    }
  }

  typeSelect.innerHTML = "";
  typeSelect.append(new Option("全部类型", "all"));
  Array.from(typeMap.entries())
    .sort((a, b) => a[1].localeCompare(b[1], "zh-Hans-CN", { sensitivity: "base" }))
    .forEach(([typeId, typeLabel]) => {
      typeSelect.append(new Option(typeLabel, typeId));
    });

  const normalize = (value) => (value || "").toLowerCase().trim();

  const updateColumns = (visibleCount) => {
    if (!desktopQuery.matches || visibleCount <= 0) {
      grid.classList.remove("tags-two-column");
      return;
    }

    const firstVisible = cards.find((card) => !card.hidden);
    if (!firstVisible) {
      grid.classList.remove("tags-two-column");
      return;
    }

    const rowHeight = firstVisible.getBoundingClientRect().height || 34;
    const estimatedHeight = rowHeight * visibleCount;
    const shouldSplit =
      visibleCount >= 18 && estimatedHeight >= window.innerHeight * 1.6;

    grid.classList.toggle("tags-two-column", shouldSplit);
  };

  const applyFilters = () => {
    const query = normalize(searchInput.value);
    const tokens = query ? query.split(/\s+/).filter(Boolean) : [];
    const activeType = typeSelect.value;
    let visible = 0;

    for (const card of cards) {
      const searchValue = normalize(card.dataset.search);
      const matchesQuery = tokens.every((token) => searchValue.includes(token));
      const matchesType = activeType === "all" || card.dataset.type === activeType;
      const show = matchesQuery && matchesType;
      card.hidden = !show;
      if (show) {
        visible += 1;
      }
    }

    if (countLabel) {
      countLabel.textContent = `显示 ${visible} / ${cards.length}`;
    }
    if (emptyHint) {
      emptyHint.hidden = visible !== 0;
    }

    updateColumns(visible);
  };

  const schedule = () => window.requestAnimationFrame(applyFilters);

  searchInput.addEventListener("input", schedule);
  typeSelect.addEventListener("change", applyFilters);
  window.addEventListener("resize", schedule);
  applyFilters();
})();
