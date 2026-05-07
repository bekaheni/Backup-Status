(function () {
  'use strict';

  var container = document.getElementById('toastContainer');

  function showToast(message, type) {
    if (!container) return;
    var toast = document.createElement('div');
    toast.className = 'toast toast--' + (type || 'info');
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(function () {
      if (toast.parentNode) toast.parentNode.removeChild(toast);
    }, 4000);
  }

  function setButtonLoading(btn, loading) {
    btn.disabled = loading;
    if (loading) {
      btn.dataset.originalText = btn.textContent;
      btn.textContent = 'Working…';
    } else {
      btn.textContent = btn.dataset.originalText || btn.textContent;
    }
  }

  function postJSON(url, body, btn, onSuccess) {
    if (btn) setButtonLoading(btn, true);
    fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
      .then(function (res) { return res.json(); })
      .then(function (data) {
        showToast(data.message, data.success ? 'success' : 'error');
        if (data.success && onSuccess) onSuccess(data);
      })
      .catch(function () {
        showToast('Request failed — check the network tab for details.', 'error');
      })
      .finally(function () {
        if (btn) setButtonLoading(btn, false);
      });
  }

  // ── Danger zone ─────────────────────────────────────────────────────────────

  function clearDatabase(emailType, btn) {
    var label = emailType === 'server' ? 'server' : 'NAS';
    if (!confirm('This will permanently delete all ' + label + ' backup records from the database.\n\nThis action cannot be undone. Continue?')) return;
    postJSON('/clear-database', { email_type: emailType }, btn, null);
  }

  function deleteOldEmails(btn) {
    if (!confirm('This will permanently delete emails older than 10 days from both inboxes.\n\nThis action cannot be undone. Continue?')) return;
    postJSON('/delete-old-emails', { email_type: 'server' }, btn, null);
  }

  document.querySelectorAll('[data-action]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var action = btn.dataset.action;
      if (action === 'clear-server') clearDatabase('server', btn);
      else if (action === 'clear-nas') clearDatabase('nas', btn);
      else if (action === 'delete-emails') deleteOldEmails(btn);
    });
  });

  // ── Scheduler interval edit ──────────────────────────────────────────────────

  var editBtn = document.getElementById('editSchedulerBtn');
  var editForm = document.getElementById('schedulerEditForm');
  var cancelBtn = document.getElementById('cancelSchedulerBtn');
  var saveSchedulerBtn = document.getElementById('saveSchedulerBtn');
  var schedulerInput = document.getElementById('schedulerIntervalInput');
  var schedulerDisplay = document.getElementById('schedulerDisplay');

  if (editBtn) {
    editBtn.addEventListener('click', function () {
      editForm.style.display = 'flex';
      editBtn.style.display = 'none';
      if (schedulerInput) schedulerInput.focus();
    });
  }

  if (cancelBtn) {
    cancelBtn.addEventListener('click', function () {
      editForm.style.display = 'none';
      editBtn.style.display = '';
    });
  }

  if (saveSchedulerBtn) {
    saveSchedulerBtn.addEventListener('click', function () {
      var val = parseInt(schedulerInput.value, 10);
      if (isNaN(val) || val < 1 || val > 60) {
        showToast('Interval must be between 1 and 60 minutes.', 'error');
        return;
      }
      postJSON('/configuration/save-settings', { scheduler_interval_minutes: val }, saveSchedulerBtn, function () {
        var label = 'Every ' + val + ' minute' + (val === 1 ? '' : 's');
        if (schedulerDisplay) schedulerDisplay.textContent = label;
        editForm.style.display = 'none';
        if (editBtn) editBtn.style.display = '';
      });
    });
  }

  // ── AI parsing toggle ────────────────────────────────────────────────────────

  var aiToggle = document.getElementById('aiParsingToggle');
  var aiLabel = document.getElementById('aiParsingLabel');

  if (aiToggle) {
    aiToggle.addEventListener('change', function () {
      var enabled = aiToggle.checked;
      postJSON('/configuration/save-settings', { ai_parsing_enabled: enabled }, null, function () {
        if (aiLabel) aiLabel.textContent = enabled ? 'Enabled' : 'Disabled';
      });
    });
  }

  // ── Prompt save / reset ──────────────────────────────────────────────────────

  document.querySelectorAll('[data-save-prompt]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var emailType = btn.dataset.savePrompt;
      var textarea = document.getElementById(emailType === 'server' ? 'serverPrompt' : 'nasPrompt');
      if (!textarea || !textarea.value.trim()) {
        showToast('Prompt cannot be empty.', 'error');
        return;
      }
      postJSON('/configuration/save-prompt', { email_type: emailType, prompt: textarea.value }, btn, null);
    });
  });

  document.querySelectorAll('[data-reset-prompt]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var emailType = btn.dataset.resetPrompt;
      var label = emailType === 'server' ? 'server' : 'NAS';
      if (!confirm('Reset the ' + label + ' prompt to the built-in default?\n\nThis will overwrite any custom changes.')) return;
      postJSON('/configuration/reset-prompt', { email_type: emailType }, btn, function (data) {
        var textarea = document.getElementById(emailType === 'server' ? 'serverPrompt' : 'nasPrompt');
        if (textarea && data.prompt) textarea.value = data.prompt;
      });
    });
  });

})();
