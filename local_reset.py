import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "prototype.db")

def reset_local_db():
    if not os.path.exists(DB_PATH):
        print(f"Error: Database not found at {DB_PATH}")
        return

    print(f"Connecting to {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    try:
        # 1. Delete all student-specific data
        print("Clearing student data (responses, mastery, reports)...")
        c.execute("DELETE FROM responses")
        c.execute("DELETE FROM mastery_scores")
        c.execute("DELETE FROM weekly_reports")
        c.execute("DELETE FROM messages")
        c.execute("DELETE FROM sessions")
        c.execute("DELETE FROM enrollments")

        # 2. Delete all Quizzes and Assignments (to start fresh)
        print("Clearing quizzes and assignments...")
        c.execute("DELETE FROM quiz_questions")
        c.execute("DELETE FROM quizzes")
        c.execute("DELETE FROM assignment_questions")
        c.execute("DELETE FROM assignments")

        # 3. Delete non-Spanish classes and their curriculum
        print("Removing other classes and their curriculum...")
        # Delete questions for other courses
        c.execute("""
            DELETE FROM questions 
            WHERE topic_id IN (
                SELECT t.id FROM topics t 
                JOIN chapters ch ON t.chapter_id = ch.id 
                WHERE ch.course_id != '11111'
            )
        """)
        # Delete topics for other courses
        c.execute("""
            DELETE FROM topics 
            WHERE chapter_id IN (
                SELECT id FROM chapters 
                WHERE course_id != '11111'
            )
        """)
        # Delete chapters for other courses
        c.execute("DELETE FROM chapters WHERE course_id != '11111'")
        # Delete the courses themselves
        c.execute("DELETE FROM courses WHERE id != '11111'")

        # 4. Delete all student users
        print("Deleting student accounts...")
        c.execute("DELETE FROM users WHERE role = 'student'")

        conn.commit()
        print("\nSUCCESS: Local database reset complete.")
        print("Preserved: Lecturer account and Spanish 101 classroom structure.")
        
        # Verify
        c.execute("SELECT name FROM courses")
        remaining_courses = c.fetchall()
        print(f"Remaining classrooms: {[r[0] for r in remaining_courses]}")
        
        c.execute("SELECT name FROM users WHERE role='lecturer'")
        lecturers = c.fetchall()
        print(f"Preserved lecturers: {[r[0] for r in lecturers]}")

    except Exception as e:
        print(f"An error occurred: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    reset_local_db()
