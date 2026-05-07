(function () {
  'use strict';

  var toastContainer = document.getElementById('toastContainer');

  function showToast(message, type) {
    if (!toastContainer) return;
    var toast = document.createElement('div');
    toast.className = 'toast toast--' + (type || 'info');
    toast.textContent = message;
    toastContainer.appendChild(toast);
    setTimeout(function () {
      if (toast.parentNode) toast.parentNode.removeChild(toast);
    }, 4000);
  }

  function postJSON(url, body) {
    return fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }).then(function (r) { return r.json(); });
  }

  // ── Rendering ──────────────────────────────────────────────────────────────

  function renderServerGroup(company, emailType, label) {
    var group = document.createElement('div');
    group.className = 'company-server-group';

    var title = document.createElement('div');
    title.className = 'company-server-group__title';
    title.textContent = label;
    group.appendChild(title);

    var tagsDiv = document.createElement('div');
    tagsDiv.className = 'server-tags';

    var servers = company[emailType] || [];
    servers.forEach(function (srv) {
      var tag = document.createElement('span');
      tag.className = 'server-tag';
      tag.textContent = srv.name;

      var removeBtn = document.createElement('button');
      removeBtn.className = 'server-tag__remove';
      removeBtn.title = 'Remove';
      removeBtn.innerHTML = '&times;';
      (function (serverId) {
        removeBtn.addEventListener('click', function () {
          deleteServer(serverId);
        });
      }(srv.id));

      tag.appendChild(removeBtn);
      tagsDiv.appendChild(tag);
    });

    group.appendChild(tagsDiv);

    // Add server row
    var addRow = document.createElement('div');
    addRow.className = 'server-add-row';

    var input = document.createElement('input');
    input.type = 'text';
    input.placeholder = 'Server name…';
    addRow.appendChild(input);

    var addBtn = document.createElement('button');
    addBtn.className = 'btn btn-secondary';
    addBtn.style.fontSize = '12px';
    addBtn.style.padding = '4px 10px';
    addBtn.textContent = 'Add';
    (function (cid, etype) {
      addBtn.addEventListener('click', function () {
        addServer(cid, input.value, etype, input, addBtn);
      });
      input.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') addBtn.click();
      });
    }(company.id, emailType));

    addRow.appendChild(addBtn);
    group.appendChild(addRow);

    return group;
  }

  function renderCompanyCard(company) {
    var card = document.createElement('div');
    card.className = 'company-card';
    card.dataset.companyId = company.id;

    // Header
    var header = document.createElement('div');
    header.className = 'company-card__header';

    var nameSpan = document.createElement('span');
    nameSpan.className = 'company-card__name';
    nameSpan.textContent = company.name;
    header.appendChild(nameSpan);

    var editBtn = document.createElement('button');
    editBtn.className = 'btn-icon';
    editBtn.title = 'Rename';
    editBtn.innerHTML = '<i class="fas fa-pencil-alt" style="font-size:12px;"></i>';
    (function (co, hdr, ns, eb) {
      editBtn.addEventListener('click', function () {
        startRename(hdr, ns, eb, co);
      });
    }(company, header, nameSpan, editBtn));
    header.appendChild(editBtn);

    var delBtn = document.createElement('button');
    delBtn.className = 'btn-icon btn-icon--danger';
    delBtn.title = 'Delete company';
    delBtn.innerHTML = '<i class="fas fa-trash" style="font-size:12px;"></i>';
    (function (co) {
      delBtn.addEventListener('click', function () { confirmDeleteCompany(co); });
    }(company));
    header.appendChild(delBtn);

    card.appendChild(header);

    // Body
    var body = document.createElement('div');
    body.className = 'company-card__body';
    body.appendChild(renderServerGroup(company, 'server', 'Server Backups'));
    body.appendChild(renderServerGroup(company, 'nas', 'NAS Backups'));
    card.appendChild(body);

    return card;
  }

  function renderCompanies(companies) {
    var list = document.getElementById('companiesList');
    if (!list) return;
    list.innerHTML = '';
    if (!companies.length) {
      list.innerHTML = '<p style="color: var(--muted); font-size: 14px;">No companies configured yet.</p>';
      return;
    }
    companies.forEach(function (c) { list.appendChild(renderCompanyCard(c)); });
  }

  // ── Data loading ───────────────────────────────────────────────────────────

  function loadCompanies() {
    fetch('/configuration/companies')
      .then(function (r) { return r.json(); })
      .then(renderCompanies)
      .catch(function () { showToast('Failed to load companies.', 'error'); });
  }

  // ── Inline rename ──────────────────────────────────────────────────────────

  function startRename(header, nameSpan, editBtn, company) {
    var input = document.createElement('input');
    input.type = 'text';
    input.className = 'company-card__name-input';
    input.value = company.name;
    header.replaceChild(input, nameSpan);

    var saveBtn = document.createElement('button');
    saveBtn.className = 'btn-icon';
    saveBtn.title = 'Save';
    saveBtn.innerHTML = '<i class="fas fa-check" style="font-size:12px; color: var(--accent);"></i>';
    header.replaceChild(editBtn, editBtn);

    var cancelBtn = document.createElement('button');
    cancelBtn.className = 'btn-icon';
    cancelBtn.title = 'Cancel';
    cancelBtn.innerHTML = '<i class="fas fa-times" style="font-size:12px;"></i>';

    // Replace edit button with save + cancel
    header.replaceChild(saveBtn, editBtn);
    header.insertBefore(cancelBtn, saveBtn.nextSibling);

    input.focus();
    input.select();

    function doSave() {
      var newName = input.value.trim();
      if (!newName) { showToast('Company name cannot be empty.', 'error'); return; }
      saveBtn.disabled = true;
      postJSON('/configuration/companies/rename', { company_id: company.id, name: newName })
        .then(function (data) {
          if (data.success) {
            company.name = newName;
            loadCompanies();
          } else {
            showToast(data.message, 'error');
            saveBtn.disabled = false;
          }
        })
        .catch(function () { showToast('Request failed.', 'error'); saveBtn.disabled = false; });
    }

    saveBtn.addEventListener('click', doSave);
    cancelBtn.addEventListener('click', loadCompanies);
    input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') doSave();
      if (e.key === 'Escape') loadCompanies();
    });
  }

  // ── CRUD operations ────────────────────────────────────────────────────────

  function addCompany() {
    var input = document.getElementById('newCompanyInput');
    var btn = document.getElementById('addCompanyBtn');
    var name = (input.value || '').trim();
    if (!name) { showToast('Company name cannot be empty.', 'error'); return; }

    btn.disabled = true;
    postJSON('/configuration/companies/add', { name: name })
      .then(function (data) {
        if (data.success) {
          input.value = '';
          loadCompanies();
          showToast('Company "' + data.name + '" added.', 'success');
        } else {
          showToast(data.message, 'error');
        }
      })
      .catch(function () { showToast('Request failed.', 'error'); })
      .finally(function () { btn.disabled = false; });
  }

  function confirmDeleteCompany(company) {
    var hasEntries = (company.server && company.server.length) || (company.nas && company.nas.length);
    var msg = 'Delete company "' + company.name + '"?';
    if (hasEntries) msg += '\n\nAll server entries for this company will also be deleted.';
    if (!confirm(msg)) return;

    postJSON('/configuration/companies/delete', { company_id: company.id })
      .then(function (data) {
        if (data.success) {
          loadCompanies();
          showToast('Company deleted.', 'success');
        } else {
          showToast(data.message, 'error');
        }
      })
      .catch(function () { showToast('Request failed.', 'error'); });
  }

  function addServer(companyId, name, emailType, input, btn) {
    name = (name || '').trim();
    if (!name) { showToast('Server name cannot be empty.', 'error'); return; }

    btn.disabled = true;
    postJSON('/configuration/servers/add', { company_id: companyId, name: name, email_type: emailType })
      .then(function (data) {
        if (data.success) {
          input.value = '';
          loadCompanies();
          showToast('Server added.', 'success');
        } else {
          showToast(data.message, 'error');
        }
      })
      .catch(function () { showToast('Request failed.', 'error'); })
      .finally(function () { btn.disabled = false; });
  }

  function deleteServer(serverId) {
    if (!confirm('Remove this server entry?')) return;
    postJSON('/configuration/servers/delete', { server_id: serverId })
      .then(function (data) {
        if (data.success) {
          loadCompanies();
          showToast('Server removed.', 'success');
        } else {
          showToast(data.message, 'error');
        }
      })
      .catch(function () { showToast('Request failed.', 'error'); });
  }

  // ── Init ───────────────────────────────────────────────────────────────────

  var addCompanyBtn = document.getElementById('addCompanyBtn');
  var newCompanyInput = document.getElementById('newCompanyInput');

  if (addCompanyBtn) {
    addCompanyBtn.addEventListener('click', addCompany);
  }
  if (newCompanyInput) {
    newCompanyInput.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') addCompany();
    });
  }

  loadCompanies();

})();
