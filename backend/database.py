import sqlite3


class FaceCodeDatabase:
    def __init__(self, db_name="facecode.db"):
        self.db_name = db_name
        self.create_tables()

    def connect(self):
        return sqlite3.connect(self.db_name)

    def create_tables(self):
        conn = self.connect()
        cursor = conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            session_id TEXT,
            confidence_score REAL DEFAULT 0.5,
            current_difficulty TEXT DEFAULT 'EASY'
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS problem_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            problem_id INTEGER,
            detected_emotion TEXT,
            correctness INTEGER,
            time_taken REAL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            problem_id TEXT,
            problem_title TEXT,
            difficulty TEXT,
            category TEXT,
            solved INTEGER DEFAULT 0,
            time_spent REAL DEFAULT 0,
            hints_used INTEGER DEFAULT 0,
            avg_confidence REAL DEFAULT 0.5,
            avg_emotion_confidence REAL DEFAULT 0.5,
            avg_behavior_confidence REAL DEFAULT 0.5,
            error_count INTEGER DEFAULT 0,
            success_count INTEGER DEFAULT 0,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS difficulty_changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            old_difficulty TEXT,
            new_difficulty TEXT,
            adjustment TEXT,
            reason TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        )
        """)

        conn.commit()
        conn.close()

    def add_user(self, name):
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (name) VALUES (?)", (name,))
        conn.commit()
        conn.close()

    def get_users(self):
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users")
        users = cursor.fetchall()
        conn.close()
        return users

    def save_session(self, data):
        """Save a problem-solving session and return the session row id."""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO sessions
               (problem_id, problem_title, difficulty, category, solved,
                time_spent, hints_used, avg_confidence,
                avg_emotion_confidence, avg_behavior_confidence,
                error_count, success_count)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                data.get("problem_id"),
                data.get("problem_title"),
                data.get("difficulty"),
                data.get("category"),
                int(data.get("solved", False)),
                data.get("time_spent", 0),
                data.get("hints_used", 0),
                data.get("avg_confidence", 0.5),
                data.get("avg_emotion_confidence", 0.5),
                data.get("avg_behavior_confidence", 0.5),
                data.get("error_count", 0),
                data.get("success_count", 0),
            ),
        )
        session_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return session_id

    def save_difficulty_change(self, change, session_id):
        """Record a difficulty adjustment linked to a session."""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO difficulty_changes
               (session_id, old_difficulty, new_difficulty, adjustment, reason)
               VALUES (?,?,?,?,?)""",
            (
                session_id,
                change.get("old_difficulty"),
                change.get("new_difficulty"),
                change.get("adjustment"),
                change.get("reason"),
            ),
        )
        conn.commit()
        conn.close()

    def get_statistics(self):
        """Return aggregate analytics across all saved sessions."""
        conn = self.connect()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM sessions")
        total_sessions = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM sessions WHERE solved = 1")
        total_solved = cursor.fetchone()[0]

        cursor.execute("SELECT AVG(avg_confidence) FROM sessions")
        avg_confidence = cursor.fetchone()[0] or 0.5

        solve_rate = (total_solved / total_sessions * 100) if total_sessions else 0

        # Difficulty breakdown
        cursor.execute(
            "SELECT difficulty, COUNT(*) FROM sessions GROUP BY difficulty"
        )
        difficulty_breakdown = {row[0]: row[1] for row in cursor.fetchall()}

        # Category breakdown
        cursor.execute(
            "SELECT category, COUNT(*) FROM sessions GROUP BY category"
        )
        category_breakdown = {row[0]: row[1] for row in cursor.fetchall()}

        conn.close()
        return {
            "total_sessions": total_sessions,
            "total_solved": total_solved,
            "solve_rate": solve_rate,
            "avg_confidence": avg_confidence,
            "difficulty_breakdown": difficulty_breakdown,
            "category_breakdown": category_breakdown,
        }

    def close(self):
        """No-op for this simple implementation (connections are opened/closed per call)."""
        pass