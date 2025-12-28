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

  async function ensureAuth() {
    try {
      await fetchJSON("/upload/admin/me");
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
  const tagsHint = document.querySelector("[data-admin-tags-hint]");
  const masonry = window.GalleryMasonry ? window.GalleryMasonry.init(grid) : null;

  let images = [];
  let collections = [];
  let defaultCollection = "";
  let showTrash = false;

  function escapeHtml(text) {
    return String(text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\"/g, "&quot;")
      .replace(/'/g, "&#39;");
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
        const metaItems = [dimension, bytesText, collectionTitle].filter(Boolean);
        return `
        <article class="illust-card admin-card" data-masonry-item data-admin-uuid="${escapeHtml(
          img.uuid
        )}">
          <a class="thumb-link" href="/images/${escapeHtml(img.uuid)}/index.html">
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
        try {
          await fetchJSON("/upload/admin/upload", {
            method: "POST",
            body: form,
          });
          if (uploadHint) uploadHint.textContent = "上传成功，等待处理";
          uploadForm.reset();
          loadImages();
        } catch (err) {
          if (uploadHint) uploadHint.textContent = err.message;
        }
      });
    }

    initTagsPage();
  }

  async function initTagsPage() {
    const tagList = document.querySelector("[data-admin-tag-list]");
    if (!tagList) return;
    let tags = [];
    async function loadTags() {
      const data = await fetchJSON("/upload/admin/tags");
      tags = data.tags || [];
      renderTags(tags);
    }

    function renderTags(tags) {
      tagList.innerHTML = tags
        .map(
          (item) => `
        <div class="tag-admin-row" data-tag-row>
          <div class="tag-admin-head">
            <div class="tag-admin-head-main">
              <label class="tag-field">
                <span>标签名</span>
                <input type="text" value="${escapeHtml(item.tag || "")}" placeholder="无需 #，例：long_hair" data-tag-field="tag">
              </label>
              <label class="tag-field">
                <span>URL Slug</span>
                <input type="text" value="${escapeHtml((item.slug || "").trim())}" placeholder="english-tag" data-tag-field="slug">
              </label>
              <label class="tag-field">
                <span>类型</span>
                <select data-tag-field="type">
                  <option value="general" ${item.type === "general" || !item.type ? "selected" : ""}>普通</option>
                  <option value="artist" ${item.type === "artist" ? "selected" : ""}>画师</option>
                  <option value="character" ${item.type === "character" ? "selected" : ""}>角色</option>
                </select>
              </label>
            </div>
            <div class="tag-admin-count">
              <span>作品数</span>
              <input type="text" value="${escapeHtml(item.count || 0)}" disabled>
            </div>
          </div>
          <div class="tag-admin-fields">
            <label class="tag-field tag-field-wide">
              <span>简介</span>
              <textarea rows="2" placeholder="标签简介" data-tag-field="intro">${escapeHtml(
                (item.intro || "").trim()
              )}</textarea>
            </label>
            <label class="tag-field tag-field-wide">
              <span>别名</span>
              <textarea rows="2" placeholder="long hair | long_hair | 长发" data-tag-field="aliases">${escapeHtml(
                (item.aliases || []).join(" | ")
              )}</textarea>
            </label>
            <label class="tag-field tag-field-wide">
              <span>父标签</span>
              <textarea rows="2" placeholder="animal_ears | kemonomimi" data-tag-field="parents">${escapeHtml(
                (item.parents || []).join(" | ")
              )}</textarea>
            </label>
            <label class="tag-field">
              <span>合并到</span>
              <input type="text" value="${escapeHtml((item.alias_to || "").trim())}" placeholder="主标签（可空）" data-tag-field="alias-to">
            </label>
          </div>
          <div class="tag-admin-actions">
            <button class="btn primary" type="button" data-tag-action="save">保存</button>
            <button class="btn ghost" type="button" data-tag-action="meta-delete">清除简介/别名</button>
            <button class="btn ghost" type="button" data-tag-action="rename">改名</button>
            <button class="btn ghost" type="button" data-tag-action="delete">删除</button>
          </div>
        </div>
      `
        )
        .join("");

      tagList.querySelectorAll("[data-tag-action='save']").forEach((btn) => {
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

      tagList.querySelectorAll("[data-tag-action='meta-delete']").forEach((btn) => {
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

      tagList.querySelectorAll("[data-tag-action='rename']").forEach((btn) => {
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
            loadTags();
          } catch (err) {
            if (tagsHint) tagsHint.textContent = err.message;
          }
        });
      });

      tagList.querySelectorAll("[data-tag-action='delete']").forEach((btn) => {
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
            loadTags();
          } catch (err) {
            if (tagsHint) tagsHint.textContent = err.message;
          }
        });
      });
    }

    if (tagAddBtn) {
      tagAddBtn.addEventListener("click", () => {
        tags = [
          { tag: "", slug: "", type: "general", count: 0, intro: "", aliases: [], parents: [], alias_to: "" },
          ...tags,
        ];
        renderTags(tags);
      });
    }

    if (refreshBtn) {
      refreshBtn.addEventListener("click", loadTags);
    }

    loadTags();
  }

  ensureAuth().then((authed) => {
    if (authed) initAdmin();
  });

  initTagSuggest(document);
  initTagEditors(document);
})();
