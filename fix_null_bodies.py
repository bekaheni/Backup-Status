from app import db, BackupStatus

with db.app.app_context():
    updated = 0
    for status in BackupStatus.query.all():
        changed = False
        if status.body is None or status.body == "None":
            status.body = ""
            changed = True
        if hasattr(status, "html_body") and (status.html_body is None or status.html_body == "None"):
            status.html_body = ""
            changed = True
        if changed:
            updated += 1
    db.session.commit()
    print(f"Updated {updated} records with empty body/html_body.") 