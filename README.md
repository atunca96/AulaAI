# AulaAI — Spanish Learning System

AI-integrated prototype for Aula Internacional Plus 1.

## How to Run

**Double-click `start.bat`** — that's it. It opens the app in your browser automatically.

Or from the terminal:
```
python server.py
```
Then go to http://localhost:3000

## Demo Accounts

| Role | Email | Password |
|------|-------|----------|
| Lecturer | garcia@university.edu | demo123 |
| Student | alejandro@student.edu | student123 |

## What's Inside

- **server.py** — Main HTTP server (zero external dependencies, pure Python)
- **database.py** — SQLite database with full Aula Internacional Plus 1 curriculum
- **services/** — Content engine, mastery algorithm, report generator
- **public/** — Frontend (HTML/CSS/JS)
- **data/** — SQLite database file (auto-created on first run)

## Features

- Lecturer dashboard with class overview
- Full curriculum viewer (Units 1-6)
- Activity generator (MCQ, fill-in-the-blank, dialogue ordering)
- Quiz creation and auto-graded quiz taking
- Student roster with per-student mastery drill-down
- AI-generated weekly reports with at-risk detection
- Student practice mode and progress tracking
