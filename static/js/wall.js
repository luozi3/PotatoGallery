(function () {
  const storageKey = "luozi_wall_state_v1";
  const sessionViewed = new Set();
  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => Array.from(document.querySelectorAll(sel));

  const galleryItems = [
    {
      id: "pixiv-101098311",
      title: "晨雾庭院",
      desc: "柔光落在石板路上，薄雾里藏着一场安静的醒来。",
      src: "/static/images/pixiv/101098311_p0.jpg",
      width: 1945,
      height: 1459,
      created: "2024-11-12",
      dominant: "#d7c7b3",
      tags: ["晨光", "庭院", "静谧", "暖调"],
      baseLikes: 328,
      baseViews: 1420,
    },
    {
      id: "landing-index",
      title: "琥珀色日落",
      desc: "日落把云层烫成了琥珀色，连风也带着暖意。",
      src: "/static/images/index.png",
      width: 941,
      height: 666,
      created: "2024-10-03",
      dominant: "#cda77a",
      tags: ["黄昏", "云层", "暖色", "暖调"],
      baseLikes: 276,
      baseViews: 980,
    },
    {
      id: "world-ping-1",
      title: "寂静山脊",
      desc: "山影与云海叠在一起，像揉皱的蓝灰色纸。",
      src: "/static/images/world-ping1.png",
      width: 1751,
      height: 930,
      created: "2024-08-18",
      dominant: "#3b4e68",
      tags: ["山脊", "冷调", "云雾"],
      baseLikes: 412,
      baseViews: 1680,
    },
    {
      id: "world-ping-2",
      title: "城市脉搏",
      desc: "窗外的城市是跳动的电路板，灯光像心率在闪。",
      src: "/static/images/world-ping2.png",
      width: 902,
      height: 602,
      created: "2024-09-01",
      dominant: "#d8c6b1",
      tags: ["城市", "夜色", "街景"],
      baseLikes: 199,
      baseViews: 720,
    },
    {
      id: "pixiv-47305056",
      title: "暮色回廊",
      desc: "木质回廊里回荡着脚步声，暖光里藏着故事。",
      src: "/static/images/47305056_p0.jpg",
      width: 1500,
      height: 814,
      created: "2024-07-11",
      dominant: "#7b5a4b",
      tags: ["建筑", "故事感", "胶片"],
      baseLikes: 341,
      baseViews: 1150,
    },
    {
      id: "icon-brown",
      title: "折纸光斑",
      desc: "小小的折纸像灯塔，投出了一点点暖意。",
      src: "/static/images/b_8d8cfbabfab17921c933b11164dd0b55.png",
      width: 303,
      height: 304,
      created: "2024-06-20",
      dominant: "#d3a46a",
      tags: ["可爱", "暖调", "留白"],
      baseLikes: 122,
      baseViews: 420,
    },
  ];

  const ui = {
    grid: $("#wall-grid"),
    search: $("#search-input"),
    sort: $("#sort-select"),
    chips: $$(".chip"),
    totalShots: $("[data-total-shots]"),
    totalViews: $("[data-total-views]"),
    totalLikes: $("[data-total-likes]"),
    themeToggle: $("#theme-toggle"),
    quickView: $("#quick-view"),
    quickImg: $("#quick-img"),
    quickTitle: $("#quick-title"),
    quickDesc: $("#quick-desc"),
    quickTags: $("#quick-tags"),
    quickMeta: $("#quick-meta"),
    quickLike: $("#quick-like"),
    quickClose: $("#quick-close"),
    quickCounts: $("#quick-counts"),
    empty: $("#empty"),
  };

  let state = loadState();
  let activeTag = "all";
  let filtered = galleryItems.slice();

  function loadState() {
    try {
      const saved = JSON.parse(localStorage.getItem(storageKey));
      return saved || { theme: prefersDark() ? "dark" : "light", items: {} };
    } catch (e) {
      return { theme: prefersDark() ? "dark" : "light", items: {} };
    }
  }

  function saveState() {
    localStorage.setItem(storageKey, JSON.stringify(state));
  }

  function prefersDark() {
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  }

  function setTheme(theme) {
    state.theme = theme;
    document.documentElement.setAttribute("data-theme", theme);
    if (ui.themeToggle) {
      ui.themeToggle.textContent = theme === "dark" ? "柔和夜间" : "米色日间";
    }
    saveState();
  }

  function toggleTheme() {
    setTheme(state.theme === "dark" ? "light" : "dark");
  }

  function getItemState(id) {
    if (!state.items[id]) {
      state.items[id] = { likes: 0, views: 0, liked: false };
    }
    return state.items[id];
  }

  function getTotals(item) {
    const s = getItemState(item.id);
    return {
      likes: item.baseLikes + s.likes,
      views: item.baseViews + s.views,
      liked: s.liked,
    };
  }

  function formatNumber(num) {
    if (num >= 10000) return (num / 10000).toFixed(1) + "w";
    if (num >= 1000) return (num / 1000).toFixed(1) + "k";
    return String(num);
  }

  function applyFilters() {
    const term = (ui.search?.value || "").trim().toLowerCase();
    filtered = galleryItems.filter((item) => {
      const inTag = activeTag === "all" || item.tags.includes(activeTag);
      const inTerm = !term ||
        item.title.toLowerCase().includes(term) ||
        item.desc.toLowerCase().includes(term) ||
        item.tags.some((t) => t.toLowerCase().includes(term));
      return inTag && inTerm;
    });

    const sort = ui.sort?.value || "trending";
    filtered.sort((a, b) => {
      const aTotal = getTotals(a);
      const bTotal = getTotals(b);
      if (sort === "trending") {
        return bTotal.likes + bTotal.views - (aTotal.likes + aTotal.views);
      }
      if (sort === "new") {
        return new Date(b.created) - new Date(a.created);
      }
      if (sort === "likes") {
        return bTotal.likes - aTotal.likes;
      }
      return 0;
    });

    render();
    updateSummary();
  }

  function render() {
    if (!ui.grid) return;
    ui.grid.innerHTML = "";

    if (!filtered.length) {
      ui.empty?.classList.remove("hidden");
      return;
    }
    ui.empty?.classList.add("hidden");

    filtered.forEach((item) => {
      const card = createCard(item);
      ui.grid.appendChild(card);
      viewObserver.observe(card);
    });
  }

  function createCard(item) {
    const totals = getTotals(item);
    const card = document.createElement("article");
    card.className = "card";
    card.dataset.id = item.id;

    const thumb = document.createElement("div");
    thumb.className = "thumb";
    thumb.style.background = `linear-gradient(135deg, ${item.dominant} 0%, transparent 65%)`;

    const img = document.createElement("img");
    img.src = item.src;
    img.loading = "lazy";
    img.alt = `${item.title} – LUOZI_SAMA`;
    img.width = item.width;
    img.height = item.height;
    img.style.aspectRatio = `${item.width}/${item.height}`;

    thumb.appendChild(img);

    const body = document.createElement("div");
    body.className = "card-body";

    const meta = document.createElement("div");
    meta.className = "meta";
    meta.innerHTML = `<div><h3>${item.title}</h3><small>${item.created}</small></div><span style="color:${item.dominant}; font-weight:700;">●</span>`;

    const desc = document.createElement("p");
    desc.textContent = item.desc;
    desc.style.margin = "0";
    desc.style.color = "var(--muted)";
    desc.style.fontSize = "13px";

    const tags = document.createElement("div");
    tags.className = "tags";
    item.tags.forEach((tag) => {
      const pill = document.createElement("span");
      pill.className = "pill";
      pill.textContent = tag;
      tags.appendChild(pill);
    });

    const footer = document.createElement("div");
    footer.className = "card-footer";

    const counts = document.createElement("div");
    counts.className = "counts";
    counts.innerHTML = `<span data-like-count="${item.id}">\u2665 ${formatNumber(totals.likes)}</span><span data-view-count="${item.id}">\u25c9 ${formatNumber(totals.views)}</span>`;

    const likeBtn = document.createElement("button");
    likeBtn.className = "icon-btn";
    likeBtn.textContent = getItemState(item.id).liked ? "已点赞" : "点赞";
    if (getItemState(item.id).liked) likeBtn.classList.add("active");
    likeBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      toggleLike(item.id);
      updateCardCounts(item.id);
    });

    footer.append(counts, likeBtn);

    body.append(meta, desc, tags, footer);
    card.append(thumb, body);

    card.addEventListener("click", () => openQuickView(item));

    return card;
  }

  function updateCardCounts(id) {
    const item = galleryItems.find((i) => i.id === id);
    if (!item) return;
    const totals = getTotals(item);
    const likeEl = document.querySelector(`[data-like-count="${id}"]`);
    const viewEl = document.querySelector(`[data-view-count="${id}"]`);
    if (likeEl) likeEl.textContent = `\u2665 ${formatNumber(totals.likes)}`;
    if (viewEl) viewEl.textContent = `\u25c9 ${formatNumber(totals.views)}`;
    if (ui.quickLike && ui.quickLike.dataset.id === id) {
      ui.quickLike.textContent = totals.liked ? "已点赞" : "点赞";
      ui.quickLike.classList.toggle("active", totals.liked);
    }
    if (ui.quickCounts && ui.quickLike && ui.quickLike.dataset.id === id) {
      ui.quickCounts.innerHTML = `\u2665 ${formatNumber(totals.likes)} · \u25c9 ${formatNumber(totals.views)}`;
    }
    updateSummary();
  }

  function updateSummary() {
    const views = filtered.reduce((sum, item) => sum + getTotals(item).views, 0);
    const likes = filtered.reduce((sum, item) => sum + getTotals(item).likes, 0);
    if (ui.totalViews) ui.totalViews.textContent = formatNumber(views);
    if (ui.totalLikes) ui.totalLikes.textContent = formatNumber(likes);
    if (ui.totalShots) ui.totalShots.textContent = filtered.length;
  }

  function toggleLike(id) {
    const item = galleryItems.find((i) => i.id === id);
    if (!item) return;
    const s = getItemState(id);
    s.liked = !s.liked;
    s.likes += s.liked ? 1 : -1;
    if (s.likes < 0) s.likes = 0;
    saveState();
    const btn = ui.grid?.querySelector(`article[data-id="${id}"] .icon-btn`);
    if (btn) {
      btn.textContent = s.liked ? "已点赞" : "点赞";
      btn.classList.toggle("active", s.liked);
    }
  }

  const viewObserver = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        const id = entry.target.dataset.id;
        bumpView(id);
        viewObserver.unobserve(entry.target);
      }
    });
  }, { threshold: 0.6 });

  function bumpView(id) {
    if (sessionViewed.has(id)) return;
    sessionViewed.add(id);
    const item = galleryItems.find((i) => i.id === id);
    if (!item) return;
    const s = getItemState(id);
    s.views += 1;
    saveState();
    updateCardCounts(id);
  }

  function openQuickView(item) {
    if (!ui.quickView) return;
    ui.quickImg.src = item.src;
    ui.quickImg.alt = item.title;
    ui.quickImg.style.aspectRatio = `${item.width}/${item.height}`;
    ui.quickTitle.textContent = item.title;
    ui.quickDesc.textContent = item.desc;
    ui.quickTags.innerHTML = "";
    item.tags.forEach((tag) => {
      const span = document.createElement("span");
      span.className = "badge";
      span.textContent = tag;
      ui.quickTags.appendChild(span);
    });

    ui.quickMeta.innerHTML = "";
    const rows = [
      { label: "创建时间", value: item.created },
      { label: "分辨率", value: `${item.width} × ${item.height}` },
      { label: "基色", value: item.dominant },
      { label: "ID", value: item.id },
    ];
    rows.forEach((row) => {
      const box = document.createElement("div");
      box.className = "meta-box";
      box.innerHTML = `<div class="label">${row.label}</div><div class="value">${row.value}</div>`;
      ui.quickMeta.appendChild(box);
    });

    ui.quickLike.dataset.id = item.id;
    const totals = getTotals(item);
    ui.quickLike.textContent = totals.liked ? "已点赞" : "点赞";
    ui.quickLike.classList.toggle("active", totals.liked);
    if (ui.quickCounts) {
      ui.quickCounts.innerHTML = `\u2665 ${formatNumber(totals.likes)} · \u25c9 ${formatNumber(totals.views)}`;
    }

    ui.quickView.classList.add("open");
    bumpView(item.id);
  }

  function closeQuickView() {
    ui.quickView?.classList.remove("open");
  }

  function bindEvents() {
    ui.search?.addEventListener("input", debounce(applyFilters, 120));
    ui.sort?.addEventListener("change", applyFilters);
    ui.themeToggle?.addEventListener("click", toggleTheme);

    ui.chips.forEach((chip) => {
      chip.addEventListener("click", () => {
        activeTag = chip.dataset.tag;
        ui.chips.forEach((c) => c.classList.toggle("active", c === chip));
        applyFilters();
      });
    });

    ui.quickClose?.addEventListener("click", closeQuickView);
    ui.quickView?.addEventListener("click", (e) => {
      if (e.target === ui.quickView) closeQuickView();
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") closeQuickView();
    });
    ui.quickLike?.addEventListener("click", () => {
      const id = ui.quickLike.dataset.id;
      toggleLike(id);
      updateCardCounts(id);
    });
  }

  function debounce(fn, delay) {
    let t;
    return (...args) => {
      clearTimeout(t);
      t = setTimeout(() => fn.apply(null, args), delay);
    };
  }

  setTheme(state.theme);
  bindEvents();
  applyFilters();
})();
