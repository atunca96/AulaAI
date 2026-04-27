
import os
import sys
import json
from services.ai_engine import ai_generate_curriculum

def test():
    print("Testing ai_generate_curriculum for Russian A1...")
    try:
        chapters = ai_generate_curriculum("Russian", "A1")
        if chapters:
            print(f"SUCCESS: Generated {len(chapters)} chapters.")
            print(json.dumps(chapters[:1], indent=2))
        else:
            print("FAILURE: No chapters returned.")
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Load API key from .env manually if needed
    with open(".env", "r") as f:
        for line in f:
            if "=" in line:
                k, v = line.strip().split("=", 1)
                os.environ[k] = v
                
    test()
