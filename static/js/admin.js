(function () {
  const loginSection = document.querySelector("[data-admin-login]");
  const panel = document.querySelector("[data-admin-panel]");
  const loginForm = document.querySelector("[data-admin-login-form]");
  const loginError = document.querySelector("[data-admin-login-error]");
  const logoutBtn = document.querySelector("[data-admin-logout]");
  const adminAvatarMenu = document.querySelector("[data-user-avatar]");
  const statusBar = document.querySelector("[data-admin-status-bar]");
  const statusFields = document.querySelectorAll("[data-admin-status]");
  const statusFlags = document.querySelectorAll("[data-admin-status-flag]");
  const adminUserLabel = document.querySelector("[data-admin-user]");

  function showLogin(message) {
    if (panel) panel.hidden = true;
    if (loginSection) loginSection.hidden = false;
    if (loginError) loginError.textContent = message || "";
    if (logoutBtn) logoutBtn.hidden = true;
  }

  function showPanel() {
    if (loginSection) loginSection.hidden = true;
    if (panel) panel.hidden = false;
    if (loginError) loginError.textContent = "";
    if (logoutBtn) logoutBtn.hidden = false;
    if (adminAvatarMenu) adminAvatarMenu.hidden = false;
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

  const sleep = (ms) => new Promise((resolve) => window.setTimeout(resolve, ms));

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
      if (adminUserLabel) adminUserLabel.textContent = currentAdminUser || "—";
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
  const trashPageBtn = document.querySelector("[data-admin-trash-page]");
  const trashAllBtn = document.querySelector("[data-admin-trash-all]");
  const trashHint = document.querySelector("[data-admin-trash-hint]");
  const queryInput = document.querySelector("[data-admin-query]");
  const collectionFilter = document.querySelector("[data-admin-collection-filter]");
  const paginations = document.querySelectorAll(
    "[data-admin-pagination], [data-admin-pagination-top]"
  );
  const pagePrevBtns = document.querySelectorAll("[data-admin-page-prev]");
  const pageNextBtns = document.querySelectorAll("[data-admin-page-next]");
  const pageLists = document.querySelectorAll("[data-admin-page-list]");
  const pageSummaries = document.querySelectorAll("[data-admin-page-summary]");
  const pageInputs = document.querySelectorAll("[data-admin-page-input]");
  const pageJumpBtns = document.querySelectorAll("[data-admin-page-jump]");
  const collectionList = document.querySelector("[data-admin-collection-list]");
  const addCollectionBtn = document.querySelector("[data-admin-add-collection]");
  const saveCollectionsBtn = document.querySelector("[data-admin-save-collections]");
  const collectionsHint = document.querySelector("[data-admin-collections-hint]");
  const defaultCollectionSelect = document.querySelector("[data-admin-default-collection]");
  const authModeSelect = document.querySelector("[data-admin-auth-mode]");
  const authSaveBtn = document.querySelector("[data-admin-auth-save]");
  const authHint = document.querySelector("[data-admin-auth-hint]");
  const inviteList = document.querySelector("[data-admin-invite-list]");
  const inviteHint = document.querySelector("[data-admin-invite-hint]");
  const inviteNoteInput = document.querySelector("[data-admin-invite-note]");
  const inviteExpiresAtInput = document.querySelector("[data-admin-invite-expires-at]");
  const inviteExpiresDaysInput = document.querySelector("[data-admin-invite-expires-days]");
  const inviteLimitToggle = document.querySelector("[data-admin-invite-limit]");
  const inviteMaxUsesInput = document.querySelector("[data-admin-invite-max-uses]");
  const inviteCreateBtn = document.querySelector("[data-admin-invite-create]");
  const inviteRefreshBtn = document.querySelector("[data-admin-invite-refresh]");
  const inviteCreatedWrap = document.querySelector("[data-admin-invite-created]");
  const inviteCreatedCode = document.querySelector("[data-admin-invite-code]");
  const inviteArchive = document.querySelector("[data-admin-invite-archive]");
  const inviteArchiveToggle = document.querySelector("[data-admin-invite-archive-toggle]");
  const inviteArchiveList = document.querySelector("[data-admin-invite-archive-list]");
  const inviteArchiveCount = document.querySelector("[data-admin-invite-archive-count]");
  const inviteDialog = document.querySelector("[data-admin-invite-dialog]");
  const inviteDialogDisable = document.querySelector("[data-admin-invite-dialog-disable]");
  const inviteDialogDelete = document.querySelector("[data-admin-invite-dialog-delete]");
  const inviteDialogCancel = document.querySelector("[data-admin-invite-dialog-cancel]");
  const inviteDialogDesc = document.querySelector("[data-admin-invite-dialog-desc]");
  const inviteDialogCloseBtns = document.querySelectorAll("[data-admin-invite-dialog-close]");
  const uploadForm = document.querySelector("[data-admin-upload-form]");
  const uploadCollection = document.querySelector("[data-admin-upload-collection]");
  const uploadHint = document.querySelector("[data-admin-upload-hint]");
  const stressToggle = document.querySelector("[data-admin-stress-toggle]");
  const stressCountInput = document.querySelector("[data-admin-stress-count]");
  const stressGenerateBtn = document.querySelector("[data-admin-stress-generate]");
  const stressStopBtn = document.querySelector("[data-admin-stress-stop]");
  const stressRetryBtn = document.querySelector("[data-admin-stress-retry]");
  const stressDeleteBtn = document.querySelector("[data-admin-stress-delete]");
  const stressHint = document.querySelector("[data-admin-stress-hint]");
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
  const dmcaList = document.querySelector("[data-admin-dmca-list]");
  const dmcaEmpty = document.querySelector("[data-admin-dmca-empty]");
  const dmcaHint = document.querySelector("[data-admin-dmca-hint]");
  const dmcaRefreshBtn = document.querySelector("[data-admin-dmca-refresh]");
  const dmcaFilter = document.querySelector("[data-admin-dmca-filter]");
  const dmcaPagination = document.querySelector("[data-admin-dmca-pagination]");
  const dmcaPagePrevBtn = document.querySelector("[data-admin-dmca-page-prev]");
  const dmcaPageNextBtn = document.querySelector("[data-admin-dmca-page-next]");
  const dmcaPageInfo = document.querySelector("[data-admin-dmca-page-info]");
  const dmcaPendingNode = document.querySelector("[data-admin-dmca-pending]");
  const masonry =
    grid && grid.hasAttribute("data-masonry") && window.GalleryMasonry
      ? window.GalleryMasonry.init(grid)
      : null;

  let images = [];
  let collections = [];
  let defaultCollection = "";
  let showTrash = false;
  let trashBusy = false;
  let currentPage = 1;
  let totalPages = 1;
  let totalItems = 0;
  const PAGE_SIZE = 40;
  const filterState = {
    query: "",
    collection: "all",
  };
  let currentAdminUser = "";
  let inviteArchiveOpen = false;
  let inviteArchiveCountValue = 0;
  let inviteDialogInviteId = null;
  let inviteDialogMode = "choice";
  let dmcaPage = 1;
  let dmcaPages = 1;
  let dmcaTotal = 0;
  const DMCA_PAGE_SIZE = 20;
  let dmcaSummaryTimer = null;
  let dmcaListTimer = null;

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

  function getStatusValue(status, path) {
    if (!status || !path) return null;
    return path.split(".").reduce((acc, key) => (acc && key in acc ? acc[key] : null), status);
  }

  function formatNumber(value) {
    if (!Number.isFinite(value)) return "-";
    return new Intl.NumberFormat("zh-CN").format(value);
  }

  function formatBytes(value) {
    if (!Number.isFinite(value)) return "-";
    const units = ["B", "KB", "MB", "GB", "TB"];
    let size = value;
    let unitIndex = 0;
    while (size >= 1024 && unitIndex < units.length - 1) {
      size /= 1024;
      unitIndex += 1;
    }
    const digits = unitIndex === 0 ? 0 : 1;
    return `${size.toFixed(digits)}${units[unitIndex]}`;
  }

  function formatDatetime(value) {
    if (!value) return "-";
    const text = String(value).trim();
    if (!text) return "-";
    if (text.includes("T")) {
      return text.replace("T", " ").replace(/\+\d{2}:\d{2}$/, "");
    }
    return text;
  }

  function formatDisk(disk) {
    if (!disk || !Number.isFinite(disk.total) || disk.total === 0) return "-";
    let free = Number.isFinite(disk.free) ? disk.free : null;
    if (free === null && Number.isFinite(disk.used)) {
      free = Math.max(disk.total - disk.used, 0);
    }
    if (!Number.isFinite(free)) return "-";
    const pct = Math.round((free / disk.total) * 100);
    return `剩余 ${formatBytes(free)} / ${formatBytes(disk.total)} (${pct}%)`;
  }

  function formatMemory(memory) {
    if (!memory || !Number.isFinite(memory.total) || memory.total === 0) return "-";
    const available = Number.isFinite(memory.available) ? memory.available : null;
    let used = Number.isFinite(memory.used) ? memory.used : null;
    if (used === null && available !== null) {
      used = Math.max(memory.total - available, 0);
    }
    if (!Number.isFinite(used)) return "-";
    const pct = Math.round((used / memory.total) * 100);
    return `已用 ${formatBytes(used)} / ${formatBytes(memory.total)} (${pct}%)`;
  }

  function formatLoad(load) {
    if (!Array.isArray(load)) return "-";
    return load.map((item) => Number(item).toFixed(2)).join(" / ");
  }

  function formatDays(value) {
    if (!Number.isFinite(value)) return "-";
    return `${value.toFixed(1)} 天`;
  }

  function formatDmcaStatus(status) {
    const value = String(status || "pending").toLowerCase();
    if (value === "approved") return { label: "已通过", className: "is-approved" };
    if (value === "rejected") return { label: "已拒绝", className: "is-rejected" };
    return { label: "待处理", className: "is-pending" };
  }

  function formatDmcaTicket(id) {
    const num = Number(id);
    if (!Number.isFinite(num)) return "DMCA";
    return `DMCA-${String(num).padStart(6, "0")}`;
  }

  function formatDmcaSummary(summary) {
    if (!summary) return "待处理 -";
    const pending = Number(summary.pending || 0);
    const today = Number(summary.today || 0);
    if (Number.isFinite(today) && today > 0) {
      return `待处理 ${pending} · 今日 ${today}`;
    }
    return `待处理 ${pending}`;
  }

  function applyStatusData(status) {
    statusFields.forEach((node) => {
      const key = node.dataset.adminStatus || "";
      const format = node.dataset.adminStatusFormat || "auto";
      let value = getStatusValue(status, key);
      let text = "-";
      if (format === "number") {
        text = formatNumber(Number(value));
      } else if (format === "bytes") {
        text = formatBytes(Number(value));
      } else if (format === "disk") {
        text = formatDisk(value);
      } else if (format === "memory") {
        text = formatMemory(value);
      } else if (format === "load") {
        text = formatLoad(value);
      } else if (format === "datetime") {
        text = formatDatetime(value);
      } else if (format === "days") {
        text = formatDays(Number(value));
      } else if (value !== null && value !== undefined) {
        text = String(value);
      }
      node.textContent = text;
    });

    if (statusFlags.length) {
      const paused = Boolean(status?.upload_paused || status?.disk?.paused);
      statusFlags.forEach((flag) => {
        const valueNode = flag.querySelector("[data-admin-status-flag-value]");
        if (valueNode) valueNode.textContent = paused ? "暂停" : "正常";
        flag.classList.toggle("is-alert", paused);
      });
    }
  }

  async function loadAdminStatus() {
    if (!statusFields.length) return;
    if (statusBar) statusBar.classList.add("is-loading");
    try {
      const resp = await fetch(`/static/status.json?v=${Date.now()}`, { cache: "no-store" });
      if (!resp.ok) throw new Error("状态读取失败");
      const data = await resp.json();
      applyStatusData(data);
    } catch (err) {
      if (statusBar) statusBar.classList.add("is-error");
    } finally {
      if (statusBar) statusBar.classList.remove("is-loading");
    }
  }

  async function loadDmcaSummary() {
    if (!dmcaPendingNode) return;
    try {
      const data = await fetchJSON("/upload/admin/dmca/summary");
      dmcaPendingNode.textContent = formatDmcaSummary(data);
    } catch (err) {
      dmcaPendingNode.textContent = "待处理 -";
    }
  }

  function renderDmcaItem(item) {
    const statusInfo = formatDmcaStatus(item.status);
    const title = formatDmcaTicket(item.id);
    const authorityLabel = item.authority === "owner" ? "版权所有者" : "授权代表";
    const createdAt = formatDatetime(item.created_at);
    const processedAt = formatDatetime(item.processed_at);
    const hasProcessed = Boolean(item.processed_at || item.processed_by || item.status_note);
    const processedText = hasProcessed
      ? `处理人：${escapeHtml(item.processed_by || "—")} · 时间：${processedAt}`
      : "尚未处理";
    const disabled = String(item.status || "").toLowerCase() !== "pending";
    const workUrl = escapeHtml(item.work_url || "");
    const sourceUrl = escapeHtml(item.source_url || "");
    const noteValue = escapeHtml(item.status_note || "");
    const authorityNote = escapeHtml(item.authority_note || "—");
    const contact = escapeHtml(item.contact || "—");
    const region = escapeHtml(item.region || "—");
    const claim = escapeHtml(item.claim || "");
    const evidence = escapeHtml(item.evidence || "");
    const fullName = escapeHtml(item.full_name || "");
    const email = escapeHtml(item.email || "");
    const ip = escapeHtml(item.ip || "—");
    const userAgent = escapeHtml(item.user_agent || "—");

    return `
      <details class="dmca-request-card" data-dmca-id="${item.id}">
        <summary class="dmca-request-summary">
          <div>
            <div class="dmca-request-title">${title}</div>
            <div class="dmca-request-meta">
              <span>${fullName}</span>
              <span>${email}</span>
              <span>${createdAt}</span>
            </div>
          </div>
          <span class="dmca-status-chip ${statusInfo.className}">${statusInfo.label}</span>
        </summary>
        <div class="dmca-request-body">
          <div class="dmca-request-grid">
            <div class="dmca-request-section">
              <div class="dmca-request-label">作品链接</div>
              <p class="dmca-request-text"><a href="${workUrl}" target="_blank" rel="noreferrer">${workUrl}</a></p>
            </div>
            <div class="dmca-request-section">
              <div class="dmca-request-label">原始来源</div>
              <p class="dmca-request-text"><a href="${sourceUrl}" target="_blank" rel="noreferrer">${sourceUrl}</a></p>
            </div>
            <div class="dmca-request-section">
              <div class="dmca-request-label">身份</div>
              <p class="dmca-request-text">${authorityLabel} · 授权说明：${authorityNote}</p>
            </div>
            <div class="dmca-request-section">
              <div class="dmca-request-label">联系信息</div>
              <p class="dmca-request-text">地区：${region} · 联系方式：${contact}</p>
            </div>
          </div>
          <div class="dmca-request-section">
            <div class="dmca-request-label">侵权说明</div>
            <p class="dmca-request-text">${claim}</p>
          </div>
          <div class="dmca-request-section">
            <div class="dmca-request-label">证明材料</div>
            <p class="dmca-request-text">${evidence}</p>
          </div>
          <div class="dmca-request-actions">
            <textarea class="admin-textarea dmca-request-note" data-dmca-note placeholder="处理备注（可选）" ${
              disabled ? "disabled" : ""
            }>${noteValue}</textarea>
            <div class="admin-actions-row">
              <button class="btn primary" type="button" data-dmca-action="approve" ${
                disabled ? "disabled" : ""
              }>通过</button>
              <button class="btn ghost danger" type="button" data-dmca-action="reject" ${
                disabled ? "disabled" : ""
              }>拒绝</button>
              <span class="hint" data-dmca-action-hint>${processedText}</span>
            </div>
            <div class="dmca-request-foot">提交 IP：${ip} · UA：${userAgent}</div>
          </div>
        </div>
      </details>
    `;
  }

  function updateDmcaPagination() {
    if (!dmcaPagination || !dmcaPageInfo) return;
    dmcaPagination.hidden = dmcaPages <= 1;
    dmcaPagePrevBtn && (dmcaPagePrevBtn.disabled = dmcaPage <= 1);
    dmcaPageNextBtn && (dmcaPageNextBtn.disabled = dmcaPage >= dmcaPages);
    dmcaPageInfo.textContent = `共 ${dmcaPages} 页 / 共 ${dmcaTotal} 条`;
  }

  async function loadDmcaList(page = 1) {
    if (!dmcaList) return;
    if (dmcaHint) dmcaHint.textContent = "加载中...";
    const status = dmcaFilter ? dmcaFilter.value : "pending";
    try {
      const params = new URLSearchParams({
        status,
        page: String(page),
        page_size: String(DMCA_PAGE_SIZE),
      });
      const data = await fetchJSON(`/upload/admin/dmca?${params.toString()}`);
      dmcaPage = data.page || 1;
      dmcaPages = data.pages || 1;
      dmcaTotal = data.total || 0;
      const items = Array.isArray(data.items) ? data.items : [];
      dmcaList.innerHTML = items.map(renderDmcaItem).join("");
      if (dmcaEmpty) dmcaEmpty.hidden = items.length > 0;
      updateDmcaPagination();
      if (dmcaHint) dmcaHint.textContent = items.length ? "已加载最新申请" : "暂无申请记录";
    } catch (err) {
      if (dmcaHint) dmcaHint.textContent = err.message;
      if (dmcaEmpty) dmcaEmpty.hidden = false;
    }
  }

  async function updateDmcaStatus(requestId, status, note, hintNode) {
    if (!requestId) return;
    if (hintNode) hintNode.textContent = "提交中...";
    try {
      await fetchJSON(`/upload/admin/dmca/${requestId}/status`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status, note }),
      });
      if (hintNode) hintNode.textContent = "已更新";
      await loadDmcaList(dmcaPage);
      await loadDmcaSummary();
    } catch (err) {
      if (hintNode) hintNode.textContent = err.message;
    }
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
    collectionFilter.value = filterState.collection || "all";
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

  function readUrlState() {
    const params = new URLSearchParams(window.location.search);
    const pageRaw = parseInt(params.get("p") || "1", 10);
    currentPage = Number.isFinite(pageRaw) && pageRaw > 0 ? pageRaw : 1;
    filterState.query = params.get("q") || "";
    filterState.collection = params.get("collection") || "all";
    showTrash = (params.get("status") || "").toLowerCase() === "trash";
    if (queryInput) queryInput.value = filterState.query;
  }

  function buildQueryParams(page) {
    const params = new URLSearchParams();
    params.set("p", String(page || 1));
    params.set("status", showTrash ? "trash" : "active");
    if (filterState.query) {
      params.set("q", filterState.query);
    }
    if (filterState.collection && filterState.collection !== "all") {
      params.set("collection", filterState.collection);
    }
    return params;
  }

  function syncUrl(page) {
    const params = buildQueryParams(page);
    const next = `${window.location.pathname}?${params.toString()}`;
    window.history.replaceState(null, "", next);
  }

  function setTrashHint(message) {
    if (!trashHint) return;
    trashHint.textContent = message || "";
    syncTrashActions();
  }

  function syncTrashActions() {
    const isTrash = showTrash;
    const hasItems = Array.isArray(images) && images.length > 0;
    if (trashPageBtn) {
      trashPageBtn.hidden = !isTrash;
      trashPageBtn.disabled = !isTrash || trashBusy || !hasItems;
    }
    if (trashAllBtn) {
      trashAllBtn.hidden = !isTrash;
      trashAllBtn.disabled = !isTrash || trashBusy;
    }
    if (trashHint) {
      trashHint.hidden = !isTrash || !trashHint.textContent;
    }
  }

  async function purgeTrash(uuids, resetPage) {
    if (trashBusy) return;
    const payload = {};
    if (Array.isArray(uuids)) {
      payload.uuids = uuids;
    }
    trashBusy = true;
    syncTrashActions();
    setTrashHint("删除中...");
    try {
      await fetchJSON("/upload/admin/images/trash/purge", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      currentPage = resetPage ? 1 : currentPage;
      await loadImages(currentPage);
      setTrashHint("已删除");
    } catch (err) {
      setTrashHint(err.message);
    } finally {
      trashBusy = false;
      syncTrashActions();
    }
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
        const showEditor = !showTrash;
        const editorHtml = showEditor
          ? `
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
          `
          : "";
        return `
        <article class="illust-card admin-card" data-admin-uuid="${escapeHtml(
          img.uuid
        )}" data-masonry-item>
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
          ${editorHtml}
        </article>
        `;
      })
      .join("");

    if (!showTrash) {
      initTagSuggest(grid);
      initTagEditors(grid);
    }

    grid.querySelectorAll("[data-admin-uuid]").forEach((card) => {
      const uuid = card.dataset.adminUuid;
      const img = list.find((item) => item.uuid === uuid);
      const select = card.querySelector("[data-field='collection']");
      if (select && img) {
        select.value = img.collection || "";
      }
      const saveBtn = card.querySelector("[data-action='save']");
      if (saveBtn) {
        saveBtn.addEventListener("click", async () => {
          const titleInput = card.querySelector("[data-field='title']");
          const descInput = card.querySelector("[data-field='description']");
          const tagsInput = card.querySelector("[data-field='tags']");
          const collectionInput = card.querySelector("[data-field='collection']");
          const status = card.querySelector("[data-field='status']");
          if (!titleInput || !descInput || !tagsInput || !collectionInput || !status) return;
          const title = titleInput.value.trim();
          const description = descInput.value.trim();
          const tags = tagsInput.value.trim();
          const collection = collectionInput.value;
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
      }
      const deleteBtn = card.querySelector("[data-action='delete']");
      if (deleteBtn) {
        deleteBtn.addEventListener("click", async () => {
          if (!confirm("确认删除该作品？")) return;
          const status = card.querySelector("[data-field='status']");
          if (!status) return;
          status.textContent = "删除中...";
          try {
            await fetchJSON(`/upload/admin/images/${uuid}/delete`, { method: "POST" });
            card.remove();
          } catch (err) {
            status.textContent = err.message;
          }
        });
      }
    });

    if (masonry) {
      masonry.refresh();
    }
  }

  function initTagSuggest(container) {
    if (!window.GalleryTagSuggest || !window.GalleryTagSuggest.initTagInputs) return;
    const scope = container || document;
    const inputs = scope.querySelectorAll("[data-tag-input]");
    if (!inputs.length) return;
    window.GalleryTagSuggest.initTagInputs(inputs);
  }

  function applyFilters() {
    filterState.query = (queryInput && queryInput.value.trim()) || "";
    filterState.collection = collectionFilter ? collectionFilter.value : "all";
    loadImages(1);
  }

  async function loadImages(page) {
    const targetPage = page || currentPage || 1;
    const params = buildQueryParams(targetPage);
    const data = await fetchJSON(`/upload/admin/images?${params.toString()}`);
    images = data.images || [];
    collections = data.collections || [];
    defaultCollection = data.default_collection || "";
    currentPage = Number(data.page || targetPage) || 1;
    totalPages = Number(data.pages || 1) || 1;
    totalItems = Number(data.total || images.length) || 0;
    renderCollections();
    renderCollectionFilter();
    renderUploadCollections();
    bindCollectionActions();
    renderImages(images);
    renderPagination();
    syncTrashActions();
    syncUrl(currentPage);
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

  function normalizeInviteDateInput(value) {
    if (!value) return "";
    return String(value).trim();
  }

  function buildInviteExpiresAt() {
    const directValue = normalizeInviteDateInput(
      inviteExpiresAtInput ? inviteExpiresAtInput.value : ""
    );
    if (directValue) {
      if (directValue.includes("T") || directValue.includes(" ")) {
        return directValue.replace("T", " ");
      }
      return `${directValue} 00:00`;
    }
    const daysValue = inviteExpiresDaysInput ? inviteExpiresDaysInput.value : "";
    const days = parseInt(daysValue || "0", 10);
    if (!Number.isFinite(days) || days <= 0) {
      return "";
    }
    const now = new Date();
    now.setHours(0, 0, 0, 0);
    now.setDate(now.getDate() + days);
    const pad = (num) => String(num).padStart(2, "0");
    return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} 00:00`;
  }

  function parseInviteDate(value) {
    if (!value) return null;
    const normalized = String(value).trim().replace(" ", "T");
    const parsed = new Date(normalized);
    if (Number.isNaN(parsed.getTime())) return null;
    return parsed;
  }

  function formatInviteDate(value) {
    const date = parseInviteDate(value);
    if (!date) return value || "不过期";
    const pad = (num) => String(num).padStart(2, "0");
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(
      date.getDate()
    )} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
  }

  function formatInviteRemaining(value) {
    const date = parseInviteDate(value);
    if (!date) return "不过期";
    const diff = date.getTime() - Date.now();
    if (diff <= 0) return "已过期";
    const hours = Math.ceil(diff / 3600000);
    if (hours < 24) {
      return `剩余 ${hours} 小时`;
    }
    const days = Math.ceil(diff / 86400000);
    return `剩余 ${days} 天`;
  }

  function renderInviteCreated(code) {
    if (!inviteCreatedWrap || !inviteCreatedCode) return;
    if (!code) {
      inviteCreatedWrap.hidden = true;
      inviteCreatedCode.textContent = "";
      return;
    }
    inviteCreatedWrap.hidden = false;
    inviteCreatedCode.textContent = code;
  }

  function renderInviteCards(list, options) {
    const emptyText = (options && options.emptyText) || "暂无邀请码。";
    if (!list || !list.length) {
      return `<div class="empty">${escapeHtml(emptyText)}</div>`;
    }
    return list
      .map((invite) => {
        const isActive = Boolean(invite.is_active);
        const codeText = `${invite.code_prefix || ""}****`;
        const maxUses =
          invite.max_uses === null || invite.max_uses === undefined
            ? "不限"
            : invite.max_uses;
        const usedText = `${invite.used_count || 0}/${maxUses}`;
        const expiresAt = invite.expires_at || "";
        const expiresLabel = expiresAt ? formatInviteDate(expiresAt) : "不过期";
        const remainingLabel = formatInviteRemaining(expiresAt);
        const statusText = isActive
          ? remainingLabel === "已过期"
            ? "已过期"
            : "启用"
          : "停用";
        const noteText = invite.note ? escapeHtml(invite.note) : "无备注";
        const actions = isActive
          ? `<button class="btn ghost" type="button" data-invite-action="disable" data-invite-id="${invite.id}">停用</button>`
          : `<button class="btn ghost" type="button" data-invite-action="enable" data-invite-id="${invite.id}">启用</button>
             <button class="btn ghost" type="button" data-invite-action="delete" data-invite-id="${invite.id}">删除</button>`;
        const cardClass = isActive ? "admin-invite-card" : "admin-invite-card is-inactive";
        return `
          <div class="${cardClass}">
            <div class="admin-invite-main">
              <div class="admin-invite-code">${escapeHtml(codeText)}</div>
              <div class="admin-invite-meta">
                <span>已用 ${escapeHtml(usedText)}</span>
                <span>${escapeHtml(statusText)}</span>
                <span>${escapeHtml(expiresLabel)}</span>
                <span>${escapeHtml(remainingLabel)}</span>
              </div>
              <div class="admin-invite-note">${noteText}</div>
            </div>
            <div class="admin-invite-actions">
              ${actions}
            </div>
          </div>
        `;
      })
      .join("");
  }

  function syncInviteArchiveState(inactiveCount) {
    inviteArchiveCountValue = inactiveCount;
    if (inviteArchiveCount) {
      inviteArchiveCount.textContent = inactiveCount ? `${inactiveCount} 个` : "0";
    }
    if (inviteArchive) {
      inviteArchive.hidden = inactiveCount === 0;
    }
    if (!inviteArchiveList) return;
    if (inactiveCount === 0) {
      inviteArchiveOpen = false;
      inviteArchiveList.hidden = true;
      if (inviteArchiveToggle) inviteArchiveToggle.setAttribute("aria-expanded", "false");
      return;
    }
    inviteArchiveList.hidden = !inviteArchiveOpen;
    if (inviteArchiveToggle) {
      inviteArchiveToggle.setAttribute("aria-expanded", inviteArchiveOpen ? "true" : "false");
    }
  }

  function renderInvites(list) {
    if (!inviteList) return;
    const active = [];
    const inactive = [];
    (list || []).forEach((invite) => {
      if (invite && invite.is_active) {
        active.push(invite);
      } else if (invite) {
        inactive.push(invite);
      }
    });
    inviteList.innerHTML = renderInviteCards(active, { emptyText: "暂无可用邀请码。" });
    if (inviteArchiveList) {
      inviteArchiveList.innerHTML = renderInviteCards(inactive, { emptyText: "暂无停用邀请码。" });
    }
    syncInviteArchiveState(inactive.length);
  }

  async function loadInvites() {
    if (!inviteList) return;
    const data = await fetchJSON("/upload/admin/invites");
    renderInvites(data.invites || []);
  }

  async function createInvite() {
    if (!inviteCreateBtn) return;
    if (inviteHint) inviteHint.textContent = "创建中...";
    renderInviteCreated("");
    const limitEnabled = inviteLimitToggle ? inviteLimitToggle.checked : true;
    let maxUses = inviteMaxUsesInput ? inviteMaxUsesInput.value : "";
    if (!limitEnabled) {
      maxUses = "";
    }
    const expiresAt = buildInviteExpiresAt();
    try {
      const payload = {
        note: inviteNoteInput ? inviteNoteInput.value.trim() : "",
        max_uses: maxUses,
        expires_at: expiresAt,
      };
      const data = await fetchJSON("/upload/admin/invites", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (inviteHint) inviteHint.textContent = "已创建";
      renderInviteCreated(data.code || "");
      await loadInvites();
    } catch (err) {
      if (inviteHint) inviteHint.textContent = err.message;
    }
  }

  async function disableInvite(inviteId) {
    if (!inviteId) return;
    if (inviteHint) inviteHint.textContent = "停用中...";
    try {
      await fetchJSON(`/upload/admin/invites/${inviteId}/disable`, { method: "POST" });
      if (inviteHint) inviteHint.textContent = "已停用";
      await loadInvites();
    } catch (err) {
      if (inviteHint) inviteHint.textContent = err.message;
    }
  }

  async function enableInvite(inviteId) {
    if (!inviteId) return;
    if (inviteHint) inviteHint.textContent = "启用中...";
    try {
      await fetchJSON(`/upload/admin/invites/${inviteId}/enable`, { method: "POST" });
      if (inviteHint) inviteHint.textContent = "已启用";
      await loadInvites();
    } catch (err) {
      if (inviteHint) inviteHint.textContent = err.message;
    }
  }

  async function deleteInvite(inviteId) {
    if (!inviteId) return;
    if (inviteHint) inviteHint.textContent = "删除中...";
    try {
      await fetchJSON(`/upload/admin/invites/${inviteId}/delete`, { method: "POST" });
      if (inviteHint) inviteHint.textContent = "已删除";
      await loadInvites();
    } catch (err) {
      if (inviteHint) inviteHint.textContent = err.message;
    }
  }

  function openInviteDialog(inviteId, mode) {
    if (!inviteDialog) return;
    inviteDialogInviteId = inviteId;
    inviteDialogMode = mode || "choice";
    if (inviteDialogDesc) {
      inviteDialogDesc.textContent =
        inviteDialogMode === "delete"
          ? "确认删除该邀请码吗？"
          : "请选择对该邀请码的操作。";
    }
    if (inviteDialogDisable) {
      inviteDialogDisable.hidden = inviteDialogMode === "delete";
    }
    if (inviteDialogDelete) {
      inviteDialogDelete.textContent = inviteDialogMode === "delete" ? "确认删除" : "删除";
    }
    inviteDialog.setAttribute("aria-hidden", "false");
    inviteDialog.classList.remove("is-open");
    void inviteDialog.offsetHeight;
    window.requestAnimationFrame(() => {
      inviteDialog.classList.add("is-open");
    });
  }

  function closeInviteDialog() {
    if (!inviteDialog) return;
    inviteDialog.classList.remove("is-open");
    inviteDialogInviteId = null;
    inviteDialogMode = "choice";
    inviteDialog.setAttribute("aria-hidden", "true");
  }

  async function handleInviteDialogDisable() {
    if (!inviteDialogInviteId) return;
    const inviteId = inviteDialogInviteId;
    closeInviteDialog();
    await disableInvite(inviteId);
  }

  async function handleInviteDialogDelete() {
    if (!inviteDialogInviteId) return;
    const inviteId = inviteDialogInviteId;
    closeInviteDialog();
    await deleteInvite(inviteId);
  }

  function handleInviteActionClick(event) {
    const btn = event.target.closest("[data-invite-action]");
    if (!btn) return;
    const inviteId = btn.dataset.inviteId;
    const action = btn.dataset.inviteAction;
    if (!inviteId || !action) return;
    if (action === "disable") {
      openInviteDialog(inviteId, "choice");
      return;
    }
    if (action === "enable") {
      enableInvite(inviteId);
      return;
    }
    if (action === "delete") {
      openInviteDialog(inviteId, "delete");
    }
  }

  function syncInviteLimitState() {
    if (!inviteMaxUsesInput || !inviteLimitToggle) return;
    inviteMaxUsesInput.disabled = !inviteLimitToggle.checked;
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
    readUrlState();
    loadAdminStatus();
    if (trashBtn) {
      trashBtn.textContent = showTrash ? "查看正常作品" : "查看垃圾桶";
    }
    syncTrashActions();
    if (grid) {
      loadImages(currentPage).catch((err) => {
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
    loadInvites().catch((err) => {
      if (inviteHint) inviteHint.textContent = err.message;
    });
    loadDmcaSummary().catch(() => {});
    if (dmcaPendingNode && !dmcaSummaryTimer) {
      dmcaSummaryTimer = window.setInterval(loadDmcaSummary, 30000);
    }
    if (dmcaList) {
      loadDmcaList(dmcaPage).catch((err) => {
        if (dmcaHint) dmcaHint.textContent = err.message;
      });
      if (!dmcaListTimer) {
        dmcaListTimer = window.setInterval(() => loadDmcaList(dmcaPage), 45000);
      }
    }

    if (grid && refreshBtn) {
      refreshBtn.addEventListener("click", () => loadImages(currentPage));
    }

    if (trashBtn) {
      trashBtn.addEventListener("click", () => {
        showTrash = !showTrash;
        trashBtn.textContent = showTrash ? "查看正常作品" : "查看垃圾桶";
        currentPage = 1;
        syncTrashActions();
        loadImages(currentPage);
      });
    }

    if (trashPageBtn) {
      trashPageBtn.addEventListener("click", async () => {
        if (!showTrash) return;
        const uuids = (images || []).map((item) => item.uuid).filter(Boolean);
        if (!uuids.length) return;
        if (!confirm("确认永久删除本页垃圾桶作品？此操作不可恢复。")) return;
        await purgeTrash(uuids, false);
      });
    }

    if (trashAllBtn) {
      trashAllBtn.addEventListener("click", async () => {
        if (!showTrash) return;
        if (!confirm("确认清空垃圾桶？此操作不可恢复。")) return;
        await purgeTrash(null, true);
      });
    }

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

    if (dmcaFilter) {
      dmcaFilter.addEventListener("change", () => {
        dmcaPage = 1;
        loadDmcaList(dmcaPage);
      });
    }

    if (dmcaRefreshBtn) {
      dmcaRefreshBtn.addEventListener("click", () => loadDmcaList(dmcaPage));
    }

    if (dmcaPagePrevBtn) {
      dmcaPagePrevBtn.addEventListener("click", () => {
        if (dmcaPage <= 1) return;
        loadDmcaList(dmcaPage - 1);
      });
    }

    if (dmcaPageNextBtn) {
      dmcaPageNextBtn.addEventListener("click", () => {
        if (dmcaPage >= dmcaPages) return;
        loadDmcaList(dmcaPage + 1);
      });
    }

    if (dmcaList) {
      dmcaList.addEventListener("click", (event) => {
        const actionBtn = event.target.closest("[data-dmca-action]");
        if (!actionBtn) return;
        const card = actionBtn.closest("[data-dmca-id]");
        if (!card) return;
        const requestId = card.dataset.dmcaId;
        const action = actionBtn.dataset.dmcaAction;
        if (!requestId || !action) return;
        if (!confirm(`确认将该申请标记为${action === "approve" ? "已通过" : "已拒绝"}？`)) {
          return;
        }
        const noteInput = card.querySelector("[data-dmca-note]");
        const hintNode = card.querySelector("[data-dmca-action-hint]");
        updateDmcaStatus(requestId, action === "approve" ? "approved" : "rejected", noteInput ? noteInput.value : "", hintNode);
      });
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
        const wrap = btn.closest("[data-admin-pagination], [data-admin-pagination-top]");
        const input = wrap ? wrap.querySelector("[data-admin-page-input]") : null;
        if (!input) return;
        jumpToPage(input.value);
      });
    });

    if (inviteLimitToggle) {
      syncInviteLimitState();
      inviteLimitToggle.addEventListener("change", syncInviteLimitState);
    }

    if (inviteCreateBtn) {
      inviteCreateBtn.addEventListener("click", createInvite);
    }

    if (inviteRefreshBtn) {
      inviteRefreshBtn.addEventListener("click", () => {
        loadInvites().catch((err) => {
          if (inviteHint) inviteHint.textContent = err.message;
        });
      });
    }

    if (inviteArchiveToggle) {
      inviteArchiveToggle.addEventListener("click", () => {
        inviteArchiveOpen = !inviteArchiveOpen;
        syncInviteArchiveState(inviteArchiveCountValue);
      });
    }

    if (inviteList) {
      inviteList.addEventListener("click", handleInviteActionClick);
    }

    if (inviteArchiveList) {
      inviteArchiveList.addEventListener("click", handleInviteActionClick);
    }

    if (inviteDialogDisable) {
      inviteDialogDisable.addEventListener("click", handleInviteDialogDisable);
    }

    if (inviteDialogDelete) {
      inviteDialogDelete.addEventListener("click", handleInviteDialogDelete);
    }

    if (inviteDialogCancel) {
      inviteDialogCancel.addEventListener("click", closeInviteDialog);
    }

    if (inviteDialogCloseBtns.length) {
      inviteDialogCloseBtns.forEach((btn) => {
        btn.addEventListener("click", closeInviteDialog);
      });
    }

    if (inviteDialog) {
      document.addEventListener("keydown", (event) => {
        if (event.key !== "Escape") return;
        if (inviteDialog.hidden) return;
        closeInviteDialog();
      });
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

    initStressTool();
    initTagsPage();
  }

  function initStressTool() {
    if (!stressToggle || !stressGenerateBtn || !stressDeleteBtn || !stressCountInput) return;
    const progress = window.GalleryUploadProgress;
    const STORAGE_KEY = "admin-stress-enabled";
    const MAX_RETRIES = 3;
    const RETRY_DELAY_MS = 1500;
    const REQUEST_TIMEOUT_MS = 12000;
    const state = {
      total: 0,
      nextIndex: 1,
      generated: 0,
      uploaded: 0,
      running: false,
      paused: false,
      stopRequested: false,
      deleting: false,
      stage: "",
      currentRequest: null,
      abortReason: "",
      retrySleepTimer: null,
      retrySleepResolve: null,
    };

    if (localStorage.getItem(STORAGE_KEY) === "1") {
      stressToggle.checked = true;
    }

    const setHint = (message) => {
      if (stressHint) stressHint.textContent = message || "";
    };

    const summaryText = () =>
      `生成 ${state.generated}/${state.total} · 上传 ${state.uploaded}/${state.total}`;

    const applyState = () => {
      const enabled = stressToggle.checked;
      const busy = state.running || state.paused || state.deleting;
      stressGenerateBtn.disabled = !enabled || busy;
      stressDeleteBtn.disabled = !enabled || busy;
      stressCountInput.disabled = !enabled || busy;
      if (stressStopBtn) stressStopBtn.disabled = !enabled || (!state.running && !state.paused);
      if (stressRetryBtn)
        stressRetryBtn.disabled = !enabled || !(state.paused || state.stage === "retrying");
      localStorage.setItem(STORAGE_KEY, enabled ? "1" : "0");
    };

    const parseCount = () => {
      const raw = parseInt(stressCountInput.value || "0", 10);
      if (!Number.isFinite(raw) || raw <= 0) return 0;
      return Math.min(raw, 500);
    };

    const clearRetrySleep = () => {
      if (state.retrySleepTimer) {
        window.clearTimeout(state.retrySleepTimer);
      }
      state.retrySleepTimer = null;
      state.retrySleepResolve = null;
    };

    const wakeRetrySleep = () => {
      if (!state.retrySleepResolve) return;
      const resolve = state.retrySleepResolve;
      clearRetrySleep();
      resolve();
    };

    const abortCurrentRequest = (reason) => {
      if (!state.currentRequest) return;
      state.abortReason = reason || "abort";
      state.currentRequest.abort();
    };

    const updateProgress = (stage, message) => {
      if (!progress || !currentAdminUser) return;
      state.stage = stage;
      const loaded =
        stage === "uploading" || stage === "retrying" || stage === "paused"
          ? state.uploaded
          : state.generated;
      progress.updateTask("admin", currentAdminUser, {
        stage,
        loaded,
        total: state.total,
        unit: "count",
        message: message || summaryText(),
      });
    };

    const startProgress = () => {
      if (!progress || !currentAdminUser) return;
      state.stage = "generating";
      progress.startTask("admin", currentAdminUser, {
        stage: "generating",
        total: state.total,
        loaded: 0,
        unit: "count",
        message: summaryText(),
      });
    };

    const requestGenerate = async (index, total) => {
      for (let attempt = 1; attempt <= MAX_RETRIES; attempt += 1) {
        if (state.stopRequested) return { stopped: true };
        const controller = new AbortController();
        state.currentRequest = controller;
        state.abortReason = "";
        let timeoutId = null;
        if (REQUEST_TIMEOUT_MS > 0) {
          timeoutId = window.setTimeout(() => {
            if (!state.abortReason) state.abortReason = "timeout";
            controller.abort();
          }, REQUEST_TIMEOUT_MS);
        }
        try {
          const data = await fetchJSON("/upload/admin/stress/generate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ index, total }),
            signal: controller.signal,
          });
          if (timeoutId) window.clearTimeout(timeoutId);
          if (state.currentRequest === controller) state.currentRequest = null;
          return { data };
        } catch (err) {
          if (timeoutId) window.clearTimeout(timeoutId);
          if (state.currentRequest === controller) state.currentRequest = null;
          const isAbort = err && err.name === "AbortError";
          if (isAbort && state.stopRequested && state.abortReason === "stop") {
            state.abortReason = "";
            return { stopped: true };
          }
          if (attempt >= MAX_RETRIES) {
            state.abortReason = "";
            throw err;
          }
          const reason =
            isAbort && state.abortReason === "timeout" ? "请求超时" : "请求失败";
          const delayMs = state.abortReason === "retry" ? 0 : RETRY_DELAY_MS * attempt;
          state.abortReason = "";
          updateProgress(
            "retrying",
            `${reason}，${Math.round(delayMs / 1000)}s 后重试 ${attempt}/${MAX_RETRIES}`
          );
          if (delayMs > 0) {
            await new Promise((resolve) => {
              state.retrySleepResolve = resolve;
              state.retrySleepTimer = window.setTimeout(resolve, delayMs);
            });
            clearRetrySleep();
          }
          if (state.stopRequested) return { stopped: true };
        }
      }
      return { data: null };
    };

    const finishStopped = () => {
      state.running = false;
      state.paused = false;
      state.stopRequested = false;
      state.stage = "stopped";
      abortCurrentRequest("");
      clearRetrySleep();
      updateProgress("stopped", `已停止：${summaryText()}`);
      setHint(`已停止：${summaryText()}`);
      applyState();
    };

    const finishCompleted = () => {
      state.running = false;
      state.paused = false;
      state.stopRequested = false;
      state.stage = "completed";
      clearRetrySleep();
      updateProgress("completed", `已生成并提交 ${state.total} 张`);
      setHint(`已生成 ${state.total} 张`);
      applyState();
    };

    const pauseWithError = (err) => {
      state.running = false;
      state.paused = true;
      state.stopRequested = false;
      state.generated = Math.max(state.uploaded, state.generated);
      state.stage = "paused";
      clearRetrySleep();
      const message = `请求失败：${err.message || "网络错误"}，可重试或停止`;
      updateProgress("paused", message);
      setHint(message);
      applyState();
    };

    const runGeneration = async () => {
      state.running = true;
      state.paused = false;
      applyState();
      while (state.nextIndex <= state.total) {
        if (state.stopRequested) break;
        const index = state.nextIndex;
        state.generated = Math.max(state.generated, index);
        updateProgress("generating", summaryText());
        try {
          const result = await requestGenerate(index, state.total);
          if (result && result.stopped) {
            break;
          }
        } catch (err) {
          pauseWithError(err);
          return;
        }
        state.uploaded = Math.max(state.uploaded, index);
        updateProgress("uploading", summaryText());
        state.nextIndex += 1;
        if (state.stopRequested) break;
      }
      if (state.stopRequested) {
        finishStopped();
        return;
      }
      finishCompleted();
    };

    stressToggle.addEventListener("change", () => {
      setHint("");
      applyState();
    });

    stressGenerateBtn.addEventListener("click", async () => {
      if (state.running || state.paused || state.deleting || !stressToggle.checked) return;
      const count = parseCount();
      if (!count) {
        setHint("请输入有效数量");
        return;
      }
      state.total = count;
      state.nextIndex = 1;
      state.generated = 0;
      state.uploaded = 0;
      state.stopRequested = false;
      state.running = true;
      state.paused = false;
      state.stage = "generating";
      applyState();
      setHint(`开始生成 ${count} 张...`);
      startProgress();
      await runGeneration();
    });

    if (stressStopBtn) {
      stressStopBtn.addEventListener("click", () => {
        if (!stressToggle.checked || (!state.running && !state.paused)) return;
        if (state.paused) {
          finishStopped();
          return;
        }
        state.stopRequested = true;
        abortCurrentRequest("stop");
        wakeRetrySleep();
        setHint("正在停止...");
      });
    }

    if (stressRetryBtn) {
      stressRetryBtn.addEventListener("click", async () => {
        if (!stressToggle.checked) return;
        if (state.paused) {
          state.stopRequested = false;
          state.running = true;
          state.paused = false;
          state.stage = "generating";
          applyState();
          setHint(`继续生成 ${state.total} 张...`);
          updateProgress("generating", summaryText());
          await runGeneration();
          return;
        }
        if (state.stage === "retrying") {
          abortCurrentRequest("retry");
          wakeRetrySleep();
        }
      });
    }

    stressDeleteBtn.addEventListener("click", async () => {
      if (state.running || state.paused || state.deleting || !stressToggle.checked) return;
      if (!window.confirm("确认删除所有压测图片？")) return;
      state.deleting = true;
      applyState();
      setHint("清理中...");
      let taskId = "";
      try {
        const data = await fetchJSON("/upload/admin/stress/cleanup/start", { method: "POST" });
        taskId = data.task_id || "";
        const total = data.total || 0;
        if (progress && currentAdminUser && taskId) {
          progress.startTask("admin", currentAdminUser, {
            stage: data.stage || "deleting",
            loaded: 0,
            total,
            unit: "count",
            message: data.message || "",
            status_url: `/upload/admin/stress/cleanup/status?task_id=${taskId}`,
          });
        }
        if (data.stage === "completed") {
          setHint(data.message || "没有可清理的压测图片");
        } else if (taskId) {
          for (let i = 0; i < 300; i += 1) {
            await sleep(2000);
            const status = await fetchJSON(
              `/upload/admin/stress/cleanup/status?task_id=${taskId}`
            );
            if (status && status.message) {
              setHint(status.message);
            }
            if (status.stage === "completed" || status.stage === "failed") {
              break;
            }
          }
        }
      } catch (err) {
        setHint(err.message);
      } finally {
        state.deleting = false;
        applyState();
      }
    });

    applyState();
  }

  async function initTagsPage() {
    const tagList = document.querySelector("[data-admin-tag-list]");
    if (!tagList && !typeList && !tagAddBtn && !tagEditorTagPanel) return;
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
    let pendingTypeFilter = "";
    const TAG_FILTER_STORAGE_KEY = "admin-tags-filters-v1";

    function loadTagFilterPrefs() {
      if (!("localStorage" in window)) return {};
      try {
        const raw = window.localStorage.getItem(TAG_FILTER_STORAGE_KEY);
        if (!raw) return {};
        const data = JSON.parse(raw);
        return data && typeof data === "object" ? data : {};
      } catch (err) {
        return {};
      }
    }

    function persistTagFilterPrefs() {
      if (!("localStorage" in window)) return;
      const payload = {};
      if (tagShowEmptyToggle) payload.showEmpty = Boolean(tagShowEmptyToggle.checked);
      if (tagCandidateToggle) payload.candidate = Boolean(tagCandidateToggle.checked);
      if (tagPageSizeSelect) {
        const size = parseInt(tagPageSizeSelect.value || "0", 10);
        if (Number.isFinite(size) && size > 0) payload.pageSize = size;
      }
      if (tagSortSelect) payload.sort = tagSortSelect.value || "count-desc";
      if (tagTypeFilter) payload.type = tagTypeFilter.value || "all";
      try {
        window.localStorage.setItem(TAG_FILTER_STORAGE_KEY, JSON.stringify(payload));
      } catch (err) {
        // ignore
      }
    }

    const savedFilters = loadTagFilterPrefs();
    if (tagShowEmptyToggle && typeof savedFilters.showEmpty === "boolean") {
      tagShowEmptyToggle.checked = savedFilters.showEmpty;
    }
    if (tagCandidateToggle && typeof savedFilters.candidate === "boolean") {
      tagCandidateToggle.checked = savedFilters.candidate;
    }
    if (tagPageSizeSelect && Number.isFinite(savedFilters.pageSize)) {
      const targetValue = String(savedFilters.pageSize);
      const hasOption = Array.from(tagPageSizeSelect.options).some(
        (option) => option.value === targetValue
      );
      if (hasOption) {
        tagPageSizeSelect.value = targetValue;
      }
    }
    if (tagSortSelect && savedFilters.sort) {
      tagSortSelect.value = String(savedFilters.sort);
    }
    if (savedFilters.type) {
      pendingTypeFilter = String(savedFilters.type);
    }
    if (tagPageSizeSelect) {
      const parsed = parseInt(tagPageSizeSelect.value || "0", 10);
      if (Number.isFinite(parsed) && parsed > 0) {
        tagPageSize = parsed;
      }
    }

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
        const preferred = pendingTypeFilter || current;
        tagTypeFilter.value = values.has(preferred) ? preferred : "all";
        pendingTypeFilter = "";
        persistTagFilterPrefs();
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
      const compact = tagEditorTagPanel.dataset.editorMode === "compact";
      const rowClass = compact ? "tag-admin-row tag-admin-row-compact" : "tag-admin-row";
      const headMarkup = `
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
          ${
            compact
              ? ""
              : `
          <div class="tag-admin-count">
            <span>作品数</span>
            <input type="text" value="${escapeHtml(tag.count || 0)}" disabled>
          </div>
          `
          }
        </div>
      `;
      const fieldsMarkup = compact
        ? `
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
              <textarea rows="2" placeholder="animal_ears | kemonomimi" data-tag-field="parents" data-tag-input>${escapeHtml(
                (tag.parents || []).join(" | ")
              )}</textarea>
            </label>
          </div>
        `
        : `
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
              <textarea rows="2" placeholder="animal_ears | kemonomimi" data-tag-field="parents" data-tag-input>${escapeHtml(
                (tag.parents || []).join(" | ")
              )}</textarea>
            </label>
            <label class="tag-field">
              <span>合并到</span>
              <input type="text" value="${escapeHtml(
                (tag.alias_to || "").trim()
              )}" placeholder="主标签（可空）" data-tag-field="alias-to">
            </label>
          </div>
        `;
      const actionsMarkup = compact
        ? `
          <div class="tag-admin-actions tag-admin-actions-compact">
            <label class="tag-quick-attach">
              <input type="checkbox" data-tag-attach checked>
              <span>保存后加入上传标签</span>
            </label>
            <button class="btn primary" type="button" data-tag-action="save">保存标签</button>
          </div>
        `
        : `
          <div class="tag-admin-actions">
            <button class="btn primary" type="button" data-tag-action="save">保存</button>
            <button class="btn ghost" type="button" data-tag-action="meta-delete">清除简介/别名</button>
            <button class="btn ghost" type="button" data-tag-action="rename">改名</button>
            <button class="btn ghost" type="button" data-tag-action="delete">删除</button>
          </div>
        `;
      tagEditorTagPanel.innerHTML = `
        <div class="${rowClass}" data-tag-row>
          ${headMarkup}
          ${fieldsMarkup}
          ${compact ? "" : renderTagTree(tag)}
          ${actionsMarkup}
        </div>
      `;
      bindTagRowActions(tagEditorTagPanel);
      bindTagTreeActions(tagEditorTagPanel);
      initTagSuggest(tagEditorTagPanel);
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
      if (!typeList && !tagEditorTagPanel && !tagTypeFilter && !tagTypeSummary) return;
      const data = await fetchJSON("/upload/admin/tag-types");
      tagTypes = data.types || [];
      if (typeList) renderTagTypes(tagTypes);
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
      await loadTagTypes();
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

    function appendTagToUploadInput(tagName) {
      if (!uploadForm) return false;
      const input = uploadForm.querySelector("[data-tag-input]");
      if (!input) return false;
      const cleaned = String(tagName || "").trim();
      if (!cleaned) return false;
      const parsed = parseTagTokens(input.value);
      const exists = parsed.tags.some(
        (item) => item.toLowerCase() === cleaned.toLowerCase()
      );
      const nextTags = exists ? parsed.tags : [...parsed.tags, cleaned];
      const requireHash = input.dataset.tagRequireHash === "1";
      const useHash = requireHash || parsed.hasHash;
      input.value = formatTagsValue(nextTags, useHash);
      input.dispatchEvent(new Event("input", { bubbles: true }));
      input.focus();
      return true;
    }

    function bindTagRowActions(scope) {
      const host = scope || document;
      host.querySelectorAll("[data-tag-action='save']").forEach((btn) => {
        btn.addEventListener("click", async () => {
          const row = btn.closest("[data-tag-row]");
          const readValue = (field) => {
            const input = row.querySelector(`[data-tag-field='${field}']`);
            return input ? input.value.trim() : "";
          };
          const tag = readValue("tag");
          const slug = readValue("slug");
          const typeField = row.querySelector("[data-tag-field='type']");
          const type = typeField ? typeField.value : "";
          const intro = readValue("intro");
          const aliases = readValue("aliases");
          const parents = readValue("parents");
          const aliasTo = readValue("alias-to");
          const attachToggle = row.querySelector("[data-tag-attach]");
          if (tagsHint) tagsHint.textContent = "保存中...";
          try {
            await fetchJSON("/upload/admin/tags/meta", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ tag, slug, type, intro, aliases, parents, alias_to: aliasTo }),
            });
            let hintMessage = "已保存，等待刷新发布";
            if (attachToggle && attachToggle.checked) {
              if (appendTagToUploadInput(tag)) {
                hintMessage = "已保存并加入上传标签";
              }
            }
            if (tagsHint) tagsHint.textContent = hintMessage;
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
        persistTagFilterPrefs();
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
      tagTypeFilter.addEventListener("change", () => {
        persistTagFilterPrefs();
        applyTagFilters({ resetPage: true });
      });
    }

    if (tagSortSelect) {
      tagSortSelect.addEventListener("change", () => {
        persistTagFilterPrefs();
        applyTagFilters({ resetPage: true });
      });
    }

    if (tagShowEmptyToggle) {
      tagShowEmptyToggle.addEventListener("change", () => {
        persistTagFilterPrefs();
        applyTagFilters({ resetPage: true });
      });
    }

    if (tagCandidateToggle) {
      tagCandidateToggle.addEventListener("change", () => {
        persistTagFilterPrefs();
        applyTagFilters({ resetPage: true });
      });
    }

    if (tagPageSizeSelect) {
      tagPageSizeSelect.addEventListener("change", () => {
        persistTagFilterPrefs();
        applyTagFilters({ resetPage: true });
      });
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
