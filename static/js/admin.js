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

  function clearDatabase(emailType, btn) {
    var label = emailType === 'server' ? 'server' : 'NAS';
    var confirmed = confirm(
      'This will permanently delete all ' + label + ' backup records from the database.\n\nThis action cannot be undone. Continue?'
    );
    if (!confirmed) return;

    setButtonLoading(btn, true);
    fetch('/clear-database', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email_type: emailType }),
    })
      .then(function (res) { return res.json(); })
      .then(function (data) {
        showToast(data.message, data.success ? 'success' : 'error');
      })
      .catch(function () {
        showToast('Request failed — check the network tab for details.', 'error');
      })
      .finally(function () {
        setButtonLoading(btn, false);
      });
  }

  function deleteOldEmails(btn) {
    var confirmed = confirm(
      'This will permanently delete emails older than 10 days from both inboxes.\n\nThis action cannot be undone. Continue?'
    );
    if (!confirmed) return;

    setButtonLoading(btn, true);
    fetch('/delete-old-emails', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email_type: 'server' }),
    })
      .then(function (res) { return res.json(); })
      .then(function (data) {
        showToast(data.message, data.success ? 'success' : 'error');
      })
      .catch(function () {
        showToast('Request failed — check the network tab for details.', 'error');
      })
      .finally(function () {
        setButtonLoading(btn, false);
      });
  }

  document.querySelectorAll('[data-action]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var action = btn.dataset.action;
      if (action === 'clear-server') {
        clearDatabase('server', btn);
      } else if (action === 'clear-nas') {
        clearDatabase('nas', btn);
      } else if (action === 'delete-emails') {
        deleteOldEmails(btn);
      }
    });
  });
})();
