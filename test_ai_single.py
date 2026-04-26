from services.ai_engine import ai_generate_single_activity
import json

topic_content = {"words": {"Hund": "Dog", "Katze": "Cat"}}
print("Testing single generation...")
try:
    act = ai_generate_single_activity("Animals", "vocabulary", topic_content, "German", 1)
    print("Success:", json.dumps(act, indent=2))
except Exception as e:
    import traceback
    traceback.print_exc()
