import os
import re
from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    String,
    Text,
    create_engine,
    func,
    select,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import declarative_base, sessionmaker

from utils.auth import get_password_hash, verify_password

# ---------------------------------------------------------------------------
# Database configuration
# ---------------------------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/health_monitor.db")

# Ensure local SQLite directory exists when using file-based SQLite.
if DATABASE_URL.startswith("sqlite:///"):
    sqlite_path = DATABASE_URL.replace("sqlite:///", "")
    sqlite_dir = os.path.dirname(sqlite_path)
    if sqlite_dir and not os.path.exists(sqlite_dir):
        os.makedirs(sqlite_dir, exist_ok=True)

# For SQLite, we need check_same_thread=False when sharing connections across threads.
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
Base = declarative_base()


# ---------------------------------------------------------------------------
# ORM Models
# ---------------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, nullable=False, unique=True, index=True)
    hashed_password = Column(String, nullable=False)
    role = Column(String, nullable=False, default="patient")
    full_name = Column(String)
    created_date = Column(DateTime, default=datetime.utcnow)


class Medication(Base):
    __tablename__ = "medications"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    dosage = Column(String, nullable=False)
    frequency = Column(String, nullable=False)
    time = Column(String, nullable=False)
    notes = Column(Text)
    max_daily_dose = Column(String)
    created_date = Column(DateTime, default=datetime.utcnow)


class ChatHistory(Base):
    __tablename__ = "chat_history"

    id = Column(Integer, primary_key=True, index=True)
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)


class MedicationLog(Base):
    __tablename__ = "medication_log"

    id = Column(Integer, primary_key=True, index=True)
    medication_id = Column(Integer, nullable=True)
    medication_name = Column(String, nullable=False)
    dosage = Column(String, nullable=False)
    taken_at = Column(DateTime, default=datetime.utcnow)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def create_tables():
    """Create all required tables."""
    Base.metadata.create_all(bind=engine)


def _row_to_med_tuple(med: Medication):
    return (
        med.id,
        med.name,
        med.dosage,
        med.frequency,
        med.time,
        med.notes,
        med.max_daily_dose,
        med.created_date.strftime("%Y-%m-%d %H:%M:%S") if med.created_date else "",
    )


def _row_to_user_dict(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "full_name": user.full_name or "",
        "created_date": user.created_date.strftime("%Y-%m-%d %H:%M:%S") if user.created_date else "",
    }


# ---------------------------------------------------------------------------
# Medication validation helpers
# ---------------------------------------------------------------------------

def _validate_medication_input(
    name: str,
    dosage: str,
    frequency: str,
    time_str: str,
    max_daily_dose: str = "",
) -> None:
    """Validate medication fields and raise ValueError with a user-friendly message."""
    if not name or not name.strip():
        raise ValueError("Medication name cannot be empty.")
    if not dosage or not dosage.strip():
        raise ValueError("Dosage cannot be empty.")
    if not frequency or not frequency.strip():
        raise ValueError("Frequency cannot be empty.")

    if not time_str or not time_str.strip():
        raise ValueError("Time must be provided in HH:MM format.")
    try:
        datetime.strptime(time_str.strip(), "%H:%M")
    except Exception:
        raise ValueError("Time must be in HH:MM format (24-hour clock).")

    # Require a milligram amount for dosage and max daily dose if provided.
    if not re.search(r"\d+(?:\.\d+)?\s*mg", dosage, re.IGNORECASE):
        raise ValueError("Dosage must include a milligram amount, e.g. '500mg'.")

    if max_daily_dose and max_daily_dose.strip():
        if not re.search(r"\d+(?:\.\d+)?\s*mg", max_daily_dose, re.IGNORECASE):
            raise ValueError("Max daily dose must include a milligram amount, e.g. '2000mg'.")


# ---------------------------------------------------------------------------
# User Management / Authentication
# ---------------------------------------------------------------------------

def create_user(username: str, password: str, role: str = "patient", full_name: str = "") -> Optional[dict]:
    """Create a new user."""
    with SessionLocal() as session:
        try:
            hashed = get_password_hash(password)
        except ValueError:
            return None

        usr = User(username=username, hashed_password=hashed, role=role, full_name=full_name)
        session.add(usr)
        try:
            session.commit()
            session.refresh(usr)
        except IntegrityError:
            session.rollback()
            return None
        return _row_to_user_dict(usr)


def get_user_by_username(username: str) -> Optional[User]:
    with SessionLocal() as session:
        return session.scalar(select(User).where(User.username == username))


def get_user_by_id(user_id: int) -> Optional[User]:
    with SessionLocal() as session:
        return session.get(User, user_id)


def authenticate_user(username: str, password: str) -> Optional[dict]:
    user = get_user_by_username(username)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return _row_to_user_dict(user)


# ---------------------------------------------------------------------------
# Medication CRUD
# ---------------------------------------------------------------------------

def add_medication(name, dosage, frequency, time, notes="", max_daily_dose=""):
    # Validate before inserting to catch inconsistent data early.
    _validate_medication_input(name, dosage, frequency, time, max_daily_dose)

    with SessionLocal() as session:
        med = Medication(
            name=name,
            dosage=dosage,
            frequency=frequency,
            time=time,
            notes=notes,
            max_daily_dose=max_daily_dose,
            created_date=datetime.utcnow(),
        )
        session.add(med)
        session.commit()
        session.refresh(med)
    return True


def get_all_medications():
    with SessionLocal() as session:
        meds = session.query(Medication).order_by(Medication.time).all()
        return [_row_to_med_tuple(m) for m in meds]


def delete_medication(med_id):
    with SessionLocal() as session:
        med = session.get(Medication, med_id)
        if not med:
            return False
        session.delete(med)
        session.commit()
        return True


def delete_medication_by_name(name):
    with SessionLocal() as session:
        meds = (
            session.query(Medication)
            .filter(func.lower(Medication.name) == func.lower(name))
            .all()
        )
        if not meds:
            return False
        for med in meds:
            session.delete(med)
        session.commit()
        return True


def get_medication_by_name(name):
    with SessionLocal() as session:
        meds = (
            session.query(Medication)
            .filter(Medication.name.ilike(f"%{name}%"))
            .all()
        )
        return [_row_to_med_tuple(m) for m in meds]


# ---------------------------------------------------------------------------
# Medication Log (Taken tracking + overdose)
# ---------------------------------------------------------------------------

def log_medication_taken(medication_id, medication_name, dosage):
    with SessionLocal() as session:
        log = MedicationLog(
            medication_id=medication_id,
            medication_name=medication_name,
            dosage=dosage,
            taken_at=datetime.utcnow(),
        )
        session.add(log)
        session.commit()


def get_today_intake(medication_name):
    """Get how many times a medication was taken today."""
    with SessionLocal() as session:
        today = date.today()
        count = (
            session.query(func.count())
            .select_from(MedicationLog)
            .filter(func.lower(MedicationLog.medication_name) == func.lower(medication_name))
            .filter(func.date(MedicationLog.taken_at) == today)
            .scalar()
        )
        return (count or 0, "")


# ---------------------------------------------------------------------------
# Chat History
# ---------------------------------------------------------------------------
def save_chat_message(role, content):
    with SessionLocal() as session:
        msg = ChatHistory(role=role, content=content, timestamp=datetime.utcnow())
        session.add(msg)
        session.commit()


def get_chat_history(limit=50):
    with SessionLocal() as session:
        rows = (
            session.query(ChatHistory)
            .order_by(ChatHistory.id.desc())
            .limit(limit)
            .all()
        )
        history = []
        for row in reversed(rows):
            history.append((row.role, row.content, row.timestamp.strftime("%Y-%m-%d %H:%M:%S")))
        return history


def clear_chat_history():
    with SessionLocal() as session:
        session.query(ChatHistory).delete()
        session.commit()


if __name__ == "__main__":
    create_tables()
    print("✅ All tables created!")