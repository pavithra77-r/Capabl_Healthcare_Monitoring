import sqlite3
import os
from datetime import datetime

def create_connection():
    """Create a database connection"""
    if not os.path.exists('data'):
        os.makedirs('data')
    conn = sqlite3.connect('data/health_monitor.db', check_same_thread=False)
    return conn

def create_tables():
    """Create all required tables"""
    conn = create_connection()
    cursor = conn.cursor()

    # Medications table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS medications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            dosage TEXT NOT NULL,
            frequency TEXT NOT NULL,
            time TEXT NOT NULL,
            notes TEXT,
            max_daily_dose TEXT,
            created_date TEXT NOT NULL
        )
    ''')

    # Chat history table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    ''')

    # Medication intake log (for overdose detection)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS medication_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            medication_id INTEGER,
            medication_name TEXT NOT NULL,
            dosage TEXT NOT NULL,
            taken_at TEXT NOT NULL,
            FOREIGN KEY (medication_id) REFERENCES medications(id)
        )
    ''')

    conn.commit()
    conn.close()

# ─── Medication CRUD ───────────────────────────────────────────────────────────

def add_medication(name, dosage, frequency, time, notes="", max_daily_dose=""):
    from datetime import datetime
    conn = create_connection()
    cursor = conn.cursor()
    created_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('''
        INSERT INTO medications (name, dosage, frequency, time, notes, max_daily_dose, created_date)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (name, dosage, frequency, time, notes, max_daily_dose, created_date))
    conn.commit()
    conn.close()
    return True

def get_all_medications():
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM medications ORDER BY time')
    medications = cursor.fetchall()
    conn.close()
    return medications

def delete_medication(med_id):
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM medications WHERE id = ?', (med_id,))
    conn.commit()
    conn.close()
    return True

def delete_medication_by_name(name):
    """Delete medication by name (case-insensitive). Returns True if deleted."""
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM medications WHERE LOWER(name) = LOWER(?)', (name,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def get_medication_by_name(name):
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM medications WHERE LOWER(name) LIKE LOWER(?)', (f'%{name}%',))
    result = cursor.fetchall()
    conn.close()
    return result

# ─── Medication Log (Taken tracking + overdose) ────────────────────────────────

def log_medication_taken(medication_id, medication_name, dosage):
    conn = create_connection()
    cursor = conn.cursor()
    taken_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('''
        INSERT INTO medication_log (medication_id, medication_name, dosage, taken_at)
        VALUES (?, ?, ?, ?)
    ''', (medication_id, medication_name, dosage, taken_at))
    conn.commit()
    conn.close()

def get_today_intake(medication_name):
    """Get how many times a medication was taken today."""
    conn = create_connection()
    cursor = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")
    cursor.execute('''
        SELECT COUNT(*), dosage FROM medication_log
        WHERE LOWER(medication_name) = LOWER(?)
        AND DATE(taken_at) = ?
    ''', (medication_name, today))
    result = cursor.fetchone()
    conn.close()
    return result  # (count, dosage)

# ─── Chat History ──────────────────────────────────────────────────────────────

def save_chat_message(role, content):
    conn = create_connection()
    cursor = conn.cursor()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('''
        INSERT INTO chat_history (role, content, timestamp)
        VALUES (?, ?, ?)
    ''', (role, content, timestamp))
    conn.commit()
    conn.close()

def get_chat_history(limit=50):
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT role, content, timestamp FROM chat_history
        ORDER BY id DESC LIMIT ?
    ''', (limit,))
    rows = cursor.fetchall()
    conn.close()
    return list(reversed(rows))  # oldest first

def clear_chat_history():
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM chat_history')
    conn.commit()
    conn.close()

if __name__ == "__main__":
    create_tables()
    print("✅ All tables created!")