(function () {
  'use strict';

  // ── Helpers ───────────────────────────────────────────────────────────────

  function relativeTime(isoString) {
    if (!isoString) return '—';
    var now = new Date();
    var then = new Date(isoString);
    var diffSec = Math.floor((now - then) / 1000);
    var diffMin = Math.floor(diffSec / 60);
    var diffHours = Math.floor(diffMin / 60);
    if (diffSec < 60) return 'just now';
    if (diffMin < 60) return diffMin + ' minute' + (diffMin !== 1 ? 's' : '') + ' ago';
    if (diffHours < 24) return diffHours + ' hour' + (diffHours !== 1 ? 's' : '') + ' ago';
    var months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    return then.getDate() + ' ' + months[then.getMonth()] + ' ' + then.getFullYear();
  }

  function pad2(n) { return n < 10 ? '0' + n : '' + n; }

  // "05 May 2026 12:34"
  function fmtDisplay(isoString) {
    var d = new Date(isoString);
    var months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    return pad2(d.getDate()) + ' ' + months[d.getMonth()] + ' ' + d.getFullYear() +
      ' ' + pad2(d.getHours()) + ':' + pad2(d.getMinutes());
  }

  // "05/05/2026 12:34" — format expected by the modal
  function fmtModal(isoString) {
    var d = new Date(isoString);
    return pad2(d.getDate()) + '/' + pad2(d.getMonth() + 1) + '/' + d.getFullYear() +
      ' ' + pad2(d.getHours()) + ':' + pad2(d.getMinutes());
  }

  function showToast(message, type) {
    var container = document.getElementById('toastContainer');
    if (!container) return;
    var toast = document.createElement('div');
    toast.className = 'toast toast--' + (type || 'info');
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(function () {
      if (toast.parentNode) toast.parentNode.removeChild(toast);
    }, 4000);
  }

  // ── Stats strip ───────────────────────────────────────────────────────────

  function updateStatsStrip(breakdown) {
    var data = breakdown[pageType] || {};
    var map = { total: data.total, healthy: data.successful, failed: data.unsuccessful, missing: data.missing };
    Object.keys(map).forEach(function (key) {
      var el = document.querySelector('[data-stat="' + key + '"]');
      if (el && map[key] !== undefined) el.textContent = map[key];
    });
  }

  // ── Last-fetched indicator ────────────────────────────────────────────────

  function setLastFetched(isoString) {
    var el = document.getElementById('lastFetched');
    if (el) el.textContent = 'Last fetched: ' + relativeTime(isoString);
  }

  // ── Background poll ───────────────────────────────────────────────────────

  function pollRefreshStatus() {
    fetch('/api/refresh-status')
      .then(function (res) { return res.ok ? res.json() : null; })
      .then(function (data) {
        if (!data) return;
        setLastFetched(data.last_fetched);
        updateStatsStrip(data.breakdown);
      })
      .catch(function () {});
  }

  // ── Card building ─────────────────────────────────────────────────────────

  function buildCard(entry) {
    var isSuccess = entry.status === 'successful';
    var card = document.createElement('div');
    card.className = 'server-card ' + (isSuccess ? 'server-card--success' : 'server-card--error');
    card.dataset.cardName = entry.server_clean;
    card.dataset.cardStatus = entry.status;
    card.setAttribute('data-bs-toggle', 'modal');
    card.setAttribute('data-bs-target', '#emailModal');
    card.setAttribute('data-server', entry.server || '');
    card.setAttribute('data-subject', entry.subject || '');
    card.setAttribute('data-timestamp', fmtModal(entry.timestamp));
    card.setAttribute('data-ai-summary', entry.ai_summary || '');

    var pill = document.createElement('span');
    pill.className = 'status-pill ' + (isSuccess ? 'status-pill--success' : 'status-pill--error');
    pill.textContent = isSuccess ? 'OK' : 'Failed';

    var nameEl = document.createElement('div');
    nameEl.className = 'card__name';
    nameEl.textContent = entry.server_clean;

    var compEl = document.createElement('div');
    compEl.className = 'card__company';
    compEl.textContent = entry.company || '';

    var timeEl = document.createElement('div');
    timeEl.className = 'card__time';
    var span = document.createElement('span');
    var ts = fmtDisplay(entry.timestamp);
    span.title = ts;
    span.textContent = ts;
    timeEl.appendChild(span);

    card.appendChild(pill);
    card.appendChild(nameEl);
    card.appendChild(compEl);
    card.appendChild(timeEl);
    return card;
  }

  function buildMissingCard(serverName, companyName) {
    var card = document.createElement('div');
    card.className = 'server-card server-card--missing';
    card.dataset.cardName = serverName;
    card.dataset.cardStatus = 'missing';

    var pill = document.createElement('span');
    pill.className = 'status-pill status-pill--missing';
    pill.textContent = 'Missing';

    var nameEl = document.createElement('div');
    nameEl.className = 'card__name';
    nameEl.textContent = serverName;

    var compEl = document.createElement('div');
    compEl.className = 'card__company';
    compEl.textContent = companyName;

    card.appendChild(pill);
    card.appendChild(nameEl);
    card.appendChild(compEl);
    return card;
  }

  // ── Attention panel ───────────────────────────────────────────────────────

  function attentionStorageKey() {
    return 'cs-attention-collapsed-' + (typeof pageType !== 'undefined' ? pageType : 'server');
  }

  function initAttentionToggle(panel, header) {
    if (!panel || !header) return;
    var isCollapsed = localStorage.getItem(attentionStorageKey()) === 'true';
    if (isCollapsed) panel.classList.add('is-collapsed');
    else panel.classList.remove('is-collapsed');
    header.addEventListener('click', function () {
      var nowCollapsed = !panel.classList.contains('is-collapsed');
      if (nowCollapsed) panel.classList.add('is-collapsed');
      else panel.classList.remove('is-collapsed');
      localStorage.setItem(attentionStorageKey(), nowCollapsed);
    });
  }

  function rebuildAttentionPanel(companies) {
    var failedEntries = [];
    var missingEntries = [];

    companies.forEach(function (company) {
      company.servers.forEach(function (server) {
        if (server.status !== 'successful') {
          failedEntries.push({ server: server, companyName: company.name });
        }
      });
      company.missing.forEach(function (name) {
        missingEntries.push({ name: name, companyName: company.name });
      });
    });

    var panel = document.getElementById('attentionPanel') || document.querySelector('.attention-panel');

    if (failedEntries.length === 0 && missingEntries.length === 0) {
      if (panel) panel.style.display = 'none';
      return;
    }

    if (!panel) {
      panel = document.createElement('div');
      panel.className = 'attention-panel';
      panel.id = 'attentionPanel';
      var firstSection = document.querySelector('.company-section');
      if (firstSection) {
        firstSection.parentNode.insertBefore(panel, firstSection);
      } else {
        var wrap = document.querySelector('.page-wrap') || document.querySelector('main');
        if (wrap) wrap.appendChild(panel);
      }
    }

    panel.style.display = '';
    while (panel.firstChild) panel.removeChild(panel.firstChild);

    // Header row
    var header = document.createElement('div');
    header.className = 'attention-panel__header';
    header.id = 'attentionToggle';

    var title = document.createElement('div');
    title.className = 'attention-panel__title';
    title.textContent = 'Needs Attention';

    var countSpan = document.createElement('span');
    countSpan.className = 'attention-count';
    countSpan.id = 'attentionCount';
    countSpan.textContent = '[' + (failedEntries.length + missingEntries.length) + ']';
    title.appendChild(countSpan);

    var chevron = document.createElement('span');
    chevron.className = 'attention-chevron';
    chevron.textContent = '›';

    header.appendChild(title);
    header.appendChild(chevron);
    panel.appendChild(header);

    // Body
    var body = document.createElement('div');
    body.className = 'attention-panel__body';
    body.id = 'attentionBody';

    if (failedEntries.length > 0) {
      var failedHeader = document.createElement('div');
      failedHeader.className = 'attention-panel__section';
      failedHeader.textContent = 'Failed in last run';
      body.appendChild(failedHeader);

      failedEntries.forEach(function (entry) {
        var row = document.createElement('div');
        row.className = 'attention-row';
        row.setAttribute('data-bs-toggle', 'modal');
        row.setAttribute('data-bs-target', '#emailModal');
        row.setAttribute('data-server', entry.server.server || '');
        row.setAttribute('data-subject', entry.server.subject || '');
        row.setAttribute('data-timestamp', fmtModal(entry.server.timestamp));
        row.setAttribute('data-ai-summary', entry.server.ai_summary || '');
        var dot = document.createElement('span');
        dot.className = 'attention-dot attention-dot--error';
        row.appendChild(dot);
        row.appendChild(document.createTextNode(
          entry.server.server_clean + ' — ' + entry.companyName
        ));
        body.appendChild(row);
      });
    }

    if (missingEntries.length > 0) {
      var missingHeader = document.createElement('div');
      missingHeader.className = 'attention-panel__section';
      missingHeader.textContent = 'Missing — expected but not received';
      body.appendChild(missingHeader);

      missingEntries.forEach(function (entry) {
        var row = document.createElement('div');
        row.className = 'attention-row attention-row--missing';
        var dot = document.createElement('span');
        dot.className = 'attention-dot attention-dot--warning';
        row.appendChild(dot);
        row.appendChild(document.createTextNode(
          entry.name + ' — ' + entry.companyName
        ));
        body.appendChild(row);
      });
    }

    panel.appendChild(body);
    initAttentionToggle(panel, header);
  }

  // ── Company section rendering ─────────────────────────────────────────────

  function createCompanySection(companyName) {
    var section = document.createElement('div');
    section.className = 'company-section';
    section.dataset.company = companyName;
    section.dataset.companyActive = 'true';

    var heading = document.createElement('h2');
    heading.className = 'company-heading';
    heading.textContent = companyName;

    var grid = document.createElement('div');
    grid.className = 'card-grid';

    section.appendChild(heading);
    section.appendChild(grid);
    return section;
  }

  function insertSectionAlphabetically(newSection) {
    var sections = document.querySelectorAll('.company-section');
    var newName = (newSection.dataset.company || '').toLowerCase();

    for (var i = 0; i < sections.length; i++) {
      if (newName < (sections[i].dataset.company || '').toLowerCase()) {
        sections[i].parentNode.insertBefore(newSection, sections[i]);
        return;
      }
    }

    // Append after all existing sections
    var last = sections[sections.length - 1];
    if (last) {
      last.parentNode.insertBefore(newSection, last.nextSibling);
    } else {
      var wrap = document.querySelector('.page-wrap') || document.querySelector('main');
      if (wrap) wrap.appendChild(newSection);
    }
  }

  function renderCompanies(companies) {
    var existingSections = {};
    document.querySelectorAll('.company-section[data-company]').forEach(function (el) {
      existingSections[el.dataset.company] = el;
    });

    var responseNames = {};
    companies.forEach(function (c) { responseNames[c.name] = true; });

    // Hide sections absent from the response
    Object.keys(existingSections).forEach(function (name) {
      if (!responseNames[name]) {
        existingSections[name].dataset.companyActive = 'false';
        existingSections[name].style.display = 'none';
      }
    });

    companies.forEach(function (company) {
      var section = existingSections[company.name];

      if (!section) {
        section = createCompanySection(company.name);
        insertSectionAlphabetically(section);
        existingSections[company.name] = section;
      } else {
        section.dataset.companyActive = 'true';
        section.style.display = '';
      }

      var grid = section.querySelector('.card-grid');
      while (grid.firstChild) grid.removeChild(grid.firstChild);

      company.servers.forEach(function (server) {
        grid.appendChild(buildCard(server));
      });
      company.missing.forEach(function (name) {
        grid.appendChild(buildMissingCard(name, company.name));
      });
    });

    rebuildAttentionPanel(companies);
  }

  // ── Client-side search and filter ─────────────────────────────────────────

  function applyFilters() {
    var searchInput = document.querySelector('[data-search-input]');
    var searchText = searchInput ? searchInput.value.toLowerCase() : '';
    var activeChip = document.querySelector('.chip.active');
    var chipValue = activeChip ? activeChip.dataset.chip : 'all';

    document.querySelectorAll('.server-card').forEach(function (card) {
      var name = (card.dataset.cardName || '').toLowerCase();
      var status = card.dataset.cardStatus || '';
      var matchesSearch = !searchText || name.indexOf(searchText) !== -1;
      var matchesChip = chipValue === 'all' ||
        (chipValue === 'healthy' && status === 'successful') ||
        (chipValue === 'failed' && status !== 'successful');
      card.style.display = matchesSearch && matchesChip ? '' : 'none';
    });

    // Hide company sections whose cards are all hidden
    document.querySelectorAll('.company-section').forEach(function (section) {
      if (section.dataset.companyActive === 'false') return;
      var cards = section.querySelectorAll('.server-card');
      var anyVisible = false;
      cards.forEach(function (card) {
        if (card.style.display !== 'none') anyVisible = true;
      });
      section.style.display = anyVisible ? '' : 'none';
    });
  }

  // ── Fetch-now button ──────────────────────────────────────────────────────

  function handleFetchNow() {
    var fetchBtn = document.getElementById('fetchBtn');
    if (!fetchBtn || fetchBtn.disabled) return;

    fetchBtn.disabled = true;
    fetchBtn.classList.add('loading');

    var savedSummary;

    fetch('/api/refresh', { method: 'POST' })
      .then(function (res) {
        if (!res.ok) throw new Error('refresh failed');
        return res.json();
      })
      .then(function (summary) {
        savedSummary = summary;
        var breakdown = summary.breakdown[pageType] || {};
        var successful = breakdown.successful || 0;
        var unsuccessful = breakdown.unsuccessful || 0;
        var msg = successful + ' server' + (successful !== 1 ? 's' : '') + ' updated';
        if (unsuccessful > 0) msg += ', ' + unsuccessful + ' failed';
        showToast(msg, unsuccessful > 0 ? 'error' : 'success');
        return fetch('/api/servers?type=' + pageType);
      })
      .then(function (res) {
        if (!res.ok) throw new Error('servers fetch failed');
        return res.json();
      })
      .then(function (data) {
        renderCompanies(data.companies);
        if (savedSummary) updateStatsStrip(savedSummary.breakdown);
        var lastFetchedEl = document.getElementById('lastFetched');
        if (lastFetchedEl) lastFetchedEl.textContent = 'Last fetched: just now';
        applyFilters();
      })
      .catch(function () {
        showToast('Fetch failed — check your network connection.', 'error');
      })
      .finally(function () {
        fetchBtn.classList.remove('loading');
        fetchBtn.disabled = false;
      });
  }

  // ── Initialise ────────────────────────────────────────────────────────────

  document.addEventListener('DOMContentLoaded', function () {
    // Mark all server-rendered company sections as active
    document.querySelectorAll('.company-section').forEach(function (el) {
      el.dataset.companyActive = 'true';
    });

    // Initial status check — populates last-fetched and stat counts
    pollRefreshStatus();

    // 60-second background poll
    setInterval(pollRefreshStatus, 60000);

    // Attention panel collapse toggle (server-rendered panel)
    initAttentionToggle(
      document.getElementById('attentionPanel'),
      document.getElementById('attentionToggle')
    );

    // Fetch-now button
    var fetchBtn = document.getElementById('fetchBtn');
    if (fetchBtn) fetchBtn.addEventListener('click', handleFetchNow);

    // Live search
    var searchInput = document.querySelector('[data-search-input]');
    if (searchInput) searchInput.addEventListener('input', applyFilters);

    // Status filter chips
    document.querySelectorAll('.chip[data-chip]').forEach(function (chip) {
      chip.addEventListener('click', function () {
        document.querySelectorAll('.chip[data-chip]').forEach(function (c) {
          c.classList.remove('active');
        });
        chip.classList.add('active');
        applyFilters();
      });
    });
  });

})();
