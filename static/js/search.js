(function () {
  const grid = document.querySelector("[data-search-grid]");
  if (!grid) return;
  const empty = document.querySelector("[data-search-empty]");
  const inputs = Array.from(document.querySelectorAll("[data-search-input]"));
  const tagSelect = document.querySelector("[data-search-tag]");
  const tabs = Array.from(document.querySelectorAll("[data-search-tab]"));
  const pills = Array.from(document.querySelectorAll("[data-search-pill]"));

  const state = {
    q: "",
    collection: "all",
    orientation: "all",
    size: "all",
    time: "all",
    tag: "",
  };

  function escapeHtml(text) {
    return String(text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function parseDate(input) {
    if (!input) return null;
    const dt = new Date(input);
    return Number.isNaN(dt.getTime()) ? null : dt;
  }

  function setQuery(value) {
    state.q = value;
    inputs.forEach((el) => {
      if (el.value !== value) el.value = value;
    });
  }

  function setActive(buttons, activeEl, ariaAttr) {
    buttons.forEach((btn) => {
      btn.classList.toggle("active", btn === activeEl);
      if (ariaAttr) btn.setAttribute(ariaAttr, btn === activeEl);
    });
  }

  function relayoutMasonry() {
    const rowHeight = parseInt(getComputedStyle(grid).getPropertyValue("grid-auto-rows")) || 8;
    const rowGap = parseInt(getComputedStyle(grid).getPropertyValue("grid-row-gap")) || 0;
    grid.querySelectorAll("[data-masonry-item]").forEach((item) => {
      const rect = item.getBoundingClientRect();
      const span = Math.max(1, Math.ceil((rect.height + rowGap) / (rowHeight + rowGap)));
      item.style.setProperty("--row-span", span);
    });
  }

  function renderCards(items) {
    const html = items
      .map((img) => {
        const title = escapeHtml(img.title || "未命名");
        const desc = escapeHtml(img.description || "");
        const tags = (img.tags || []).slice(0, 3);
        return `
          <article class="illust-card" data-masonry-item data-collection="${escapeHtml(
            img.collection || ""
          )}" data-orientation="${escapeHtml(img.orientation || "")}" data-size="${escapeHtml(
            img.size_bucket || ""
          )}">
            <a class="thumb-link" href="/images/${escapeHtml(
              img.uuid
            )}/index.html" aria-label="${title}">
              <div class="thumb-shell" style="background:${escapeHtml(
                img.dominant_color || "#eef1f5"
              )}; aspect-ratio:${img.thumb_width}/${img.thumb_height};">
                <img class="thumb" src="/thumb/${escapeHtml(
                  img.thumb_filename || ""
                )}" alt="${title}" loading="lazy" width="${img.thumb_width || ""}" height="${
          img.thumb_height || ""
        }" onerror="this.onerror=null;this.src='/raw/${escapeHtml(
          img.raw_filename || ""
        )}';">
              </div>
            </a>
            <div class="card-body">
              <div class="title">${title}</div>
              ${desc ? `<p class="desc">${desc}</p>` : ""}
              <div class="meta">
                <span>${img.width || "-"}×${img.height || "-"}</span>
                <span>${escapeHtml(img.bytes_human || "")}</span>
              </div>
              <div class="tags">
                ${tags
                  .map(
                    (tag) =>
                      `<a class="tag ghost" href="/tags/${encodeURIComponent(
                        tag
                      )}/">#${escapeHtml(tag)}</a>`
                  )
                  .join("")}
              </div>
            </div>
          </article>
        `;
      })
      .join("");
    grid.innerHTML = html;
    relayoutMasonry();
  }

  function applyFilters(data) {
    const term = state.q.trim().toLowerCase();
    const tagTerm = term.startsWith("#") ? term.slice(1) : "";
    const selectedTag = state.tag ? state.tag.toLowerCase() : "";
    const days = state.time === "all" ? 0 : parseInt(state.time, 10) || 0;
    const now = new Date();

    const filtered = data.filter((img) => {
      const matchCollection = state.collection === "all" || img.collection === state.collection;
      const matchOrientation = state.orientation === "all" || img.orientation === state.orientation;
      const matchSize = state.size === "all" || img.size_bucket === state.size;
      if (!matchCollection || !matchOrientation || !matchSize) return false;

      if (selectedTag) {
        const tags = (img.tags || []).map((t) => String(t).toLowerCase());
        if (!tags.includes(selectedTag)) return false;
      }

      if (days > 0) {
        const created = parseDate(img.created_at);
        if (created) {
          const diff = (now - created) / (1000 * 60 * 60 * 24);
          if (diff > days) return false;
        }
      }

      if (!term) return true;
      const hay = `${img.title || ""} ${img.description || ""}`.toLowerCase();
      const tags = (img.tags || []).map((t) => String(t).toLowerCase());
      if (tagTerm) {
        return tags.some((t) => t.includes(tagTerm));
      }
      return hay.includes(term) || tags.some((t) => t.includes(term));
    });

    renderCards(filtered);
    if (empty) {
      empty.classList.toggle("show", filtered.length === 0);
    }
  }

  function debounce(fn, delay) {
    let timer;
    return function (...args) {
      clearTimeout(timer);
      timer = setTimeout(() => fn.apply(this, args), delay);
    };
  }

  function init(data) {
    const query = new URLSearchParams(window.location.search).get("q") || "";
    setQuery(query);

    const apply = () => applyFilters(data);
    const debounced = debounce(apply, 120);

    inputs.forEach((input) => {
      input.addEventListener("input", (e) => {
        setQuery(e.target.value || "");
        debounced();
      });
    });

    tabs.forEach((tab) => {
      tab.addEventListener("click", () => {
        state.collection = tab.dataset.collection || "all";
        setActive(tabs, tab, "aria-selected");
        apply();
      });
    });

    pills.forEach((pill) => {
      pill.addEventListener("click", () => {
        const filter = pill.dataset.filter;
        const value = pill.dataset.value || "all";
        state[filter] = value;
        const group = pills.filter((p) => p.dataset.filter === filter);
        setActive(group, pill, "aria-pressed");
        apply();
      });
    });

    if (tagSelect) {
      tagSelect.addEventListener("change", () => {
        state.tag = tagSelect.value || "";
        apply();
      });
    }

    apply();
  }

  fetch("/static/data/search_index.json", { cache: "no-store" })
    .then((resp) => resp.json())
    .then((payload) => {
      const data = payload.images || [];
      init(data);
    })
    .catch(() => {
      if (empty) empty.classList.add("show");
    });
})();
