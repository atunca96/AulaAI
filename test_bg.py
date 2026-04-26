from database import db_connection
import json
import uuid

def _uid(): return str(uuid.uuid4())

def test():
    from services.ai_engine import ai_generate_single_activity
    with db_connection() as db:
        topic = dict(db.execute("SELECT * FROM topics LIMIT 1").fetchone())
        course = dict(db.execute("SELECT * FROM courses LIMIT 1").fetchone())
    
    print("Topic:", topic["title"])
    print("Course Lang:", course["language"])
    
    content = json.loads(topic["content"]) if isinstance(topic.get("content"), str) else topic.get("content", {})
    
    act = ai_generate_single_activity(topic["title"], topic.get("type", "vocabulary"), content, course.get("language", "Spanish"), index=1)
    if act:
        act["id"] = _uid()
        print("Success!", act)
    else:
        print("Returned None!")

if __name__ == "__main__":
    test()
