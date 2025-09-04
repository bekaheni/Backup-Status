// Initialize email modal
const emailModal = document.getElementById('emailModal');
if (emailModal) {
    emailModal.addEventListener('show.bs.modal', function (event) {
        const button = event.relatedTarget;
        const server = button.getAttribute('data-server');
        const subject = button.getAttribute('data-subject');
        const timestamp = button.getAttribute('data-timestamp');
        const body = button.getAttribute('data-body');

        document.getElementById('modalServer').textContent = server;
        document.getElementById('modalSubject').textContent = subject;
        document.getElementById('modalTimestamp').textContent = timestamp;
        document.getElementById('modalBody').innerHTML = (!body || body.trim() === "" || body.trim() === "None") ? "No email body available" : body;
    });
}

// Database clearing function
function clearDatabase(emailType) {
    if (confirm(`Are you sure you want to clear the database for ${emailType.toUpperCase()} backups? This action cannot be undone.`)) {
        fetch('/clear-database', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ email_type: emailType })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert(data.message);
                window.location.reload();
            } else {
                alert('Error: ' + data.message);
            }
        })
        .catch(error => {
            alert('Error: ' + error);
        });
    }
}

// Delete old emails function
function deleteOldEmails(emailType) {
    if (confirm('Are you sure you want to delete old emails? This action cannot be undone.')) {
        fetch('/delete-old-emails', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ email_type: emailType })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert(data.message);
                window.location.reload();
            } else {
                alert('Error: ' + data.message);
            }
        })
        .catch(error => {
            alert('Error: ' + error);
        });
    }
}

// Combined refresh function - clears database and deletes old emails for both server and NAS
function refreshAllData() {
    if (confirm('Are you sure you want to refresh all data? This will clear both Server and NAS databases and delete old emails. This action cannot be undone.')) {
        // Show loading message
        const button = event.target;
        const originalText = button.textContent;
        button.textContent = 'Refreshing...';
        button.disabled = true;
        
        // Clear server database
        fetch('/clear-database', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ email_type: 'server' })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                console.log('Server database cleared:', data.message);
                // Delete old server emails
                return fetch('/delete-old-emails', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ email_type: 'server' })
                });
            } else {
                throw new Error('Server database clear failed: ' + data.message);
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                console.log('Server emails deleted:', data.message);
                // Clear NAS database
                return fetch('/clear-database', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ email_type: 'nas' })
                });
            } else {
                throw new Error('Server email deletion failed: ' + data.message);
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                console.log('NAS database cleared:', data.message);
                // Delete old NAS emails
                return fetch('/delete-old-emails', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ email_type: 'nas' })
                });
            } else {
                throw new Error('NAS database clear failed: ' + data.message);
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                console.log('NAS emails deleted:', data.message);
                alert('All data refreshed successfully! Both Server and NAS databases have been cleared and old emails deleted.');
                window.location.reload();
            } else {
                throw new Error('NAS email deletion failed: ' + data.message);
            }
        })
        .catch(error => {
            console.error('Error during refresh:', error);
            alert('Error during refresh: ' + error.message);
        })
        .finally(() => {
            // Restore button state
            button.textContent = originalText;
            button.disabled = false;
        });
    }
} 