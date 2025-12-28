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

  function escapeHtml(text) {
    return String(text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\"/g, "&quot;")
      .replace(/'/g, "&#39;");
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

  async function initMyPage() {
    const page = document.querySelector("[data-user-page]");
    if (!page) return;
    const form = document.querySelector("[data-user-upload-form]");
    const collectionSelect = document.querySelector("[data-user-upload-collection]");
    const hint = document.querySelector("[data-user-upload-hint]");
    const loginHint = document.querySelector("[data-user-login-hint]");
    const gallery = document.querySelector("[data-user-gallery]");
    const empty = document.querySelector("[data-user-empty]");
    const masonry = window.GalleryMasonry ? window.GalleryMasonry.init(gallery) : null;

    let me = null;
    try {
      me = await fetchJSON("/auth/me");
    } catch (err) {
      if (loginHint) loginHint.textContent = "请先登录后再管理作品。";
      if (form) {
        Array.from(form.elements).forEach((el) => {
          el.disabled = true;
        });
      }
      return;
    }

    if (loginHint) loginHint.textContent = `已登录：${me.user}`;

    async function loadImages() {
      const data = await fetchJSON("/api/my/images");
      const images = data.images || [];
      renderCollectionOptions(collectionSelect, data.collections || [], true);
      if (!gallery) return;
      if (!images.length) {
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
      gallery.innerHTML = images
        .map((img) => {
          const tags = (img.tags || []).map((t) => `#${escapeHtml(t)}`).join(" ");
          return `
          <article class="illust-card user-card" data-masonry-item data-card-link="/images/${escapeHtml(
            img.uuid
          )}/index.html" tabindex="0" role="link" aria-label="${escapeHtml(img.title || "")}">
            <a class="thumb-link" href="/images/${escapeHtml(img.uuid)}/index.html">
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
                <a class="btn ghost" href="/images/${escapeHtml(img.uuid)}/index.html">编辑</a>
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

    if (form) {
      form.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (hint) hint.textContent = "上传中...";
        const formData = new FormData(form);
        try {
          await fetchJSON("/api/upload", {
            method: "POST",
            body: formData,
          });
          if (hint) hint.textContent = "上传成功，等待处理";
          form.reset();
          loadImages();
        } catch (err) {
          if (hint) hint.textContent = err.message;
        }
      });
    }

    initTagSuggest(document);
    loadImages();
  }

  async function initDetailEditor() {
    const editor = document.querySelector("[data-image-editor]");
    if (!editor) return;
    const uuid = editor.dataset.imageUuid;
    const titleInput = editor.querySelector("[data-image-field='title']");
    const descInput = editor.querySelector("[data-image-field='description']");
    const tagsInput = editor.querySelector("[data-image-field='tags']");
    const collectionSelect = editor.querySelector("[data-image-field='collection']");
    const saveBtn = editor.querySelector("[data-image-save]");
    const status = editor.querySelector("[data-image-status]");

    try {
      const data = await fetchJSON(`/api/images/${uuid}`);
      if (!data || !data.can_edit) return;
      editor.hidden = false;
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

  initMyPage();
  initDetailEditor();
})();
