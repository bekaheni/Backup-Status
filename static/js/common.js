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