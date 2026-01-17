(function () {
  const page = document.querySelector("[data-favorites-page]");
  if (!page) return;

  const grid = page.querySelector("[data-fav-grid]");
  if (!grid) return;

  const empty = page.querySelector("[data-fav-empty]");
  const loginHint = page.querySelector("[data-fav-login-hint]");
  const countChip = page.querySelector("[data-fav-count]");
  const totalStat = page.querySelector("[data-fav-total]");
  const activeBox = page.querySelector("[data-fav-active]");
  const artistList = page.querySelector("[data-fav-artist-list]");
  const characterList = page.querySelector("[data-fav-character-list]");
  const monthList = page.querySelector("[data-fav-month-list]");
  const searchInput = page.querySelector("[data-fav-search-input]");
  const galleryList = page.querySelector("[data-fav-gallery-list]");
  const galleryNewBtn = page.querySelector("[data-fav-gallery-new]");
  const galleryForm = page.querySelector("[data-fav-gallery-form]");
  const galleryTitleInput = page.querySelector("[data-fav-gallery-title]");
  const galleryDescInput = page.querySelector("[data-fav-gallery-desc]");
  const galleryCancel = page.querySelector("[data-fav-gallery-cancel]");
  const galleryPanel = page.querySelector("[data-fav-gallery-panel]");
  const galleryName = page.querySelector("[data-fav-gallery-name]");
  const galleryDescText = page.querySelector("[data-fav-gallery-desc-text]");
  const galleryCountText = page.querySelector("[data-fav-gallery-count]");
  const galleryUpdatedText = page.querySelector("[data-fav-gallery-updated]");
  const galleryEditBtn = page.querySelector("[data-fav-gallery-edit]");
  const galleryDeleteBtn = page.querySelector("[data-fav-gallery-delete]");
  const galleryClearCoverBtn = page.querySelector("[data-fav-gallery-clear-cover]");
  const sortSelect = page.querySelector("[data-fav-sort]");
  const ratingFilterBox = page.querySelector("[data-fav-rating-filter]");
  const assignPanel = page.querySelector("[data-fav-assign]");
  const assignList = page.querySelector("[data-fav-assign-list]");
  const assignMeta = page.querySelector("[data-fav-assign-meta]");
  const assignClose = page.querySelector("[data-fav-assign-close]");

  const state = {
    q: "",
    artist: "",
    character: "",
    month: "",
    rating: 0,
    flag: "",
    color: "",
    sort: "favorited_desc",
    galleryId: "all",
  };

  let images = [];
  let allFavorites = [];
  let galleries = [];
  let currentGallery = null;
  let tagIndex = null;
  const tagCache = new Map();
  const monthCache = new Map();
  const galleryCache = new Map();
  let assignTarget = null;
  let assignGalleries = [];

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

  function normalizeTagName(input) {
    const value = String(input || "").trim().replace(/^#/, "");
    return value.replace(/\s+/g, " ").toLowerCase();
  }

  function tokenizeQuery(input) {
    if (!input) return [];
    const tokens = [];
    let buffer = "";
    let inQuote = false;
    for (let i = 0; i < input.length; i += 1) {
      const char = input[i];
      if (char === "\"") {
        inQuote = !inQuote;
        continue;
      }
      if (!inQuote && /\s/.test(char)) {
        if (buffer) {
          tokens.push(buffer);
          buffer = "";
        }
        continue;
      }
      buffer += char;
    }
    if (buffer) tokens.push(buffer);
    return tokens;
  }

  function parseDate(value) {
    if (!value) return null;
    const dt = new Date(value);
    return Number.isNaN(dt.getTime()) ? null : dt;
  }

  function formatMonth(dt) {
    if (!dt) return "";
    const year = dt.getFullYear();
    const month = String(dt.getMonth() + 1).padStart(2, "0");
    return `${year}-${month}`;
  }

  function formatShortDate(value) {
    const dt = parseDate(value);
    if (!dt) return "-";
    const year = dt.getFullYear();
    const month = String(dt.getMonth() + 1).padStart(2, "0");
    const day = String(dt.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
  }

  function buildTagIndex(raw) {
    const aliasMap = new Map();
    const typeMap = new Map();
    const canonicalSet = new Set();
    if (!raw || !Array.isArray(raw.tags)) {
      return { aliasMap, typeMap, canonicalSet };
    }
    raw.tags.forEach((item) => {
      const tag = normalizeTagName(item.tag);
      if (!tag) return;
      const aliasOf = normalizeTagName(item.alias_of);
      const canonical = aliasOf || tag;
      aliasMap.set(tag, canonical);
      (item.aliases || []).forEach((alias) => {
        const normalized = normalizeTagName(alias);
        if (normalized) aliasMap.set(normalized, canonical);
      });
      const tagType = String(item.type || "").toLowerCase() || "general";
      typeMap.set(tag, tagType);
      typeMap.set(canonical, tagType);
      if (!aliasOf) canonicalSet.add(tag);
    });
    return { aliasMap, typeMap, canonicalSet };
  }

  function resolveTag(tag) {
    if (!tagIndex || !tagIndex.aliasMap) return tag;
    return tagIndex.aliasMap.get(tag) || tag;
  }

  function expandTags(img) {
    const key = img.uuid || "";
    if (tagCache.has(key)) return tagCache.get(key);
    const canonicalTags = new Set();
    const artistTags = new Set();
    const characterTags = new Set();
    const aliasMap = tagIndex ? tagIndex.aliasMap : new Map();
    const typeMap = tagIndex ? tagIndex.typeMap : new Map();
    (img.tags || []).forEach((tag) => {
      const normalized = normalizeTagName(tag);
      if (!normalized) return;
      const canonical = aliasMap.get(normalized) || normalized;
      canonicalTags.add(canonical);
      const type = typeMap.get(canonical) || typeMap.get(normalized) || "general";
      if (type === "artist") artistTags.add(canonical);
      if (type === "character") characterTags.add(canonical);
    });
    const data = { canonicalTags, artistTags, characterTags };
    tagCache.set(key, data);
    return data;
  }

  function favoriteMonth(img) {
    const key = img.uuid || "";
    if (monthCache.has(key)) return monthCache.get(key);
    const dt = parseDate(img.favorited_at || img.added_at || img.created_at);
    const month = formatMonth(dt);
    monthCache.set(key, month);
    return month;
  }

  function parseQuery(input) {
    const includeTags = [];
    const excludeTags = [];
    const includeArtists = [];
    const excludeArtists = [];
    const includeCharacters = [];
    const excludeCharacters = [];
    const textTerms = [];
    const textExclude = [];
    tokenizeQuery(input).forEach((token) => {
      let raw = token;
      let neg = false;
      if (raw.startsWith("-")) {
        neg = true;
        raw = raw.slice(1);
      }
      if (!raw) return;
      const keyMatch = raw.match(/^([a-zA-Z_]+)\s*[:=]\s*(.+)$/);
      if (keyMatch) {
        const key = keyMatch[1].toLowerCase();
        const value = keyMatch[2].trim();
        if (!value) return;
        if (["tag", "tags", "t"].includes(key)) {
          value
            .split(/[,\|]+/)
            .map((item) => normalizeTagName(item))
            .filter(Boolean)
            .forEach((tag) => (neg ? excludeTags : includeTags).push(resolveTag(tag)));
          return;
        }
        if (["artist", "a"].includes(key)) {
          const tag = resolveTag(normalizeTagName(value));
          if (tag) (neg ? excludeArtists : includeArtists).push(tag);
          return;
        }
        if (["character", "ch", "c"].includes(key)) {
          const tag = resolveTag(normalizeTagName(value));
          if (tag) (neg ? excludeCharacters : includeCharacters).push(tag);
          return;
        }
        if (["fav", "favorite", "favorites"].includes(key)) {
          return;
        }
      }
      const normalized = normalizeTagName(raw);
      const canonical = resolveTag(normalized);
      const isKnownTag = canonical && tagIndex && tagIndex.canonicalSet.has(canonical);
      if (normalized && isKnownTag) {
        (neg ? excludeTags : includeTags).push(canonical);
      } else if (normalized) {
        (neg ? textExclude : textTerms).push(normalized);
      }
    });
    return {
      includeTags: Array.from(new Set(includeTags)),
      excludeTags: Array.from(new Set(excludeTags)),
      includeArtists: Array.from(new Set(includeArtists)),
      excludeArtists: Array.from(new Set(excludeArtists)),
      includeCharacters: Array.from(new Set(includeCharacters)),
      excludeCharacters: Array.from(new Set(excludeCharacters)),
      textTerms: Array.from(new Set(textTerms)),
      textExclude: Array.from(new Set(textExclude)),
    };
  }

  function renderGalleryShelf() {
    if (!galleryList) return;
    const allCard = {
      id: "all",
      title: "All Favorites",
      description: "",
      count: allFavorites.length,
      cover_thumb_filename: "",
      cover_dominant_color: "",
      updated_at: "",
      cover_is_manual: false,
    };
    const cards = [allCard].concat(galleries);
    galleryList.innerHTML = cards
      .map((gallery) => {
        const active = String(state.galleryId) === String(gallery.id) ? "active" : "";
        const cover = gallery.cover_thumb_filename
          ? `<img src="/thumb/${escapeHtml(gallery.cover_thumb_filename)}" alt="">`
          : "<span>ALL</span>";
        const updated = gallery.updated_at ? formatShortDate(gallery.updated_at) : "";
        const metaParts = [`${gallery.count || 0} items`];
        if (updated) metaParts.push(updated);
        const metaText = metaParts.join(" / ");
        return `
          <div class="favorites-gallery-card ${active}" data-fav-gallery="${escapeHtml(String(gallery.id))}">
            <div class="favorites-gallery-thumb" style="${gallery.cover_dominant_color ? `background:${escapeHtml(gallery.cover_dominant_color)}` : ""}">
              ${cover}
            </div>
            <div>
              <div class="favorites-gallery-name">${escapeHtml(gallery.title || "")}</div>
              <div class="favorites-gallery-meta">${escapeHtml(metaText)}</div>
            </div>
          </div>
        `;
      })
      .join("");
    galleryList.querySelectorAll("[data-fav-gallery]").forEach((card) => {
      card.addEventListener("click", () => {
        const id = card.dataset.favGallery || "all";
        if (state.galleryId === id) return;
        state.galleryId = id;
        loadGallery(id);
      });
    });
  }

  function updateGalleryPanel() {
    if (!galleryPanel) return;
    if (!currentGallery) {
      galleryPanel.hidden = true;
      return;
    }
    galleryPanel.hidden = false;
    if (galleryName) galleryName.textContent = currentGallery.title || "";
    if (galleryDescText) galleryDescText.textContent = currentGallery.description || "";
    if (galleryCountText) galleryCountText.textContent = `${currentGallery.count || 0} items`;
    if (galleryUpdatedText) {
      galleryUpdatedText.textContent = currentGallery.updated_at ? formatShortDate(currentGallery.updated_at) : "";
    }
    if (galleryClearCoverBtn) {
      galleryClearCoverBtn.disabled = !currentGallery.cover_is_manual;
    }
  }

  function closeAssignPanel() {
    if (!assignPanel) return;
    assignPanel.hidden = true;
    assignTarget = null;
    assignGalleries = [];
    if (assignList) assignList.innerHTML = "";
    if (assignMeta) assignMeta.textContent = "";
  }

  function renderAssignPanel() {
    if (!assignList) return;
    if (!assignGalleries.length) {
      assignList.innerHTML = '<span class="muted">No galleries yet</span>';
      return;
    }
    assignList.innerHTML = assignGalleries
      .map((item) => {
        const active = item.contains ? "active" : "";
        return `
          <button class="favorites-assign-item ${active}" type="button" data-gallery-id="${escapeHtml(
            String(item.id)
          )}">
            <span>${escapeHtml(item.title || "")}</span>
            <span class="muted">${item.count || 0}</span>
          </button>
        `;
      })
      .join("");
    assignList.querySelectorAll("[data-gallery-id]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        if (!assignTarget) return;
        const galleryId = btn.dataset.galleryId || "";
        const entry = assignGalleries.find((item) => String(item.id) === String(galleryId));
        if (!entry) return;
        const action = entry.contains ? "remove" : "add";
        try {
          await fetchJSON(`/api/galleries/${galleryId}/items`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ uuid: assignTarget.uuid, action }),
          });
          galleryCache.delete(String(galleryId));
          if (state.galleryId === String(galleryId)) {
            await loadGallery(state.galleryId, true, true);
          }
          await reloadAssignPanel();
        } catch (err) {
          return;
        }
      });
    });
  }

  async function reloadAssignPanel() {
    if (!assignTarget) return;
    try {
      const data = await fetchJSON(`/api/galleries?uuid=${encodeURIComponent(assignTarget.uuid)}`, {
        cache: "no-store",
      });
      assignGalleries = data.galleries || [];
      galleries = data.galleries || [];
      renderGalleryShelf();
    } catch (err) {
      assignGalleries = [];
    }
    renderAssignPanel();
  }

  async function openAssignPanel(uuid, title) {
    if (!assignPanel) return;
    assignTarget = { uuid, title: title || "" };
    assignPanel.hidden = false;
    if (assignMeta) {
      assignMeta.textContent = title ? `Target: ${title}` : `Target: ${uuid}`;
    }
    await reloadAssignPanel();
  }

  function renderCards(items) {
    const html = items
      .map((img) => {
        const title = escapeHtml(img.title || "Untitled");
        const desc = escapeHtml(img.description || "");
        const tags = (img.tags || []).slice(0, 6);
        const favored = img.favorited_at ? formatShortDate(img.favorited_at) : "-";
        const created = img.created_at ? formatShortDate(img.created_at) : "-";
        const detailPath = escapeHtml(resolveDetailPath(img));
        const rating = Math.max(0, Math.min(5, Number(img.rating) || 0));
        const flag = String(img.flag || "");
        const color = String(img.color_label || "");
        const coverAction = currentGallery
          ? `<button class="btn ghost btn-mini" type="button" data-fav-cover>Set Cover</button>`
          : "";
        const manageAction = `<button class="btn ghost btn-mini" type="button" data-fav-assign>Manage</button>`;
        return `
          <div class="favorites-row" data-masonry-item data-card-link="${detailPath}" data-uuid="${escapeHtml(img.uuid || "")}" data-title="${title}" tabindex="0" role="link" aria-label="${title}">
            <div class="favorites-cell main">
              <a class="favorites-thumb" href="${detailPath}" aria-label="${title}">
                <img src="/thumb/${escapeHtml(img.thumb_filename || "")}" alt="${title}" loading="lazy" width="${img.thumb_width || ""}" height="${img.thumb_height || ""}" onerror="this.onerror=null;this.src='/raw/${escapeHtml(img.raw_filename || "")}';">
              </a>
              <div class="favorites-summary">
                <a class="favorites-title-link" href="${detailPath}">${title}</a>
                ${desc ? `<div class="favorites-desc">${desc}</div>` : ""}
                <div class="favorites-tags">
                  ${tags.map((tag) => `#${escapeHtml(tag)}`).join(" ")}
                </div>
              </div>
            </div>
            <div class="favorites-cell meta">
              <div class="favorites-meta-lines">
                <span>${img.width || "-"}x${img.height || "-"}</span>
                <span>${escapeHtml(img.bytes_human || "")}</span>
                <span>Fav ${favored}</span>
                <span>Created ${created}</span>
              </div>
            </div>
            <div class="favorites-cell marks">
              <div class="favorites-marks">
                <div class="mark-stars">
                  ${[1, 2, 3, 4, 5]
                    .map((value) => {
                      const active = value <= rating ? "active" : "";
                      const symbol = value <= rating ? "\u2605" : "\u2606";
                      return `<button class="mark-star ${active}" type="button" data-fav-rate="${value}" aria-label="Rating ${value} stars">${symbol}</button>`;
                    })
                    .join("")}
                </div>
                <div class="mark-flags">
                  <button class="mark-flag ${flag === "pick" ? "active" : ""}" type="button" data-fav-flag="pick" aria-label="精选" title="精选">⚑</button>
                  <button class="mark-flag ${flag === "reject" ? "active" : ""}" type="button" data-fav-flag="reject" aria-label="淘汰" title="淘汰">⚐</button>
                </div>
                <div class="mark-colors">
                  ${["red", "yellow", "green", "blue", "purple"]
                    .map((value) => {
                      const active = value === color ? "active" : "";
                      return `<button class="mark-color ${active}" type="button" data-fav-color="${value}" style="background:${colorSwatch(value)}"></button>`;
                    })
                    .join("")}
                </div>
              </div>
            </div>
            <div class="favorites-cell actions">
              <div class="favorites-actions">
                ${coverAction}
                ${manageAction}
              </div>
            </div>
          </div>
        `;
      })
      .join("");
    grid.innerHTML = html;
    if (window.GalleryCardLinks) {
      window.GalleryCardLinks.init(grid.querySelectorAll('[data-card-link]'));
    }
  }

  function colorSwatch(name) {
    if (name === "red") return "#e4525d";
    if (name === "yellow") return "#f2c84b";
    if (name === "green") return "#4bc27d";
    if (name === "blue") return "#4d8cf2";
    if (name === "purple") return "#8f6df2";
    return "transparent";
  }

  function renderActiveFilters() {
    if (!activeBox) return;
    const active = [];
    if (state.galleryId !== "all" && currentGallery) {
      active.push({ key: "gallery", label: `gallery:${currentGallery.title || ""}` });
    }
    if (state.artist) active.push({ key: "artist", label: `artist:${state.artist}` });
    if (state.character) active.push({ key: "character", label: `character:${state.character}` });
    if (state.month) active.push({ key: "month", label: state.month });
    if (state.rating) active.push({ key: "rating", label: `rating:${state.rating}` });
    if (state.flag) active.push({ key: "flag", label: `flag:${state.flag}` });
    if (state.color) active.push({ key: "color", label: `color:${state.color}` });
    if (!active.length) {
      activeBox.innerHTML = '<span class="muted">No facet filter selected</span>';
      return;
    }
    activeBox.innerHTML = active
      .map(
        (item) => `
        <button class="chip chip-active" type="button" data-fav-clear="${escapeHtml(item.key)}">
          ${escapeHtml(item.label)} <span aria-hidden="true">x</span>
        </button>
      `
      )
      .join("");
    activeBox.querySelectorAll("[data-fav-clear]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const key = btn.dataset.favClear;
        if (key === "artist") state.artist = "";
        if (key === "character") state.character = "";
        if (key === "month") state.month = "";
        if (key === "rating") state.rating = 0;
        if (key === "flag") state.flag = "";
        if (key === "color") state.color = "";
        if (key === "gallery") {
          state.galleryId = "all";
          loadGallery("all");
          return;
        }
        applyFilters();
      });
    });
  }

  function renderFacetList(container, items, key, selectedValue, labelPrefix) {
    if (!container) return;
    if (!items.length) {
      container.innerHTML = '<span class="facet-empty">-</span>';
      return;
    }
    container.innerHTML = items
      .map(
        (item) => `
        <button class="facet-item ${selectedValue === item.key ? "active" : ""}" type="button" data-fav-facet="${key}" data-value="${escapeHtml(item.key)}">
          <span class="facet-label">${labelPrefix}${escapeHtml(item.key)}</span>
          <span class="facet-count">${item.count}</span>
        </button>
      `
      )
      .join("");
    container.querySelectorAll("[data-fav-facet]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const facetKey = btn.dataset.favFacet;
        const value = btn.dataset.value || "";
        if (facetKey === "artist") state.artist = state.artist === value ? "" : value;
        if (facetKey === "character") state.character = state.character === value ? "" : value;
        if (facetKey === "month") state.month = state.month === value ? "" : value;
        applyFilters();
      });
    });
  }

  function buildFacets() {
    const artistCounts = new Map();
    const characterCounts = new Map();
    const monthCounts = new Map();

    images.forEach((img) => {
      const tags = expandTags(img);
      tags.artistTags.forEach((tag) => {
        artistCounts.set(tag, (artistCounts.get(tag) || 0) + 1);
      });
      tags.characterTags.forEach((tag) => {
        characterCounts.set(tag, (characterCounts.get(tag) || 0) + 1);
      });
      const month = favoriteMonth(img);
      if (month) {
        monthCounts.set(month, (monthCounts.get(month) || 0) + 1);
      }
    });

    const artists = Array.from(artistCounts.entries())
      .map(([key, count]) => ({ key, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 10);
    const characters = Array.from(characterCounts.entries())
      .map(([key, count]) => ({ key, count }))
      .sort((a, b) => b.count - a.count);
    const months = Array.from(monthCounts.entries())
      .map(([key, count]) => ({ key, count }))
      .sort((a, b) => (a.key < b.key ? 1 : -1));

    renderFacetList(artistList, artists, "artist", state.artist, "#");
    renderFacetList(characterList, characters, "character", state.character, "#");
    renderFacetList(monthList, months, "month", state.month, "");
  }

  function sortImages(list) {
    const sorted = list.slice();
    const sortKey = state.sort;
    const dateValue = (img, fieldList) => {
      for (let i = 0; i < fieldList.length; i += 1) {
        const dt = parseDate(img[fieldList[i]]);
        if (dt) return dt.getTime();
      }
      return 0;
    };
    sorted.sort((a, b) => {
      if (sortKey === "favorited_desc") {
        return dateValue(b, ["favorited_at", "added_at", "created_at"]) - dateValue(a, ["favorited_at", "added_at", "created_at"]);
      }
      if (sortKey === "favorited_asc") {
        return dateValue(a, ["favorited_at", "added_at", "created_at"]) - dateValue(b, ["favorited_at", "added_at", "created_at"]);
      }
      if (sortKey === "created_desc") {
        return dateValue(b, ["created_at"]) - dateValue(a, ["created_at"]);
      }
      if (sortKey === "created_asc") {
        return dateValue(a, ["created_at"]) - dateValue(b, ["created_at"]);
      }
      if (sortKey === "title_desc") {
        return String(b.title || "").localeCompare(String(a.title || ""));
      }
      if (sortKey === "title_asc") {
        return String(a.title || "").localeCompare(String(b.title || ""));
      }
      if (sortKey === "size_desc") {
        return (Number(b.bytes) || 0) - (Number(a.bytes) || 0);
      }
      if (sortKey === "size_asc") {
        return (Number(a.bytes) || 0) - (Number(b.bytes) || 0);
      }
      return 0;
    });
    return sorted;
  }

  function applyFilters() {
    const query = parseQuery(state.q);
    const filtered = images.filter((img) => {
      const tags = expandTags(img);
      if (state.artist && !tags.artistTags.has(state.artist)) return false;
      if (state.character && !tags.characterTags.has(state.character)) return false;
      if (state.month && favoriteMonth(img) !== state.month) return false;
      if (state.rating && Number(img.rating || 0) !== state.rating) return false;
      if (state.flag && String(img.flag || "") !== state.flag) return false;
      if (state.color && String(img.color_label || "") !== state.color) return false;

      if (query.includeTags.length) {
        if (!query.includeTags.every((tag) => tags.canonicalTags.has(tag))) return false;
      }
      if (query.excludeTags.length) {
        if (query.excludeTags.some((tag) => tags.canonicalTags.has(tag))) return false;
      }
      if (query.includeArtists.length) {
        if (!query.includeArtists.every((tag) => tags.artistTags.has(tag))) return false;
      }
      if (query.excludeArtists.length) {
        if (query.excludeArtists.some((tag) => tags.artistTags.has(tag))) return false;
      }
      if (query.includeCharacters.length) {
        if (!query.includeCharacters.every((tag) => tags.characterTags.has(tag))) return false;
      }
      if (query.excludeCharacters.length) {
        if (query.excludeCharacters.some((tag) => tags.characterTags.has(tag))) return false;
      }
      if (query.textTerms.length || query.textExclude.length) {
        const hay = `${img.title || ""} ${img.description || ""} ${(img.tags || []).join(" ")}`.toLowerCase();
        if (query.textTerms.some((term) => term && !hay.includes(term))) return false;
        if (query.textExclude.some((term) => term && hay.includes(term))) return false;
      }
      return true;
    });

    const sorted = sortImages(filtered);
    renderCards(sorted);
    if (empty) empty.classList.toggle("show", !sorted.length);
    if (countChip) countChip.textContent = String(sorted.length);
    renderActiveFilters();
    if (assignTarget && !images.some((img) => img.uuid === assignTarget.uuid)) {
      closeAssignPanel();
    }
  }

  async function fetchJSON(url, options) {
    const resp = await fetch(url, { credentials: "include", ...options });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      const message = data.error || "Request failed";
      throw new Error(message);
    }
    return data;
  }

  function getGalleryPayload(title, description, coverUuid) {
    const payload = { title: title || "", description: description || "" };
    if (coverUuid !== undefined) payload.cover_uuid = coverUuid || "";
    return payload;
  }

  async function submitGalleryForm(event) {
    event.preventDefault();
    if (!galleryForm) return;
    const title = (galleryTitleInput && galleryTitleInput.value.trim()) || "";
    const description = (galleryDescInput && galleryDescInput.value.trim()) || "";
    if (!title) return;
    const isEdit = galleryForm.dataset.mode === "edit" && currentGallery;
    const url = isEdit ? `/api/galleries/${currentGallery.id}/update` : "/api/galleries";
    const payload = getGalleryPayload(title, description, isEdit ? currentGallery.cover_uuid : undefined);
    await fetchJSON(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    hideGalleryForm();
    await reloadGalleries();
    if (isEdit) {
      state.galleryId = String(currentGallery.id);
      await loadGallery(state.galleryId, true, true);
    }
  }

  function showGalleryForm(mode) {
    if (!galleryForm) return;
    galleryForm.hidden = false;
    galleryForm.dataset.mode = mode;
  }

  function hideGalleryForm() {
    if (!galleryForm) return;
    galleryForm.hidden = true;
    galleryForm.dataset.mode = "";
    if (galleryTitleInput) galleryTitleInput.value = "";
    if (galleryDescInput) galleryDescInput.value = "";
  }

  async function reloadGalleries() {
    const data = await fetchJSON("/api/galleries", { cache: "no-store" });
    galleries = data.galleries || [];
    renderGalleryShelf();
  }

  async function loadGallery(id, skipShelf, force) {
    if (id === "all") {
      images = allFavorites.slice();
      currentGallery = null;
      if (totalStat) totalStat.textContent = String(images.length);
      buildFacets();
      applyFilters();
      if (!skipShelf) renderGalleryShelf();
      updateGalleryPanel();
      return;
    }
    const galleryId = String(id || "");
    let cached = galleryCache.get(galleryId);
    if (!cached || force) {
      const data = await fetchJSON(`/api/galleries/${galleryId}/images`, { cache: "no-store" });
      cached = {
        gallery: data.gallery,
        images: data.images || [],
      };
      galleryCache.set(galleryId, cached);
    }
    images = cached.images.slice();
    currentGallery = cached.gallery || null;
    if (totalStat) totalStat.textContent = String(images.length);
    buildFacets();
    applyFilters();
    if (!skipShelf) renderGalleryShelf();
    updateGalleryPanel();
  }

  async function setGalleryCover(uuid) {
    if (!currentGallery) return;
    const payload = getGalleryPayload(currentGallery.title, currentGallery.description || "", uuid);
    await fetchJSON(`/api/galleries/${currentGallery.id}/update`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    await reloadGalleries();
    await loadGallery(String(currentGallery.id), true, true);
  }

  async function clearGalleryCover() {
    if (!currentGallery) return;
    const payload = getGalleryPayload(currentGallery.title, currentGallery.description || "", "");
    await fetchJSON(`/api/galleries/${currentGallery.id}/update`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    await reloadGalleries();
    await loadGallery(String(currentGallery.id), true, true);
  }

  async function deleteGallery() {
    if (!currentGallery) return;
    await fetchJSON(`/api/galleries/${currentGallery.id}/delete`, { method: "POST" });
    currentGallery = null;
    state.galleryId = "all";
    await reloadGalleries();
    await loadGallery("all", true);
  }

  async function updateFavoriteMeta(uuid, payload) {
    const data = await fetchJSON(`/api/favorites/${uuid}/meta`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    updateLocalMeta(uuid, data);
    if (state.rating || state.flag || state.color) {
      applyFilters();
    } else {
      updateRowMeta(uuid);
    }
  }

  function updateLocalMeta(uuid, data) {
    const patch = {
      rating: data.rating,
      flag: data.flag,
      color_label: data.color_label,
    };
    [allFavorites, images].forEach((list) => {
      list.forEach((item) => {
        if (item.uuid === uuid) Object.assign(item, patch);
      });
    });
    galleryCache.forEach((entry) => {
      entry.images.forEach((item) => {
        if (item.uuid === uuid) Object.assign(item, patch);
      });
    });
  }

  function updateRowMeta(uuid) {
    const row = grid.querySelector(`[data-uuid="${uuid}"]`);
    if (!row) return;
    const item = images.find((img) => img.uuid === uuid) || allFavorites.find((img) => img.uuid === uuid);
    if (!item) return;
    const rating = Math.max(0, Math.min(5, Number(item.rating) || 0));
    const flag = String(item.flag || "");
    const color = String(item.color_label || "");
    row.querySelectorAll("[data-fav-rate]").forEach((btn) => {
      const value = Number(btn.dataset.favRate || 0);
      btn.classList.toggle("active", value <= rating);
      btn.textContent = value <= rating ? "\u2605" : "\u2606";
    });
    row.querySelectorAll("[data-fav-flag]").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.favFlag === flag);
    });
    row.querySelectorAll("[data-fav-color]").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.favColor === color);
    });
  }

  function bindFilters() {
    if (ratingFilterBox) {
      ratingFilterBox.querySelectorAll("[data-fav-rating]").forEach((btn) => {
        btn.addEventListener("click", () => {
          const value = Number(btn.dataset.favRating || 0);
          state.rating = state.rating === value ? 0 : value;
          ratingFilterBox.querySelectorAll("[data-fav-rating]").forEach((item) => {
            item.classList.toggle("active", Number(item.dataset.favRating || 0) === state.rating);
          });
          applyFilters();
        });
      });
    }
    page.querySelectorAll("[data-fav-flag]").forEach((btn) => {
      if (btn.closest(".mark-flags")) return;
      btn.addEventListener("click", () => {
        const value = btn.dataset.favFlag || "";
        state.flag = state.flag === value ? "" : value;
        page.querySelectorAll(".favorites-filter-group [data-fav-flag]").forEach((item) => {
          item.classList.toggle("active", item.dataset.favFlag === state.flag);
        });
        applyFilters();
      });
    });
    page.querySelectorAll("[data-fav-color]").forEach((btn) => {
      if (btn.closest(".mark-colors")) return;
      btn.addEventListener("click", () => {
        const value = btn.dataset.favColor || "";
        state.color = state.color === value ? "" : value;
        page.querySelectorAll(".favorites-filter-group [data-fav-color]").forEach((item) => {
          item.classList.toggle("active", item.dataset.favColor === state.color);
        });
        applyFilters();
      });
    });
    if (sortSelect) {
      sortSelect.addEventListener("change", () => {
        state.sort = sortSelect.value || "favorited_desc";
        applyFilters();
      });
    }
  }

  grid.addEventListener("click", (event) => {
    const target = event.target.closest(
      "[data-fav-rate],[data-fav-flag],[data-fav-color],[data-fav-cover],[data-fav-assign]"
    );
    if (!target) return;
    const row = target.closest("[data-uuid]");
    if (!row) return;
    const uuid = row.dataset.uuid || "";
    if (!uuid) return;
    event.preventDefault();
    event.stopPropagation();
    if (target.dataset.favRate) {
      const rating = Number(target.dataset.favRate || 0);
      updateFavoriteMeta(uuid, { rating });
      return;
    }
    if (target.dataset.favFlag) {
      const current = String(row.querySelector(".mark-flag.active")?.dataset.favFlag || "");
      const next = current === target.dataset.favFlag ? "" : target.dataset.favFlag;
      updateFavoriteMeta(uuid, { flag: next });
      return;
    }
    if (target.dataset.favColor) {
      const current = String(row.querySelector(".mark-color.active")?.dataset.favColor || "");
      const next = current === target.dataset.favColor ? "" : target.dataset.favColor;
      updateFavoriteMeta(uuid, { color_label: next });
      return;
    }
    if (target.dataset.favCover !== undefined) {
      setGalleryCover(uuid);
      return;
    }
    if (target.dataset.favAssign !== undefined) {
      const title = row.dataset.title || "";
      openAssignPanel(uuid, title);
    }
  });

  async function init() {
    try {
      await fetchJSON("/auth/me");
    } catch (err) {
      if (loginHint) {
        loginHint.hidden = false;
        loginHint.classList.add("show");
      }
      if (empty) empty.classList.remove("show");
      return;
    }

    try {
      const [favData, tagData, galleryData] = await Promise.all([
        fetchJSON("/api/favorites", { cache: "no-store" }),
        fetchJSON("/static/data/tag_index.json", { cache: "no-store" }),
        fetchJSON("/api/galleries", { cache: "no-store" }),
      ]);
      allFavorites = favData.images || [];
      images = allFavorites.slice();
      tagIndex = buildTagIndex(tagData);
      galleries = galleryData.galleries || [];
      if (totalStat) totalStat.textContent = String(images.length);
      if (countChip) countChip.textContent = String(images.length);
      renderGalleryShelf();
      buildFacets();
      const urlQ = new URLSearchParams(window.location.search).get("q") || "";
      state.q = urlQ;
      if (searchInput) searchInput.value = urlQ;
      if (sortSelect) state.sort = sortSelect.value || state.sort;
      applyFilters();
      updateGalleryPanel();
      if (images.length) {
        if (empty) empty.classList.remove("show");
      } else if (empty) {
        empty.classList.add("show");
      }
    } catch (err) {
      if (empty) empty.classList.add("show");
    }
  }

  if (searchInput) {
    let timer = null;
    searchInput.addEventListener("input", () => {
      state.q = searchInput.value.trim();
      if (timer) window.clearTimeout(timer);
      timer = window.setTimeout(() => applyFilters(), 120);
    });
  }

  if (galleryNewBtn) {
    galleryNewBtn.addEventListener("click", () => {
      if (galleryTitleInput) galleryTitleInput.value = "";
      if (galleryDescInput) galleryDescInput.value = "";
      showGalleryForm("create");
    });
  }

  if (galleryForm) {
    galleryForm.addEventListener("submit", submitGalleryForm);
  }

  if (galleryCancel) {
    galleryCancel.addEventListener("click", () => {
      hideGalleryForm();
    });
  }

  if (galleryEditBtn) {
    galleryEditBtn.addEventListener("click", () => {
      if (!currentGallery) return;
      if (galleryTitleInput) galleryTitleInput.value = currentGallery.title || "";
      if (galleryDescInput) galleryDescInput.value = currentGallery.description || "";
      showGalleryForm("edit");
    });
  }

  if (galleryDeleteBtn) {
    galleryDeleteBtn.addEventListener("click", () => {
      deleteGallery();
    });
  }

  if (galleryClearCoverBtn) {
    galleryClearCoverBtn.addEventListener("click", () => {
      if (galleryClearCoverBtn.disabled) return;
      clearGalleryCover();
    });
  }

  if (assignClose) {
    assignClose.addEventListener("click", () => {
      closeAssignPanel();
    });
  }

  bindFilters();
  init();
})();
