"""
Mastery & Reporting services — Computes student mastery scores,
trends, risk flags, and generates weekly reports.
"""

import math
import json
import uuid
from datetime import datetime, timedelta
from collections import defaultdict

DECAY_LAMBDA = 0.1
MASTERY_LOW = 0.4
MASTERY_HIGH = 0.75
MIN_RESPONSES = 3


def _uid():
    return str(uuid.uuid4())


def compute_mastery(responses):
    """
    Compute mastery from a list of responses.
    Each response: dict with 'score' (float) and 'submitted_at' (str ISO).
    Returns: {score, confidence, classification}
    """
    if not responses:
        return {"score": 0.0, "confidence": "none", "classification": "unknown"}

    now = datetime.utcnow()
    weighted_sum = 0.0
    weight_total = 0.0

    for r in responses:
        submitted = r["submitted_at"] if isinstance(r["submitted_at"], datetime) else datetime.fromisoformat(r["submitted_at"])
        days_ago = (now - submitted).total_seconds() / 86400
        weight = math.exp(-DECAY_LAMBDA * max(days_ago, 0))
        weighted_sum += float(r["score"]) * weight
        weight_total += weight

    mastery = weighted_sum / weight_total if weight_total > 0 else 0.0

    n = len(responses)
    if n >= MIN_RESPONSES * 2:
        confidence = "high"
    elif n >= MIN_RESPONSES:
        confidence = "medium"
    else:
        confidence = "low"

    if mastery < MASTERY_LOW:
        classification = "struggling"
    elif mastery < MASTERY_HIGH:
        classification = "developing"
    else:
        classification = "proficient"

    return {
        "score": round(mastery, 3),
        "confidence": confidence,
        "classification": classification
    }


def compute_trend(weekly_scores):
    """
    Compute trend using linear regression over weekly scores.
    Returns: {slope, direction}
    """
    n = len(weekly_scores)
    if n < 2:
        return {"slope": 0.0, "direction": "insufficient_data"}

    x_mean = (n - 1) / 2
    y_mean = sum(weekly_scores) / n

    numerator = sum((i - x_mean) * (y - y_mean) for i, y in enumerate(weekly_scores))
    denominator = sum((i - x_mean) ** 2 for i in range(n))

    slope = numerator / denominator if denominator != 0 else 0.0

    if slope > 0.02:
        direction = "improving"
    elif slope < -0.02:
        direction = "declining"
    else:
        direction = "stable"

    return {"slope": round(slope, 4), "direction": direction}


def generate_risk_flags(mastery_score, trend_direction, engagement):
    """Flag at-risk students."""
    flags = []
    if mastery_score < MASTERY_LOW:
        flags.append("low_mastery")
    if trend_direction == "declining":
        flags.append("declining_performance")
    if engagement < 0.6:
        flags.append("low_engagement")
    if mastery_score < MASTERY_LOW and engagement < 0.5:
        flags.append("critical_risk")
    return flags


def generate_weekly_report(db_conn, course_id):
    """Generate a comprehensive weekly report for a course."""
    c = db_conn.cursor()

    # Get course info
    course = dict(c.execute("SELECT * FROM courses WHERE id = ?", (course_id,)).fetchone())

    # Get enrolled students
    students = c.execute("""
        SELECT u.* FROM users u
        JOIN enrollments e ON u.id = e.student_id
        WHERE e.course_id = ? AND u.role = 'student'
    """, (course_id,)).fetchall()
    students = [dict(s) for s in students]

    # Get all topics for this course
    topics = c.execute("""
        SELECT t.* FROM topics t
        JOIN chapters ch ON t.chapter_id = ch.id
        WHERE ch.course_id = ?
        ORDER BY ch.number, t.sort_order
    """, (course_id,)).fetchall()
    topics = [dict(t) for t in topics]

    student_reports = []
    mastery_values = []
    at_risk = []
    top_performers = []

    for student in students:
        topic_masteries = {}
        for topic in topics:
            # Get responses for this student-topic
            responses = c.execute("""
                SELECT r.score, r.submitted_at FROM responses r
                JOIN questions q ON r.question_id = q.id
                WHERE r.student_id = ? AND q.topic_id = ?
                ORDER BY r.submitted_at DESC
            """, (student["id"], topic["id"])).fetchall()
            responses = [dict(r) for r in responses]

            mastery = compute_mastery(responses)
            topic_masteries[topic["title"]] = mastery

        # Also check mastery_scores table
        stored_masteries = c.execute(
            "SELECT topic_id, score FROM mastery_scores WHERE student_id = ?",
            (student["id"],)
        ).fetchall()

        for sm in stored_masteries:
            topic_name = None
            for t in topics:
                if t["id"] == sm["topic_id"]:
                    topic_name = t["title"]
                    break
            if topic_name and topic_name not in topic_masteries:
                topic_masteries[topic_name] = {
                    "score": float(sm["score"]),
                    "confidence": "stored",
                    "classification": "proficient" if sm["score"] >= MASTERY_HIGH
                        else "developing" if sm["score"] >= MASTERY_LOW
                        else "struggling"
                }

        if topic_masteries:
            overall = sum(m["score"] for m in topic_masteries.values()) / len(topic_masteries)
        else:
            overall = 0.0
        mastery_values.append(overall)

        # Engagement: responses in last 7 days vs total questions available
        recent_responses = c.execute("""
            SELECT COUNT(*) as cnt FROM responses
            WHERE student_id = ? AND submitted_at >= datetime('now', '-7 days')
        """, (student["id"],)).fetchone()
        total_questions = len(topics) * 5  # Rough estimate
        engagement = min(1.0, (recent_responses["cnt"] / max(total_questions, 1)))

        # Trend (mock weekly history for prototype)
        weekly_history = [max(0, overall + (i - 2) * 0.05) for i in range(4)]
        trend = compute_trend(weekly_history)

        weak_topics = [t for t, m in topic_masteries.items() if m["score"] < 0.5]
        flags = generate_risk_flags(overall, trend["direction"], engagement)

        # Generate personalized AI evaluation code
        if overall > 0.85:
            eval_code = "excellent"
        elif overall > 0.70:
            eval_code = "good"
        elif overall > 0.50:
            eval_code = "fluctuating"
        elif engagement == 0:
            eval_code = "inactive"
        else:
            eval_code = "critical"

        report = {
            "student_id": student["id"],
            "name": student["name"],
            "overall_mastery": round(overall, 3),
            "trend": trend,
            "engagement": round(engagement, 3),
            "weak_topics": weak_topics,
            "strong_topics": [t for t, m in topic_masteries.items() if m["score"] >= 0.75],
            "flags": flags,
            "eval_code": eval_code,
            "topic_details": {k: v["score"] for k, v in topic_masteries.items()}
        }
        student_reports.append(report)

        if flags:
            at_risk.append(report)
        if overall >= 0.8:
            top_performers.append(report)

    # Topic difficulty ranking (class-wide)
    topic_difficulty = {}
    for topic in topics:
        scores = []
        for sr in student_reports:
            if topic["title"] in sr.get("topic_details", {}):
                scores.append(sr["topic_details"][topic["title"]])
        if scores:
            topic_difficulty[topic["title"]] = round(sum(scores) / len(scores), 3)

    # Topics needing review
    review_topics = []
    for topic_name, avg_score in topic_difficulty.items():
        if avg_score < 0.5:
            review_topics.append({"topic": topic_name, "avg_mastery": avg_score})

    # Sort reports
    at_risk.sort(key=lambda x: x["overall_mastery"])
    top_performers.sort(key=lambda x: x["overall_mastery"], reverse=True)
    student_reports.sort(key=lambda x: x["name"])

    week_number = datetime.utcnow().isocalendar()[1]

    report = {
        "course_id": course_id,
        "course_name": course["name"],
        "week_number": week_number,
        "generated_at": datetime.utcnow().isoformat(),
        "summary": {
            "total_students": len(students),
            "active_students": sum(1 for sr in student_reports if sr["engagement"] > 0),
            "class_avg_mastery": round(sum(mastery_values) / max(len(mastery_values), 1), 3),
            "at_risk_count": len(at_risk),
            "top_performer_count": len(top_performers),
        },
        "topic_difficulty": dict(sorted(topic_difficulty.items(), key=lambda x: x[1])),
        "review_topics": review_topics,
        "at_risk_students": at_risk[:5],
        "top_performers": top_performers[:5],
        "student_reports": student_reports,
    }

    # Store the report
    try:
        c.execute(
            "INSERT OR REPLACE INTO weekly_reports VALUES (?,?,?,?,datetime('now'))",
            (_uid(), course_id, week_number, json.dumps(report))
        )
        db_conn.commit()
    except Exception:
        pass

    return report
