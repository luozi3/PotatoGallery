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

  const state = {
    q: "",
    artist: "",
    character: "",
    month: "",
  };

  let images = [];
  let tagIndex = null;
  const tagCache = new Map();
  const monthCache = new Map();

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
    const dt = parseDate(img.favorited_at || img.created_at);
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
        const title = escapeHtml(img.title || "Untitled");
        const desc = escapeHtml(img.description || "");
        const tags = (img.tags || []).slice(0, 3);
        const favored = img.favorited_at ? escapeHtml(String(img.favorited_at)) : "";
        const detailPath = escapeHtml(resolveDetailPath(img));
        return `
          <article class="illust-card" data-masonry-item data-card-link="${detailPath}" tabindex="0" role="link" aria-label="${title}">
            <a class="thumb-link" href="${detailPath}" aria-label="${title}">
              <div class="thumb-shell" style="--thumb-ratio:${img.thumb_width}/${img.thumb_height};">
                <img class="thumb" src="/thumb/${escapeHtml(img.thumb_filename || "")}" alt="${title}" loading="lazy" width="${img.thumb_width || ""}" height="${img.thumb_height || ""}" onerror="this.onerror=null;this.src='/raw/${escapeHtml(img.raw_filename || "")}';">
              </div>
            </a>
            <div class="card-body">
              <div class="title">${title}</div>
              ${desc ? `<p class="desc">${desc}</p>` : ""}
              <div class="meta">
                <span>${img.width || "-"}x${img.height || "-"}</span>
                <span>${escapeHtml(img.bytes_human || "")}</span>
                ${favored ? `<span>${favored}</span>` : ""}
              </div>
              <div class="tags">
                ${tags
                  .map((tag) => `<span class="tag ghost">#${escapeHtml(tag)}</span>`)
                  .join("")}
              </div>
            </div>
          </article>
        `;
      })
      .join("");
    grid.innerHTML = html;
    if (window.GalleryCardLinks) {
      window.GalleryCardLinks.init(grid.querySelectorAll('[data-card-link]'));
    }
    relayoutMasonry();
    grid.classList.add("masonry-ready");
  }

  function renderActiveFilters() {
    if (!activeBox) return;
    const active = [];
    if (state.artist) active.push({ key: "artist", label: `artist:${state.artist}` });
    if (state.character) active.push({ key: "character", label: `character:${state.character}` });
    if (state.month) active.push({ key: "month", label: state.month });
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

  function applyFilters() {
    const query = parseQuery(state.q);
    const filtered = images.filter((img) => {
      const tags = expandTags(img);
      if (state.artist && !tags.artistTags.has(state.artist)) return false;
      if (state.character && !tags.characterTags.has(state.character)) return false;
      if (state.month && favoriteMonth(img) !== state.month) return false;

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

    renderCards(filtered);
    if (empty) empty.classList.toggle("show", !filtered.length);
    if (countChip) countChip.textContent = String(filtered.length);
    renderActiveFilters();
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
      const [favData, tagData] = await Promise.all([
        fetchJSON("/api/favorites"),
        fetchJSON("/static/data/tag_index.json", { cache: "no-store" }),
      ]);
      images = favData.images || [];
      tagIndex = buildTagIndex(tagData);
      if (totalStat) totalStat.textContent = String(images.length);
      if (countChip) countChip.textContent = String(images.length);
      buildFacets();
      const urlQ = new URLSearchParams(window.location.search).get("q") || "";
      state.q = urlQ;
      if (searchInput) searchInput.value = urlQ;
      applyFilters();
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

  init();
})();
