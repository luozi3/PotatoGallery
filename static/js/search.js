(function () {
  const grid = document.querySelector("[data-search-grid]");
  if (!grid) return;
  const empty = document.querySelector("[data-search-empty]");
  const inputs = Array.from(document.querySelectorAll("[data-search-input]"));
  const tagSelect = document.querySelector("[data-search-tag]");
  const tabs = Array.from(document.querySelectorAll("[data-search-tab]"));
  const pills = Array.from(document.querySelectorAll("[data-search-pill]"));
  const masonry = window.GalleryMasonry ? window.GalleryMasonry.init(grid) : null;

  const state = {
    q: "",
    collection: "all",
    orientation: "all",
    size: "all",
    time: "all",
    tag: "",
    tagSlugMap: null,
    tagIndex: null,
  };

  const expandedTagsCache = new Map();
  const dateCache = new Map();

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

  function parseAgeValue(raw) {
    const match = String(raw || "")
      .trim()
      .match(/^(\d+)\s*(d|day|days|w|week|weeks|m|month|months)?$/i);
    if (!match) return null;
    const value = parseInt(match[1], 10);
    const unit = (match[2] || "d").toLowerCase();
    if (unit.startsWith("w")) return value * 7;
    if (unit.startsWith("m")) return value * 30;
    return value;
  }

  function parseDateRange(raw) {
    const text = String(raw || "").trim();
    if (!text) return { min: null, max: null };
    if (text.includes("..")) {
      const [start, end] = text.split("..");
      return { min: parseDate(start), max: parseDate(end) };
    }
    const single = parseDate(text);
    return { min: single, max: single };
  }

  function applyRangeFilter(filters, key, op, value) {
    const num = parseInt(value, 10);
    if (Number.isNaN(num)) return;
    if (op === ">=" || op === ">") {
      filters[key].min = filters[key].min == null ? num : Math.max(filters[key].min, num);
    } else if (op === "<=" || op === "<") {
      filters[key].max = filters[key].max == null ? num : Math.min(filters[key].max, num);
    } else if (op === "=") {
      filters[key].min = num;
      filters[key].max = num;
    }
  }

  function resolveTag(tag, tagIndex) {
    if (!tagIndex || !tagIndex.aliasMap) return tag;
    return tagIndex.aliasMap.get(tag) || tag;
  }

  function resolveTagPrefix(tag, tagIndex) {
    if (!tagIndex || !tagIndex.aliasMap) return "";
    if (!tag || tag.length < 2) return "";
    if (!tagIndex.aliasPrefixCache) {
      tagIndex.aliasPrefixCache = new Map();
    }
    const cache = tagIndex.aliasPrefixCache;
    if (cache.has(tag)) return cache.get(tag);
    let match = "";
    let ambiguous = false;
    tagIndex.aliasMap.forEach((canonical, alias) => {
      if (ambiguous) return;
      if (alias.startsWith(tag)) {
        if (!match) {
          match = canonical;
        } else if (match !== canonical) {
          ambiguous = true;
        }
      }
    });
    const resolved = !ambiguous ? match : "";
    cache.set(tag, resolved);
    return resolved;
  }

  function collectAncestors(tag, tagIndex) {
    if (!tagIndex || !tagIndex.parentMap) return [];
    if (!tagIndex.ancestorCache) {
      tagIndex.ancestorCache = new Map();
    }
    const cache = tagIndex.ancestorCache;
    if (cache.has(tag)) return cache.get(tag);
    const parents = tagIndex.parentMap.get(tag) || [];
    const chain = [];
    parents.forEach((parent) => {
      if (!chain.includes(parent)) chain.push(parent);
      collectAncestors(parent, tagIndex).forEach((item) => {
        if (!chain.includes(item)) chain.push(item);
      });
    });
    cache.set(tag, chain);
    return chain;
  }

  function buildFallbackTagIndex(tags) {
    const canonicalTags = (tags || []).map((tag) => normalizeTagName(tag)).filter(Boolean);
    const aliasMap = new Map();
    canonicalTags.forEach((tag) => aliasMap.set(tag, tag));
    return { aliasMap, parentMap: new Map(), canonicalTags };
  }

  function buildTagIndexFromRaw(raw) {
    if (!raw || !Array.isArray(raw.tags)) return null;
    const aliasMap = new Map();
    const parentMap = new Map();
    const canonicalTags = [];
    raw.tags.forEach((item) => {
      const tag = normalizeTagName(item.tag);
      if (!tag) return;
      const aliasOf = normalizeTagName(item.alias_of);
      const canonical = aliasOf || tag;
      aliasMap.set(tag, canonical);
      const aliases = Array.isArray(item.aliases) ? item.aliases : [];
      aliases.forEach((alias) => {
        const normalized = normalizeTagName(alias);
        if (normalized) aliasMap.set(normalized, canonical);
      });
      if (!aliasOf) {
        canonicalTags.push(tag);
        const parents = Array.isArray(item.parents) ? item.parents : [];
        parentMap.set(
          tag,
          parents.map((parent) => normalizeTagName(parent)).filter(Boolean)
        );
      }
    });
    canonicalTags.sort();
    return { aliasMap, parentMap, canonicalTags };
  }

  function parseQuery(input, tagIndex) {
    const filters = {
      collection: "",
      orientation: "",
      size: "",
      width: { min: null, max: null },
      height: { min: null, max: null },
      bytes: { min: null, max: null },
      date: { min: null, max: null },
      ageMaxDays: null,
      ageMinDays: null,
      sort: "",
    };
    const includeTags = [];
    const excludeTags = [];
    const textTerms = [];
    const textExclude = [];
    const knownTags = new Set(tagIndex ? tagIndex.canonicalTags || [] : []);
    const aliasMap = tagIndex ? tagIndex.aliasMap : new Map();

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
        if (["tag", "tags", "t"].includes(key)) {
          value
            .split(/[,\|]+/)
            .map((item) => normalizeTagName(item))
            .filter(Boolean)
            .forEach((tag) => {
              const canonical = resolveTag(tag, tagIndex);
              (neg ? excludeTags : includeTags).push(canonical);
            });
          return;
        }
        if (["collection", "col", "c", "album"].includes(key)) {
          filters.collection = value.toLowerCase();
          return;
        }
        if (["orientation", "ori", "o"].includes(key)) {
          const normalized = value.toLowerCase();
          filters.orientation =
            normalized === "p" || normalized.startsWith("port") || normalized === "vertical"
              ? "portrait"
              : normalized === "l" || normalized.startsWith("land") || normalized === "horizontal"
              ? "landscape"
              : normalized === "s" || normalized.startsWith("square")
              ? "square"
              : normalized;
          return;
        }
        if (["size", "quality", "q"].includes(key)) {
          const normalized = value.toLowerCase();
          filters.size =
            normalized === "u" || normalized.startsWith("ultra") || normalized === "xl"
              ? "ultra"
              : normalized === "l" || normalized.startsWith("large") || normalized === "hd"
              ? "large"
              : normalized === "m" || normalized.startsWith("medium") || normalized === "md"
              ? "medium"
              : normalized === "c" || normalized.startsWith("compact") || normalized === "sm"
              ? "compact"
              : normalized;
          return;
        }
        if (["sort", "order"].includes(key)) {
          filters.sort = value.toLowerCase();
          return;
        }
        if (["width", "w", "height", "h", "bytes", "b"].includes(key)) {
          const numMatch = value.match(/^(>=|<=|=|>|<)?\s*(\d+)$/);
          if (numMatch) {
            const op = numMatch[1] || "=";
            const num = numMatch[2];
            const targetKey =
              key === "width" || key === "w" ? "width" : key === "height" || key === "h" ? "height" : "bytes";
            applyRangeFilter(filters, targetKey, op, num);
          }
          return;
        }
        if (["date", "created", "time"].includes(key)) {
          const range = parseDateRange(value.replace(/^[><=]+/, ""));
          if (value.startsWith(">=") || value.startsWith(">")) {
            filters.date.min = range.min;
          } else if (value.startsWith("<=") || value.startsWith("<")) {
            filters.date.max = range.max;
          } else {
            filters.date.min = range.min;
            filters.date.max = range.max;
          }
          return;
        }
        if (["after", "since"].includes(key)) {
          filters.date.min = parseDate(value);
          return;
        }
        if (["before", "until"].includes(key)) {
          filters.date.max = parseDate(value);
          return;
        }
        if (["age", "day", "days"].includes(key)) {
          const numMatch = value.match(/^(>=|<=|=|>|<)?\s*(.+)$/);
          if (numMatch) {
            const op = numMatch[1] || "<=";
            const days = parseAgeValue(numMatch[2]);
            if (days != null) {
              if (op === ">=" || op === ">") {
                filters.ageMinDays = days;
              } else {
                filters.ageMaxDays = days;
              }
            }
          }
          return;
        }
        if (["text", "title", "desc", "description"].includes(key)) {
          textTerms.push(normalizeTagName(value) || value.toLowerCase());
          return;
        }
      }

      const numMatch = raw.match(/^(width|w|height|h|bytes|b)(>=|<=|=|>|<)(\d+)$/i);
      if (numMatch) {
        const op = numMatch[2];
        const num = numMatch[3];
        const targetKey =
          numMatch[1].toLowerCase().startsWith("w")
            ? "width"
            : numMatch[1].toLowerCase().startsWith("h")
            ? "height"
            : "bytes";
        applyRangeFilter(filters, targetKey, op, num);
        return;
      }

      const dateMatch = raw.match(/^(date|created|time)(>=|<=|=|>|<)(.+)$/i);
      if (dateMatch) {
        const op = dateMatch[2];
        const range = parseDateRange(dateMatch[3]);
        if (op === ">=" || op === ">") {
          filters.date.min = range.min;
        } else if (op === "<=" || op === "<") {
          filters.date.max = range.max;
        } else {
          filters.date.min = range.min;
          filters.date.max = range.max;
        }
        return;
      }

      const ageMatch = raw.match(/^(age|days?)(>=|<=|=|>|<)?(.+)$/i);
      if (ageMatch) {
        const op = ageMatch[2] || "<=";
        const days = parseAgeValue(ageMatch[3]);
        if (days != null) {
          if (op === ">=" || op === ">") {
            filters.ageMinDays = days;
          } else {
            filters.ageMaxDays = days;
          }
        }
        return;
      }

      const normalized = normalizeTagName(raw);
      if (!normalized) return;
      let canonical = aliasMap.get(normalized) || normalized;
      let isTag = raw.startsWith("#") || aliasMap.has(normalized) || knownTags.has(canonical);
      if (!isTag) {
        const prefixMatch = resolveTagPrefix(normalized, tagIndex);
        if (prefixMatch) {
          canonical = prefixMatch;
          isTag = true;
        }
      }
      if (isTag) {
        (neg ? excludeTags : includeTags).push(canonical);
      } else {
        (neg ? textExclude : textTerms).push(normalized);
      }
    });

    return {
      includeTags: Array.from(new Set(includeTags)),
      excludeTags: Array.from(new Set(excludeTags)),
      textTerms: Array.from(new Set(textTerms)),
      textExclude: Array.from(new Set(textExclude)),
      filters,
    };
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

  function renderCards(items, tagSlugMap) {
    const html = items
      .map((img) => {
        const title = escapeHtml(img.title || "未命名");
        const desc = escapeHtml(img.description || "");
        const tags = (img.tags || []).slice(0, 3);
        return `
          <article class="illust-card" data-masonry-item data-card-link="/images/${escapeHtml(
            img.uuid
          )}/index.html" data-collection="${escapeHtml(img.collection || "")}" data-orientation="${escapeHtml(
          img.orientation || ""
        )}" data-size="${escapeHtml(img.size_bucket || "")}" tabindex="0" role="link" aria-label="${title}">
            <a class="thumb-link" href="/images/${escapeHtml(
              img.uuid
            )}/index.html" aria-label="${title}">
              <div class="thumb-shell" style="--thumb-ratio:${img.thumb_width}/${img.thumb_height};">
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
                  .map((tag) => {
                    const slug = (tagSlugMap && tagSlugMap.get(tag)) || tag;
                    return `<a class="tag ghost" href="/tags/${encodeURIComponent(
                      slug
                    )}/">#${escapeHtml(tag)}</a>`;
                  })
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
    if (masonry) {
      masonry.refresh();
      return;
    }
    grid.classList.add("masonry-ready");
  }

  function applyFilters(data) {
    const query = parseQuery(state.q, state.tagIndex);
    const filters = query.filters;
    const now = new Date();

    const effectiveCollection = filters.collection || state.collection;
    const effectiveOrientation = filters.orientation || state.orientation;
    const effectiveSize = filters.size || state.size;

    const includeTags = query.includeTags.slice();
    const selectedTag = state.tag ? normalizeTagName(state.tag) : "";
    if (selectedTag) {
      includeTags.push(resolveTag(selectedTag, state.tagIndex));
    }
    const excludeTags = query.excludeTags;
    const textTerms = query.textTerms;
    const textExclude = query.textExclude;

    let minDate = filters.date.min;
    let maxDate = filters.date.max;
    if (filters.ageMaxDays != null) {
      const cutoff = new Date(now.getTime() - filters.ageMaxDays * 24 * 60 * 60 * 1000);
      minDate = minDate ? (cutoff > minDate ? cutoff : minDate) : cutoff;
    }
    if (filters.ageMinDays != null) {
      const cutoff = new Date(now.getTime() - filters.ageMinDays * 24 * 60 * 60 * 1000);
      maxDate = maxDate ? (cutoff < maxDate ? cutoff : maxDate) : cutoff;
    }
    if (state.time !== "all") {
      const days = parseInt(state.time, 10) || 0;
      if (days > 0) {
        const cutoff = new Date(now.getTime() - days * 24 * 60 * 60 * 1000);
        minDate = minDate ? (cutoff > minDate ? cutoff : minDate) : cutoff;
      }
    }

    const filtered = data.filter((img) => {
      const matchCollection =
        effectiveCollection === "all" ||
        String(img.collection || "").toLowerCase() === effectiveCollection;
      const matchOrientation = effectiveOrientation === "all" || img.orientation === effectiveOrientation;
      const matchSize = effectiveSize === "all" || img.size_bucket === effectiveSize;
      if (!matchCollection || !matchOrientation || !matchSize) return false;

      if (filters.width.min != null || filters.width.max != null) {
        const width = img.width != null ? parseInt(img.width, 10) : null;
        if (width == null) return false;
        if (filters.width.min != null && width < filters.width.min) return false;
        if (filters.width.max != null && width > filters.width.max) return false;
      }

      if (filters.height.min != null || filters.height.max != null) {
        const height = img.height != null ? parseInt(img.height, 10) : null;
        if (height == null) return false;
        if (filters.height.min != null && height < filters.height.min) return false;
        if (filters.height.max != null && height > filters.height.max) return false;
      }

      if (filters.bytes.min != null || filters.bytes.max != null) {
        const bytes = img.bytes != null ? parseInt(img.bytes, 10) : null;
        if (bytes == null) return false;
        if (filters.bytes.min != null && bytes < filters.bytes.min) return false;
        if (filters.bytes.max != null && bytes > filters.bytes.max) return false;
      }

      if (minDate || maxDate) {
        const key = img.uuid || "";
        let created = dateCache.get(key);
        if (created === undefined) {
          created = parseDate(img.created_at);
          dateCache.set(key, created);
        }
        if (!created) return false;
        if (minDate && created < minDate) return false;
        if (maxDate && created > maxDate) return false;
      }

      const expandedTags = (() => {
        const key = img.uuid || "";
        if (expandedTagsCache.has(key)) return expandedTagsCache.get(key);
        const aliasMap = state.tagIndex ? state.tagIndex.aliasMap : new Map();
        const expanded = new Set();
        (img.tags || []).forEach((tag) => {
          const normalized = normalizeTagName(tag);
          if (!normalized) return;
          const canonical = aliasMap.get(normalized) || normalized;
          expanded.add(canonical);
          collectAncestors(canonical, state.tagIndex).forEach((parent) => expanded.add(parent));
        });
        expandedTagsCache.set(key, expanded);
        return expanded;
      })();

      if (includeTags.length) {
        const hasAll = includeTags.every((tag) => expandedTags.has(tag));
        if (!hasAll) return false;
      }
      if (excludeTags.length) {
        const hasBlocked = excludeTags.some((tag) => expandedTags.has(tag));
        if (hasBlocked) return false;
      }

      if (textTerms.length || textExclude.length) {
        const hay = `${img.title || ""} ${img.description || ""} ${(img.tags || []).join(" ")}`.toLowerCase();
        if (textTerms.some((term) => term && !hay.includes(term))) return false;
        if (textExclude.some((term) => term && hay.includes(term))) return false;
      }

      return true;
    });

    let result = filtered;
    if (filters.sort) {
      const key = filters.sort;
      if (["new", "newest", "latest", "desc", "created"].includes(key)) {
        result = filtered.slice().sort((a, b) => {
          const da = parseDate(a.created_at);
          const db = parseDate(b.created_at);
          return (db ? db.getTime() : 0) - (da ? da.getTime() : 0);
        });
      } else if (["old", "oldest", "asc", "earliest"].includes(key)) {
        result = filtered.slice().sort((a, b) => {
          const da = parseDate(a.created_at);
          const db = parseDate(b.created_at);
          return (da ? da.getTime() : 0) - (db ? db.getTime() : 0);
        });
      } else if (["bytes", "size", "large", "big"].includes(key)) {
        result = filtered.slice().sort((a, b) => (b.bytes || 0) - (a.bytes || 0));
      } else if (["small", "tiny"].includes(key)) {
        result = filtered.slice().sort((a, b) => (a.bytes || 0) - (b.bytes || 0));
      } else if (["random", "rand"].includes(key)) {
        result = filtered.slice();
        for (let i = result.length - 1; i > 0; i -= 1) {
          const j = Math.floor(Math.random() * (i + 1));
          [result[i], result[j]] = [result[j], result[i]];
        }
      }
    }

    renderCards(result, state.tagSlugMap);
    if (empty) {
      empty.classList.toggle("show", result.length === 0);
    }
  }

  function debounce(fn, delay) {
    let timer;
    return function (...args) {
      clearTimeout(timer);
      timer = setTimeout(() => fn.apply(this, args), delay);
    };
  }

  function init(data, tagSlugMap, tagIndex) {
    const query = new URLSearchParams(window.location.search).get("q") || "";
    setQuery(query);

    state.tagSlugMap = tagSlugMap;
    state.tagIndex = tagIndex;
    expandedTagsCache.clear();
    dateCache.clear();
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

  function loadTagIndexData() {
    if (window.GalleryTagSuggest && window.GalleryTagSuggest.loadTagIndex) {
      return window.GalleryTagSuggest.loadTagIndex();
    }
    return fetch("/static/data/tag_index.json", { cache: "no-store" })
      .then((resp) => (resp.ok ? resp.json() : null))
      .then((raw) => buildTagIndexFromRaw(raw))
      .catch(() => null);
  }

  Promise.all([
    fetch("/static/data/search_index.json", { cache: "no-store" }).then((resp) => resp.json()),
    loadTagIndexData(),
  ])
    .then(([payload, tagIndex]) => {
      const data = payload.images || [];
      const tagSlugMap = new Map(
        (payload.tags || []).map((item) => [String(item.tag), item.slug])
      );
      const resolvedTagIndex =
        tagIndex || buildFallbackTagIndex((payload.tags || []).map((item) => item.tag));
      init(data, tagSlugMap, resolvedTagIndex);
    })
    .catch(() => {
      if (empty) empty.classList.add("show");
    });
})();
