# Capabl Healthcare Monitoring

This project provides a Streamlit dashboard plus a FastAPI backend for tracking medications, logging doses, and chatting with an AI health assistant.

## ✅ What’s included

- **Streamlit UI** (Streamlit app entrypoint: `streamlit_app.py`)
- **FastAPI backend** (`app/api.py`) for programmatic access & automation
- **PostgreSQL + Redis** via `docker-compose`
- **SQLAlchemy**-based database layer with easy `DATABASE_URL` switching
- **LangChain / LangGraph** ready for LLM workflows

---

## 🚀 Quick start with Docker (recommended)

1) Copy the env example:

```bash
copy .env.example .env
```

2) Start services:

```bash
docker compose up --build
```

3) Open apps:

- Streamlit UI: http://localhost:8501
- FastAPI docs: http://localhost:8000/docs

---

## 🧪 Run locally without Docker (SQLite)

1) Create & activate a virtual env:

```bash
python -m venv .venv
.\.venv\Scripts\activate
```

2) Install deps:

```bash
pip install -r requirements.txt
```

3) Start Streamlit UI:

```bash
streamlit run streamlit_app.py
```

4) Start FastAPI API:

```bash
uvicorn app.api:app --reload
```

---

## 🔧 Database configuration (PostgreSQL)

Set `DATABASE_URL` in `.env` (docker-compose uses this automatically):

```env
DATABASE_URL=postgresql+psycopg2://<user>:<pass>@postgres:5432/<db>
```

---

## 💬 AI Agent

- The AI assistant uses OpenAI via `OPENAI_API_KEY`.
- In Streamlit, enter your key in the sidebar.
- In the API, send `openai_api_key` to `/chat/query`.

---

## 🔐 Role-based Authentication

This project now supports role-based auth (Patient / Doctor / Caregiver). Users are stored in the database and can log in via the Streamlit sidebar.

- Register/login in Streamlit sidebar.
- Roles control certain operations (e.g., only doctor/caregiver can delete medications).
- The FastAPI backend exposes `/auth/register` and `/auth/token` to manage users and obtain JWT tokens.

---

## 🧠 LangGraph

LangGraph is installed and available for building graph-based LLM pipelines. You can start by importing it in `utils/health_agent.py` or adding a dedicated module.
