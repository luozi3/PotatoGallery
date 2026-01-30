(function () {

  function initTagSuggest(container) {
    if (!window.GalleryTagSuggest || !window.GalleryTagSuggest.initTagInputs) return;
    const scope = container || document;
    const inputs = scope.querySelectorAll("[data-tag-input]");
    if (!inputs.length) return;
    window.GalleryTagSuggest.initTagInputs(inputs);
  }
  async function fetchJSON(url, options) {
    const resp = await fetch(url, { credentials: "include", ...options });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      const message = data.error || "请求失败";
      throw new Error(message);
    }
    return data;
  }

  function uploadWithProgress(url, formData, onProgress) {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("POST", url, true);
      xhr.withCredentials = true;
      xhr.upload.addEventListener("progress", (event) => {
        if (!event.lengthComputable) return;
        if (onProgress) onProgress(event.loaded, event.total);
      });
      xhr.addEventListener("load", () => {
        let data = {};
        try {
          data = JSON.parse(xhr.responseText || "{}");
        } catch (err) {
          data = {};
        }
        if (xhr.status >= 200 && xhr.status < 300 && data && data.ok) {
          resolve(data);
          return;
        }
        const message = data.error || "上传失败";
        reject(new Error(message));
      });
      xhr.addEventListener("error", () => reject(new Error("网络错误")));
      xhr.send(formData);
    });
  }

  function escapeHtml(text) {
    return String(text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function resolveDetailPath(img) {
    if (!img) return "/images/";
    if (img.detail_path) return img.detail_path;
    const shortId = img.short_id || img.image_id || img.id;
    if (shortId) {
      return `/images/${shortId}/index.html`;
    }
    return `/images/${img.uuid || ""}/index.html`;
  }

  function renderCollectionOptions(select, collections, includeAuto) {
    if (!select) return;
    const options = [];
    if (includeAuto) {
      options.push('<option value="">自动</option>');
    }
    collections.forEach((item) => {
      options.push(
        `<option value="${escapeHtml(item.slug)}">${escapeHtml(item.title)}</option>`
      );
    });
    select.innerHTML = options.join("");
  }

  function setFormDisabled(form, disabled) {
    if (!form || !form.elements) return;
    Array.from(form.elements).forEach((el) => {
      el.disabled = disabled;
    });
  }

  function bindUserUploadForm(form, options) {
    if (!form) return;
    const hint = options && options.hint;
    const currentUser = options && options.currentUser ? options.currentUser : "";
    const onSuccess = options && options.onSuccess;
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (hint) hint.textContent = "上传中...";
      const formData = new FormData(form);
      const fileInput = form.querySelector("input[type='file']");
      const file = fileInput && fileInput.files ? fileInput.files[0] : null;
      const progress = window.GalleryUploadProgress;
      const submitBtn = form.querySelector("button[type='submit']");
      if (submitBtn) submitBtn.disabled = true;
      if (progress && file && currentUser) {
        progress.start("user", currentUser, file);
      }
      try {
        const data = await uploadWithProgress("/api/upload", formData, (loaded, total) => {
          if (progress && currentUser) {
            progress.updateUpload("user", currentUser, loaded, total);
          }
        });
        if (hint) hint.textContent = "上传成功，等待处理";
        if (progress && currentUser) {
          progress.finishUpload("user", currentUser, data.uuid);
        }
        form.reset();
        if (onSuccess) onSuccess(data);
      } catch (err) {
        if (hint) hint.textContent = err.message;
        if (progress && currentUser) {
          progress.fail("user", currentUser, err.message);
        }
      } finally {
        if (submitBtn) submitBtn.disabled = false;
      }
    });
  }

  async function initMyPage() {
    const page = document.querySelector("[data-user-page]");
    if (!page) return;
    const form = document.querySelector("[data-user-upload-form]");
    const collectionSelect = document.querySelector("[data-user-upload-collection]");
    const hint = document.querySelector("[data-user-upload-hint]");
    const loginHint = document.querySelector("[data-user-login-hint]");
    const gallery = document.querySelector("[data-user-gallery]");
    const empty = document.querySelector("[data-user-empty]");
    const queryInput = document.querySelector("[data-user-query]");
    const collectionFilter = document.querySelector("[data-user-collection-filter]");
    const paginations = document.querySelectorAll(
      "[data-user-pagination], [data-user-pagination-top]"
    );
    const pagePrevBtns = document.querySelectorAll("[data-user-page-prev]");
    const pageNextBtns = document.querySelectorAll("[data-user-page-next]");
    const pageLists = document.querySelectorAll("[data-user-page-list]");
    const pageSummaries = document.querySelectorAll("[data-user-page-summary]");
    const pageInputs = document.querySelectorAll("[data-user-page-input]");
    const pageJumpBtns = document.querySelectorAll("[data-user-page-jump]");
    const masonry = window.GalleryMasonry ? window.GalleryMasonry.init(gallery) : null;

    let images = [];
    let currentPage = 1;
    let totalPages = 1;
    let totalItems = 0;
    const filterState = {
      query: "",
      collection: "all",
    };

    const initialParams = new URLSearchParams(window.location.search);
    filterState.query = initialParams.get("q") || "";
    filterState.collection = initialParams.get("collection") || "all";
    const pageParam = initialParams.get("p") || initialParams.get("page") || "";
    const parsedPage = parseInt(pageParam, 10);
    if (Number.isFinite(parsedPage) && parsedPage > 0) {
      currentPage = parsedPage;
    }
    if (queryInput) queryInput.value = filterState.query;
    if (collectionFilter) collectionFilter.value = filterState.collection;

    let me = null;
    let currentUser = "";
    try {
      me = await fetchJSON("/auth/me");
      currentUser = me.user || "";
    } catch (err) {
      if (loginHint) loginHint.textContent = "请先登录后再管理作品。";
      setFormDisabled(form, true);
      return;
    }

    if (loginHint) loginHint.textContent = `已登录：${me.user}`;

    function renderCollectionFilter(collections) {
      if (!collectionFilter) return;
      const selected = filterState.collection || "all";
      const options = ['<option value="all">全部分区</option>'];
      (collections || []).forEach((item) => {
        options.push(
          `<option value="${escapeHtml(item.slug)}">${escapeHtml(item.title)}</option>`
        );
      });
      collectionFilter.innerHTML = options.join("");
      collectionFilter.value = selected;
      if (collectionFilter.value !== selected) {
        filterState.collection = "all";
        collectionFilter.value = "all";
      }
    }

    function buildQueryParams(page) {
      const params = new URLSearchParams();
      if (filterState.query) {
        params.set("q", filterState.query);
      }
      if (filterState.collection && filterState.collection !== "all") {
        params.set("collection", filterState.collection);
      }
      params.set("p", page);
      return params;
    }

    function syncUrl(page) {
      const params = buildQueryParams(page);
      const next = `${window.location.pathname}?${params.toString()}`;
      window.history.replaceState(null, "", next);
    }

    function buildPageItems(total, current) {
      if (total <= 1) return [];
      const pages = new Set([1, total, current, current - 1, current + 1, current - 2, current + 2]);
      const list = Array.from(pages)
        .filter((page) => page >= 1 && page <= total)
        .sort((a, b) => a - b);
      return list;
    }

    function renderPagination() {
      if (!paginations.length || !pageLists.length || !pagePrevBtns.length || !pageNextBtns.length) {
        return;
      }
      if (totalItems <= 0) {
        paginations.forEach((node) => {
          node.hidden = true;
        });
        return;
      }
      const safeTotal = Math.max(1, totalPages || 1);
      paginations.forEach((node) => {
        node.hidden = false;
      });
      pagePrevBtns.forEach((btn) => {
        btn.disabled = currentPage <= 1;
      });
      pageNextBtns.forEach((btn) => {
        btn.disabled = currentPage >= safeTotal;
      });
      pageSummaries.forEach((node) => {
        node.textContent = `共 ${safeTotal} 页 / 共 ${totalItems} 张`;
      });
      pageInputs.forEach((input) => {
        input.max = String(safeTotal);
        input.value = String(currentPage);
        input.disabled = safeTotal <= 1;
      });
      pageJumpBtns.forEach((btn) => {
        btn.disabled = safeTotal <= 1;
      });
      const items = buildPageItems(safeTotal, currentPage);
      let html = "";
      let last = 0;
      items.forEach((page) => {
        if (last && page - last > 1) {
          html += '<span class="page-ellipsis">…</span>';
        }
        const active = page === currentPage ? " is-active" : "";
        html += `<button class="page-number${active}" type="button" data-page="${page}">${page}</button>`;
        last = page;
      });
      pageLists.forEach((list) => {
        list.innerHTML = html;
      });
    }

    function jumpToPage(rawValue) {
      if (!totalPages) return;
      const target = parseInt(rawValue || "0", 10);
      if (!Number.isFinite(target)) return;
      const safeTotal = Math.max(1, totalPages || 1);
      const clamped = Math.max(1, Math.min(safeTotal, target));
      if (clamped === currentPage) return;
      loadImages(clamped);
    }

    function renderImages(list) {
      if (!gallery) return;
      if (!list.length) {
        gallery.innerHTML = "";
        if (empty) empty.classList.add("show");
        if (masonry) {
          masonry.refresh();
        } else {
          gallery.classList.add("masonry-ready");
        }
        return;
      }
      if (empty) empty.classList.remove("show");
      gallery.innerHTML = list
        .map((img) => {
          const tags = (img.tags || []).map((t) => `#${escapeHtml(t)}`).join(" ");
          const detailPath = escapeHtml(resolveDetailPath(img));
          return `
          <article class="illust-card user-card" data-masonry-item data-card-link="${detailPath}" tabindex="0" role="link" aria-label="${escapeHtml(
            img.title || ""
          )}">
            <a class="thumb-link" href="${detailPath}">
              <div class="thumb-shell" style="--thumb-ratio:${img.thumb_width}/${img.thumb_height};">
                <img class="thumb" src="/thumb/${escapeHtml(
                  img.thumb_filename || ""
                )}" alt="${escapeHtml(img.title || "")}" loading="lazy" width="${img.thumb_width || ""}" height="${
            img.thumb_height || ""
          }" onerror="this.onerror=null;this.src='/raw/${escapeHtml(img.raw_filename || "")}';">
              </div>
            </a>
            <div class="card-body">
              <div class="title">${escapeHtml(img.title || "")}</div>
              ${img.description ? `<p class="desc">${escapeHtml(img.description)}</p>` : ""}
              <div class="meta">
                <span>${escapeHtml(img.collection_title || img.collection || "")}</span>
                <span>${escapeHtml(img.created_at || "")}</span>
              </div>
              ${tags ? `<div class="tags"><span class="tag ghost">${tags}</span></div>` : ""}
              <div class="admin-actions-row">
                <a class="btn ghost" href="${detailPath}">编辑</a>
              </div>
            </div>
          </article>
        `;
        })
        .join("");
      if (window.GalleryCardLinks) {
        window.GalleryCardLinks.init(gallery.querySelectorAll('[data-card-link]'));
      }
      if (masonry) {
        masonry.refresh();
        return;
      }
      gallery.classList.add("masonry-ready");
    }

    function applyFilters() {
      filterState.query = (queryInput && queryInput.value.trim()) || "";
      filterState.collection = collectionFilter ? collectionFilter.value : "all";
      loadImages(1);
    }

    async function loadImages(page) {
      const targetPage = page || currentPage || 1;
      const params = buildQueryParams(targetPage);
      const data = await fetchJSON(`/api/my/images?${params.toString()}`);
      images = data.images || [];
      currentPage = Number(data.page || targetPage) || 1;
      totalPages = Number(data.pages || 1) || 1;
      totalItems = Number(data.total || images.length) || 0;
      renderCollectionOptions(collectionSelect, data.collections || [], true);
      renderCollectionFilter(data.collections || []);
      renderImages(images);
      renderPagination();
      syncUrl(currentPage);
    }

    bindUserUploadForm(form, {
      hint,
      currentUser,
      onSuccess: () => loadImages(1),
    });

    initTagSuggest(document);
    if (queryInput) {
      let searchTimer = null;
      queryInput.addEventListener("input", () => {
        if (searchTimer) window.clearTimeout(searchTimer);
        searchTimer = window.setTimeout(() => {
          searchTimer = null;
          applyFilters();
        }, 300);
      });
    }

    if (collectionFilter) {
      collectionFilter.addEventListener("change", applyFilters);
    }

    pagePrevBtns.forEach((btn) => {
      btn.addEventListener("click", () => {
        if (currentPage <= 1) return;
        loadImages(currentPage - 1);
      });
    });

    pageNextBtns.forEach((btn) => {
      btn.addEventListener("click", () => {
        if (currentPage >= totalPages) return;
        loadImages(currentPage + 1);
      });
    });

    pageLists.forEach((list) => {
      list.addEventListener("click", (event) => {
        const btn = event.target.closest("[data-page]");
        if (!btn) return;
        const target = parseInt(btn.dataset.page || "1", 10);
        if (!Number.isFinite(target) || target === currentPage) return;
        loadImages(target);
      });
    });

    pageInputs.forEach((input) => {
      input.addEventListener("keydown", (event) => {
        if (event.key !== "Enter") return;
        event.preventDefault();
        jumpToPage(input.value);
      });
    });

    pageJumpBtns.forEach((btn) => {
      btn.addEventListener("click", () => {
        const wrap = btn.closest("[data-user-pagination], [data-user-pagination-top]");
        const input = wrap ? wrap.querySelector("[data-user-page-input]") : null;
        if (!input) return;
        jumpToPage(input.value);
      });
    });

    loadImages(currentPage);
  }

  async function initUploadPage() {
    const page = document.querySelector("[data-user-upload-page]");
    if (!page) return;
    const form = page.querySelector("[data-user-upload-form]");
    const collectionSelect = page.querySelector("[data-user-upload-collection]");
    const hint = page.querySelector("[data-user-upload-hint]");
    const loginHint = page.querySelector("[data-user-login-hint]");

    let currentUser = "";
    try {
      const me = await fetchJSON("/auth/me");
      currentUser = me.user || "";
      if (loginHint) loginHint.textContent = `已登录：${me.user || ""}`;
    } catch (err) {
      if (loginHint) loginHint.textContent = "请先登录后上传作品。";
      setFormDisabled(form, true);
      return;
    }

    if (collectionSelect && collectionSelect.options.length <= 1) {
      try {
        const data = await fetchJSON("/api/my/images?p=1");
        renderCollectionOptions(collectionSelect, data.collections || [], true);
      } catch (err) {
        // ignore collection fetch errors
      }
    }

    bindUserUploadForm(form, { hint, currentUser });
    initTagSuggest(page);
  }

  async function initDetailEditor() {
    const editor = document.querySelector("[data-image-editor]");
    if (!editor) return;
    const toggleBtn = document.querySelector("[data-image-edit-toggle]");
    const closeBtn = editor.querySelector("[data-image-edit-close]");
    const form = editor.querySelector("[data-image-edit-form]");
    const uuid = editor.dataset.imageUuid;
    const titleInput = editor.querySelector("[data-image-field='title']");
    const descInput = editor.querySelector("[data-image-field='description']");
    const tagsInput = editor.querySelector("[data-image-field='tags']");
    const collectionSelect = editor.querySelector("[data-image-field='collection']");
    const saveBtn = editor.querySelector("[data-image-save]");
    const status = editor.querySelector("[data-image-status]");

    function setEditorVisible(visible) {
      editor.hidden = !visible;
      if (toggleBtn) {
        toggleBtn.hidden = false;
        toggleBtn.setAttribute("aria-expanded", visible ? "true" : "false");
        toggleBtn.textContent = visible ? "收起编辑" : "编辑作品";
      }
    }

    try {
      const data = await fetchJSON(`/api/images/${uuid}`);
      if (!data || !data.can_edit) return;
      setEditorVisible(false);
      renderCollectionOptions(collectionSelect, data.collections || [], true);
      if (collectionSelect) {
        collectionSelect.value = data.image.collection || "";
      }
      if (titleInput) titleInput.value = data.image.title || "";
      if (descInput) descInput.value = data.image.description || "";
      if (tagsInput) {
        tagsInput.value = (data.image.tags || []).join(" ");
      }
    } catch (err) {
      return;
    }

    if (toggleBtn) {
      toggleBtn.addEventListener("click", () => {
        const shouldOpen = editor.hidden;
        setEditorVisible(shouldOpen);
        if (shouldOpen) {
          editor.scrollIntoView({ behavior: "smooth", block: "start" });
        }
      });
    }

    if (closeBtn) {
      closeBtn.addEventListener("click", () => {
        setEditorVisible(false);
      });
    }

    if (form) {
      form.addEventListener("submit", (event) => {
        event.preventDefault();
      });
    }

    if (saveBtn) {
      saveBtn.addEventListener("click", async () => {
        if (status) status.textContent = "保存中...";
        const payload = {
          title: titleInput ? titleInput.value.trim() : "",
          description: descInput ? descInput.value.trim() : "",
          tags: tagsInput ? tagsInput.value.trim() : "",
          collection: collectionSelect ? collectionSelect.value : "",
        };
        try {
          await fetchJSON(`/api/images/${uuid}/update`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
          });
          if (status) status.textContent = "已保存，等待刷新发布";
        } catch (err) {
          if (status) status.textContent = err.message;
        }
      });
    }

    initTagSuggest(document);
  }

  async function initDetailFavorite() {
    const button = document.querySelector("[data-fav-toggle]");
    if (!button) return;
    const uuid = button.dataset.imageUuid;
    if (!uuid) return;
    const label = button.querySelector("[data-fav-label]");
    const manageBtn = document.querySelector("[data-fav-manage]");
    const panel = document.querySelector("[data-fav-panel]");
    const panelList = panel ? panel.querySelector("[data-fav-panel-list]") : null;
    const panelClose = panel ? panel.querySelector("[data-fav-panel-close]") : null;
    let panelGalleries = [];

    function setState(isActive) {
      button.classList.toggle("is-active", isActive);
      button.dataset.favorited = isActive ? "1" : "0";
      if (label) label.textContent = isActive ? "已收藏" : "收藏";
      if (manageBtn) manageBtn.hidden = !isActive;
      if (!isActive && panel) panel.hidden = true;
    }

    button.classList.add("is-loading");
    button.disabled = true;
    if (label) label.textContent = "加载中";

    async function renderPanel() {
      if (!panelList) return;
      if (!panelGalleries.length) {
        panelList.innerHTML = '<span class="muted">暂无收藏夹</span>';
        return;
      }
      panelList.innerHTML = panelGalleries
        .map((item) => {
          const active = item.contains ? "active" : "";
          return `
            <button class="detail-fav-item ${active}" type="button" data-gallery-id="${escapeHtml(String(item.id))}">
              <span>${escapeHtml(item.title || "")}</span>
              <span class="muted">${item.count || 0}</span>
            </button>
          `;
        })
        .join("");
      panelList.querySelectorAll("[data-gallery-id]").forEach((btn) => {
        btn.addEventListener("click", async () => {
          const galleryId = btn.dataset.galleryId;
          const entry = panelGalleries.find((item) => String(item.id) === String(galleryId));
          if (!entry) return;
          const action = entry.contains ? "remove" : "add";
          try {
            await fetchJSON(`/api/galleries/${galleryId}/items`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ uuid, action }),
            });
            await loadPanel();
          } catch (err) {
            return;
          }
        });
      });
    }

    async function loadPanel() {
      if (!panel) return;
      const data = await fetchJSON(`/api/galleries?uuid=${encodeURIComponent(uuid)}`, { cache: "no-store" });
      panelGalleries = data.galleries || [];
      renderPanel();
    }

    let isAuthorized = true;
    let stateReady = true;
    try {
      const data = await fetchJSON(`/api/favorites/${uuid}`, { cache: "no-store" });
      setState(Boolean(data.favorited));
    } catch (err) {
      if (err && err.message === "未授权") {
        isAuthorized = false;
        button.disabled = true;
        if (label) label.textContent = "登录后收藏";
      } else {
        stateReady = false;
        button.disabled = true;
        if (label) label.textContent = "加载失败";
      }
    } finally {
      button.classList.remove("is-loading");
      if (isAuthorized && stateReady) {
        button.disabled = false;
      }
    }
    if (!isAuthorized || !stateReady) return;

    if (manageBtn) {
      manageBtn.addEventListener("click", async () => {
        if (!panel) return;
        panel.hidden = !panel.hidden;
        if (!panel.hidden) {
          await loadPanel();
        }
      });
    }

    if (panelClose) {
      panelClose.addEventListener("click", () => {
        if (panel) panel.hidden = true;
      });
    }

    button.addEventListener("click", async () => {
      if (button.dataset.loading === "1") return;
      button.dataset.loading = "1";
      try {
        const data = await fetchJSON(`/api/favorites/${uuid}/toggle`, { method: "POST" });
        setState(data.status === "added");
      } catch (err) {
        if (label) {
          const prev = button.dataset.favorited === "1";
          label.textContent = "操作失败";
          window.setTimeout(() => setState(prev), 1200);
        }
      } finally {
        button.dataset.loading = "";
      }
    });
  }

  initMyPage();
  initUploadPage();
  initDetailEditor();
  initDetailFavorite();
})();
