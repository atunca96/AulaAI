from database import db_connection

def check_building():
    with db_connection() as db:
        res = db.execute("SELECT is_building FROM courses WHERE id='515fdee7-c368-4033-8380-5f752eab4ace'").fetchone()
        print(f"Is Building: {res[0] if res else 'Not Found'}")

if __name__ == "__main__":
    check_building()
