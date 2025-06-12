from app import db, BackupStatus

with db.app.app_context():
    statuses = BackupStatus.query.order_by(BackupStatus.timestamp.desc()).limit(5).all()
    for s in statuses:
        print(f"Subject: {s.subject}")
        print(f"Body: {repr(s.body)[:500]}")
        print(f"HTML Body: {repr(s.html_body)[:500]}")
        print('-' * 60) 