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