from database import db_connection

def migrate():
    with db_connection() as db:
        try:
            db.execute("ALTER TABLE courses ADD COLUMN progress INTEGER DEFAULT 0")
        except: pass
        try:
            db.execute("ALTER TABLE courses ADD COLUMN total_steps INTEGER DEFAULT 0")
        except: pass
        db.commit()
    print("Migration complete.")

if __name__ == "__main__":
    migrate()
