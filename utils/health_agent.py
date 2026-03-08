"""
health_agent.py  –  LangChain-powered Health Assistant Agent
Supports:
  - Persistent chat history
  - Delete medication via conversation
  - Overdose detection
  - Medication reminders
"""
from __future__ import annotations

import os
import json
import re
from datetime import datetime, time as dt_time
from typing import Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain.tools import tool
from langchain.agents import create_agent

from utils.database import (
    get_all_medications,
    delete_medication_by_name,
    get_medication_by_name,
    log_medication_taken,
    get_today_intake,
    save_chat_message,
    get_chat_history,
)
from utils.drug_info import check_overdose_risk

# ─── Helper ────────────────────────────────────────────────────────────────────

def _parse_dosage_mg(dosage_str: str) -> Optional[float]:
    match = re.search(r'(\d+(?:\.\d+)?)\s*mg', dosage_str, re.IGNORECASE)
    return float(match.group(1)) if match else None

# ─── Agent Tools ───────────────────────────────────────────────────────────────

@tool
def list_medications(query: str = "") -> str:
    """List all medications currently tracked. Use this whenever the user asks what medications they have."""
    meds = get_all_medications()
    if not meds:
        return "No medications are currently tracked."
    lines = []
    for m in meds:
        med_id, name, dosage, frequency, med_time, notes, max_dose, created = m
        lines.append(f"• [{med_id}] {name} — {dosage} | {frequency} at {med_time}" +
                     (f" | Notes: {notes}" if notes else "") +
                     (f" | Max daily: {max_dose}" if max_dose else ""))
    return "Current medications:\n" + "\n".join(lines)

@tool
def delete_medication_tool(medicine_name: str) -> str:
    """
    Delete a medication from the tracker by its name.
    Use this when the user asks to remove, delete, or stop tracking a medication.
    Input: the medicine name (e.g. 'Paracetamol' or 'Dolo 650').
    """
    deleted = delete_medication_by_name(medicine_name)
    if deleted:
        return f"✅ '{medicine_name}' has been successfully removed from your medication list."
    else:
        # Try fuzzy match
        matches = get_medication_by_name(medicine_name)
        if matches:
            names = ", ".join([m[1] for m in matches])
            return f"❓ Could not find exact match for '{medicine_name}'. Did you mean: {names}? Please confirm."
        return f"❌ No medication named '{medicine_name}' was found in your list."

@tool
def check_overdose_tool(medicine_name: str) -> str:
    """
    Check whether taking a medication again today risks an overdose.
    Input: medicine name. This tool checks today's intake log.
    """
    meds = get_medication_by_name(medicine_name)
    if not meds:
        return f"'{medicine_name}' is not in your medication list. Please add it first."

    med = meds[0]
    med_id, name, dosage, frequency, med_time, notes, max_dose, created = med

    intake = get_today_intake(name)
    count_today = intake[0] if intake and intake[0] else 0

    result = check_overdose_risk(name, count_today, dosage)
    return result['message']

@tool
def log_medication_taken_tool(medicine_name: str) -> str:
    """
    Mark a medication as taken right now and check for overdose risk.
    Use when user says they just took a medication or want to mark it as taken.
    Input: medicine name.
    """
    meds = get_medication_by_name(medicine_name)
    if not meds:
        return f"'{medicine_name}' is not in your medication list."

    med = meds[0]
    med_id, name, dosage, frequency, med_time, notes, max_dose, created = med

    # Check overdose BEFORE logging
    intake = get_today_intake(name)
    count_today = intake[0] if intake and intake[0] else 0
    risk = check_overdose_risk(name, count_today, dosage)

    if not risk['safe']:
        return (
            f"⛔ DOSE BLOCKED — {risk['message']}\n"
            f"Your dose of {name} has NOT been logged to protect your safety. "
            f"Please consult your doctor."
        )

    # Safe — log it
    log_medication_taken(med_id, name, dosage)
    msg = f"✅ Logged: {name} ({dosage}) taken at {datetime.now().strftime('%H:%M')}."
    if risk['severity'] == 'warning':
        msg += f"\n{risk['message']}"
    return msg

@tool
def get_medication_reminders(query: str = "") -> str:
    """
    Get medication reminders — what medications need to be taken soon or are overdue.
    Use when user asks about upcoming medications, reminders, or what to take next.
    """
    meds = get_all_medications()
    if not meds:
        return "You have no medications scheduled."

    now = datetime.now()
    current_time = now.time()
    reminders = []

    for med in meds:
        med_id, name, dosage, frequency, med_time_str, notes, max_dose, created = med
        try:
            h, m = map(int, med_time_str.split(':'))
            med_time_obj = dt_time(h, m)
        except Exception:
            continue

        # Calculate minutes difference
        med_minutes = h * 60 + m
        now_minutes = current_time.hour * 60 + current_time.minute
        diff = med_minutes - now_minutes

        intake = get_today_intake(name)
        taken_today = intake[0] if intake and intake[0] else 0

        if diff < 0 and abs(diff) <= 60:
            reminders.append(f"🔴 OVERDUE: {name} ({dosage}) was due at {med_time_str} — {abs(diff)} min ago. Taken today: {taken_today}x")
        elif 0 <= diff <= 30:
            reminders.append(f"🟡 DUE SOON: {name} ({dosage}) at {med_time_str} — in {diff} min. Taken today: {taken_today}x")
        elif 30 < diff <= 120:
            reminders.append(f"🟢 UPCOMING: {name} ({dosage}) at {med_time_str} — in {diff} min. Taken today: {taken_today}x")
        else:
            reminders.append(f"📋 {name} ({dosage}) scheduled at {med_time_str}. Taken today: {taken_today}x")

    if not reminders:
        return "All medications are up to date!"
    return "📅 Medication Reminders:\n" + "\n".join(reminders)

# ─── Agent Factory ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are HealthGuard AI, a caring and knowledgeable personal health assistant for an Indian healthcare monitoring app.

Your capabilities:
1. 📋 List, manage and track medications
2. 🗑️ Delete medications when users ask (use delete_medication_tool)
3. ⚠️ Detect overdose risks and alert users immediately  
4. 🔔 Provide medication reminders and schedules
5. 💊 Log when medications are taken (with safety checks)
6. 💬 Answer general health questions

IMPORTANT RULES:
- Always prioritize patient safety. If overdose risk is detected, warn clearly.
- When deleting a medication, always confirm with the user before proceeding.
- For serious medical conditions, always recommend consulting a doctor.
- Be warm, empathetic, and clear — many users may be elderly or non-technical.
- Provide information relevant to Indian healthcare context when appropriate.
- If you're unsure about medical information, say so and recommend professional advice.
- NEVER recommend specific prescription medications without doctor consultation.

Remember: You have persistent memory of this conversation. Refer to previous messages naturally.
"""

def create_agent(api_key: str):
    """Create the LangChain agent with all health tools."""
    llm = ChatOpenAI(
        model="gpt-3.5-turbo",
        temperature=0.3,
        openai_api_key=api_key,
    )

    tools = [
        list_medications,
        delete_medication_tool,
        check_overdose_tool,
        log_medication_taken_tool,
        get_medication_reminders,
    ]

    agent = create_agent(
    model=llm,
    tools=tools,
    system_prompt="You are a helpful healthcare assistant."
)
    return agent

def run_agent_with_history(user_message: str, api_key: str) -> str:
    """
    Run the agent with full chat history context.
    Saves both user message and AI response to DB.
    """
    # Save user message
    save_chat_message("user", user_message)

    # Build history for context
    history_rows = get_chat_history(limit=20)
    chat_history = []
    for row in history_rows[:-1]:  # exclude the just-saved message
        role, content, ts = row
        if role == "user":
            chat_history.append(HumanMessage(content=content))
        else:
            chat_history.append(AIMessage(content=content))

    try:
        agent = create_agent(api_key)
        response = agent.run(input=user_message, chat_history=chat_history)
    except Exception as e:
        response = (
            f"I encountered an issue: {str(e)}\n\n"
            "Please make sure your OpenAI API key is configured correctly. "
            "You can still use all other features of the app!"
        )

    # Save AI response
    save_chat_message("assistant", response)
    return response


# ─── Fallback (no API key) ─────────────────────────────────────────────────────

def run_simple_chat(user_message: str) -> str:
    """
    Rule-based fallback when no API key is provided.
    Handles common health assistant tasks without LLM.
    """
    save_chat_message("user", user_message)
    msg_lower = user_message.lower()

    # Delete medication intent
    if any(kw in msg_lower for kw in ['delete', 'remove', 'stop taking', 'discontinue']):
        # Extract medicine name heuristically
        for kw in ['delete', 'remove', 'stop taking', 'discontinue']:
            if kw in msg_lower:
                after = msg_lower.split(kw)[-1].strip().strip('.,!?')
                candidate = after.replace('medication', '').replace('medicine', '').replace('my', '').strip()
                if candidate:
                    deleted = delete_medication_by_name(candidate)
                    if deleted:
                        resp = f"✅ Done! I've removed **{candidate.title()}** from your medication list."
                    else:
                        matches = get_medication_by_name(candidate)
                        if matches:
                            names = ", ".join([m[1] for m in matches])
                            resp = f"❓ I found these similar medications: **{names}**. Could you confirm the exact name to delete?"
                        else:
                            resp = f"❌ I couldn't find **'{candidate}'** in your medications. Use 'list medications' to see all."
                    save_chat_message("assistant", resp)
                    return resp

    # List medications
    if any(kw in msg_lower for kw in ['list', 'show', 'what medication', 'my medication', 'all medication']):
        meds = get_all_medications()
        if not meds:
            resp = "You have no medications tracked yet. Go to the 💊 Medications page to add some!"
        else:
            lines = [f"• **{m[1]}** — {m[2]} | {m[3]} at {m[4]}" for m in meds]
            resp = "📋 Your current medications:\n" + "\n".join(lines)
        save_chat_message("assistant", resp)
        return resp

    # Reminders
    if any(kw in msg_lower for kw in ['reminder', 'remind', 'when', 'next dose', 'schedule', 'due']):
        meds = get_all_medications()
        if not meds:
            resp = "No medications scheduled. Add medications on the 💊 Medications page."
        else:
            now = datetime.now()
            lines = []
            for med in meds:
                med_id, name, dosage, frequency, med_time_str, notes, max_dose, created = med
                intake = get_today_intake(name)
                taken = intake[0] if intake and intake[0] else 0
                lines.append(f"🔔 **{name}** ({dosage}) — scheduled at **{med_time_str}** | Taken today: {taken}x")
            resp = f"📅 **Medication Schedule for today ({now.strftime('%A, %d %b')}):**\n" + "\n".join(lines)
        save_chat_message("assistant", resp)
        return resp

    # Overdose check
    if any(kw in msg_lower for kw in ['overdose', 'too much', 'safe to take', 'can i take', 'again']):
        meds = get_all_medications()
        if not meds:
            resp = "No medications in your list to check. Please add medications first."
        else:
            alerts = []
            for med in meds:
                med_id, name, dosage, frequency, med_time_str, notes, max_dose, created = med
                intake = get_today_intake(name)
                count = intake[0] if intake and intake[0] else 0
                risk = check_overdose_risk(name, count, dosage)
                if risk['severity'] in ('warning', 'danger'):
                    alerts.append(risk['message'])
            if alerts:
                resp = "⚠️ **Overdose Alerts:**\n\n" + "\n\n".join(alerts)
            else:
                resp = "✅ All your medications appear to be within safe dosage limits for today."
        save_chat_message("assistant", resp)
        return resp

    # Mark taken
    if any(kw in msg_lower for kw in ['took', 'taken', 'just had', 'mark as taken', 'i took']):
        meds = get_all_medications()
        found = None
        for med in meds:
            if med[1].lower() in msg_lower:
                found = med
                break
        if found:
            med_id, name, dosage, frequency, med_time_str, notes, max_dose, created = found
            intake = get_today_intake(name)
            count = intake[0] if intake and intake[0] else 0
            risk = check_overdose_risk(name, count, dosage)
            if not risk['safe']:
                resp = f"⛔ **DOSE BLOCKED!**\n{risk['message']}"
            else:
                log_medication_taken(med_id, name, dosage)
                resp = f"✅ Marked **{name}** ({dosage}) as taken at {datetime.now().strftime('%H:%M')}."
                if risk['severity'] == 'warning':
                    resp += f"\n\n{risk['message']}"
        else:
            resp = "Please specify which medication you took. E.g., 'I took Paracetamol'."
        save_chat_message("assistant", resp)
        return resp

    # Health tips / greetings
    if any(kw in msg_lower for kw in ['hello', 'hi', 'hey', 'good morning', 'good evening']):
        meds = get_all_medications()
        resp = (
            f"👋 Hello! I'm HealthGuard, your personal health assistant.\n\n"
            f"You have **{len(meds)} medication(s)** tracked. Here's what I can help you with:\n"
            f"• 📋 List your medications\n"
            f"• 🗑️ Delete a medication (just say 'remove [name]')\n"
            f"• ⚠️ Check for overdose risks\n"
            f"• 🔔 View medication reminders\n"
            f"• ✅ Mark a medication as taken\n\n"
            f"What would you like to do?"
        )
        save_chat_message("assistant", resp)
        return resp

    # Default
    resp = (
        "I'm your HealthGuard assistant! I can help you:\n"
        "• **List** your medications\n"
        "• **Delete** a medication (say 'remove [medicine name]')\n"
        "• **Check** overdose risks\n"
        "• **Remind** you about upcoming doses\n"
        "• **Mark** a medication as taken\n\n"
        "For complex medical questions, please consult your doctor. "
        "*(Tip: Add your OpenAI API key in Settings for full AI-powered responses!)*"
    )
    save_chat_message("assistant", resp)
    return resp