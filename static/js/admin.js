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
      return;
    }
    if (empty) empty.classList.remove("show");
    const collectionOptions = collections
      .map(
        (c) => `<option value="${escapeHtml(c.slug)}">${escapeHtml(c.title)}</option>`
      )
      .join("");
    grid.innerHTML = list
      .map((img) => {
        const tagsValue = (img.tags || []).map((t) => `#${t}`).join(" ");
        const disabled = img.deleted_at ? "disabled" : "";
        return `
        <article class="illust-card admin-card" data-masonry-item data-admin-uuid="${escapeHtml(
          img.uuid
        )}">
          <a class="thumb-link" href="/images/${escapeHtml(img.uuid)}/index.html">
            <div class="thumb-shell" style="background:${escapeHtml(
              img.dominant_color || "#eef1f5"
            )}; aspect-ratio:${img.thumb_width}/${img.thumb_height};">
              <img class="thumb" src="/thumb/${escapeHtml(
                img.thumb_filename || ""
              )}" alt="${escapeHtml(img.title || "")}" loading="lazy" width="${img.thumb_width || ""}" height="${
          img.thumb_height || ""
        }" onerror="this.onerror=null;this.src='/raw/${escapeHtml(img.raw_filename || "")}';">
            </div>
          </a>
          <div class="card-body admin-fields">
            <label class="label">标题</label>
            <input class="admin-input" type="text" value="${escapeHtml(
              img.title || ""
            )}" data-field="title" ${disabled}>
            <label class="label">描述</label>
            <textarea class="admin-textarea" data-field="description" ${disabled}>${escapeHtml(
              img.description || ""
            )}</textarea>
            <label class="label">标签</label>
            <input class="admin-tag-input" type="text" value="${escapeHtml(
              tagsValue
            )}" placeholder="#tag1 #tag2" data-field="tags" ${disabled}>
            <label class="label">分区</label>
            <select class="admin-select" data-field="collection" ${disabled}>
              <option value="">自动</option>
              ${collectionOptions}
            </select>
            <div class="admin-actions-row">
              <button class="btn primary" type="button" data-action="save" ${disabled}>保存</button>
              <button class="btn ghost" type="button" data-action="delete" ${disabled}>删除</button>
            </div>
            <p class="hint" data-field="status">${img.deleted_at ? "已进入垃圾桶" : ""}</p>
          </div>
        </article>
        `;
      })
      .join("");

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
    bindCollectionActions();
    applyFilters();
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
    }

    if (refreshBtn) {
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

    initTagsPage();
  }

  async function initTagsPage() {
    const tagList = document.querySelector("[data-admin-tag-list]");
    if (!tagList) return;
    async function loadTags() {
      const data = await fetchJSON("/upload/admin/tags");
      renderTags(data.tags || []);
    }

    function renderTags(tags) {
      tagList.innerHTML = tags
        .map(
          (item) => `
        <div class="tag-admin-row" data-tag-row>
          <input type="text" value="#${escapeHtml(item.tag)}" data-tag-field="tag">
          <input type="text" value="${escapeHtml(item.count)}" disabled>
          <input type="text" placeholder="#新标签" data-tag-field="new">
          <div class="admin-actions-row">
            <button class="btn primary" type="button" data-tag-action="rename">改名</button>
            <button class="btn ghost" type="button" data-tag-action="delete">删除</button>
          </div>
        </div>
      `
        )
        .join("");

      tagList.querySelectorAll("[data-tag-action='rename']").forEach((btn) => {
        btn.addEventListener("click", async () => {
          const row = btn.closest("[data-tag-row]");
          const from = row.querySelector("[data-tag-field='tag']").value.trim();
          const to = row.querySelector("[data-tag-field='new']").value.trim();
          if (!to) return;
          await fetchJSON("/upload/admin/tags/rename", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ from, to }),
          });
          loadTags();
        });
      });

      tagList.querySelectorAll("[data-tag-action='delete']").forEach((btn) => {
        btn.addEventListener("click", async () => {
          const row = btn.closest("[data-tag-row]");
          const tag = row.querySelector("[data-tag-field='tag']").value.trim();
          if (!confirm("确认删除该标签？")) return;
          await fetchJSON("/upload/admin/tags/delete", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ tag }),
          });
          loadTags();
        });
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
})();
