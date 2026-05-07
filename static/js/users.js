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

  // ── Password change modal ──────────────────────────────────────────────────

  function openChangePasswordModal(userId, username) {
    var overlay = document.createElement('div');
    overlay.className = 'pw-modal-overlay';

    var modal = document.createElement('div');
    modal.className = 'pw-modal';
    modal.innerHTML =
      '<h3 class="pw-modal__title">Change password for <strong>' + username + '</strong></h3>' +
      '<div class="pw-modal__body">' +
        '<div class="form-group" style="margin-bottom:14px;">' +
          '<label class="form-label">New Password</label>' +
          '<input type="password" id="pwNew" class="form-control" autocomplete="new-password">' +
        '</div>' +
        '<div class="form-group" style="margin-bottom:14px;">' +
          '<label class="form-label">Confirm Password</label>' +
          '<input type="password" id="pwConfirm" class="form-control" autocomplete="new-password">' +
        '</div>' +
        '<p id="pwError" style="color:var(--error);font-size:13px;margin-bottom:10px;display:none;"></p>' +
        '<div style="display:flex;gap:10px;">' +
          '<button id="pwSave" class="btn btn-primary">Save</button>' +
          '<button id="pwCancel" class="btn btn-secondary">Cancel</button>' +
        '</div>' +
      '</div>';

    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    var pwNew     = modal.querySelector('#pwNew');
    var pwConfirm = modal.querySelector('#pwConfirm');
    var pwError   = modal.querySelector('#pwError');
    var pwSave    = modal.querySelector('#pwSave');
    var pwCancel  = modal.querySelector('#pwCancel');

    function closeModal() {
      if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
    }

    function showError(msg) {
      pwError.textContent = msg;
      pwError.style.display = 'block';
    }

    pwCancel.addEventListener('click', closeModal);
    overlay.addEventListener('click', function (e) {
      if (e.target === overlay) closeModal();
    });

    pwSave.addEventListener('click', function () {
      var np = pwNew.value;
      var cp = pwConfirm.value;
      if (np.length < 8) { showError('Password must be at least 8 characters.'); return; }
      if (np !== cp)     { showError('Passwords do not match.'); return; }
      pwError.style.display = 'none';
      pwSave.disabled = true;
      pwSave.textContent = 'Saving…';

      fetch('/users/change-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, new_password: np }),
      })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (data.success) {
            closeModal();
            showToast(data.message, 'success');
          } else {
            showError(data.message);
            pwSave.disabled = false;
            pwSave.textContent = 'Save';
          }
        })
        .catch(function () {
          showError('Request failed.');
          pwSave.disabled = false;
          pwSave.textContent = 'Save';
        });
    });

    pwNew.focus();
  }

  // ── Toggle admin ───────────────────────────────────────────────────────────

  function toggleAdmin(userId, username) {
    var confirmed = confirm(
      'Toggle admin status for "' + username + '"?\n\nThis will grant or revoke their admin access.'
    );
    if (!confirmed) return;

    fetch('/users/toggle-admin', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: userId }),
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.success) {
          showToast(data.message, 'success');
          setTimeout(function () { window.location.reload(); }, 800);
        } else {
          showToast(data.message, 'error');
        }
      })
      .catch(function () { showToast('Request failed.', 'error'); });
  }

  // ── Delete user ────────────────────────────────────────────────────────────

  function deleteUser(userId, username) {
    var confirmed = confirm(
      'Delete user "' + username + '"?\n\nThis action cannot be undone.'
    );
    if (!confirmed) return;

    fetch('/users/delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: userId }),
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.success) {
          var row = document.getElementById('user-row-' + userId);
          if (row) {
            row.style.transition = 'opacity 0.3s ease';
            row.style.opacity = '0';
            setTimeout(function () { row.parentNode && row.parentNode.removeChild(row); }, 300);
          }
          showToast(data.message, 'success');
        } else {
          showToast(data.message, 'error');
        }
      })
      .catch(function () { showToast('Request failed.', 'error'); });
  }

  // ── Event delegation for table buttons ────────────────────────────────────

  var tbody = document.getElementById('usersTableBody');
  if (tbody) {
    tbody.addEventListener('click', function (e) {
      var btn = e.target.closest('[data-action-user]');
      if (!btn || btn.disabled) return;
      var action   = btn.dataset.actionUser;
      var userId   = parseInt(btn.dataset.userId, 10);
      var username = btn.dataset.username;

      if (action === 'change-password') openChangePasswordModal(userId, username);
      else if (action === 'toggle-admin') toggleAdmin(userId, username);
      else if (action === 'delete') deleteUser(userId, username);
    });
  }

  // ── Add user form ──────────────────────────────────────────────────────────

  var addForm = document.getElementById('addUserForm');
  if (addForm) {
    addForm.addEventListener('submit', function (e) {
      e.preventDefault();
      var username = document.getElementById('newUsername').value.trim();
      var password = document.getElementById('newPassword').value;
      var confirm  = document.getElementById('confirmPassword').value;

      if (!username) { showToast('Username cannot be empty.', 'error'); return; }
      if (password.length < 8) { showToast('Password must be at least 8 characters.', 'error'); return; }
      if (password !== confirm) { showToast('Passwords do not match.', 'error'); return; }

      var formData = new FormData(addForm);
      fetch('/users/add', { method: 'POST', body: formData })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (data.success) {
            showToast(data.message, 'success');
            setTimeout(function () { window.location.reload(); }, 800);
          } else {
            showToast(data.message, 'error');
          }
        })
        .catch(function () { showToast('Request failed.', 'error'); });
    });
  }

  // ── Inline modal styles ────────────────────────────────────────────────────

  var style = document.createElement('style');
  style.textContent =
    '.pw-modal-overlay{position:fixed;inset:0;background:rgba(0,0,0,0.45);z-index:2000;display:flex;align-items:center;justify-content:center;}' +
    '.pw-modal{background:var(--surface);border-radius:var(--radius-modal);padding:28px;width:100%;max-width:380px;box-shadow:0 8px 32px rgba(0,0,0,0.18);}' +
    '.pw-modal__title{font-size:16px;font-weight:600;margin-bottom:18px;color:var(--text);}';
  document.head.appendChild(style);

})();
