import sqlite3


class FaceCodeDatabase:
    def __init__(self, db_name="facecode.db"):
        self.db_name = db_name
        self.create_tables()

    def connect(self):
        conn = sqlite3.connect(self.db_name, timeout=30)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    def is_available(self):
        try:
            conn = self.connect()
            conn.execute("SELECT 1").fetchone()
            conn.close()
            return True
        except sqlite3.Error:
            return False

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
            client_session_id TEXT,
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
            dominant_emotion TEXT DEFAULT 'unknown',
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)

        existing_columns = {
            row[1] for row in cursor.execute("PRAGMA table_info(sessions)").fetchall()
        }
        if "client_session_id" not in existing_columns:
            cursor.execute("ALTER TABLE sessions ADD COLUMN client_session_id TEXT")
        if "dominant_emotion" not in existing_columns:
            cursor.execute(
                "ALTER TABLE sessions ADD COLUMN dominant_emotion TEXT DEFAULT 'unknown'"
            )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_sessions_client ON sessions(client_session_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_sessions_timestamp ON sessions(timestamp)"
        )

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
               (client_session_id, problem_id, problem_title, difficulty, category, solved,
                time_spent, hints_used, avg_confidence,
                avg_emotion_confidence, avg_behavior_confidence,
                error_count, success_count, dominant_emotion)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                data.get("client_session_id"),
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
                data.get("dominant_emotion", "unknown"),
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

    def get_statistics(self, client_session_id=None):
        """Return analytics, optionally scoped to one client session."""
        conn = self.connect()
        cursor = conn.cursor()
        where = " WHERE client_session_id = ?" if client_session_id else ""
        params = (client_session_id,) if client_session_id else ()

        cursor.execute(f"SELECT COUNT(*) FROM sessions{where}", params)
        total_sessions = cursor.fetchone()[0]

        solved_where = (
            " WHERE solved = 1 AND client_session_id = ?"
            if client_session_id else " WHERE solved = 1"
        )
        cursor.execute(f"SELECT COUNT(*) FROM sessions{solved_where}", params)
        total_solved = cursor.fetchone()[0]

        cursor.execute(f"SELECT AVG(avg_confidence) FROM sessions{where}", params)
        avg_confidence = cursor.fetchone()[0] or 0.5

        solve_rate = (total_solved / total_sessions * 100) if total_sessions else 0

        # Difficulty breakdown
        cursor.execute(
            f"SELECT difficulty, COUNT(*) FROM sessions{where} GROUP BY difficulty",
            params,
        )
        difficulty_breakdown = {row[0]: row[1] for row in cursor.fetchall()}

        # Category breakdown
        cursor.execute(
            f"SELECT category, COUNT(*) FROM sessions{where} GROUP BY category",
            params,
        )
        category_breakdown = {row[0]: row[1] for row in cursor.fetchall()}

        emotion_where = (
            " WHERE dominant_emotion IS NOT NULL AND client_session_id = ?"
            if client_session_id else " WHERE dominant_emotion IS NOT NULL"
        )
        cursor.execute(
            f"SELECT dominant_emotion, COUNT(*) FROM sessions{emotion_where} "
            "GROUP BY dominant_emotion",
            params,
        )
        emotion_breakdown = {row[0]: row[1] for row in cursor.fetchall()}

        conn.close()
        return {
            "total_sessions": total_sessions,
            "total_solved": total_solved,
            "solve_rate": solve_rate,
            "avg_confidence": avg_confidence,
            "difficulty_breakdown": difficulty_breakdown,
            "category_breakdown": category_breakdown,
            "emotion_breakdown": emotion_breakdown,
        }

    def delete_client_session(self, client_session_id):
        conn = self.connect()
        cursor = conn.cursor()
        session_ids = [
            row[0] for row in cursor.execute(
                "SELECT id FROM sessions WHERE client_session_id = ?",
                (client_session_id,),
            ).fetchall()
        ]
        if session_ids:
            placeholders = ",".join("?" for _ in session_ids)
            cursor.execute(
                f"DELETE FROM difficulty_changes WHERE session_id IN ({placeholders})",
                session_ids,
            )
        cursor.execute(
            "DELETE FROM sessions WHERE client_session_id = ?",
            (client_session_id,),
        )
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        return deleted

    def purge_expired_sessions(self, retention_days):
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM difficulty_changes WHERE session_id IN ("
            "SELECT id FROM sessions WHERE timestamp < datetime('now', ?)"
            ")",
            (f"-{retention_days} days",),
        )
        cursor.execute(
            "DELETE FROM sessions WHERE timestamp < datetime('now', ?)",
            (f"-{retention_days} days",),
        )
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        return deleted

    def close(self):
        """No-op for this simple implementation (connections are opened/closed per call)."""
        pass
