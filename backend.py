import sqlite3
import json
import hashlib
import logging
import statistics
from abc import ABC, abstractmethod
from datetime import datetime
from tabulate import tabulate


class ExamLogger:
    """Singleton pattern — only ONE logger instance ever exists."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            logging.basicConfig(
                filename="exam_system.log",
                level=logging.INFO,
                format="%(asctime)s | %(levelname)s | %(message)s"
            )
            cls._instance.log = logging.getLogger("ExamSystem")
        return cls._instance

    def info(self, msg):    self.log.info(msg)
    def warning(self, msg): self.log.warning(msg)
    def error(self, msg):   self.log.error(msg)


logger = ExamLogger()  # Only one instance, always


class Question(ABC):
    """Abstract base class — all question types must implement grade()."""

    def __init__(self, qid, text, marks, topic):
        self.qid   = qid
        self.text  = text
        self.marks = marks
        self.topic = topic

    @abstractmethod
    def grade(self, answer):
        """Return marks awarded for the given student answer."""
        pass

    @abstractmethod
    def to_dict(self):
        """Serialize to dict for JSON storage."""
        pass

    @property
    @abstractmethod
    def q_type(self):
        pass


class MCQQuestion(Question):
    """Multiple choice — full marks if correct, zero otherwise."""

    def __init__(self, qid, text, marks, topic, options, correct_index):
        super().__init__(qid, text, marks, topic)
        self.options       = options        # list of 4 strings
        self.correct_index = correct_index  # 0-based

    @property
    def q_type(self): return "MCQ"

    def grade(self, answer):
        # answer is "A", "B", "C", or "D"
        mapping = {"A": 0, "B": 1, "C": 2, "D": 3}
        chosen = mapping.get(str(answer).strip().upper(), -1)
        return self.marks if chosen == self.correct_index else 0

    def to_dict(self):
        return {
            "qid": self.qid, "type": "MCQ", "text": self.text,
            "marks": self.marks, "topic": self.topic,
            "options": self.options, "correct_index": self.correct_index
        }


class ShortAnswerQuestion(Question):
    """Short answer — partial marks based on keywords matched."""

    def __init__(self, qid, text, marks, topic, keywords, sample_answer):
        super().__init__(qid, text, marks, topic)
        self.keywords      = [k.lower().strip() for k in keywords]
        self.sample_answer = sample_answer

    @property
    def q_type(self): return "Short Answer"

    def grade(self, answer):
        if not answer or not answer.strip():
            return 0
        answer_lower = answer.lower()
        matched = sum(1 for kw in self.keywords if kw in answer_lower)
        ratio   = matched / len(self.keywords) if self.keywords else 0
        return round(self.marks * ratio)

    def to_dict(self):
        return {
            "qid": self.qid, "type": "ShortAnswer", "text": self.text,
            "marks": self.marks, "topic": self.topic,
            "keywords": self.keywords, "sample_answer": self.sample_answer
        }



DB_PATH = "data/exam_system.db"


def get_conn():
    import os; os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS students (
            student_id    INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT NOT NULL,
            email         TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS exams (
            exam_id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title            TEXT NOT NULL,
            subject          TEXT NOT NULL,
            duration_minutes INTEGER NOT NULL,
            questions_json   TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS results (
            result_id          INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id         INTEGER NOT NULL,
            exam_id            INTEGER NOT NULL,
            answers_json       TEXT NOT NULL,
            scores_json        TEXT NOT NULL,
            total_score        INTEGER NOT NULL,
            total_marks        INTEGER NOT NULL,
            time_taken_seconds INTEGER NOT NULL,
            submitted_at       TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS teachers (
            teacher_id    INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        );
        """)
    logger.info("Database ready.")



def hash_pw(password):
    return hashlib.sha256(password.encode()).hexdigest()

def register_student(name, email, password):
    try:
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO students (name, email, password_hash) VALUES (?,?,?)",
                (name, email, hash_pw(password))
            )
        logger.info(f"Registered: {email}")
        return True
    except sqlite3.IntegrityError:
        return False  # email already exists

def login_student(email, password):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM students WHERE email=? AND password_hash=?",
            (email, hash_pw(password))
        ).fetchone()
    return dict(row) if row else None

def get_student(student_id):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM students WHERE student_id=?", (student_id,)).fetchone()
    return dict(row) if row else None

def get_all_students():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM students ORDER BY name").fetchall()
    return [dict(r) for r in rows]



def register_teacher(username, password):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO teachers (username, password_hash) VALUES (?,?)",
            (username.lower(), hash_pw(password))
        )
    logger.info(f"Teacher registered: {username}")

def login_teacher(username, password):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM teachers WHERE username=? AND password_hash=?",
            (username.lower(), hash_pw(password))
        ).fetchone()
    return dict(row) if row else None

def teacher_exists(username):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT teacher_id FROM teachers WHERE username=?", (username.lower(),)
        ).fetchone()
    return row is not None



def _parse_questions(json_str):
    questions = []
    for d in json.loads(json_str):
        if d["type"] == "MCQ":
            questions.append(MCQQuestion(
                d["qid"], d["text"], d["marks"], d["topic"],
                d["options"], d["correct_index"]
            ))
        else:
            questions.append(ShortAnswerQuestion(
                d["qid"], d["text"], d["marks"], d["topic"],
                d["keywords"], d["sample_answer"]
            ))
    return questions

def save_exam(title, subject, duration_minutes, questions):
    q_json = json.dumps([q.to_dict() for q in questions])
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO exams (title, subject, duration_minutes, questions_json) VALUES (?,?,?,?)",
            (title, subject, duration_minutes, q_json)
        )
    logger.info(f"Exam saved: {title}")
    return cur.lastrowid

def get_exam(exam_id):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM exams WHERE exam_id=?", (exam_id,)).fetchone()
    if not row:
        return None
    d = dict(row)
    d["questions"] = _parse_questions(d["questions_json"])
    d["total_marks"] = sum(q.marks for q in d["questions"])
    return d

def get_all_exams():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM exams").fetchall()
    exams = []
    for row in rows:
        d = dict(row)
        d["questions"]   = _parse_questions(d["questions_json"])
        d["total_marks"] = sum(q.marks for q in d["questions"])
        exams.append(d)
    return exams

def delete_exam(exam_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM exams WHERE exam_id=?", (exam_id,))
    logger.info(f"Exam deleted: id={exam_id}")

def update_exam(exam_id, title, subject, duration_minutes, questions):
    """Update an existing exam's title, subject, duration and questions."""
    q_json = json.dumps([q.to_dict() for q in questions])
    with get_conn() as conn:
        conn.execute(
            """UPDATE exams
               SET title=?, subject=?, duration_minutes=?, questions_json=?
               WHERE exam_id=?""",
            (title, subject, duration_minutes, q_json, exam_id)
        )
    logger.info(f"Exam updated: id={exam_id} title={title}")



def save_result(student_id, exam_id, answers, scores, total_score, total_marks, time_taken):
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO results
               (student_id, exam_id, answers_json, scores_json, total_score,
                total_marks, time_taken_seconds, submitted_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (student_id, exam_id,
             json.dumps(answers), json.dumps(scores),
             total_score, total_marks, time_taken,
             datetime.now().strftime("%Y-%m-%d %H:%M"))
        )
    logger.info(f"Result saved: student={student_id} exam={exam_id} score={total_score}/{total_marks}")
    return cur.lastrowid

def get_student_results(student_id):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM results WHERE student_id=? ORDER BY submitted_at DESC", (student_id,)
        ).fetchall()
    return [_enrich_result(dict(r)) for r in rows]

def get_exam_results(exam_id):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM results WHERE exam_id=? ORDER BY total_score DESC", (exam_id,)
        ).fetchall()
    return [_enrich_result(dict(r)) for r in rows]

def get_all_results():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM results ORDER BY submitted_at DESC").fetchall()
    return [_enrich_result(dict(r)) for r in rows]

def has_attempted(student_id, exam_id):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM results WHERE student_id=? AND exam_id=?",
            (student_id, exam_id)
        ).fetchone()
    return row is not None

def _enrich_result(r):
    pct = round(r["total_score"] / r["total_marks"] * 100, 1) if r["total_marks"] else 0
    r["percentage"] = pct
    r["grade"]      = _calc_grade(pct)
    r["passed"]     = pct >= 50
    r["answers"]    = json.loads(r["answers_json"])
    r["scores"]     = json.loads(r["scores_json"])
    return r

def _calc_grade(pct):
    if pct >= 90: return "A+"
    if pct >= 80: return "A"
    if pct >= 70: return "B"
    if pct >= 60: return "C"
    if pct >= 50: return "D"
    return "F"



def student_analytics(student_id):
    results = get_student_results(student_id)
    if not results:
        return None
    percentages = [r["percentage"] for r in results]
    return {
        "total":   len(results),
        "average": round(statistics.mean(percentages), 1),
        "highest": max(percentages),
        "lowest":  min(percentages),
        "passed":  sum(1 for r in results if r["passed"]),
    }

def topic_scores(student_id):
    """Returns avg % per topic across all attempts."""
    results = get_student_results(student_id)
    topic_data = {}
    for r in results:
        exam = get_exam(r["exam_id"])
        if not exam: continue
        for q in exam["questions"]:
            awarded = r["scores"].get(str(q.qid), 0)
            pct = (awarded / q.marks * 100) if q.marks else 0
            topic_data.setdefault(q.topic, []).append(pct)
    return {t: round(statistics.mean(v), 1) for t, v in topic_data.items()}


def leaderboard_report(exam_id):
    results = get_exam_results(exam_id)
    exam    = get_exam(exam_id)
    rows = []
    for rank, r in enumerate(results, 1):
        student = get_student(r["student_id"])
        m, s = divmod(r["time_taken_seconds"], 60)
        rows.append([rank, student["name"] if student else "?",
                     f"{r['total_score']}/{r['total_marks']}",
                     f"{r['percentage']}%", r["grade"], f"{m}m {s}s"])
    header = f"\nLEADERBOARD: {exam['title']}\n"
    return header + tabulate(rows,
        headers=["Rank","Student","Score","%","Grade","Time"],
        tablefmt="rounded_outline")

def student_history_report(student_id):
    results  = get_student_results(student_id)
    student  = get_student(student_id)
    rows = []
    for r in results:
        exam = get_exam(r["exam_id"])
        rows.append([exam["title"] if exam else r["exam_id"],
                     f"{r['total_score']}/{r['total_marks']}",
                     f"{r['percentage']}%", r["grade"],
                     "Pass" if r["passed"] else "Fail",
                     r["submitted_at"]])
    header = f"\nEXAM HISTORY: {student['name'] if student else student_id}\n"
    return header + tabulate(rows,
        headers=["Exam","Score","%","Grade","Status","Date"],
        tablefmt="rounded_outline")


def seed_data():
    if get_all_exams():
        return  # Already seeded

    # Demo student
    register_student("Demo Student", "demo@test.com", "demo1234")

    # Exam 1: Python
    python_qs = [
        MCQQuestion(1, "Which keyword defines a function in Python?", 2, "Syntax",
                    ["func", "define", "def", "function"], 2),
        MCQQuestion(2, "What is the output of type([])?", 2, "Data Types",
                    ["<class 'tuple'>", "<class 'list'>", "<class 'dict'>", "<class 'set'>"], 1),
        MCQQuestion(3, "Which of these is immutable?", 2, "Data Types",
                    ["List", "Dictionary", "Set", "Tuple"], 3),
        MCQQuestion(4, "Which method is called when an object is created?", 2, "OOP",
                    ["__start__", "__create__", "__init__", "__new__"], 2),
        ShortAnswerQuestion(5, "What is the difference between a list and a tuple?", 4, "Data Types",
                            ["mutable", "immutable", "list", "tuple"],
                            "A list is mutable (can change) while a tuple is immutable (cannot change after creation)."),
    ]
    save_exam("Python Fundamentals", "Computer Science", 20, python_qs)

    # Exam 2: Data Structures
    ds_qs = [
        MCQQuestion(1, "Which data structure uses LIFO ordering?", 2, "Stacks",
                    ["Queue", "Stack", "Heap", "Array"], 1),
        MCQQuestion(2, "Worst-case time complexity of Bubble Sort?", 2, "Sorting",
                    ["O(n)", "O(log n)", "O(n log n)", "O(n²)"], 3),
        MCQQuestion(3, "Which traversal visits Left → Root → Right?", 2, "Trees",
                    ["Pre-order", "In-order", "Post-order", "Level-order"], 1),
        MCQQuestion(4, "What data structure is used in BFS?", 2, "Graphs",
                    ["Stack", "Queue", "Array", "Tree"], 1),
        ShortAnswerQuestion(5, "Explain the difference between a Stack and a Queue.", 4, "Data Structures",
                            ["stack", "queue", "lifo", "fifo", "last", "first"],
                            "Stack uses LIFO (Last In First Out) while Queue uses FIFO (First In First Out)."),
    ]
    save_exam("Data Structures", "Computer Science", 25, ds_qs)

    logger.info("Seed data loaded.")
