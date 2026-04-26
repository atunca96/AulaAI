from database import db_connection
import json

def check_topic():
    with db_connection() as db:
        row = db.execute("SELECT title, content FROM topics WHERE title LIKE '%Kleidung%'").fetchone()
        if row:
            print(f"Title: {row[0]}")
            print(f"Content length: {len(row[1]) if row[1] else 0}")
            print(f"Content: {row[1][:200]}...")
        else:
            print("Topic not found")

if __name__ == "__main__":
    check_topic()
