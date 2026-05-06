// Modal functionality for email details
document.addEventListener('DOMContentLoaded', function () {
    var emailModal = document.getElementById('emailModal');
    if (emailModal) {
        emailModal.addEventListener('show.bs.modal', function (event) {
            var button = event.relatedTarget;
            document.getElementById('modalServer').textContent = button.getAttribute('data-server');
            document.getElementById('modalSubject').textContent = button.getAttribute('data-subject');
            document.getElementById('modalTimestamp').textContent = button.getAttribute('data-timestamp');
            
            // Sanitize email body content
            var emailBody = button.getAttribute('data-body');
            var sanitizedBody = sanitizeEmailContent(emailBody);
            document.getElementById('modalBody').textContent = sanitizedBody;
        });
    }
});

function copyEmailBody(btn) {
    var body = document.getElementById('modalBody').textContent;
    navigator.clipboard.writeText(body).then(function () {
        var original = btn.textContent;
        btn.textContent = 'Copied!';
        setTimeout(function () { btn.textContent = original; }, 1500);
    });
}

// Function to sanitize email content
function sanitizeEmailContent(htmlContent) {
    if (!htmlContent) return '';
    
    // Create a temporary div to parse HTML
    var tempDiv = document.createElement('div');
    tempDiv.innerHTML = htmlContent;
    
    // Remove script tags and style tags
    var scripts = tempDiv.querySelectorAll('script, style');
    scripts.forEach(function(script) {
        script.remove();
    });
    
    // Get text content and clean it up
    var textContent = tempDiv.textContent || tempDiv.innerText || '';
    
    // Clean up common email artifacts
    textContent = textContent
        .replace(/Running Altaro VM Backup Free Edition.*?paid editions\./g, '')
        .replace(/Click here to learn more.*?paid editions\./g, '')
        .replace(/Altaro VM Backup.*?www\.altaro\.com/g, '')
        .replace(/http:\/\/www\.altaro\.com/g, '')
        .replace(/--------------------------------------------------------------------------------/g, '')
        .replace(/\n\s*\n\s*\n/g, '\n\n') // Remove excessive line breaks
        .trim();
    
    return textContent;
}

