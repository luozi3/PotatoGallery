<template>
  <div ref="rootEl">
    <section class="home-tag-strip" aria-label="热门标签">
      <div class="tag-strip-label">标签</div>
      <div class="tag-strip-list" data-tag-strip-list>
        <template v-if="topTags.length">
          <a
            v-for="tag in topTags.slice(0, 6)"
            :key="tag.tag"
            class="tag-chip"
            :href="tagLink(tag.tag)"
            :style="tag.style"
          >
            #{{ tag.tag }}
          </a>
        </template>
        <span v-else class="tag-chip muted">暂无标签</span>
        <a class="tag-chip tag-chip-more" href="/tags/">→全部标签</a>
      </div>
    </section>

    <section class="controls" aria-label="筛选与子集">
      <div class="tabs" role="tablist" aria-label="分区切换">
        <button
          class="tab"
          :class="{ active: filters.collection === 'all' }"
          role="tab"
          :aria-selected="filters.collection === 'all'"
          data-collection-tab
          data-collection="all"
          type="button"
          @click="setCollection('all')"
        >
          全部 <span class="count">{{ stats.total }}</span>
        </button>
        <button
          v-for="collection in collections"
          :key="collection.slug"
          class="tab"
          :class="{ active: filters.collection === collection.slug }"
          role="tab"
          :aria-selected="filters.collection === collection.slug"
          data-collection-tab
          :data-collection="collection.slug"
          type="button"
          @click="setCollection(collection.slug)"
        >
          {{ collection.title }} <span class="count">{{ collection.count }}</span>
        </button>
      </div>
      <div class="filters">
        <div class="filter-group" aria-label="方向">
          <span class="label">方向</span>
          <div class="filter-pills">
            <button
              class="pill"
              :class="{ active: filters.orientation === 'all' }"
              :aria-pressed="filters.orientation === 'all'"
              data-filter-pill
              data-filter="orientation"
              data-value="all"
              type="button"
              @click="setFilter('orientation', 'all')"
            >
              全部
            </button>
            <button
              class="pill"
              :class="{ active: filters.orientation === 'portrait' }"
              :aria-pressed="filters.orientation === 'portrait'"
              data-filter-pill
              data-filter="orientation"
              data-value="portrait"
              type="button"
              @click="setFilter('orientation', 'portrait')"
            >
              竖屏
            </button>
            <button
              class="pill"
              :class="{ active: filters.orientation === 'landscape' }"
              :aria-pressed="filters.orientation === 'landscape'"
              data-filter-pill
              data-filter="orientation"
              data-value="landscape"
              type="button"
              @click="setFilter('orientation', 'landscape')"
            >
              横屏
            </button>
            <button
              class="pill"
              :class="{ active: filters.orientation === 'square' }"
              :aria-pressed="filters.orientation === 'square'"
              data-filter-pill
              data-filter="orientation"
              data-value="square"
              type="button"
              @click="setFilter('orientation', 'square')"
            >
              方形
            </button>
          </div>
        </div>
        <div class="filter-group" aria-label="清晰度">
          <span class="label">清晰度</span>
          <div class="filter-pills">
            <button
              class="pill"
              :class="{ active: filters.size === 'all' }"
              :aria-pressed="filters.size === 'all'"
              data-filter-pill
              data-filter="size"
              data-value="all"
              type="button"
              @click="setFilter('size', 'all')"
            >
              全部
            </button>
            <button
              class="pill"
              :class="{ active: filters.size === 'ultra' }"
              :aria-pressed="filters.size === 'ultra'"
              data-filter-pill
              data-filter="size"
              data-value="ultra"
              type="button"
              @click="setFilter('size', 'ultra')"
            >
              超清
            </button>
            <button
              class="pill"
              :class="{ active: filters.size === 'large' }"
              :aria-pressed="filters.size === 'large'"
              data-filter-pill
              data-filter="size"
              data-value="large"
              type="button"
              @click="setFilter('size', 'large')"
            >
              高清
            </button>
            <button
              class="pill"
              :class="{ active: filters.size === 'medium' }"
              :aria-pressed="filters.size === 'medium'"
              data-filter-pill
              data-filter="size"
              data-value="medium"
              type="button"
              @click="setFilter('size', 'medium')"
            >
              中等
            </button>
            <button
              class="pill"
              :class="{ active: filters.size === 'compact' }"
              :aria-pressed="filters.size === 'compact'"
              data-filter-pill
              data-filter="size"
              data-value="compact"
              type="button"
              @click="setFilter('size', 'compact')"
            >
              轻量
            </button>
          </div>
        </div>
      </div>
      <div class="filter-summary" data-filter-summary v-show="filterSummary.length">
        <span class="filter-summary-label">当前筛选</span>
        <div class="filter-summary-list" data-filter-summary-list>
          <button
            v-for="item in filterSummary"
            :key="item.filter"
            class="filter-chip"
            type="button"
            :data-filter-chip="item.filter"
            @click="resetFilter(item.filter)"
          >
            {{ item.label }} ×
          </button>
        </div>
        <button class="filter-summary-clear" type="button" data-filter-summary-clear @click="clearFilters">
          清空
        </button>
      </div>
    </section>

    <section class="gallery" data-gallery-grid data-masonry aria-live="polite" ref="gridEl">
      <div
        v-if="virtualState.topSpacer > 0"
        class="virtual-spacer"
        data-masonry-item
        :style="spacerStyle(virtualState.topSpacer)"
        aria-hidden="true"
      ></div>
      <article
        v-for="image in visibleImages"
        :key="image.uuid || image.detail_path"
        class="illust-card"
        data-image-card
        data-masonry-item
        :data-card-link="image.detail_path"
        :data-collection="image.collection"
        :data-orientation="image.orientation"
        :data-size="image.size_bucket"
        tabindex="0"
        role="link"
        :aria-label="image.title"
      >
        <a class="thumb-link" :href="image.detail_path" :aria-label="image.title">
          <div class="thumb-shell" :style="thumbStyle(image)">
            <img
              class="thumb"
              :src="thumbSrc(image)"
              :alt="image.title"
              loading="lazy"
              :width="image.thumb_width"
              :height="image.thumb_height"
              @error="handleThumbError($event, image)"
            >
          </div>
        </a>
        <div class="card-body">
          <div class="title">{{ image.title }}</div>
          <p v-if="image.description" class="desc">{{ image.description }}</p>
          <div class="meta">
            <span>{{ imageDimensions(image) }}</span>
            <span>{{ image.bytes_human }}</span>
            <span>{{ collectionTitle(image.collection) }}</span>
          </div>
          <div class="tags">
            <span class="tag accent">{{ orientationLabel(image.orientation) }}</span>
            <span class="tag">{{ sizeLabel(image.size_bucket) }}</span>
            <a
              v-for="tag in image.tags.slice(0, 3)"
              :key="tag"
              class="tag ghost"
              :href="tagLink(tag)"
              :style="tagStyle(tag)"
            >
              #{{ tag }}
            </a>
          </div>
        </div>
      </article>
      <article
        v-for="n in skeletonCount"
        :key="`skeleton-${n}`"
        class="illust-card skeleton"
        data-masonry-item
        aria-hidden="true"
      >
        <div class="thumb-shell skeleton-block"></div>
        <div class="card-body">
          <div class="skeleton-line title"></div>
          <div class="skeleton-line"></div>
          <div class="skeleton-line short"></div>
          <div class="skeleton-tags">
            <span class="skeleton-pill"></span>
            <span class="skeleton-pill"></span>
            <span class="skeleton-pill"></span>
          </div>
        </div>
      </article>
      <div
        v-if="virtualState.bottomSpacer > 0"
        class="virtual-spacer"
        data-masonry-item
        :style="spacerStyle(virtualState.bottomSpacer)"
        aria-hidden="true"
      ></div>
      <div ref="loadSentinel" class="load-sentinel" aria-hidden="true"></div>
      <div class="empty" data-empty-state :class="{ show: filteredImages.length === 0 && !isLoading }">
        <span v-if="manifestError">{{ manifestError }}</span>
        <span v-else>当前筛选暂无作品，换个筛选试试。</span>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue';

const props = defineProps({
  bootstrap: {
    type: Object,
    default: () => ({}),
  },
});

const ORIENTATION_LABELS = {
  portrait: '竖屏',
  landscape: '横屏',
  square: '方形',
  unknown: '未标',
};
const SIZE_LABELS = {
  ultra: '超清',
  large: '高清',
  medium: '中等',
  compact: '轻量',
  unknown: '未标',
};
const SUMMARY_LABELS = {
  collection: '分区',
  orientation: '方向',
  size: '清晰度',
};

const CARD_BODY_ESTIMATE = 120;
const FILTER_MIN_RESULTS = 40;
const INITIAL_CHUNKS = 2;
const COLLECTION_PREFETCH = 2;

const rootEl = ref(null);
const gridEl = ref(null);
const loadSentinel = ref(null);
const masonry = ref(null);

const bootstrap = props.bootstrap || {};
const stats = ref(bootstrap.stats || { total: 0, collections: {} });
const collections = ref(bootstrap.collections || []);
const collectionTitles = ref(bootstrap.collection_titles || {});
const topTags = ref(bootstrap.top_tags || []);
const tagSlugMap = ref(bootstrap.tag_slug_map || {});
const tagStyleMap = ref(bootstrap.tag_style_map || {});
const filters = reactive({
  collection: 'all',
  orientation: 'all',
  size: 'all',
});

const manifest = ref(null);
const manifestError = ref('');
const manifestLoading = ref(false);
const loadedChunks = reactive(new Set());
const loadingChunks = reactive(new Set());
const chunkStore = new Map();
const chunkVersion = ref(0);
const nextChunkIndex = ref(0);

const gridMetrics = reactive({
  columns: 1,
  rowGap: 18,
  columnGap: 18,
  columnWidth: 240,
  cardThumbMax: Infinity,
});
const chunkOffsets = ref([]);
const cardBodyEstimate = ref(CARD_BODY_ESTIMATE);
const virtualState = reactive({
  startChunk: 0,
  endChunk: 0,
  topSpacer: 0,
  bottomSpacer: 0,
});

const images = computed(() => {
  chunkVersion.value;
  if (!manifest.value) return [];
  const output = [];
  for (let i = 0; i < manifest.value.chunks.length; i += 1) {
    const items = chunkStore.get(i);
    if (items && items.length) {
      output.push(...items);
    }
  }
  return output;
});

const filteredImages = computed(() => {
  return (images.value || []).filter((image) => {
    const matchCollection = filters.collection === 'all' || image.collection === filters.collection;
    const matchOrientation =
      filters.orientation === 'all' || image.orientation === filters.orientation;
    const matchSize = filters.size === 'all' || image.size_bucket === filters.size;
    return matchCollection && matchOrientation && matchSize;
  });
});

const visibleImages = computed(() => {
  if (!manifest.value || !chunkOffsets.value.length) {
    return filteredImages.value;
  }
  const start = virtualState.startChunk;
  const end = virtualState.endChunk;
  return filteredImages.value.filter((image) => {
    const chunkId = typeof image.__chunk === 'number' ? image.__chunk : 0;
    return chunkId >= start && chunkId <= end;
  });
});

const filterSummary = computed(() => {
  const items = [];
  if (filters.collection !== 'all') {
    const info = collections.value.find((item) => item.slug === filters.collection);
    const label = info ? info.title : filters.collection;
    items.push({ filter: 'collection', label: `${SUMMARY_LABELS.collection}: ${label}` });
  }
  if (filters.orientation !== 'all') {
    const label = ORIENTATION_LABELS[filters.orientation] || filters.orientation;
    items.push({ filter: 'orientation', label: `${SUMMARY_LABELS.orientation}: ${label}` });
  }
  if (filters.size !== 'all') {
    const label = SIZE_LABELS[filters.size] || filters.size;
    items.push({ filter: 'size', label: `${SUMMARY_LABELS.size}: ${label}` });
  }
  return items;
});

const isLoading = computed(() => manifestLoading.value || loadingChunks.size > 0);
const hasMoreChunks = computed(() => {
  if (!manifest.value) return false;
  return nextChunkIndex.value < manifest.value.chunks.length;
});
const skeletonCount = computed(() => {
  if (!isLoading.value) return 0;
  const columns = Math.max(1, gridMetrics.columns);
  return Math.min(18, Math.max(6, columns * 3));
});

function scheduleLayoutRefresh() {
  nextTick(() => {
    if (masonry.value) {
      masonry.value.refresh();
    }
    if (window.GalleryCardLinks && rootEl.value) {
      window.GalleryCardLinks.init(rootEl.value.querySelectorAll('[data-card-link]'));
    }
    window.requestAnimationFrame(updateCardBodyEstimate);
  });
}

function parsePx(value) {
  const parsed = parseFloat(value);
  return Number.isNaN(parsed) ? 0 : parsed;
}

function parseMinMaxTemplate(template) {
  if (!template) return null;
  const match = template.match(/minmax\((\d+\.?\d*)px,\s*([^)]+)\)/);
  if (!match) return null;
  const minWidth = parseFloat(match[1]);
  const maxRaw = match[2].trim();
  const maxWidth = maxRaw.endsWith('px') ? parseFloat(maxRaw) : Infinity;
  return { minWidth, maxWidth };
}

function readGridMetrics() {
  if (!gridEl.value) return;
  const style = window.getComputedStyle(gridEl.value);
  gridMetrics.rowGap = parsePx(style.rowGap || style.gridRowGap || '0');
  gridMetrics.columnGap = parsePx(style.columnGap || style.gridColumnGap || '0');
  const template = style.gridTemplateColumns || '';
  const gridWidth = gridEl.value.clientWidth || gridEl.value.getBoundingClientRect().width || 0;
  const minmaxInfo = parseMinMaxTemplate(template);
  const minmaxCount = (template.match(/minmax\(/g) || []).length;
  const pxColumns = template.match(/\d+\.?\d*px/g) || [];
  // gridTemplateColumns may stay in repeat/minmax form; infer columns to keep offsets accurate.
  if (minmaxInfo) {
    let columns = 1;
    if (template.includes('auto-fill') || template.includes('auto-fit')) {
      columns = Math.max(
        1,
        Math.floor((gridWidth + gridMetrics.columnGap) / (minmaxInfo.minWidth + gridMetrics.columnGap))
      );
    } else if (minmaxCount) {
      columns = Math.max(1, minmaxCount);
    }
    const rawWidth =
      columns > 0 && gridWidth > 0
        ? (gridWidth - gridMetrics.columnGap * (columns - 1)) / columns
        : minmaxInfo.minWidth || 240;
    const columnWidth = Math.min(
      minmaxInfo.maxWidth,
      Math.max(minmaxInfo.minWidth || 0, rawWidth)
    );
    gridMetrics.columns = columns;
    gridMetrics.columnWidth = columnWidth;
  } else if (pxColumns.length) {
    const total = pxColumns.reduce((sum, item) => sum + parseFloat(item), 0);
    gridMetrics.columns = Math.max(1, pxColumns.length || 1);
    gridMetrics.columnWidth = total / pxColumns.length;
  } else {
    gridMetrics.columns = 1;
    gridMetrics.columnWidth = gridWidth || 240;
  }
  const thumbMax = style.getPropertyValue('--card-thumb-max').trim();
  if (!thumbMax || thumbMax === 'none') {
    gridMetrics.cardThumbMax = Infinity;
  } else {
    gridMetrics.cardThumbMax = parsePx(thumbMax) || Infinity;
  }
}

function estimateItemHeight(image) {
  const width = image.thumb_width || image.width || 1;
  const height = image.thumb_height || image.height || 1;
  const ratio = height / width;
  const thumbHeight = Math.min(gridMetrics.columnWidth * ratio, gridMetrics.cardThumbMax);
  return thumbHeight + cardBodyEstimate.value;
}

function updateCardBodyEstimate() {
  if (!gridEl.value) return;
  const cards = Array.from(gridEl.value.querySelectorAll('[data-image-card]'));
  if (!cards.length) return;
  const rects = [];
  let total = 0;
  let count = 0;
  cards.forEach((card) => {
    const cardRect = card.getBoundingClientRect();
    rects.push({ top: cardRect.top, width: cardRect.width });
    const thumb = card.querySelector('.thumb-shell');
    if (!thumb) return;
    const thumbRect = thumb.getBoundingClientRect();
    const bodyHeight = cardRect.height - thumbRect.height;
    if (!Number.isFinite(bodyHeight) || bodyHeight <= 0) return;
    total += bodyHeight;
    count += 1;
  });
  if (!count) return;
  const average = total / count;
  const clamped = Math.max(64, Math.min(220, average));
  const blended = cardBodyEstimate.value * 0.7 + clamped * 0.3;
  if (Math.abs(blended - cardBodyEstimate.value) >= 3) {
    cardBodyEstimate.value = blended;
    scheduleVirtualRecalc();
  }
  updateGridMetricsFromRects(rects);
}

function updateGridMetricsFromRects(rects) {
  if (!rects || rects.length < 6) return;
  let minTop = rects[0].top;
  rects.forEach((rect) => {
    if (rect.top < minTop) minTop = rect.top;
  });
  const tolerance = 2;
  const firstRow = rects.filter((rect) => Math.abs(rect.top - minTop) <= tolerance && rect.width > 0);
  if (firstRow.length < 2) return;
  if (rects.length < firstRow.length * 2) return;
  const totalWidth = firstRow.reduce((sum, rect) => sum + rect.width, 0);
  const averageWidth = totalWidth / firstRow.length;
  let changed = false;
  if (gridMetrics.columns !== firstRow.length) {
    gridMetrics.columns = firstRow.length;
    changed = true;
  }
  if (Math.abs(gridMetrics.columnWidth - averageWidth) > 1) {
    gridMetrics.columnWidth = averageWidth;
    changed = true;
  }
  if (changed) {
    scheduleVirtualRecalc();
  }
}

function computeChunkOffsets() {
  if (!manifest.value) {
    chunkOffsets.value = [];
    return;
  }
  const maxLoaded = maxLoadedChunk();
  if (maxLoaded < 0) {
    chunkOffsets.value = [];
    return;
  }
  const totalChunks = Math.max(1, maxLoaded + 1);
  const columnCount = Math.max(1, gridMetrics.columns);
  const rowGap = gridMetrics.rowGap || 0;
  const columnHeights = new Array(columnCount).fill(0);
  const offsets = new Array(totalChunks).fill(0);
  const imagesByChunk = new Map();
  filteredImages.value.forEach((image) => {
    const chunkId = typeof image.__chunk === 'number' ? image.__chunk : 0;
    if (!imagesByChunk.has(chunkId)) {
      imagesByChunk.set(chunkId, []);
    }
    imagesByChunk.get(chunkId).push(image);
  });
  for (let chunk = 0; chunk < totalChunks; chunk += 1) {
    const items = imagesByChunk.get(chunk) || [];
    for (const image of items) {
      let targetIndex = 0;
      let minHeight = columnHeights[0];
      for (let i = 1; i < columnHeights.length; i += 1) {
        if (columnHeights[i] < minHeight) {
          minHeight = columnHeights[i];
          targetIndex = i;
        }
      }
      columnHeights[targetIndex] += estimateItemHeight(image) + rowGap;
    }
    offsets[chunk] = Math.max(...columnHeights);
  }
  chunkOffsets.value = offsets;
}

function maxLoadedChunk() {
  let max = -1;
  loadedChunks.forEach((idx) => {
    if (idx > max) max = idx;
  });
  return max;
}

function maybePrefetchNext(viewBottom) {
  if (!manifest.value || !hasMoreChunks.value) return;
  const offsets = chunkOffsets.value;
  if (!offsets.length) return;
  const maxLoaded = maxLoadedChunk();
  if (maxLoaded < 0) return;
  const loadedBottom = offsets[maxLoaded] || 0;
  if (!loadedBottom) return;
  const threshold = window.innerHeight * 0.8;
  if (viewBottom + threshold >= loadedBottom) {
    loadNextChunk();
  }
}

function updateVirtualWindow() {
  const offsets = chunkOffsets.value;
  if (!offsets.length || !gridEl.value) {
    virtualState.startChunk = 0;
    virtualState.endChunk = offsets.length ? offsets.length - 1 : 0;
    virtualState.topSpacer = 0;
    virtualState.bottomSpacer = 0;
    return;
  }
  const gridTop = gridEl.value.getBoundingClientRect().top + window.scrollY;
  const viewTop = Math.max(0, window.scrollY - gridTop);
  const viewBottom = viewTop + window.innerHeight;
  const buffer = window.innerHeight * 1.5;
  const targetTop = Math.max(0, viewTop - buffer);
  const targetBottom = viewBottom + buffer;
  const maxLoaded = Math.max(0, maxLoadedChunk());
  let startChunk = 0;
  while (startChunk < offsets.length && offsets[startChunk] < targetTop) {
    startChunk += 1;
  }
  if (startChunk >= offsets.length) startChunk = offsets.length - 1;
  let endChunk = startChunk;
  while (endChunk < offsets.length && offsets[endChunk] < targetBottom) {
    endChunk += 1;
  }
  if (endChunk >= offsets.length) endChunk = offsets.length - 1;
  if (endChunk < startChunk) endChunk = startChunk;
  if (startChunk > maxLoaded) startChunk = maxLoaded;
  if (endChunk > maxLoaded) endChunk = maxLoaded;
  virtualState.startChunk = startChunk;
  virtualState.endChunk = endChunk;
  const totalHeight = offsets[offsets.length - 1] || 0;
  const topHeight = startChunk > 0 ? offsets[startChunk - 1] : 0;
  const bottomHeight = totalHeight - offsets[endChunk];
  virtualState.topSpacer = Math.max(0, topHeight);
  virtualState.bottomSpacer = Math.max(0, bottomHeight);
  maybePrefetchNext(viewBottom);
}

let virtualRecalcFrame = 0;
let virtualScrollFrame = 0;
function scheduleVirtualRecalc() {
  if (virtualRecalcFrame) return;
  virtualRecalcFrame = window.requestAnimationFrame(() => {
    virtualRecalcFrame = 0;
    computeChunkOffsets();
    updateVirtualWindow();
  });
}

function scheduleVirtualScroll() {
  if (virtualScrollFrame) return;
  virtualScrollFrame = window.requestAnimationFrame(() => {
    virtualScrollFrame = 0;
    updateVirtualWindow();
  });
}

function updateNextChunkIndex() {
  if (!manifest.value) return;
  let idx = nextChunkIndex.value;
  while (idx < manifest.value.chunks.length && loadedChunks.has(idx)) {
    idx += 1;
  }
  nextChunkIndex.value = idx;
}

let loadQueue = Promise.resolve();
function enqueueChunkLoad(index) {
  loadQueue = loadQueue.then(() => loadChunk(index));
  return loadQueue;
}

function resolveChunkUrl(path) {
  if (!manifest.value) return path;
  if (!path) return '';
  if (path.startsWith('http') || path.startsWith('/')) return path;
  const base = manifest.value.base_path || '/static/data/';
  if (base.endsWith('/')) return `${base}${path}`;
  return `${base}/${path}`;
}

async function loadChunk(index) {
  if (!manifest.value) return;
  if (loadedChunks.has(index) || loadingChunks.has(index)) return;
  const chunk = manifest.value.chunks[index];
  if (!chunk) return;
  const url = resolveChunkUrl(chunk.path);
  if (!url) return;
  loadingChunks.add(index);
  try {
    const resp = await fetch(url, { cache: 'force-cache' });
    if (!resp.ok) {
      throw new Error(`chunk ${index} fetch failed`);
    }
    const data = await resp.json();
    const chunkImages = Array.isArray(data.images) ? data.images : [];
    chunkImages.forEach((image) => {
      image.__chunk = index;
    });
    chunkStore.set(index, chunkImages);
    loadedChunks.add(index);
    chunkVersion.value += 1;
    updateNextChunkIndex();
    scheduleVirtualRecalc();
  } catch (err) {
    manifestError.value = '首页分片加载失败';
  } finally {
    loadingChunks.delete(index);
  }
}

async function loadManifest() {
  if (manifest.value || manifestLoading.value) return;
  manifestLoading.value = true;
  try {
    const url = bootstrap.manifest_path || '/static/data/home_manifest.json';
    const resp = await fetch(url, { cache: 'force-cache' });
    if (!resp.ok) {
      throw new Error('manifest fetch failed');
    }
    const data = await resp.json();
    manifest.value = data;
    nextChunkIndex.value = 0;
  } catch (err) {
    manifestError.value = '首页索引加载失败';
  } finally {
    manifestLoading.value = false;
  }
}

async function preloadCollectionChunks(collection) {
  if (!manifest.value || !collection || collection === 'all') return;
  const indexMap = manifest.value.collection_index || {};
  const chunkList = Array.isArray(indexMap[collection]) ? indexMap[collection] : [];
  const targets = chunkList.filter((chunk) => !loadedChunks.has(chunk)).slice(0, COLLECTION_PREFETCH);
  for (const chunkId of targets) {
    await enqueueChunkLoad(chunkId);
  }
}

async function loadInitialChunks() {
  if (!manifest.value) return;
  const count = Math.min(INITIAL_CHUNKS, manifest.value.chunks.length);
  for (let i = 0; i < count; i += 1) {
    await enqueueChunkLoad(i);
  }
}

async function loadNextChunk() {
  if (!manifest.value) return;
  if (!hasMoreChunks.value) return;
  const index = nextChunkIndex.value;
  await enqueueChunkLoad(index);
}

let filterToken = 0;
async function ensureFilteredResults() {
  if (!manifest.value) return;
  const filtering =
    filters.collection !== 'all' || filters.orientation !== 'all' || filters.size !== 'all';
  if (!filtering) return;
  const token = (filterToken += 1);
  await preloadCollectionChunks(filters.collection);
  while (filteredImages.value.length < FILTER_MIN_RESULTS && hasMoreChunks.value) {
    if (token !== filterToken) return;
    await loadNextChunk();
  }
}

function setupMasonry() {
  if (rootEl.value) {
    const grid = rootEl.value.querySelector('[data-gallery-grid]');
    if (window.GalleryMasonry && grid) {
      masonry.value = window.GalleryMasonry.init(grid);
    }
  }
}

function setCollection(value) {
  filters.collection = value || 'all';
}

function setFilter(filter, value) {
  if (!filter) return;
  filters[filter] = value || 'all';
}

function resetFilter(filter) {
  if (!filter) return;
  if (filter === 'collection') {
    filters.collection = 'all';
    return;
  }
  if (filter === 'orientation') {
    filters.orientation = 'all';
    return;
  }
  if (filter === 'size') {
    filters.size = 'all';
  }
}

function clearFilters() {
  filters.collection = 'all';
  filters.orientation = 'all';
  filters.size = 'all';
}

function orientationLabel(value) {
  return ORIENTATION_LABELS[value] || ORIENTATION_LABELS.unknown;
}

function sizeLabel(value) {
  return SIZE_LABELS[value] || SIZE_LABELS.unknown;
}

function imageDimensions(image) {
  const width = image.width || '?';
  const height = image.height || '?';
  return `${width}×${height}`;
}

function collectionTitle(slug) {
  if (!slug) return '';
  return collectionTitles.value[slug] || slug;
}

function tagLink(tag) {
  const slug = tagSlugMap.value[tag] || tag;
  return `/tags/${encodeURIComponent(slug)}/`;
}

function tagStyle(tag) {
  return tagStyleMap.value[tag] || '';
}

function thumbSrc(image) {
  if (!image.thumb_filename) return '';
  return `/thumb/${image.thumb_filename}`;
}

function thumbStyle(image) {
  const width = image.thumb_width || image.width || 1;
  const height = image.thumb_height || image.height || 1;
  return { '--thumb-ratio': `${width}/${height}` };
}

function handleThumbError(event, image) {
  const target = event ? event.target : null;
  if (!target || !image || !image.raw_filename) return;
  if (target.dataset && target.dataset.fallbackApplied) return;
  if (target.dataset) target.dataset.fallbackApplied = '1';
  target.src = `/raw/${image.raw_filename}`;
}

function spacerStyle(height) {
  return { '--virtual-height': `${Math.max(0, Math.round(height))}px` };
}

let scrollHandler = null;
let resizeHandler = null;
let sentinelObserver = null;

onMounted(async () => {
  setupMasonry();
  readGridMetrics();
  scheduleVirtualRecalc();
  await loadManifest();
  await loadInitialChunks();
  scheduleLayoutRefresh();
  scheduleVirtualRecalc();

  scrollHandler = () => scheduleVirtualScroll();
  resizeHandler = () => {
    readGridMetrics();
    scheduleVirtualRecalc();
  };
  window.addEventListener('scroll', scrollHandler, { passive: true });
  window.addEventListener('resize', resizeHandler, { passive: true });

  if (loadSentinel.value) {
    sentinelObserver = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          loadNextChunk();
        }
      },
      { rootMargin: '1200px 0px' }
    );
    sentinelObserver.observe(loadSentinel.value);
  }
});

onBeforeUnmount(() => {
  if (scrollHandler) window.removeEventListener('scroll', scrollHandler);
  if (resizeHandler) window.removeEventListener('resize', resizeHandler);
  if (sentinelObserver) sentinelObserver.disconnect();
});

watch(filteredImages, () => {
  scheduleVirtualRecalc();
});

watch(
  () => ({ ...filters }),
  () => {
    ensureFilteredResults();
    scheduleVirtualRecalc();
  },
  { deep: true }
);

watch(visibleImages, () => {
  scheduleLayoutRefresh();
});
</script>
