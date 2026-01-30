(function () {
  if (window.__tagPageInit) return;
  const body = document.body;
  if (!body || !body.classList.contains("page-tag")) return;
  window.__tagPageInit = true;

  const gallery =
    document.querySelector("[data-tag-gallery]") ||
    document.querySelector("[data-gallery-grid]");
  if (!gallery) return;
  const masonry = window.GalleryMasonry ? window.GalleryMasonry.init(gallery) : null;

  const endpoint = (gallery.dataset.galleryEndpoint || gallery.dataset.tagEndpoint || "").trim();
  if (!endpoint) return;

  const paginations = document.querySelectorAll(
    "[data-tag-pagination], [data-tag-pagination-top]"
  );
  const prevBtns = document.querySelectorAll("[data-tag-page-prev]");
  const nextBtns = document.querySelectorAll("[data-tag-page-next]");
  const pageLists = document.querySelectorAll("[data-tag-page-list]");
  const pageSummaries = document.querySelectorAll("[data-tag-page-summary]");
  const pageInputs = document.querySelectorAll("[data-tag-page-input]");
  const pageJumpBtns = document.querySelectorAll("[data-tag-page-jump]");

  const pageLimit = parseInt(gallery.dataset.pageLimit || "40", 10) || 40;
  const totalItems = parseInt(gallery.dataset.total || "0", 10) || 0;
  const totalPages = Math.max(1, Math.ceil(totalItems / pageLimit));

  const state = {
    currentPage: 1,
    loading: false,
    seq: 0,
  };
  const pageCache = new Map();
  const pageHtmlCache = new Map();
  const pageCursors = new Map();
  pageCursors.set(1, null);

  let empty = gallery.querySelector("[data-empty-state]");
  if (!empty) {
    empty = document.createElement("div");
    empty.className = "empty";
    empty.dataset.emptyState = "1";
    empty.textContent = "该标签暂无作品。";
    gallery.appendChild(empty);
  }

  const statusHost =
    document.querySelector("[data-tag-pagination]") ||
    document.querySelector("[data-tag-pagination-top]");
  const loader = document.createElement("div");
  loader.className = "gallery-loader";
  loader.textContent = "加载中…";
  loader.hidden = true;
  const errorBox = document.createElement("div");
  errorBox.className = "gallery-error";
  errorBox.hidden = true;
  const errorText = document.createElement("span");
  const retryButton = document.createElement("button");
  retryButton.type = "button";
  retryButton.className = "btn ghost";
  retryButton.textContent = "重试";
  errorBox.append(errorText, retryButton);
  if (statusHost && statusHost.parentNode) {
    statusHost.parentNode.insertBefore(loader, statusHost);
    statusHost.parentNode.insertBefore(errorBox, statusHost);
  } else if (gallery.parentNode) {
    gallery.parentNode.append(loader, errorBox);
  }

  pageHtmlCache.set(1, gallery.innerHTML);
  const initialCards = Array.from(gallery.querySelectorAll("[data-image-card]"));
  const lastCard = initialCards[initialCards.length - 1];
  if (lastCard && lastCard.dataset.createdAt && lastCard.dataset.imageId) {
    pageCursors.set(2, `${lastCard.dataset.createdAt}|${lastCard.dataset.imageId}`);
  }

  function readPageParam() {
    const params = new URLSearchParams(window.location.search);
    const raw = parseInt(params.get("p") || "1", 10);
    return Number.isFinite(raw) && raw > 0 ? raw : 1;
  }

  function clampPage(page) {
    if (!Number.isFinite(page)) return 1;
    return Math.max(1, Math.min(totalPages, page));
  }

  function syncUrl(page) {
    const params = new URLSearchParams(window.location.search);
    if (page > 1) {
      params.set("p", String(page));
    } else {
      params.delete("p");
    }
    const query = params.toString();
    const next = query ? `${window.location.pathname}?${query}` : window.location.pathname;
    window.history.replaceState(null, "", next);
  }

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

  function buildPageItems(total, current) {
    if (total <= 1) return [];
    const pages = new Set([1, total, current, current - 1, current + 1, current - 2, current + 2]);
    return Array.from(pages)
      .filter((page) => page >= 1 && page <= total)
      .sort((a, b) => a - b);
  }

  function renderPagination() {
    if (!paginations.length) return;
    if (totalItems <= 0) {
      paginations.forEach((node) => {
        node.hidden = true;
      });
      return;
    }
    paginations.forEach((node) => {
      node.hidden = false;
    });
    prevBtns.forEach((btn) => {
      btn.disabled = state.loading || state.currentPage <= 1;
    });
    nextBtns.forEach((btn) => {
      btn.disabled = state.loading || state.currentPage >= totalPages;
    });
    pageSummaries.forEach((node) => {
      node.textContent = `共 ${totalPages} 页 / 共 ${totalItems} 张`;
    });
    pageInputs.forEach((input) => {
      input.max = String(totalPages);
      input.value = String(state.currentPage);
      input.disabled = state.loading || totalPages <= 1;
    });
    pageJumpBtns.forEach((btn) => {
      btn.disabled = state.loading || totalPages <= 1;
    });
    const items = buildPageItems(totalPages, state.currentPage);
    let html = "";
    let last = 0;
    items.forEach((page) => {
      if (last && page - last > 1) {
        html += '<span class="page-ellipsis">…</span>';
      }
      const active = page === state.currentPage ? " is-active" : "";
      html += `<button class="page-number${active}" type="button" data-page="${page}">${page}</button>`;
      last = page;
    });
    pageLists.forEach((list) => {
      list.innerHTML = html;
    });
  }

  function createCard(item) {
    const article = document.createElement("article");
    article.className = "illust-card";
    article.dataset.imageCard = "1";
    article.dataset.masonryItem = "1";
    if (item.detail_path) {
      article.dataset.cardLink = item.detail_path;
    }
    if (item.id) {
      article.dataset.imageId = String(item.id);
    }
    if (item.created_at) {
      article.dataset.createdAt = item.created_at;
    }
    article.dataset.collection = item.collection || "all";
    article.dataset.orientation = item.orientation || "unknown";
    article.dataset.size = item.size_bucket || "unknown";
    article.tabIndex = 0;
    article.setAttribute("role", "link");
    article.setAttribute("aria-label", item.title || "");

    const link = document.createElement("a");
    link.className = "thumb-link";
    link.href = item.detail_path || "/";
    link.setAttribute("aria-label", item.title || "");

    const shell = document.createElement("div");
    shell.className = "thumb-shell";
    const ratio =
      item.thumb_width && item.thumb_height ? `${item.thumb_width}/${item.thumb_height}` : "1/1";
    shell.style.setProperty("--thumb-ratio", ratio);

    const img = document.createElement("img");
    img.className = "thumb";
    img.alt = item.title || "";
    img.loading = "lazy";
    if (item.thumb_width) img.width = item.thumb_width;
    if (item.thumb_height) img.height = item.thumb_height;
    img.src = item.thumb_filename ? `/thumb/${item.thumb_filename}` : "";
    if (item.raw_filename) {
      img.onerror = () => {
        img.onerror = null;
        img.src = `/raw/${item.raw_filename}`;
      };
    }

    shell.appendChild(img);
    link.appendChild(shell);
    article.appendChild(link);

    const body = document.createElement("div");
    body.className = "card-body";

    const title = document.createElement("div");
    title.className = "title";
    title.textContent = item.title || "";
    body.appendChild(title);

    if (item.description) {
      const desc = document.createElement("p");
      desc.className = "desc";
      desc.textContent = item.description;
      body.appendChild(desc);
    }

    const meta = document.createElement("div");
    meta.className = "meta";
    const sizeText = item.width && item.height ? `${item.width}×${item.height}` : "-";
    const bytesText = item.bytes_human || "-";
    const collectionText = item.collection_title || item.collection || "-";
    [sizeText, bytesText, collectionText].forEach((text) => {
      const span = document.createElement("span");
      span.textContent = text;
      meta.appendChild(span);
    });
    body.appendChild(meta);

    const tags = document.createElement("div");
    tags.className = "tags";
    const orientationTag = document.createElement("span");
    orientationTag.className = "tag accent";
    orientationTag.textContent =
      {
        portrait: "竖屏",
        landscape: "横屏",
        square: "方形",
        unknown: "未标",
      }[item.orientation] || "未标";
    tags.appendChild(orientationTag);

    const sizeTag = document.createElement("span");
    sizeTag.className = "tag";
    sizeTag.textContent =
      {
        ultra: "超清",
        large: "高清",
        medium: "中等",
        compact: "轻量",
        unknown: "未标",
      }[item.size_bucket] || "未标";
    tags.appendChild(sizeTag);

    (item.tags || []).slice(0, 3).forEach((tag) => {
      const tagLink = document.createElement("a");
      tagLink.className = "tag ghost";
      tagLink.href = `/tags/${encodeURIComponent(tag.slug || tag.tag || "")}/`;
      if (tag.style) tagLink.setAttribute("style", tag.style);
      tagLink.textContent = `#${tag.tag || ""}`;
      tags.appendChild(tagLink);
    });

    body.appendChild(tags);
    article.appendChild(body);
    return article;
  }

  function clearCards() {
    gallery.querySelectorAll("[data-image-card]").forEach((node) => node.remove());
  }

  function updateEmptyState(items) {
    if (!empty) return;
    empty.classList.toggle("show", items.length === 0 && !state.loading);
  }

  function renderItems(items) {
    clearCards();
    if (!Array.isArray(items)) items = [];
    const fragment = document.createDocumentFragment();
    const newCards = [];
    items.forEach((item) => {
      const card = createCard(item);
      newCards.push(card);
      fragment.appendChild(card);
    });
    if (empty) {
      gallery.insertBefore(fragment, empty);
    } else {
      gallery.appendChild(fragment);
    }
    if (window.GalleryCardLinks) {
      window.GalleryCardLinks.init(newCards);
    }
    if (masonry && masonry.refresh) {
      masonry.refresh({ items: newCards });
    } else {
      gallery.classList.add("masonry-ready");
    }
    updateEmptyState(items);
  }

  function restoreMarkup(html) {
    gallery.innerHTML = html || "";
    empty = gallery.querySelector("[data-empty-state]");
    if (!empty) {
      empty = document.createElement("div");
      empty.className = "empty";
      empty.dataset.emptyState = "1";
      empty.textContent = "该标签暂无作品。";
      gallery.appendChild(empty);
    }
    if (window.GalleryCardLinks) {
      window.GalleryCardLinks.init(gallery.querySelectorAll("[data-card-link]"));
    }
    if (masonry && masonry.refresh) {
      masonry.refresh();
    } else {
      gallery.classList.add("masonry-ready");
    }
    updateEmptyState(gallery.querySelectorAll("[data-image-card]"));
  }

  async function fetchPage(cursor) {
    const params = new URLSearchParams();
    params.set("limit", String(pageLimit));
    if (cursor) params.set("cursor", cursor);
    const url = `${endpoint}${endpoint.includes("?") ? "&" : "?"}${params.toString()}`;
    const resp = await fetch(url, { credentials: "same-origin" });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok || data.ok === false) {
      throw new Error(data.error || "加载失败");
    }
    return data;
  }

  async function fetchAndStorePage(page) {
    const cursor = pageCursors.get(page);
    if (cursor === undefined) {
      throw new Error("分页游标缺失");
    }
    const data = await fetchPage(cursor);
    const items = Array.isArray(data.items) ? data.items : [];
    pageCache.set(page, items);
    if (data.next_cursor) {
      pageCursors.set(page + 1, data.next_cursor);
    }
    if (page < totalPages && !pageCursors.has(page + 1) && data.has_more) {
      throw new Error("分页信息不足");
    }
  }

  function findClosestCursorPage(target) {
    let page = target;
    while (page > 1 && !pageCursors.has(page)) {
      page -= 1;
    }
    return page;
  }

  async function ensurePageData(target) {
    if (target <= 1) return;
    if (!pageCursors.has(2)) {
      await fetchAndStorePage(1);
    }
    const start = findClosestCursorPage(target);
    for (let page = start; page <= target; page += 1) {
      if (pageCache.has(page) || (page === 1 && pageHtmlCache.has(1))) {
        continue;
      }
      await fetchAndStorePage(page);
    }
  }

  async function loadPage(rawPage, options = {}) {
    const target = clampPage(rawPage);
    if (
      !options.force &&
      target === state.currentPage &&
      (pageCache.has(target) || (target === 1 && pageHtmlCache.has(1)))
    ) {
      return;
    }
    state.seq += 1;
    const seq = state.seq;
    setLoading(true);
    setError("");
    renderPagination();
    try {
      if (target === 1 && pageHtmlCache.has(1) && !pageCache.has(1)) {
        restoreMarkup(pageHtmlCache.get(1));
      } else {
        await ensurePageData(target);
        if (seq !== state.seq) return;
        const items = pageCache.get(target) || [];
        renderItems(items);
      }
      state.currentPage = target;
      syncUrl(target);
      renderPagination();
    } catch (err) {
      setError(err.message || "加载失败");
    } finally {
      if (seq === state.seq) {
        setLoading(false);
        renderPagination();
      }
    }
  }

  retryButton.addEventListener("click", () => {
    loadPage(state.currentPage, { force: true });
  });

  prevBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      if (state.currentPage <= 1) return;
      loadPage(state.currentPage - 1);
    });
  });
  nextBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      if (state.currentPage >= totalPages) return;
      loadPage(state.currentPage + 1);
    });
  });
  pageLists.forEach((list) => {
    list.addEventListener("click", (event) => {
      const btn = event.target.closest("[data-page]");
      if (!btn) return;
      const target = parseInt(btn.dataset.page || "1", 10);
      loadPage(target);
    });
  });
  pageInputs.forEach((input) => {
    input.addEventListener("keydown", (event) => {
      if (event.key !== "Enter") return;
      const raw = parseInt(input.value || "0", 10);
      loadPage(raw);
    });
  });
  pageJumpBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      const host = btn.closest("[data-tag-pagination], [data-tag-pagination-top]");
      const input = host ? host.querySelector("[data-tag-page-input]") : null;
      const raw = parseInt((input && input.value) || "0", 10);
      loadPage(raw);
    });
  });

  state.currentPage = clampPage(readPageParam());
  renderPagination();
  if (state.currentPage > 1) {
    loadPage(state.currentPage);
  } else {
    updateEmptyState(initialCards);
  }
})();
