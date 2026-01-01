(function () {
  const loginSection = document.querySelector("[data-admin-login]");
  const panel = document.querySelector("[data-admin-panel]");
  const loginForm = document.querySelector("[data-admin-login-form]");
  const loginError = document.querySelector("[data-admin-login-error]");
  const logoutBtn = document.querySelector("[data-admin-logout]");

  function showLogin(message) {
    if (panel) panel.hidden = true;
    if (loginSection) loginSection.hidden = false;
    if (loginError) loginError.textContent = message || "";
  }

  function showPanel() {
    if (loginSection) loginSection.hidden = true;
    if (panel) panel.hidden = false;
    if (loginError) loginError.textContent = "";
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

  async function ensureAuth() {
    try {
      const data = await fetchJSON("/upload/admin/me");
      currentAdminUser = data.user || "";
      showPanel();
      return true;
    } catch (err) {
      showLogin(err.message);
      return false;
    }
  }

  if (loginForm) {
    loginForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const form = new FormData(loginForm);
      const payload = {
        username: form.get("username"),
        password: form.get("password"),
      };
      try {
        await fetchJSON("/upload/admin/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        await ensureAuth();
        initAdmin();
      } catch (err) {
        showLogin(err.message);
      }
    });
  }

  if (logoutBtn) {
    logoutBtn.addEventListener("click", async () => {
      try {
        await fetchJSON("/upload/admin/logout", { method: "POST" });
      } catch (err) {
        // ignore
      }
      currentAdminUser = "";
      location.reload();
    });
  }

  const grid = document.querySelector("[data-admin-grid]");
  const empty = document.querySelector("[data-admin-empty]");
  const refreshBtn = document.querySelector("[data-admin-refresh]");
  const trashBtn = document.querySelector("[data-admin-toggle-trash]");
  const queryInput = document.querySelector("[data-admin-query]");
  const collectionFilter = document.querySelector("[data-admin-collection-filter]");
  const collectionList = document.querySelector("[data-admin-collection-list]");
  const addCollectionBtn = document.querySelector("[data-admin-add-collection]");
  const saveCollectionsBtn = document.querySelector("[data-admin-save-collections]");
  const collectionsHint = document.querySelector("[data-admin-collections-hint]");
  const defaultCollectionSelect = document.querySelector("[data-admin-default-collection]");
  const authModeSelect = document.querySelector("[data-admin-auth-mode]");
  const authSaveBtn = document.querySelector("[data-admin-auth-save]");
  const authHint = document.querySelector("[data-admin-auth-hint]");
  const uploadForm = document.querySelector("[data-admin-upload-form]");
  const uploadCollection = document.querySelector("[data-admin-upload-collection]");
  const uploadHint = document.querySelector("[data-admin-upload-hint]");
  const tagAddBtn = document.querySelector("[data-admin-tag-add]");
  const tagSearchInput = document.querySelector("[data-admin-tag-search]");
  const tagSuggestList = document.querySelector("[data-admin-tag-suggest-list]");
  const tagTypeFilter = document.querySelector("[data-admin-tag-type-filter]");
  const tagSortSelect = document.querySelector("[data-admin-tag-sort]");
  const tagShowEmptyToggle = document.querySelector("[data-admin-tag-show-empty]");
  const tagCandidateToggle = document.querySelector("[data-admin-tag-candidate]");
  const tagPageSizeSelect = document.querySelector("[data-admin-tag-page-size]");
  const tagPrevBtn = document.querySelector("[data-admin-tag-prev]");
  const tagNextBtn = document.querySelector("[data-admin-tag-next]");
  const tagPageInfo = document.querySelector("[data-admin-tag-page-info]");
  const tagShell = document.querySelector("[data-admin-tag-shell]");
  const tagEditor = document.querySelector("[data-admin-editor]");
  const tagEditorTitle = document.querySelector("[data-admin-editor-title]");
  const tagEditorBack = document.querySelector("[data-admin-editor-back]");
  const tagEditorTagPanel = document.querySelector("[data-admin-editor-panel='tag']");
  const tagEditorTypePanel = document.querySelector("[data-admin-editor-panel='types']");
  const tagTypeToggle = document.querySelector("[data-admin-type-toggle]");
  const tagTypeSummary = document.querySelector("[data-admin-type-summary]");
  const tagTypeCount = document.querySelector("[data-admin-type-count]");
  const tagsHint = document.querySelector("[data-admin-tags-hint]");
  const typeAddBtn = document.querySelector("[data-admin-type-add]");
  const typeSaveBtn = document.querySelector("[data-admin-type-save]");
  const typeList = document.querySelector("[data-admin-type-list]");
  const typeHint = document.querySelector("[data-admin-type-hint]");
  const masonry = window.GalleryMasonry ? window.GalleryMasonry.init(grid) : null;

  let images = [];
  let collections = [];
  let defaultCollection = "";
  let showTrash = false;
  let currentAdminUser = "";

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

  function parseTagTokens(raw) {
    const rawValue = String(raw || "");
    const hasHash = rawValue.includes("#");
    const trimmed = rawValue.trim();
    if (!trimmed) {
      return { tags: [], hasHash };
    }
    let parts = [];
    if (hasHash) {
      const chunks = rawValue.replace(/,/g, " ").split("#");
      parts = chunks.map((chunk) => chunk.trim()).filter(Boolean);
    } else {
      parts = rawValue.split(/[,\s|]+/).filter(Boolean);
    }
    const tags = [];
    const seen = new Set();
    parts.forEach((item) => {
      let tag = item.trim();
      if (!tag) return;
      if (tag.startsWith("#")) {
        tag = tag.slice(1).trim();
      }
      if (!tag) return;
      const key = tag.toLowerCase();
      if (seen.has(key)) return;
      seen.add(key);
      tags.push(tag);
    });
    return { tags, hasHash };
  }

  function formatTagsValue(tags, useHash) {
    const unique = [];
    const seen = new Set();
    tags.forEach((tag) => {
      const cleaned = String(tag || "").trim();
      if (!cleaned) return;
      const key = cleaned.toLowerCase();
      if (seen.has(key)) return;
      seen.add(key);
      unique.push(cleaned);
    });
    const prefix = useHash ? "#" : "";
    return unique.map((tag) => `${prefix}${tag}`).join("\n");
  }

  function renderTagChips(editor, tags, useHash) {
    const chips = editor.querySelector("[data-tag-chips]");
    if (!chips) return;
    chips.innerHTML = tags
      .map((tag) => {
        const display = `${useHash ? "#" : ""}${tag}`;
        return `<button class="tag-chip" type="button" data-tag-chip="${escapeHtml(
          tag
        )}" aria-label="移除 ${escapeHtml(display)}">
          <span>${escapeHtml(display)}</span>
          <span class="tag-chip-close" aria-hidden="true">×</span>
        </button>`;
      })
      .join("");
    editor.classList.toggle("has-chips", tags.length > 0);
  }

  function initTagEditors(scope) {
    const host = scope || document;
    const editors = Array.from(host.querySelectorAll("[data-tag-editor]"));
    if (!editors.length) return;
    editors.forEach((editor) => {
      if (editor.dataset.tagEditorReady === "1") return;
      const input = editor.querySelector("[data-tag-input]");
      if (!input) return;
      const requireHash = input.dataset.tagRequireHash === "1";
      const formatBtn = editor.querySelector("[data-tag-format]");
      const update = () => {
        const parsed = parseTagTokens(input.value);
        renderTagChips(editor, parsed.tags, requireHash || parsed.hasHash);
      };
      editor.dataset.tagEditorReady = "1";
      input.addEventListener("input", update);
      input.addEventListener("blur", update);
      if (formatBtn) {
        formatBtn.addEventListener("click", () => {
          const parsed = parseTagTokens(input.value);
          const useHash = requireHash || parsed.hasHash;
          input.value = formatTagsValue(parsed.tags, useHash);
          input.dispatchEvent(new Event("input", { bubbles: true }));
        });
      }
      const chips = editor.querySelector("[data-tag-chips]");
      if (chips) {
        chips.addEventListener("click", (event) => {
          const target = event.target.closest("[data-tag-chip]");
          if (!target) return;
          if (input.disabled) return;
          const tag = target.dataset.tagChip || "";
          const parsed = parseTagTokens(input.value);
          const remaining = parsed.tags.filter(
            (item) => item.toLowerCase() !== tag.toLowerCase()
          );
          const useHash = requireHash || parsed.hasHash;
          input.value = formatTagsValue(remaining, useHash);
          input.dispatchEvent(new Event("input", { bubbles: true }));
        });
      }
      update();
    });
  }

  function renderCollections() {
    if (!collectionList) return;
    collectionList.innerHTML = collections
      .map((item) => {
        return `
          <div class="collection-row" data-collection-row>
            <input type="text" value="${escapeHtml(item.slug)}" data-collection-field="slug" placeholder="slug">
            <input type="text" value="${escapeHtml(item.title)}" data-collection-field="title" placeholder="标题">
            <input type="text" value="${escapeHtml(item.description || "")}" data-collection-field="description" placeholder="描述">
            <button class="icon-button" type="button" data-collection-remove>删除</button>
          </div>
        `;
      })
      .join("");
    if (defaultCollectionSelect) {
      defaultCollectionSelect.innerHTML = collections
        .map(
          (item) =>
            `<option value="${escapeHtml(item.slug)}">${escapeHtml(item.title)}</option>`
        )
        .join("");
      defaultCollectionSelect.value = defaultCollection || (collections[0] && collections[0].slug) || "";
    }
  }

  function renderCollectionFilter() {
    if (!collectionFilter) return;
    const options = [
      '<option value="all">全部分区</option>',
      ...collections.map(
        (item) =>
          `<option value="${escapeHtml(item.slug)}">${escapeHtml(item.title)}</option>`
      ),
    ];
    collectionFilter.innerHTML = options.join("");
  }

  function renderUploadCollections() {
    if (!uploadCollection) return;
    const options = [
      '<option value="">自动</option>',
      ...collections.map(
        (item) =>
          `<option value="${escapeHtml(item.slug)}">${escapeHtml(item.title)}</option>`
      ),
    ];
    uploadCollection.innerHTML = options.join("");
  }

  async function loadCollectionsMeta() {
    const data = await fetchJSON("/upload/admin/collections");
    collections = data.collections || [];
    defaultCollection = data.default_collection || "";
    renderCollections();
    renderCollectionFilter();
    renderUploadCollections();
    bindCollectionActions();
  }

  function bindCollectionActions() {
    if (!collectionList) return;
    collectionList.querySelectorAll("[data-collection-remove]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const row = btn.closest("[data-collection-row]");
        if (row) row.remove();
      });
    });
  }

  function renderImages(list) {
    if (!grid) return;
    if (!list.length) {
      grid.innerHTML = "";
      if (empty) empty.classList.add("show");
      if (masonry) {
        masonry.refresh();
      } else {
        grid.classList.add("masonry-ready");
      }
      return;
    }
    if (empty) empty.classList.remove("show");
    const collectionOptions = collections
      .map(
        (c) => `<option value="${escapeHtml(c.slug)}">${escapeHtml(c.title)}</option>`
      )
      .join("");
    const orientationLabels = {
      portrait: "竖屏",
      landscape: "横屏",
      square: "方形",
      unknown: "未标",
    };
    const sizeLabels = {
      ultra: "超清",
      large: "高清",
      medium: "中等",
      compact: "轻量",
      unknown: "未标",
    };
    const collectionMap = new Map(
      (collections || []).map((item) => [item.slug, item.title || item.slug])
    );

    grid.innerHTML = list
      .map((img) => {
        const titleText = img.title || "未命名作品";
        const descriptionText = img.description || "";
        const tagsValue = (img.tags || []).join("\n");
        const disabled = img.deleted_at ? "disabled" : "";
        const dimension =
          img.width && img.height ? `${img.width}×${img.height}` : "尺寸未知";
        const bytesText = img.bytes_human || "";
        const collectionTitle =
          collectionMap.get(img.collection) || img.collection || "未分区";
        const orientationLabel =
          orientationLabels[img.orientation] || orientationLabels.unknown;
        const sizeLabel = sizeLabels[img.size_bucket] || sizeLabels.unknown;
        const tagLinks = (img.tags || [])
          .slice(0, 3)
          .map(
            (tag) =>
              `<a class="tag ghost" href="/tags/${encodeURIComponent(
                tag
              )}/">#${escapeHtml(tag)}</a>`
          )
          .join("");
        const thumbWidth = img.thumb_width || 1;
        const thumbHeight = img.thumb_height || 1;
        const detailPath = escapeHtml(resolveDetailPath(img));
        const metaItems = [dimension, bytesText, collectionTitle].filter(Boolean);
        return `
        <article class="illust-card admin-card" data-masonry-item data-admin-uuid="${escapeHtml(
          img.uuid
        )}">
          <a class="thumb-link" href="${detailPath}">
            <div class="thumb-shell" style="--thumb-ratio:${thumbWidth}/${thumbHeight};">
              <img class="thumb" src="/thumb/${escapeHtml(
                img.thumb_filename || ""
              )}" alt="${escapeHtml(img.title || "")}" loading="lazy" width="${thumbWidth}" height="${thumbHeight}" onerror="this.onerror=null;this.src='/raw/${escapeHtml(
          img.raw_filename || ""
        )}';">
            </div>
          </a>
          <div class="card-body">
            <div class="title">${escapeHtml(titleText)}</div>
            ${descriptionText ? `<p class="desc">${escapeHtml(descriptionText)}</p>` : ""}
            <div class="meta">
              ${metaItems.map((item) => `<span>${escapeHtml(item)}</span>`).join("")}
            </div>
            <div class="tags">
              <span class="tag accent">${escapeHtml(orientationLabel)}</span>
              <span class="tag">${escapeHtml(sizeLabel)}</span>
              ${tagLinks}
            </div>
          </div>
          <div class="admin-card-editor">
            <div class="admin-fields-grid">
              <div class="admin-field">
                <label class="label">标题</label>
                <input class="admin-input" type="text" value="${escapeHtml(
                  img.title || ""
                )}" data-field="title" ${disabled}>
              </div>
              <div class="admin-field admin-field-wide">
                <label class="label">描述</label>
                <textarea class="admin-textarea" data-field="description" ${disabled}>${escapeHtml(
                  img.description || ""
                )}</textarea>
              </div>
              <div class="admin-field admin-field-wide">
                <label class="label">标签</label>
                <div class="tag-editor" data-tag-editor>
                  <textarea class="admin-tag-input" rows="3" data-field="tags" data-tag-input ${disabled}>${escapeHtml(
                    tagsValue
                  )}</textarea>
                  <div class="tag-editor-meta">
                    <button class="btn ghost" type="button" data-tag-format ${disabled}>整理标签</button>
                    <span class="hint">支持换行/逗号/竖线</span>
                  </div>
                  <div class="tag-editor-chips" data-tag-chips></div>
                </div>
              </div>
              <div class="admin-field">
                <label class="label">分区</label>
                <select class="admin-select" data-field="collection" ${disabled}>
                  <option value="">自动</option>
                  ${collectionOptions}
                </select>
              </div>
              <div class="admin-actions-row admin-field-wide">
                <button class="btn primary" type="button" data-action="save" ${disabled}>保存</button>
                <button class="btn ghost" type="button" data-action="delete" ${disabled}>删除</button>
              </div>
              <p class="hint admin-field-wide" data-field="status">${
                img.deleted_at ? "已进入垃圾桶" : ""
              }</p>
            </div>
          </div>
        </article>
        `;
      })
      .join("");

    initTagSuggest(grid);
    initTagEditors(grid);

    grid.querySelectorAll("[data-admin-uuid]").forEach((card) => {
      const uuid = card.dataset.adminUuid;
      const img = list.find((item) => item.uuid === uuid);
      const select = card.querySelector("[data-field='collection']");
      if (select && img) {
        select.value = img.collection || "";
      }
      card.querySelector("[data-action='save']").addEventListener("click", async () => {
        const title = card.querySelector("[data-field='title']").value.trim();
        const description = card.querySelector("[data-field='description']").value.trim();
        const tags = card.querySelector("[data-field='tags']").value.trim();
        const collection = card.querySelector("[data-field='collection']").value;
        const status = card.querySelector("[data-field='status']");
        status.textContent = "保存中...";
        try {
          await fetchJSON(`/upload/admin/images/${uuid}/update`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ title, description, tags, collection }),
          });
          status.textContent = "已保存，等待刷新发布";
        } catch (err) {
          status.textContent = err.message;
        }
      });
      card.querySelector("[data-action='delete']").addEventListener("click", async () => {
        if (!confirm("确认删除该作品？")) return;
        const status = card.querySelector("[data-field='status']");
        status.textContent = "删除中...";
        try {
          await fetchJSON(`/upload/admin/images/${uuid}/delete`, { method: "POST" });
          card.remove();
        } catch (err) {
          status.textContent = err.message;
        }
      });
    });

    if (masonry) {
      masonry.refresh();
      return;
    }
    grid.classList.add("masonry-ready");
  }

  function initTagSuggest(container) {
    if (!window.GalleryTagSuggest || !window.GalleryTagSuggest.initTagInputs) return;
    const scope = container || document;
    const inputs = scope.querySelectorAll("[data-tag-input]");
    if (!inputs.length) return;
    window.GalleryTagSuggest.initTagInputs(inputs);
  }

  function applyFilters() {
    const term = (queryInput && queryInput.value.trim().toLowerCase()) || "";
    const collection = collectionFilter ? collectionFilter.value : "all";
    const filtered = images.filter((img) => {
      if (collection !== "all" && img.collection !== collection) return false;
      if (!term) return true;
      const hay = `${img.title || ""} ${img.description || ""}`.toLowerCase();
      const tags = (img.tags || []).map((t) => String(t).toLowerCase());
      if (term.startsWith("#")) {
        const tagTerm = term.slice(1);
        return tags.some((t) => t.includes(tagTerm));
      }
      return hay.includes(term) || tags.some((t) => t.includes(term));
    });
    renderImages(filtered);
  }

  async function loadImages() {
    const data = await fetchJSON(`/upload/admin/images?status=${showTrash ? "trash" : "active"}`);
    images = data.images || [];
    collections = data.collections || [];
    defaultCollection = data.default_collection || "";
    renderCollections();
    renderCollectionFilter();
    renderUploadCollections();
    bindCollectionActions();
    applyFilters();
  }

  async function loadAuthConfig() {
    if (!authModeSelect) return;
    const data = await fetchJSON("/upload/admin/auth-config");
    if (data.registration_mode === "open" || data.registration_mode === "invite" || data.registration_mode === "closed") {
      authModeSelect.value = data.registration_mode;
    }
  }

  async function saveAuthConfig() {
    if (!authModeSelect) return;
    if (authHint) authHint.textContent = "保存中...";
    try {
      const payload = { registration_mode: authModeSelect.value };
      await fetchJSON("/upload/admin/auth-config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (authHint) authHint.textContent = "已保存";
    } catch (err) {
      if (authHint) authHint.textContent = err.message;
    }
  }

  async function saveCollections() {
    if (!collectionList) return;
    const rows = Array.from(collectionList.querySelectorAll("[data-collection-row]"));
    const next = rows.map((row) => {
      return {
        slug: row.querySelector("[data-collection-field='slug']").value.trim(),
        title: row.querySelector("[data-collection-field='title']").value.trim(),
        description: row.querySelector("[data-collection-field='description']").value.trim(),
      };
    });
    const payload = {
      collections: next.filter((item) => item.slug && item.title),
      default_collection: defaultCollectionSelect ? defaultCollectionSelect.value : "",
    };
    if (!payload.collections.length) {
      if (collectionsHint) collectionsHint.textContent = "至少保留一个分区";
      return;
    }
    if (collectionsHint) collectionsHint.textContent = "保存中...";
    try {
      await fetchJSON("/upload/admin/collections", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (collectionsHint) collectionsHint.textContent = "分区已保存";
      await loadImages();
    } catch (err) {
      if (collectionsHint) collectionsHint.textContent = err.message;
    }
  }

  function initAdmin() {
    if (grid) {
      loadImages().catch((err) => {
        if (empty) empty.textContent = err.message;
      });
    } else if (collectionList || uploadCollection || collectionFilter || defaultCollectionSelect) {
      loadCollectionsMeta().catch((err) => {
        if (collectionsHint) collectionsHint.textContent = err.message;
        if (uploadHint) uploadHint.textContent = err.message;
      });
    }
    loadAuthConfig().catch((err) => {
      if (authHint) authHint.textContent = err.message;
    });

    if (grid && refreshBtn) {
      refreshBtn.addEventListener("click", () => loadImages());
    }

    if (trashBtn) {
      trashBtn.addEventListener("click", () => {
        showTrash = !showTrash;
        trashBtn.textContent = showTrash ? "查看正常作品" : "查看垃圾桶";
        loadImages();
      });
    }

    if (queryInput) {
      queryInput.addEventListener("input", applyFilters);
    }

    if (collectionFilter) {
      collectionFilter.addEventListener("change", applyFilters);
    }

    if (addCollectionBtn) {
      addCollectionBtn.addEventListener("click", () => {
        collections.push({ slug: "", title: "", description: "" });
        renderCollections();
        bindCollectionActions();
      });
    }

    if (saveCollectionsBtn) {
      saveCollectionsBtn.addEventListener("click", saveCollections);
    }

    if (authSaveBtn) {
      authSaveBtn.addEventListener("click", saveAuthConfig);
    }

    if (uploadForm) {
      uploadForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (uploadHint) uploadHint.textContent = "上传中...";
        const form = new FormData(uploadForm);
        const fileInput = uploadForm.querySelector("input[type='file']");
        const file = fileInput && fileInput.files ? fileInput.files[0] : null;
        const progress = window.GalleryUploadProgress;
        const submitBtn = uploadForm.querySelector("button[type='submit']");
        if (submitBtn) submitBtn.disabled = true;
        if (progress && file && currentAdminUser) {
          progress.start("admin", currentAdminUser, file);
        }
        try {
          const data = await uploadWithProgress("/upload/admin/upload", form, (loaded, total) => {
            if (progress && currentAdminUser) {
              progress.updateUpload("admin", currentAdminUser, loaded, total);
            }
          });
          if (uploadHint) uploadHint.textContent = "上传成功，等待处理";
          if (progress && currentAdminUser) {
            progress.finishUpload("admin", currentAdminUser, data.uuid);
          }
          uploadForm.reset();
          loadImages();
        } catch (err) {
          if (uploadHint) uploadHint.textContent = err.message;
          if (progress && currentAdminUser) {
            progress.fail("admin", currentAdminUser, err.message);
          }
        } finally {
          if (submitBtn) submitBtn.disabled = false;
        }
      });
    }

    initTagsPage();
  }

  async function initTagsPage() {
    const tagList = document.querySelector("[data-admin-tag-list]");
    if (!tagList && !typeList) return;
    let tags = [];
    let tagTypes = [];
    let tagPage = 1;
    let tagPageSize = tagPageSizeSelect ? parseInt(tagPageSizeSelect.value, 10) || 30 : 30;
    let activeEditor = "";
    let activeTagName = "";
    let tagTypesExpanded = false;
    let tagIndex = null;
    let tagIndexTags = [];
    let candidateMode = false;
    let tagInfoMap = new Map();
    let tagParentMap = new Map();
    let tagChildMap = new Map();

    const defaultType = () => {
      const first = tagTypes.length ? String(tagTypes[0].type || "") : "";
      return first || "general";
    };

    function buildTagTypeOptions(selected) {
      const selectedValue = String(selected || "").toLowerCase();
      const list = tagTypes.length ? tagTypes : [{ type: "general", label: "普通" }];
      const known = list.some((item) => String(item.type || "").toLowerCase() === selectedValue);
      const options = list
        .map((item) => {
          const value = String(item.type || "");
          const label = String(item.label || item.type || value);
          const isSelected = selectedValue && selectedValue === value.toLowerCase();
          return `<option value="${escapeHtml(value)}" ${isSelected ? "selected" : ""}>${escapeHtml(
            label
          )}</option>`;
        })
        .join("");
      if (selectedValue && !known) {
        return `<option value="${escapeHtml(selectedValue)}" selected>未注册(${escapeHtml(
          selectedValue
        )})</option>${options}`;
      }
      return options;
    }

    function normalizeQuery(raw) {
      return String(raw || "")
        .toLowerCase()
        .split(/\s+/)
        .filter(Boolean);
    }

    function normalizeTagText(raw) {
      return String(raw || "").trim().toLowerCase();
    }

    function setEditorOpen(isOpen) {
      if (tagShell) {
        tagShell.dataset.editorOpen = isOpen ? "1" : "0";
      }
      if (tagEditor) {
        tagEditor.hidden = !isOpen;
      }
    }

    function setCandidateMode(isActive) {
      candidateMode = isActive;
      if (tagShell) {
        tagShell.dataset.candidateMode = isActive ? "1" : "0";
      }
    }

    function syncActiveTagHighlight() {
      if (!tagList) return;
      if (tagList.dataset.listMode === "candidate") return;
      tagList.querySelectorAll("[data-tag-item]").forEach((btn) => {
        btn.classList.toggle("is-active", btn.dataset.tagItem === activeTagName);
      });
    }

    function getTagTypeMeta(typeValue) {
      const value = String(typeValue || "");
      const match = tagTypes.find((item) => String(item.type || "") === value);
      if (match) {
        return {
          label: String(match.label || match.type || value || "普通"),
          color: String(match.color || "#7b8794"),
        };
      }
      if (!value) {
        return { label: "普通", color: "#7b8794" };
      }
      return { label: `未注册(${value})`, color: "#7b8794" };
    }

    function buildTagRelationMaps() {
      tagInfoMap = new Map();
      tagParentMap = new Map();
      tagChildMap = new Map();
      tags.forEach((item) => {
        const tagName = String(item.tag || "");
        if (!tagName) return;
        tagInfoMap.set(tagName, item);
        const parents = Array.isArray(item.parents)
          ? item.parents.map((parent) => String(parent || "")).filter(Boolean)
          : [];
        tagParentMap.set(tagName, parents);
        parents.forEach((parent) => {
          if (!tagChildMap.has(parent)) {
            tagChildMap.set(parent, []);
          }
          const list = tagChildMap.get(parent);
          if (!list.includes(tagName)) {
            list.push(tagName);
          }
        });
      });
      tagChildMap.forEach((list) => list.sort((a, b) => a.localeCompare(b)));
    }

    function getTagInfo(tagName) {
      return tagInfoMap.get(tagName) || tags.find((item) => item.tag === tagName) || null;
    }

    function getIndexTagMeta(item) {
      if (!item) {
        return { label: "普通", color: "#7b8794" };
      }
      const label = String(item.type_label || item.type || "普通");
      const color = String(item.type_color || "#7b8794");
      return { label, color };
    }

    async function loadTagIndex() {
      if (!window.GalleryTagSuggest || !window.GalleryTagSuggest.loadTagIndex) return;
      try {
        tagIndex = await window.GalleryTagSuggest.loadTagIndex();
        tagIndexTags =
          tagIndex && tagIndex.raw && Array.isArray(tagIndex.raw.tags) ? tagIndex.raw.tags : [];
      } catch (err) {
        tagIndex = null;
        tagIndexTags = [];
      }
    }

    function buildCandidateMatches(query) {
      const cleaned = normalizeTagText(query);
      if (!cleaned || !tagIndexTags.length) {
        return [];
      }
      const tokens = cleaned.split(/\s+/).filter(Boolean);
      const results = [];
      tagIndexTags.forEach((item) => {
        const tagName = String(item.tag || "");
        if (!tagName) return;
        const slug = String(item.slug || "");
        const aliases = Array.isArray(item.aliases) ? item.aliases : [];
        const haystack = [tagName, slug, ...aliases].map(normalizeTagText).join(" ");
        const matched = tokens.every((token) => haystack.includes(token));
        if (!matched) return;
        let score = 0;
        const tagMatch = normalizeTagText(tagName);
        const slugMatch = normalizeTagText(slug);
        if (tagMatch.startsWith(cleaned)) score += 3;
        if (slugMatch.startsWith(cleaned)) score += 2;
        if (aliases.some((alias) => normalizeTagText(alias).startsWith(cleaned))) score += 1;
        results.push({ item, score });
      });
      results.sort((a, b) => {
        if (a.score !== b.score) return b.score - a.score;
        return String(a.item.tag || "").localeCompare(String(b.item.tag || ""));
      });
      return results.map((entry) => entry.item);
    }

    function renderTagSearchSuggest(list) {
      if (!tagSuggestList) return;
      if (!list.length) {
        tagSuggestList.hidden = true;
        tagSuggestList.innerHTML = "";
        return;
      }
      const items = list.slice(0, 6).map((item) => {
        const name = String(item.tag || "");
        const meta = getIndexTagMeta(item);
        return `
          <button class="tag-search-suggest-item" type="button" data-suggest-value="${escapeHtml(
            name
          )}" style="--tag-type-color: ${escapeHtml(meta.color)};">
            <span class="tag-search-dot" aria-hidden="true"></span>
            <span class="tag-search-name">${escapeHtml(name)}</span>
            <span class="tag-search-type">${escapeHtml(meta.label)}</span>
          </button>
        `;
      });
      tagSuggestList.innerHTML = items.join("");
      tagSuggestList.hidden = false;
      tagSuggestList.querySelectorAll("[data-suggest-value]").forEach((btn) => {
        btn.addEventListener("click", () => {
          if (!tagSearchInput) return;
          tagSearchInput.value = btn.dataset.suggestValue || "";
          tagSearchInput.focus();
          tagSearchInput.dispatchEvent(new Event("input", { bubbles: true }));
        });
      });
    }

    function renderTagTypeSummary() {
      if (!tagTypeSummary) return;
      const list = tagTypes.length
        ? tagTypes
        : [{ type: "general", label: "普通", color: "#7b8794" }];
      const items = [
        `
          <button class="tag-type-item" type="button" data-admin-type-manage>
            <span class="tag-type-dot" aria-hidden="true"></span>
            <span>编辑类型</span>
          </button>
        `,
        ...list.map((item) => {
          const label = String(item.label || item.type || "");
          const color = String(item.color || "#7b8794");
          const typeValue = String(item.type || "");
          return `
          <button class="tag-type-item" type="button" data-type-item="${escapeHtml(
            typeValue
          )}" style="--tag-type-color: ${escapeHtml(color)};">
            <span class="tag-type-dot" aria-hidden="true"></span>
            <span>${escapeHtml(label)}</span>
          </button>
        `;
        }),
      ];
      tagTypeSummary.innerHTML = items.join("");
      tagTypeSummary.querySelectorAll("[data-type-item]").forEach((btn) => {
        btn.addEventListener("click", () => openTypeEditor());
      });
      const manageBtn = tagTypeSummary.querySelector("[data-admin-type-manage]");
      if (manageBtn) {
        manageBtn.addEventListener("click", () => openTypeEditor());
      }
      if (tagTypeCount) {
        tagTypeCount.textContent = `${list.length} 个`;
      }
    }

    function setTagTypesExpanded(next) {
      tagTypesExpanded = next;
      if (tagTypeToggle) {
        tagTypeToggle.setAttribute("aria-expanded", next ? "true" : "false");
      }
      if (tagTypeSummary) {
        tagTypeSummary.hidden = !next;
      }
    }

    function refreshTypeFilterOptions() {
      if (tagTypeFilter) {
        const current = tagTypeFilter.value || "all";
        const knownTypes = new Set(tagTypes.map((item) => String(item.type || "")));
        const unknownTypes = new Set();
        tags.forEach((item) => {
          const rawType = String(item.type || "");
          if (rawType && !knownTypes.has(rawType)) {
            unknownTypes.add(rawType);
          }
        });
        const options = [
          `<option value="all">全部类型</option>`,
          ...tagTypes.map((item) => {
            const value = String(item.type || "");
            const label = String(item.label || item.type || value);
            return `<option value="${escapeHtml(value)}">${escapeHtml(label)}</option>`;
          }),
          ...Array.from(unknownTypes).map((value) => {
            return `<option value="${escapeHtml(value)}">未注册(${escapeHtml(value)})</option>`;
          }),
        ];
        tagTypeFilter.innerHTML = options.join("");
        const values = new Set([
          "all",
          ...tagTypes.map((item) => String(item.type || "")),
          ...unknownTypes,
        ]);
        tagTypeFilter.value = values.has(current) ? current : "all";
      }
      renderTagTypeSummary();
    }

    function filterTags(list, filters) {
      const tokens = normalizeQuery(filters.query);
      const typeValue = filters.type || "all";
      return list.filter((item) => {
        const countValue = Number(item.count || 0);
        if (!filters.showEmpty && countValue <= 0) {
          return false;
        }
        if (typeValue !== "all" && String(item.type || "") !== typeValue) {
          return false;
        }
        if (!tokens.length) {
          return true;
        }
        const haystack = [
          item.tag,
          item.slug,
          item.alias_to,
          item.intro,
          ...(item.aliases || []),
          ...(item.parents || []),
        ]
          .join(" ")
          .toLowerCase();
        return tokens.every((token) => haystack.includes(token));
      });
    }

    function sortTags(list, sortKey) {
      const cloned = list.slice();
      const key = sortKey || "count-desc";
      cloned.sort((a, b) => {
        const nameA = String(a.tag || "");
        const nameB = String(b.tag || "");
        const countA = Number(a.count || 0);
        const countB = Number(b.count || 0);
        if (key === "count-asc") {
          if (countA !== countB) return countA - countB;
          return nameA.localeCompare(nameB);
        }
        if (key === "tag-asc") {
          return nameA.localeCompare(nameB);
        }
        if (key === "tag-desc") {
          return nameB.localeCompare(nameA);
        }
        if (countA !== countB) return countB - countA;
        return nameA.localeCompare(nameB);
      });
      return cloned;
    }

    function renderTagEditor(tag) {
      if (!tagEditorTagPanel) return;
      tagEditorTagPanel.innerHTML = `
        <div class="tag-admin-row" data-tag-row>
          <div class="tag-admin-head">
            <div class="tag-admin-head-main">
              <label class="tag-field">
                <span>标签名</span>
                <input type="text" value="${escapeHtml(tag.tag || "")}" placeholder="无需 #，例：long_hair" data-tag-field="tag">
              </label>
              <label class="tag-field">
                <span>URL Slug</span>
                <input type="text" value="${escapeHtml((tag.slug || "").trim())}" placeholder="english-tag" data-tag-field="slug">
              </label>
              <label class="tag-field">
                <span>类型</span>
                <select data-tag-field="type">
                  ${buildTagTypeOptions(tag.type)}
                </select>
              </label>
            </div>
            <div class="tag-admin-count">
              <span>作品数</span>
              <input type="text" value="${escapeHtml(tag.count || 0)}" disabled>
            </div>
          </div>
          <div class="tag-admin-fields">
            <label class="tag-field tag-field-wide">
              <span>简介</span>
              <textarea rows="2" placeholder="标签简介" data-tag-field="intro">${escapeHtml(
                (tag.intro || "").trim()
              )}</textarea>
            </label>
            <label class="tag-field tag-field-wide">
              <span>别名</span>
              <textarea rows="2" placeholder="long hair | long_hair | 长发" data-tag-field="aliases">${escapeHtml(
                (tag.aliases || []).join(" | ")
              )}</textarea>
            </label>
            <label class="tag-field tag-field-wide">
              <span>父标签</span>
              <textarea rows="2" placeholder="animal_ears | kemonomimi" data-tag-field="parents">${escapeHtml(
                (tag.parents || []).join(" | ")
              )}</textarea>
            </label>
            <label class="tag-field">
              <span>合并到</span>
              <input type="text" value="${escapeHtml((tag.alias_to || "").trim())}" placeholder="主标签（可空）" data-tag-field="alias-to">
            </label>
          </div>
          ${renderTagTree(tag)}
          <div class="tag-admin-actions">
            <button class="btn primary" type="button" data-tag-action="save">保存</button>
            <button class="btn ghost" type="button" data-tag-action="meta-delete">清除简介/别名</button>
            <button class="btn ghost" type="button" data-tag-action="rename">改名</button>
            <button class="btn ghost" type="button" data-tag-action="delete">删除</button>
          </div>
        </div>
      `;
      bindTagRowActions(tagEditorTagPanel);
      bindTagTreeActions(tagEditorTagPanel);
      if (tagEditorTitle) {
        tagEditorTitle.textContent = tag.tag ? `编辑标签：${tag.tag}` : "新增标签";
      }
    }

    function openTagEditor(tag) {
      activeEditor = "tag";
      activeTagName = tag.tag || "";
      if (tagEditorTypePanel) tagEditorTypePanel.hidden = true;
      if (tagEditorTagPanel) tagEditorTagPanel.hidden = false;
      setEditorOpen(true);
      renderTagEditor(tag);
      syncActiveTagHighlight();
    }

    function openTypeEditor() {
      activeEditor = "types";
      activeTagName = "";
      if (tagEditorTagPanel) tagEditorTagPanel.hidden = true;
      if (tagEditorTypePanel) tagEditorTypePanel.hidden = false;
      setEditorOpen(true);
      if (tagEditorTitle) {
        tagEditorTitle.textContent = "编辑标签类型";
      }
      renderTagTypes(tagTypes);
      syncActiveTagHighlight();
    }

    function closeEditor() {
      activeEditor = "";
      activeTagName = "";
      if (tagEditorTagPanel) tagEditorTagPanel.innerHTML = "";
      if (tagEditorTypePanel) tagEditorTypePanel.hidden = true;
      setEditorOpen(false);
      syncActiveTagHighlight();
    }

    function renderTagList(list) {
      if (!tagList) return;
      tagList.dataset.listMode = "tags";
      if (!list.length) {
        tagList.innerHTML = '<div class="empty show">无匹配标签</div>';
        return;
      }
      tagList.innerHTML = list
        .map((item) => {
          const meta = getTagTypeMeta(item.type);
          const tagLabel = item.tag ? item.tag : "未命名";
          return `
          <button class="tag-admin-item" type="button" data-tag-item="${escapeHtml(item.tag || "")}">
            <span class="tag-admin-item-main">
              <span class="tag-admin-item-name">${escapeHtml(tagLabel)}</span>
              <span class="tag-admin-item-type" style="--tag-type-color: ${escapeHtml(meta.color)};">
                <span class="tag-admin-item-dot" aria-hidden="true"></span>
                ${escapeHtml(meta.label)}
              </span>
            </span>
          </button>
        `;
        })
        .join("");
      tagList.querySelectorAll("[data-tag-item]").forEach((btn) => {
        btn.addEventListener("click", () => {
          const tagName = btn.dataset.tagItem || "";
          const target = tags.find((item) => item.tag === tagName);
          if (!target) return;
          openTagEditor(target);
        });
      });
      syncActiveTagHighlight();
    }

    function renderCandidateList(list, query) {
      if (!tagList) return;
      tagList.dataset.listMode = "candidate";
      if (!list.length) {
        tagList.innerHTML = query
          ? '<div class="empty show">无候补标签</div>'
          : '<div class="empty show">输入关键词显示候补</div>';
        return;
      }
      tagList.innerHTML = list
        .map((item) => {
          const meta = getIndexTagMeta(item);
          const tagLabel = item.tag ? item.tag : "未命名";
          return `
          <button class="tag-admin-item tag-admin-candidate" type="button" data-candidate-item="${escapeHtml(
            tagLabel
          )}">
            <span class="tag-admin-item-main">
              <span class="tag-admin-item-name">${escapeHtml(tagLabel)}</span>
              <span class="tag-admin-item-type" style="--tag-type-color: ${escapeHtml(meta.color)};">
                <span class="tag-admin-item-dot" aria-hidden="true"></span>
                ${escapeHtml(meta.label)}
              </span>
            </span>
          </button>
        `;
        })
        .join("");
      tagList.querySelectorAll("[data-candidate-item]").forEach((btn) => {
        btn.addEventListener("click", () => {
          if (!tagSearchInput) return;
          tagSearchInput.value = btn.dataset.candidateItem || "";
          tagSearchInput.focus();
          tagSearchInput.dispatchEvent(new Event("input", { bubbles: true }));
        });
      });
    }

    function buildTreeItem(tagName) {
      const info = getTagInfo(tagName);
      const meta = getTagTypeMeta(info ? info.type : "");
      const label = info && info.tag ? info.tag : tagName;
      return `
        <button class="tag-tree-item" type="button" data-tag-tree-item="${escapeHtml(
          tagName
        )}" style="--tag-type-color: ${escapeHtml(meta.color)};">
          <span class="tag-tree-dot" aria-hidden="true"></span>
          <span class="tag-tree-name">${escapeHtml(label)}</span>
          <span class="tag-tree-type">${escapeHtml(meta.label)}</span>
        </button>
      `;
    }

    function buildParentTree(tagName, visited = new Set()) {
      if (visited.has(tagName)) return "";
      visited.add(tagName);
      const parents = tagParentMap.get(tagName) || [];
      if (!parents.length) return "";
      return `
        <ul class="tag-tree">
          ${parents
            .map((parent) => {
              const nested = buildParentTree(parent, new Set(visited));
              return `<li>${buildTreeItem(parent)}${nested}</li>`;
            })
            .join("")}
        </ul>
      `;
    }

    function buildChildTree(tagName, visited = new Set()) {
      if (visited.has(tagName)) return "";
      visited.add(tagName);
      const children = tagChildMap.get(tagName) || [];
      if (!children.length) return "";
      return `
        <ul class="tag-tree">
          ${children
            .map((child) => {
              const nested = buildChildTree(child, new Set(visited));
              return `<li>${buildTreeItem(child)}${nested}</li>`;
            })
            .join("")}
        </ul>
      `;
    }

    function renderTagTree(tag) {
      if (!tag) return "";
      const parentsMarkup = buildParentTree(tag.tag);
      const childrenMarkup = buildChildTree(tag.tag);
      return `
        <div class="tag-admin-tree">
          <div class="tag-tree-group">
            <div class="tag-tree-title">父标签</div>
            <div class="tag-tree-body">
              ${parentsMarkup || '<div class="tag-tree-empty">无父标签</div>'}
            </div>
          </div>
          <div class="tag-tree-group">
            <div class="tag-tree-title">子标签</div>
            <div class="tag-tree-body">
              ${childrenMarkup || '<div class="tag-tree-empty">无子标签</div>'}
            </div>
          </div>
        </div>
      `;
    }

    function applyTagFilters(options = {}) {
      if (!tagList) return;
      if (options.resetPage) {
        tagPage = 1;
      }
      const query = tagSearchInput ? tagSearchInput.value.trim() : "";
      const nextPageSize = tagPageSizeSelect
        ? parseInt(tagPageSizeSelect.value, 10) || tagPageSize
        : tagPageSize;
      if (nextPageSize !== tagPageSize) {
        tagPageSize = nextPageSize;
        tagPage = 1;
      }
      const candidateSource = buildCandidateMatches(query);
      renderTagSearchSuggest(candidateSource);
      const candidateEnabled = tagCandidateToggle ? tagCandidateToggle.checked : false;
      if (candidateEnabled) {
        setCandidateMode(true);
        const total = candidateSource.length;
        const totalPages = Math.max(1, Math.ceil(total / tagPageSize));
        if (tagPage > totalPages) {
          tagPage = totalPages;
        }
        const start = (tagPage - 1) * tagPageSize;
        const pageItems = candidateSource.slice(start, start + tagPageSize);
        renderCandidateList(pageItems, query);
        if (tagPageInfo) {
          tagPageInfo.textContent = total
            ? `候补 ${tagPage}/${totalPages} · 显示 ${pageItems.length}/${total}`
            : "候补列表为空";
        }
        if (tagPrevBtn) {
          tagPrevBtn.disabled = tagPage <= 1;
        }
        if (tagNextBtn) {
          tagNextBtn.disabled = tagPage >= totalPages;
        }
        return;
      }
      setCandidateMode(false);
      const typeValue = tagTypeFilter ? tagTypeFilter.value : "all";
      const sortValue = tagSortSelect ? tagSortSelect.value : "count-desc";
      const showEmpty = tagShowEmptyToggle ? tagShowEmptyToggle.checked : false;
      const filtered = filterTags(tags, { query, type: typeValue, showEmpty });
      const sorted = sortTags(filtered, sortValue);
      const total = sorted.length;
      const totalPages = Math.max(1, Math.ceil(total / tagPageSize));
      if (tagPage > totalPages) {
        tagPage = totalPages;
      }
      const start = (tagPage - 1) * tagPageSize;
      const pageItems = sorted.slice(start, start + tagPageSize);
      renderTagList(pageItems);
      if (tagPageInfo) {
        tagPageInfo.textContent = total
          ? `第 ${tagPage}/${totalPages} 页 · 显示 ${pageItems.length}/${total}（总 ${tags.length}）`
          : "无匹配标签";
      }
      if (tagPrevBtn) {
        tagPrevBtn.disabled = tagPage <= 1;
      }
      if (tagNextBtn) {
        tagNextBtn.disabled = tagPage >= totalPages;
      }
    }

    async function loadTagTypes() {
      if (!typeList) return;
      const data = await fetchJSON("/upload/admin/tag-types");
      tagTypes = data.types || [];
      renderTagTypes(tagTypes);
      refreshTypeFilterOptions();
    }

    async function loadTags() {
      if (!tagList) return;
      const data = await fetchJSON("/upload/admin/tags");
      tags = data.tags || [];
      buildTagRelationMaps();
      refreshTypeFilterOptions();
      applyTagFilters();
      if (activeEditor === "tag" && activeTagName) {
        const target = tags.find((item) => item.tag === activeTagName);
        if (target) {
          renderTagEditor(target);
        } else {
          closeEditor();
        }
      }
    }

    async function refreshAll() {
      await loadTagIndex();
      if (typeList) await loadTagTypes();
      await loadTags();
    }

    function collectTagTypes() {
      if (!typeList) return [];
      return Array.from(typeList.querySelectorAll("[data-type-row]"))
        .map((row) => {
          const type = row.querySelector("[data-type-field='type']").value.trim();
          const label = row.querySelector("[data-type-field='label']").value.trim();
          const color = row.querySelector("[data-type-field='color']").value.trim();
          return { type, label, color };
        })
        .filter((item) => item.type || item.label);
    }

    async function saveTagTypes() {
      if (!typeList) return;
      if (typeHint) typeHint.textContent = "保存中...";
      try {
        await fetchJSON("/upload/admin/tag-types", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ types: collectTagTypes() }),
        });
        if (typeHint) typeHint.textContent = "已保存，等待刷新发布";
        await refreshAll();
      } catch (err) {
        if (typeHint) typeHint.textContent = err.message;
      }
    }

    function renderTagTypes(types) {
      if (!typeList) return;
      typeList.innerHTML = types
        .map(
          (item) => `
        <div class="tag-type-row" data-type-row>
          <label class="tag-field">
            <span>标识</span>
            <input type="text" value="${escapeHtml(item.type || "")}" placeholder="general" data-type-field="type">
          </label>
          <label class="tag-field">
            <span>名称</span>
            <input type="text" value="${escapeHtml(item.label || "")}" placeholder="普通" data-type-field="label">
          </label>
          <label class="tag-field tag-color-field">
            <span>颜色</span>
            <input type="color" value="${escapeHtml(item.color || "#7b8794")}" data-type-field="color">
          </label>
          <div class="tag-type-actions">
            <button class="btn ghost" type="button" data-type-action="up">上移</button>
            <button class="btn ghost" type="button" data-type-action="down">下移</button>
            <button class="btn primary" type="button" data-type-action="save">保存</button>
            <button class="btn ghost" type="button" data-type-action="delete">删除</button>
          </div>
        </div>
      `
        )
        .join("");

      typeList.querySelectorAll("[data-type-action='up']").forEach((btn) => {
        btn.addEventListener("click", () => {
          const row = btn.closest("[data-type-row]");
          const prev = row.previousElementSibling;
          if (prev) row.parentNode.insertBefore(row, prev);
        });
      });

      typeList.querySelectorAll("[data-type-action='down']").forEach((btn) => {
        btn.addEventListener("click", () => {
          const row = btn.closest("[data-type-row]");
          const next = row.nextElementSibling;
          if (next) row.parentNode.insertBefore(next, row);
        });
      });

      typeList.querySelectorAll("[data-type-action='save']").forEach((btn) => {
        btn.addEventListener("click", saveTagTypes);
      });

      typeList.querySelectorAll("[data-type-action='delete']").forEach((btn) => {
        btn.addEventListener("click", () => {
          const row = btn.closest("[data-type-row]");
          if (!confirm("确认删除该类型？")) return;
          row.remove();
          saveTagTypes();
        });
      });
    }

    function bindTagRowActions(scope) {
      const host = scope || document;
      host.querySelectorAll("[data-tag-action='save']").forEach((btn) => {
        btn.addEventListener("click", async () => {
          const row = btn.closest("[data-tag-row]");
          const tag = row.querySelector("[data-tag-field='tag']").value.trim();
          const slug = row.querySelector("[data-tag-field='slug']").value.trim();
          const type = row.querySelector("[data-tag-field='type']").value;
          const intro = row.querySelector("[data-tag-field='intro']").value.trim();
          const aliases = row.querySelector("[data-tag-field='aliases']").value.trim();
          const parents = row.querySelector("[data-tag-field='parents']").value.trim();
          const aliasTo = row.querySelector("[data-tag-field='alias-to']").value.trim();
          if (tagsHint) tagsHint.textContent = "保存中...";
          try {
            await fetchJSON("/upload/admin/tags/meta", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ tag, slug, type, intro, aliases, parents, alias_to: aliasTo }),
            });
            if (tagsHint) tagsHint.textContent = "已保存，等待刷新发布";
            loadTags();
          } catch (err) {
            if (tagsHint) tagsHint.textContent = err.message;
          }
        });
      });

      host.querySelectorAll("[data-tag-action='meta-delete']").forEach((btn) => {
        btn.addEventListener("click", async () => {
          const row = btn.closest("[data-tag-row]");
          const tag = row.querySelector("[data-tag-field='tag']").value.trim();
          if (!tag) return;
          if (tagsHint) tagsHint.textContent = "清除中...";
          try {
            await fetchJSON("/upload/admin/tags/meta/delete", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ tag }),
            });
            if (tagsHint) tagsHint.textContent = "已清除";
            loadTags();
          } catch (err) {
            if (tagsHint) tagsHint.textContent = err.message;
          }
        });
      });

      host.querySelectorAll("[data-tag-action='rename']").forEach((btn) => {
        btn.addEventListener("click", async () => {
          const row = btn.closest("[data-tag-row]");
          const from = row.querySelector("[data-tag-field='tag']").value.trim();
          const to = prompt("改名为（无需 #）", "");
          if (!to) return;
          if (tagsHint) tagsHint.textContent = "改名中...";
          try {
            await fetchJSON("/upload/admin/tags/rename", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ from, to }),
            });
            if (tagsHint) tagsHint.textContent = "已改名";
            activeTagName = to.trim();
            loadTags();
          } catch (err) {
            if (tagsHint) tagsHint.textContent = err.message;
          }
        });
      });

      host.querySelectorAll("[data-tag-action='delete']").forEach((btn) => {
        btn.addEventListener("click", async () => {
          const row = btn.closest("[data-tag-row]");
          const tag = row.querySelector("[data-tag-field='tag']").value.trim();
          if (!confirm("确认删除该标签？")) return;
          if (tagsHint) tagsHint.textContent = "删除中...";
          try {
            await fetchJSON("/upload/admin/tags/delete", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ tag }),
            });
            if (tagsHint) tagsHint.textContent = "已删除";
            if (activeTagName === tag) {
              closeEditor();
            }
            loadTags();
          } catch (err) {
            if (tagsHint) tagsHint.textContent = err.message;
          }
        });
      });
    }

    function bindTagTreeActions(scope) {
      const host = scope || document;
      host.querySelectorAll("[data-tag-tree-item]").forEach((btn) => {
        btn.addEventListener("click", () => {
          const tagName = btn.dataset.tagTreeItem || "";
          const target = getTagInfo(tagName);
          if (!target) return;
          openTagEditor(target);
        });
      });
    }

    if (typeAddBtn) {
      typeAddBtn.addEventListener("click", () => {
        tagTypes = [
          { type: "", label: "", color: "#7b8794" },
          ...tagTypes,
        ];
        renderTagTypes(tagTypes);
      });
    }

    if (typeSaveBtn) {
      typeSaveBtn.addEventListener("click", saveTagTypes);
    }

    if (tagAddBtn) {
      tagAddBtn.addEventListener("click", () => {
        const newTag = {
          tag: "",
          slug: "",
          type: defaultType(),
          count: 0,
          intro: "",
          aliases: [],
          parents: [],
          alias_to: "",
        };
        tags = [newTag, ...tags];
        buildTagRelationMaps();
        if (tagSearchInput) tagSearchInput.value = "";
        if (tagTypeFilter) tagTypeFilter.value = "all";
        if (tagShowEmptyToggle) tagShowEmptyToggle.checked = true;
        tagPage = 1;
        applyTagFilters({ resetPage: true });
        openTagEditor(newTag);
      });
    }

    if (tagSearchInput) {
      tagSearchInput.addEventListener("input", () => applyTagFilters({ resetPage: true }));
      tagSearchInput.addEventListener("focus", () => applyTagFilters({ resetPage: false }));
      tagSearchInput.addEventListener("blur", () => {
        window.setTimeout(() => {
          if (tagSuggestList) {
            tagSuggestList.hidden = true;
          }
        }, 120);
      });
    }

    if (tagTypeFilter) {
      tagTypeFilter.addEventListener("change", () => applyTagFilters({ resetPage: true }));
    }

    if (tagSortSelect) {
      tagSortSelect.addEventListener("change", () => applyTagFilters({ resetPage: true }));
    }

    if (tagShowEmptyToggle) {
      tagShowEmptyToggle.addEventListener("change", () => applyTagFilters({ resetPage: true }));
    }

    if (tagCandidateToggle) {
      tagCandidateToggle.addEventListener("change", () => applyTagFilters({ resetPage: true }));
    }

    if (tagPageSizeSelect) {
      tagPageSizeSelect.addEventListener("change", () => applyTagFilters({ resetPage: true }));
    }

    if (tagPrevBtn) {
      tagPrevBtn.addEventListener("click", () => {
        if (tagPage <= 1) return;
        tagPage -= 1;
        applyTagFilters();
      });
    }

    if (tagNextBtn) {
      tagNextBtn.addEventListener("click", () => {
        tagPage += 1;
        applyTagFilters();
      });
    }

    if (tagEditorBack) {
      tagEditorBack.addEventListener("click", () => {
        closeEditor();
      });
    }

    if (tagTypeToggle) {
      tagTypeToggle.addEventListener("click", () => {
        setTagTypesExpanded(!tagTypesExpanded);
      });
    }

    if (refreshBtn) {
      refreshBtn.addEventListener("click", refreshAll);
    }

    setEditorOpen(false);
    setTagTypesExpanded(false);
    refreshAll();
  }

  ensureAuth().then((authed) => {
    if (authed) initAdmin();
  });

  initTagSuggest(document);
  initTagEditors(document);
})();
