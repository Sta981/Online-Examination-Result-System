# Online Examination & Result System

A web-based exam platform built with Python and Streamlit. Students can take timed MCQ and short-answer exams, and teachers can create, edit, and monitor them — all through a browser interface with no separate server setup required.

**Live Demo:** [exampro.streamlit.app](https://examprooo.streamlit.app/) 

---

## Features

**For Students**
- Login with any username (must contain the word `student`) and any password
- Account created automatically on first login — same password required on return
- Take timed exams with an auto-submit countdown
- View scores, grades, and per-question breakdown immediately after submission
- Track performance over time through an analytics dashboard

**For Teachers**
- Login with any username containing the word `teacher`
- Account persisted in DB — same password required on return
- Create exams with MCQ and short-answer questions
- Set time limits, marks per question, and topics
- Edit any exam after creation — title, subject, duration, questions, options, correct answers
- View all student submissions and per-exam leaderboards

---

## Project Structure

```
exam_system/
├── app.py            # Frontend — all Streamlit pages and UI
├── backend.py        # Backend — database, OOP classes, grading logic
├── requirements.txt  # Python dependencies
└── README.md
```

The database (`exam_system.db`) and log file (`exam_system.log`) are created automatically on first run.

---

## OOP Concepts Used

This project was built as a demonstration of core Object-Oriented Programming concepts.

| Concept | Where Used |
|---|---|
| Abstract Class | `Question` — base class with abstract `grade()` method |
| Inheritance | `MCQQuestion` and `ShortAnswerQuestion` both extend `Question` |
| Singleton Pattern | `ExamLogger` — only one logger instance exists throughout runtime |
| Encapsulation | All DB logic is encapsulated inside backend functions |
| Polymorphism | `grade()` behaves differently for MCQ vs short-answer questions |

---

## How Login Works

No fixed accounts. Anyone can log in using a username that follows this rule:

| Role | Username Rule | Example |
|---|---|---|
| Student | Must contain the word `student` | `student_ali`, `sara_student` |
| Teacher | Must contain the word `teacher` | `teacher_sara`, `mr_teacher` |

First login creates the account. Returning users must use the same password they set on first login. Wrong password = access denied.

---

## Setup & Installation

**Requirements:** Python 3.9 or higher

**Step 1 — Clone or download the project**
```
exam_system/
├── app.py
├── backend.py
└── requirements.txt
```

**Step 2 — Install dependencies**
```bash
pip install -r requirements.txt
```

**Step 3 — Run the app**
```bash
streamlit run app.py
```

The app will open in your browser at `http://localhost:8501`

---

## Deployment

Deployed on [Streamlit Community Cloud](https://examprooo.streamlit.app/).

---

## Dependencies

| Package | Version | Purpose |
|---|---|---|
| streamlit | >=1.32.0 | Web UI framework |
| pandas | >=2.0.0 | Data tables and charts |
| tabulate | >=0.9.0 | Text-based leaderboard reports |

SQLite is used for the database — part of Python's standard library, no installation needed.

---

## Database Schema

Four tables are created automatically:

**students**
- `student_id`, `name`, `email`, `password_hash`

**teachers**
- `teacher_id`, `username`, `password_hash`

**exams**
- `exam_id`, `title`, `subject`, `duration_minutes`, `questions_json`

**results**
- `result_id`, `student_id`, `exam_id`, `answers_json`, `scores_json`, `total_score`, `total_marks`, `time_taken_seconds`, `submitted_at`

Questions are stored as JSON inside the `exams` table. Each result stores the student's answers and per-question scores as JSON as well.

---

## Grading Logic

**MCQ:** Full marks if the selected option matches the correct answer. Zero otherwise.

**Short Answer:** The student's response is checked for keywords defined by the teacher. Marks are awarded proportionally based on how many keywords appear in the answer.

| Grade | Percentage |
|---|---|
| A+ | 90% and above |
| A  | 80 – 89% |
| B  | 70 – 79% |
| C  | 60 – 69% |
| D  | 50 – 59% |
| F  | Below 50% |

---
