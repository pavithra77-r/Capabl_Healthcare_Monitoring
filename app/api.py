from datetime import timedelta
from typing import Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Security, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel

from utils.auth import create_access_token, decode_access_token
from utils.database import (
    authenticate_user,
    clear_chat_history,
    create_tables,
    create_user,
    delete_medication,
    get_all_medications,
    get_chat_history,
    get_today_intake,
    log_medication_taken,
    add_medication,  # ADD THIS LINE
)
from utils.health_agent import run_agent_with_history, run_simple_chat

app = FastAPI(title="HealthGuard API")

# Ensure DB exists when the app starts
create_tables()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


def _get_current_user(token: str = Depends(oauth2_scheme)) -> Dict:
    payload = decode_access_token(token)
    username = payload.get("sub")
    role = payload.get("role")
    if not username or not role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {"username": username, "role": role}


def require_roles(*allowed_roles: str):
    def _dependency(current_user: Dict = Depends(_get_current_user)):
        if current_user["role"] not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User does not have required privileges",
            )
        return current_user

    return _dependency


class MedicationIn(BaseModel):
    name: str
    dosage: str
    frequency: str
    time: str
    notes: Optional[str] = ""
    max_daily_dose: Optional[str] = ""


class MedicationOut(MedicationIn):
    id: int
    created_date: str


class ChatMessage(BaseModel):
    role: str
    content: str
    timestamp: str


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None


class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "patient"
    full_name: Optional[str] = ""


class UserOut(BaseModel):
    username: str
    role: str
    full_name: Optional[str] = ""


class ChatQuery(BaseModel):
    message: str
    openai_api_key: Optional[str] = None


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/auth/register", response_model=UserOut, status_code=201)
def register_user(user: UserCreate):
    if len(user.password.encode("utf-8")) > 72:
        raise HTTPException(
            status_code=400,
            detail="Password is too long (max 72 bytes). Please use a shorter password.",
        )

    created = create_user(user.username, user.password, role=user.role, full_name=user.full_name)
    if created is None:
        raise HTTPException(status_code=400, detail="Username already exists")
    return UserOut(**created)


@app.post("/auth/token", response_model=Token)
def get_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=60)
    access_token = create_access_token(
        data={"sub": user["username"], "role": user["role"]},
        expires_delta=access_token_expires,
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/users/me", response_model=UserOut)
def read_current_user(current_user: Dict = Depends(_get_current_user)):
    return UserOut(**current_user)


@app.get("/medications", response_model=List[MedicationOut])
def list_medications(current_user: Dict = Depends(_get_current_user)):
    meds = get_all_medications()
    return [
        MedicationOut(
            id=m[0],
            name=m[1],
            dosage=m[2],
            frequency=m[3],
            time=m[4],
            notes=m[5] or "",
            max_daily_dose=m[6] or "",
            created_date=m[7],
        )
        for m in meds
    ]


@app.post("/medications", response_model=MedicationOut, status_code=201)
def create_medication(med: MedicationIn, current_user: Dict = Depends(_get_current_user)):
    add_medication(
        med.name,
        med.dosage,
        med.frequency,
        med.time,
        notes=med.notes or "",
        max_daily_dose=med.max_daily_dose or "",
    )
    meds = get_all_medications()
    created = meds[-1]
    return MedicationOut(
        id=created[0],
        name=created[1],
        dosage=created[2],
        frequency=created[3],
        time=created[4],
        notes=created[5] or "",
        max_daily_dose=created[6] or "",
        created_date=created[7],
    )


@app.delete("/medications/{med_id}")
def remove_medication(med_id: int, current_user: Dict = Depends(require_roles("doctor", "caregiver"))):
    delete_medication(med_id)
    return {"status": "deleted", "id": med_id}


@app.post("/medications/{med_id}/take")
def take_medication(med_id: int, current_user: Dict = Depends(_get_current_user)):
    meds = get_all_medications()
    med = next((m for m in meds if m[0] == med_id), None)
    if not med:
        raise HTTPException(status_code=404, detail="Medication not found")

    log_medication_taken(med_id, med[1], med[2])
    return {"status": "logged", "medication": med[1]}


@app.get("/medications/{med_id}/intake")
def medication_intake(med_id: int, current_user: Dict = Depends(_get_current_user)):
    meds = get_all_medications()
    med = next((m for m in meds if m[0] == med_id), None)
    if not med:
        raise HTTPException(status_code=404, detail="Medication not found")

    count, _ = get_today_intake(med[1]) or (0, "")
    return {"medication": med[1], "today_count": count}


@app.get("/chat/history", response_model=List[ChatMessage])
def fetch_chat_history(current_user: Dict = Depends(_get_current_user)):
    history = get_chat_history(limit=50)
    return [
        ChatMessage(role=r[0], content=r[1], timestamp=r[2]) for r in history
    ]


@app.post("/chat/clear")
def clear_history(current_user: Dict = Depends(require_roles("doctor", "caregiver"))):
    clear_chat_history()
    return {"status": "cleared"}


@app.post("/chat/query")
def chat_query(query: ChatQuery, current_user: Dict = Depends(_get_current_user)):
    if query.openai_api_key:
        response = run_agent_with_history(query.message, query.openai_api_key)
    else:
        response = run_simple_chat(query.message)
    return {"response": response}
