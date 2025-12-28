(function () {
  const contentEl = document.querySelector('[data-wiki-content]');
  if (!contentEl) return;
  const treeEl = document.querySelector('[data-wiki-tree]');
  const editBtn = document.querySelector('[data-wiki-edit]');
  const editor = document.querySelector('[data-wiki-editor]');
  const textarea = document.querySelector('[data-wiki-textarea]');
  const preview = document.querySelector('[data-wiki-preview]');
  const status = document.querySelector('[data-wiki-status]');
  const closeBtn = document.querySelector('[data-wiki-close]');
  const saveBtn = document.querySelector('[data-wiki-save]');
  const toggleBtn = document.querySelector('[data-wiki-toggle]');
  const body = document.body;

  let markdownSource = '';

  function escapeHtml(text) {
    return String(text)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function renderInline(text) {
    let output = escapeHtml(text);
    output = output.replace(/`([^`]+)`/g, '<code>$1</code>');
    output = output.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    output = output.replace(/\*([^*]+)\*/g, '<em>$1</em>');
    output = output.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
    return output;
  }

  function slugify(text, fallbackIndex) {
    const base = String(text || '')
      .trim()
      .toLowerCase()
      .replace(/[^\w\u4e00-\u9fa5]+/g, '-')
      .replace(/^-+|-+$/g, '');
    return base || `section-${fallbackIndex}`;
  }

  function parseMarkdown(md) {
    const lines = String(md || '').replace(/\r\n/g, '\n').split('\n');
    const html = [];
    const headings = [];
    let paragraph = [];
    let listItems = [];
    let listType = '';
    let quoteLines = [];
    let codeLines = [];
    let inCode = false;
    const usedSlugs = new Set();

    function flushParagraph() {
      if (!paragraph.length) return;
      html.push(`<p>${renderInline(paragraph.join(' '))}</p>`);
      paragraph = [];
    }

    function flushList() {
      if (!listItems.length) return;
      html.push(`<${listType}>${listItems.join('')}</${listType}>`);
      listItems = [];
      listType = '';
    }

    function flushQuote() {
      if (!quoteLines.length) return;
      html.push(`<blockquote>${renderInline(quoteLines.join(' '))}</blockquote>`);
      quoteLines = [];
    }

    function flushCode() {
      if (!codeLines.length) return;
      html.push(`<pre><code>${escapeHtml(codeLines.join('\n'))}</code></pre>`);
      codeLines = [];
    }

    lines.forEach((rawLine, index) => {
      const line = rawLine.replace(/\s+$/g, '');
      if (inCode) {
        if (line.trim().startsWith('```')) {
          inCode = false;
          flushCode();
        } else {
          codeLines.push(line);
        }
        return;
      }

      if (line.trim().startsWith('```')) {
        flushParagraph();
        flushList();
        flushQuote();
        inCode = true;
        return;
      }

      if (/^\s*$/.test(line)) {
        flushParagraph();
        flushList();
        flushQuote();
        return;
      }

      if (/^---+$/.test(line.trim()) || /^\*\*\*+$/.test(line.trim())) {
        flushParagraph();
        flushList();
        flushQuote();
        html.push('<hr>');
        return;
      }

      const headingMatch = line.match(/^(#{1,6})\s+(.+)$/);
      if (headingMatch) {
        flushParagraph();
        flushList();
        flushQuote();
        const level = headingMatch[1].length;
        const text = headingMatch[2].trim();
        let slug = slugify(text, headings.length + 1);
        if (usedSlugs.has(slug)) {
          slug = `${slug}-${headings.length + 1}`;
        }
        usedSlugs.add(slug);
        headings.push({ level, text, id: slug });
        html.push(`<h${level} id="${slug}">${renderInline(text)}</h${level}>`);
        return;
      }

      const quoteMatch = line.match(/^>\s*(.+)$/);
      if (quoteMatch) {
        flushParagraph();
        flushList();
        quoteLines.push(quoteMatch[1].trim());
        return;
      }

      const orderedMatch = line.match(/^\d+\.\s+(.+)$/);
      if (orderedMatch) {
        flushParagraph();
        flushQuote();
        if (listType && listType !== 'ol') {
          flushList();
        }
        listType = 'ol';
        listItems.push(`<li>${renderInline(orderedMatch[1])}</li>`);
        return;
      }

      const unorderedMatch = line.match(/^[-*+]\s+(.+)$/);
      if (unorderedMatch) {
        flushParagraph();
        flushQuote();
        if (listType && listType !== 'ul') {
          flushList();
        }
        listType = 'ul';
        listItems.push(`<li>${renderInline(unorderedMatch[1])}</li>`);
        return;
      }

      paragraph.push(line.trim());
    });

    flushParagraph();
    flushList();
    flushQuote();
    flushCode();

    return { html: html.join('\n'), headings };
  }

  function renderToc(headings) {
    if (!treeEl) return;
    if (!headings.length) {
      treeEl.innerHTML = '';
      return;
    }
    const minLevel = Math.min(...headings.map((h) => h.level));
    let currentLevel = minLevel;
    let html = '<ul>';
    headings.forEach((heading) => {
      let level = heading.level;
      if (level < minLevel) level = minLevel;
      while (level > currentLevel) {
        html += '<ul>';
        currentLevel += 1;
      }
      while (level < currentLevel) {
        html += '</ul>';
        currentLevel -= 1;
      }
      html += `<li><a href="#${heading.id}">${escapeHtml(heading.text)}</a></li>`;
    });
    while (currentLevel > minLevel) {
      html += '</ul>';
      currentLevel -= 1;
    }
    html += '</ul>';
    treeEl.innerHTML = html;
  }

  function renderMarkdown(md, target, updateNav) {
    const parsed = parseMarkdown(md);
    target.innerHTML = parsed.html;
    if (updateNav) {
      renderToc(parsed.headings);
    }
    return parsed;
  }

  function setEditorVisible(show) {
    if (!editor) return;
    editor.hidden = !show;
    contentEl.hidden = show;
  }

  function loadMarkdown() {
    return fetch('/static/data/wiki.md', { cache: 'no-store' })
      .then((resp) => (resp.ok ? resp.text() : ''))
      .catch(() => '');
  }

  function updatePreview() {
    if (!preview || !textarea) return;
    renderMarkdown(textarea.value || '', preview, false);
  }

  function setStatus(message) {
    if (status) status.textContent = message || '';
  }

  function initNavToggle() {
    if (!toggleBtn) return;
    const saved = localStorage.getItem('wiki_nav');
    if (saved === 'collapsed') {
      body.classList.add('nav-collapsed');
      toggleBtn.setAttribute('aria-expanded', 'false');
    }
    toggleBtn.addEventListener('click', () => {
      const collapsed = body.classList.toggle('nav-collapsed');
      toggleBtn.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
      localStorage.setItem('wiki_nav', collapsed ? 'collapsed' : 'expanded');
    });
  }

  function initEditor() {
    if (!editBtn || !editor || !textarea || !preview) return;
    editBtn.addEventListener('click', () => {
      textarea.value = markdownSource || '';
      updatePreview();
      setEditorVisible(true);
      setStatus('');
    });
    if (closeBtn) {
      closeBtn.addEventListener('click', () => {
        setEditorVisible(false);
      });
    }
    textarea.addEventListener('input', () => {
      updatePreview();
    });
    if (saveBtn) {
      saveBtn.addEventListener('click', async () => {
        setStatus('保存中...');
        const payload = { markdown: textarea.value || '' };
        try {
          const resp = await fetch('/upload/admin/wiki', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify(payload),
          });
          const data = await resp.json().catch(() => ({}));
          if (!resp.ok) {
            throw new Error(data.error || '保存失败');
          }
          markdownSource = payload.markdown;
          renderMarkdown(markdownSource, contentEl, true);
          setStatus('已保存，等待刷新发布');
          setEditorVisible(false);
        } catch (err) {
          setStatus(err.message);
        }
      });
    }
  }

  function checkAdmin() {
    if (!editBtn) return;
    fetch('/upload/admin/me', { credentials: 'include' })
      .then((resp) => (resp.ok ? resp.json() : null))
      .then((data) => {
        if (data && data.ok) {
          editBtn.hidden = false;
        }
      })
      .catch(() => undefined);
  }

  initNavToggle();
  initEditor();
  checkAdmin();

  loadMarkdown().then((md) => {
    markdownSource = md;
    renderMarkdown(md, contentEl, true);
  });
})();
