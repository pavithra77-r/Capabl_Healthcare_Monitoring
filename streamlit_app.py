import streamlit as st
import pandas as pd
from datetime import datetime, time

from utils.database import (
    authenticate_user,
    create_tables,
    create_user,
    add_medication,
    get_all_medications,
    delete_medication,
    log_medication_taken,
    get_today_intake,
    get_chat_history,
    clear_chat_history,
)
from utils.drug_info import (
    search_drug_info, get_indian_medicine_info, check_overdose_risk
)
from utils.health_agent import run_agent_with_history, run_simple_chat, _validate_med_record

# ─── Page Config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="HealthGuard Monitor",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── DB Init ───────────────────────────────────────────────────────────────────
create_tables()

# ─── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap');

html, body, [class*="css"] { font-family: 'Nunito', sans-serif; }

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0f4c75 0%, #1b6ca8 60%, #163172 100%);
}
[data-testid="stSidebar"] * { color: #e8f4fd !important; }
[data-testid="stSidebar"] .stRadio label { font-weight: 600; font-size: 0.95rem; }

/* ── Main Header ── */
.main-header {
    background: linear-gradient(135deg, #0f4c75, #1b6ca8);
    color: white;
    padding: 1.4rem 2rem;
    border-radius: 16px;
    text-align: center;
    font-size: 2rem;
    font-weight: 800;
    margin-bottom: 1.5rem;
    box-shadow: 0 4px 20px rgba(15,76,117,0.3);
    letter-spacing: -0.5px;
}

/* ── Metric Cards ── */
.metric-card {
    background: white;
    border: 1px solid #e2eaf3;
    border-radius: 14px;
    padding: 1.2rem 1.5rem;
    text-align: center;
    box-shadow: 0 2px 12px rgba(0,0,0,0.06);
    transition: transform 0.2s;
}
.metric-card:hover { transform: translateY(-2px); }
.metric-value { font-size: 2.2rem; font-weight: 800; color: #0f4c75; }
.metric-label { color: #6b7a8d; font-size: 0.85rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }

/* ── Medication Cards ── */
.med-card {
    background: linear-gradient(135deg, #f8fbff, #edf4ff);
    border-left: 4px solid #1b6ca8;
    border-radius: 12px;
    padding: 1rem 1.2rem;
    margin: 0.5rem 0;
    box-shadow: 0 2px 8px rgba(0,0,0,0.05);
}
.med-card.overdue { border-left-color: #e74c3c; background: linear-gradient(135deg, #fff8f8, #ffe8e8); }
.med-card.due-soon { border-left-color: #f39c12; background: linear-gradient(135deg, #fffcf0, #fff3cc); }

/* ── Alert boxes ── */
.overdose-alert {
    background: linear-gradient(135deg, #fff0f0, #ffe0e0);
    border: 2px solid #e74c3c;
    border-radius: 12px;
    padding: 1rem 1.2rem;
    margin: 0.5rem 0;
}
.overdose-warning {
    background: linear-gradient(135deg, #fffbf0, #fff3cc);
    border: 2px solid #f39c12;
    border-radius: 12px;
    padding: 1rem 1.2rem;
    margin: 0.5rem 0;
}

/* ── Chat ── */
.chat-container {
    height: 420px;
    overflow-y: auto;
    padding: 1rem;
    background: #f7fafd;
    border-radius: 14px;
    border: 1px solid #dde8f5;
    margin-bottom: 1rem;
}
.chat-msg-user {
    background: linear-gradient(135deg, #0f4c75, #1b6ca8);
    color: white;
    border-radius: 18px 18px 4px 18px;
    padding: 0.7rem 1rem;
    margin: 0.5rem 0 0.5rem 3rem;
    font-size: 0.93rem;
    box-shadow: 0 2px 8px rgba(15,76,117,0.2);
}
.chat-msg-assistant {
    background: white;
    color: #1a2e42;
    border-radius: 18px 18px 18px 4px;
    padding: 0.7rem 1rem;
    margin: 0.5rem 3rem 0.5rem 0;
    font-size: 0.93rem;
    border: 1px solid #dde8f5;
    box-shadow: 0 2px 8px rgba(0,0,0,0.05);
}
.chat-time { font-size: 0.7rem; color: #9aa8b8; margin-top: 3px; }

/* ── Buttons ── */
.stButton > button {
    border-radius: 10px !important;
    font-weight: 700 !important;
    border: none !important;
    transition: all 0.2s !important;
}
.stButton > button:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(0,0,0,0.15) !important; }

div[data-testid="stForm"] { border: none !important; padding: 0 !important; }
</style>
""", unsafe_allow_html=True)

# ─── Session State Init ─────────────────────────────────────────────────────────
if 'chat_input' not in st.session_state:
    st.session_state.chat_input = ""
if 'openai_api_key' not in st.session_state:
    st.session_state.openai_api_key = ""

# Role-based auth state
if 'current_user' not in st.session_state:
    st.session_state.current_user = None
if 'auth_message' not in st.session_state:
    st.session_state.auth_message = ""

# ─── Overdose Alert Banner (shown on all pages) ────────────────────────────────
def show_global_overdose_alerts():
    meds = get_all_medications()
    alerts = []
    for med in meds:
        med_id, name, dosage, frequency, med_time, notes, max_dose, created = med
        intake = get_today_intake(name)
        count_today = intake[0] if intake and intake[0] else 0
        if count_today > 0:
            risk = check_overdose_risk(name, count_today, dosage)
            if risk['severity'] == 'danger':
                alerts.append(('danger', name, risk['message']))
            elif risk['severity'] == 'warning':
                alerts.append(('warning', name, risk['message']))
    for severity, name, msg in alerts:
        if severity == 'danger':
            st.error(f"🚨 **OVERDOSE RISK — {name}**: {msg}")
        else:
            st.warning(f"⚠️ **High Dose Warning — {name}**: {msg}")

# ─── Sidebar ───────────────────────────────────────────────────────────────────
st.sidebar.markdown("## 🏥 HealthGuard")
st.sidebar.markdown("---")

# ─── Login / Logout Section ────────────────────────────────────────────────────
if st.session_state.current_user is None:
    # ─── NOT LOGGED IN - Show Login/Register ───
    st.sidebar.markdown("### 🔐 Login / Register")
    
    username = st.sidebar.text_input("Username", key="login_username", placeholder="Enter username")
    password = st.sidebar.text_input("Password", type="password", key="login_password", placeholder="Enter password")
    role = st.sidebar.selectbox("Role", ["patient", "doctor", "caregiver"], index=0)
    
    col1, col2 = st.sidebar.columns(2)
    
    with col1:
        if st.button("🔑 Login", use_container_width=True, key="login_btn"):
            if not username or not password:
                st.session_state.auth_message = "⚠️ Please enter both username and password."
            else:
                user = authenticate_user(username, password)
                if user:
                    st.session_state.current_user = user
                    st.session_state.auth_message = ""
                    st.sidebar.success(f"✅ Welcome, {user['username']}!")
                    st.rerun()
                else:
                    st.session_state.auth_message = "❌ Invalid credentials."
    
    with col2:
        if st.button("📝 Register", use_container_width=True, key="register_btn"):
            if not username or not password:
                st.session_state.auth_message = "⚠️ Username and password required."
            elif len(password.encode('utf-8')) > 72:
                st.session_state.auth_message = "❌ Password too long (max 72 bytes)."
            else:
                created = create_user(username, password, role=role)
                if created:
                    st.session_state.auth_message = f"✅ Account created! Please login."
                else:
                    st.session_state.auth_message = "❌ Username already exists."
    
    # Display auth messages
    if st.session_state.auth_message:
        if "✅" in st.session_state.auth_message:
            st.sidebar.success(st.session_state.auth_message)
        elif "❌" in st.session_state.auth_message or "⚠️" in st.session_state.auth_message:
            st.sidebar.error(st.session_state.auth_message)
        else:
            st.sidebar.info(st.session_state.auth_message)

else:
    # ─── LOGGED IN - Show User Profile & Logout ────────────────────────────────
    st.sidebar.markdown("### 👤 User Profile")
    
    user_info = f"""
**Username:** {st.session_state.current_user['username']}  
**Role:** {st.session_state.current_user['role'].title()}
"""
    
    if st.session_state.current_user.get('full_name'):
        user_info += f"  \n**Name:** {st.session_state.current_user['full_name']}"
    
    st.sidebar.info(user_info)
    
    st.sidebar.markdown("---")
    
    # ─── LOGOUT BUTTON ───
    if st.sidebar.button("🚪 Logout", use_container_width=True, type="primary", key="logout_btn"):
        # Clear all session data
        st.session_state.current_user = None
        st.session_state.auth_message = "👋 You have been logged out successfully!"
        st.session_state.openai_api_key = ""  # Clear API key for security
        
        # Show success and redirect to login
        st.rerun()

st.sidebar.markdown("---")

# ─── AI Settings (Only show when logged in) ────────────────────────────────────
if st.session_state.current_user is not None:
    st.sidebar.markdown("### ⚙️ AI Settings")
    api_key_input = st.sidebar.text_input(
        "OpenAI API Key (optional)",
        value=st.session_state.openai_api_key,
        type="password",
        help="Add your OpenAI key for full AI responses. Without it, the assistant uses smart rule-based mode.",
        key="api_key_input"
    )
    if api_key_input:
        st.session_state.openai_api_key = api_key_input
        st.sidebar.success("✅ API key saved!")

    st.sidebar.markdown("---")
    st.sidebar.info("💡 **Tip:** The Health Assistant can delete medications, check overdose risk, and remind you about doses — just ask!")

# ─── Navigation (Only show when logged in) ─────────────────────────────────────
if st.session_state.current_user is not None:
    page = st.sidebar.radio(
        "Navigate",
        ["📊 Dashboard", "💊 Medications", "📈 Health Metrics", "🔎 Drug Information", "🤖 Health Assistant"],
        label_visibility="collapsed",
    )
else:
    page = None

# ─── Header ────────────────────────────────────────────────────────────────────
st.markdown('<div class="main-header">🏥 HealthGuard Monitoring System</div>', unsafe_allow_html=True)

# ─── Enforce login ─────────────────────────────────────────────────────────────
if st.session_state.current_user is None:
    st.info("👋 **Welcome to HealthGuard!**")
    st.markdown("""
    ### Please login or register to access your health dashboard.
    
    **Features:**
    - 💊 Track your medications
    - 📊 Monitor your health metrics
    - 🤖 AI health assistant
    - ⚠️ Overdose detection
    - 🔍 Drug information lookup
    
    Use the **sidebar** on the left to get started! →
    """)
    st.stop()

# ─── Show global overdose alerts (only for logged-in users) ────────────────────
show_global_overdose_alerts()

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 1: DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
if page == "📊 Dashboard":
    st.subheader("📊 Today's Overview")

    medications = get_all_medications()
    now = datetime.now()

    # Count taken today
    taken_count = 0
    overdue_count = 0
    for med in medications:
        med_id, name, dosage, frequency, med_time_str, notes, max_dose, created = med
        intake = get_today_intake(name)
        count = intake[0] if intake and intake[0] else 0
        if count > 0:
            taken_count += 1
        try:
            h, m = map(int, med_time_str.split(':'))
            med_time_obj = time(h, m)
            if med_time_obj < now.time() and count == 0:
                overdue_count += 1
        except Exception:
            pass

    adherence = int((taken_count / len(medications) * 100)) if medications else 0

    # Metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f'<div class="metric-card"><div class="metric-value">{len(medications)}</div><div class="metric-label">Total Medications</div></div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="metric-card"><div class="metric-value" style="color:#27ae60">{taken_count}</div><div class="metric-label">Taken Today</div></div>', unsafe_allow_html=True)
    with col3:
        st.markdown(f'<div class="metric-card"><div class="metric-value" style="color:#e74c3c">{overdue_count}</div><div class="metric-label">Overdue</div></div>', unsafe_allow_html=True)
    with col4:
        color = '#27ae60' if adherence >= 80 else '#f39c12' if adherence >= 50 else '#e74c3c'
        st.markdown(f'<div class="metric-card"><div class="metric-value" style="color:{color}">{adherence}%</div><div class="metric-label">Adherence Rate</div></div>', unsafe_allow_html=True)

    st.markdown("---")
    st.subheader(f"📅 Schedule — {now.strftime('%A, %d %B %Y')}")

    if medications:
        for med in medications:
            med_id, name, dosage, frequency, med_time_str, notes, max_dose, created = med
            intake = get_today_intake(name)
            taken_today = intake[0] if intake and intake[0] else 0

            # Validate record for possible inconsistencies
            warnings = _validate_med_record(med)
            warning_note = "" if not warnings else f"⚠️ Data issue: {'; '.join(warnings)}"

            # Determine status and detect any malformed time data
            invalid_time_note = None
            try:
                h, m = map(int, med_time_str.split(':'))
                is_overdue = time(h, m) < now.time() and taken_today == 0
                is_due_soon = not is_overdue and abs((h * 60 + m) - (now.hour * 60 + now.minute)) <= 30
            except Exception:
                is_overdue = is_due_soon = False
                invalid_time_note = "⚠️ Time format invalid (expected HH:MM). Please update this medication entry."

            card_class = "med-card overdue" if is_overdue else "med-card due-soon" if is_due_soon else "med-card"
            status_icon = "🔴" if is_overdue else "🟡" if is_due_soon else "🟢"

            col_a, col_b = st.columns([5, 1])
            with col_a:
                st.markdown(f"""
                <div class="{card_class}">
                    <strong>{status_icon} {med_time_str}</strong> &nbsp;|&nbsp; 
                    <strong>{name}</strong> &nbsp;({dosage})<br>
                    <small style="color:#6b7a8d">
                        {frequency} &nbsp;·&nbsp; Taken today: {taken_today}x
                        {f'&nbsp;·&nbsp; ⚠️ <b>OVERDUE</b>' if is_overdue else ''}
                        {f'&nbsp;·&nbsp; ⏰ <b>DUE SOON</b>' if is_due_soon else ''}
                        {f'<br><span style="color:#e67e22">{invalid_time_note}</span>' if invalid_time_note else ''}
                        {f'<br><span style="color:#e67e22">{warning_note}</span>' if warning_note else ''}
                    </small>
                </div>
                """, unsafe_allow_html=True)

            with col_b:
                # Check overdose risk before allowing mark as taken
                risk = check_overdose_risk(name, taken_today, dosage)
                if warnings:
                    st.warning(warning_note)
                    st.button("✅ Taken", key=f"taken_{med_id}", disabled=True)
                elif "Could not parse dosage" in risk.get('message', ''):
                    st.warning(risk['message'])
                    st.button("✅ Taken", key=f"taken_{med_id}", disabled=True)
                elif risk['severity'] == 'danger':
                    st.error("🚨 Limit!")
                elif st.button("✅ Taken", key=f"taken_{med_id}"):
                    log_medication_taken(med_id, name, dosage)
                    st.success(f"Logged {name}!")
                    st.rerun()
    else:
        st.info("No medications added yet. Go to 💊 Medications to add your first one.")

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 2: MEDICATIONS
# ══════════════════════════════════════════════════════════════════════════════
elif page == "💊 Medications":
    st.subheader("💊 Medication Management")
    tab1, tab2 = st.tabs(["➕ Add Medication", "📋 All Medications"])

    with tab1:
        with st.form("add_medication_form"):
            col1, col2 = st.columns(2)
            with col1:
                med_name    = st.text_input("💊 Medication Name*", placeholder="e.g., Paracetamol")
                dosage      = st.text_input("📊 Dosage*", placeholder="e.g., 500mg")
                frequency   = st.selectbox("🔄 Frequency*",
                    ["Once daily", "Twice daily", "Three times daily", "Four times daily", "As needed"])
            with col2:
                med_time      = st.time_input("🕐 Time to take*", value=time(9, 0))
                max_daily_dose = st.text_input("⚠️ Max Daily Dose (optional)", placeholder="e.g., 2000mg")
                notes         = st.text_area("📝 Notes", placeholder="e.g., Take with food")

            submitted = st.form_submit_button("➕ Add Medication", use_container_width=True)
            if submitted:
                if med_name and dosage and frequency:
                    try:
                        add_medication(med_name, dosage, frequency, med_time.strftime("%H:%M"), notes, max_daily_dose)
                        st.success(f"✅ {med_name} added!")
                        st.balloons()
                    except ValueError as e:
                        st.error(f"❌ {e}")
                else:
                    st.error("❌ Please fill in required fields.")

    with tab2:
        medications = get_all_medications()
        if medications:
            for med in medications:
                med_id, name, dosage, frequency, med_time, notes, max_dose, created = med
                intake = get_today_intake(name)
                taken_today = intake[0] if intake and intake[0] else 0
                risk = check_overdose_risk(name, taken_today, dosage)

                warnings = _validate_med_record(med)
                warning_note = "" if not warnings else f"⚠️ Data issue: {'; '.join(warnings)}"

                with st.expander(f"💊 {name} — {dosage} at {med_time}"):
                    c1, c2, c3 = st.columns([2, 2, 1])
                    with c1:
                        st.write(f"**Frequency:** {frequency}")
                        st.write(f"**Time:** {med_time}")
                        st.write(f"**Max Daily:** {max_dose or 'Not set'}")
                    with c2:
                        st.write(f"**Notes:** {notes or 'None'}")
                        st.write(f"**Added:** {created}")
                        st.write(f"**Taken today:** {taken_today}x")
                        if warning_note:
                            st.warning(warning_note)
                    with c3:
                        if risk['severity'] == 'danger':
                            st.error("🚨 Over limit!")
                        elif risk['severity'] == 'warning':
                            st.warning("⚠️ High dose")

                        role = st.session_state.current_user.get('role') if st.session_state.current_user else None
                        if role in ["doctor", "caregiver"]:
                            if st.button("🗑️ Delete", key=f"del_{med_id}"):
                                delete_medication(med_id)
                                st.rerun()
                        else:
                            st.caption("Only doctors/caregivers can delete medications.")
        else:
            st.info("📭 No medications yet. Add your first one above!")

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 3: HEALTH METRICS
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📈 Health Metrics":
    st.subheader("📈 Health Metrics Tracking")
    st.info("🚧 Coming soon — weight, BP, blood sugar, and more health tracking!")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Record Metrics")
        weight  = st.number_input("Weight (kg)", min_value=30.0, max_value=200.0, value=70.0)
        bp_sys  = st.number_input("Blood Pressure - Systolic", min_value=70, max_value=200, value=120)
        bp_dia  = st.number_input("Blood Pressure - Diastolic", min_value=40, max_value=130, value=80)
        sugar   = st.number_input("Blood Sugar (mg/dL)", min_value=50, max_value=500, value=100)
        if st.button("💾 Save Metrics"):
            st.success("✅ Metrics saved! (Full database integration coming soon)")

    with col2:
        st.subheader("Trends (Demo Data)")
        st.line_chart({"Weight (kg)": [70, 71, 69, 70, 72, 71], "Blood Sugar": [100, 105, 98, 102, 99, 101]})

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 4: DRUG INFORMATION
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🔎 Drug Information":
    st.subheader("🔎 Drug Information Lookup")
    st.markdown("Search for medicines — supports 🇮🇳 Indian medicines and 🌍 FDA international database.")

    drug_name = st.text_input("Enter medicine name:", placeholder="e.g., Dolo 650, Aspirin, Crocin")
    col1, col2 = st.columns(2)
    with col1:
        search_btn = st.button("🔎 Search", use_container_width=True)
    with col2:
        if st.button("📋 View Indian Medicines", use_container_width=True):
            st.info("**Available:** Dolo 650, Crocin, Combiflam, Azithral 500, Pantoprazole")

    if search_btn and drug_name:
        with st.spinner(f"Searching for {drug_name}..."):
            indian = get_indian_medicine_info(drug_name)
            if indian:
                st.success("✅ Found in Indian Medicines Database!")
                st.subheader(f"💊 {drug_name.title()}")
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown(f"**Generic:** {indian['generic_name']}")
                    st.markdown(f"**Manufacturer:** {indian['manufacturer']}")
                    st.markdown(f"**Price:** {indian['price_range']}")
                with c2:
                    st.markdown(f"**Purpose:** {indian['purpose']}")
                    st.markdown(f"**Max Daily Dose:** {indian.get('max_daily_dose', 'N/A')}")

                with st.expander("📊 Dosage Information", expanded=True):
                    st.info(indian['dosage'])
                with st.expander("⚠️ Warnings & Precautions", expanded=True):
                    st.warning(indian['warnings'])

                if st.button("➕ Add to My Medications"):
                    st.session_state['prefill_med'] = drug_name.title()
                    st.info("Go to 💊 Medications to complete adding this medicine!")
            else:
                st.info("Not in Indian database — searching FDA international database...")
                fda = search_drug_info(drug_name)
                if fda:
                    st.success("✅ Found in FDA Database!")
                    st.subheader(f"💊 {fda['brand_name']}")
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown(f"**Generic:** {fda['generic_name']}")
                        st.markdown(f"**Manufacturer:** {fda['manufacturer']}")
                    with c2:
                        st.markdown(f"**Purpose:** {fda['purpose'][:200]}...")
                    with st.expander("📋 Indications"):
                        st.write(fda['indications'][:500] + "..." if len(fda['indications']) > 500 else fda['indications'])
                    with st.expander("📊 Dosage"):
                        st.write(fda['dosage'][:500] + "..." if len(fda['dosage']) > 500 else fda['dosage'])
                    with st.expander("⚠️ Warnings"):
                        st.warning(fda['warnings'][:500] + "..." if len(fda['warnings']) > 500 else fda['warnings'])
                else:
                    st.error(f"❌ '{drug_name}' not found. Try: Dolo 650, Crocin, Combiflam, Aspirin")

    st.divider()
    st.caption("⚠️ For educational purposes only. Always consult a healthcare professional.")

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 5: AI HEALTH ASSISTANT
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🤖 Health Assistant":
    st.subheader("🤖 HealthGuard AI Assistant")

    col_chat, col_info = st.columns([3, 1])

    with col_info:
        st.markdown("### 💡 What I can do")
        st.markdown("""
        - 📋 **List** your medications  
        - 🗑️ **Delete** a medication  
          *(just say "remove Paracetamol")*  
        - ⚠️ **Check overdose** risks  
        - 🔔 **Remind** you about doses  
        - ✅ **Mark** a medication taken  
        - 💬 Answer health questions  
        """)

        st.markdown("---")
        st.markdown("### 💬 Try saying:")
        examples = [
            "Show my medications",
            "Remove Paracetamol",
            "Am I safe to take Dolo?",
            "What are my reminders?",
            "I took Crocin just now",
            "Check overdose risk",
        ]
        for ex in examples:
            if st.button(f'"{ex}"', key=f"ex_{ex}"):
                st.session_state['prefill_chat'] = ex

        st.markdown("---")
        
        # Only doctors/caregivers can clear chat
        role = st.session_state.current_user.get('role') if st.session_state.current_user else None
        if role in ["doctor", "caregiver"]:
            if st.button("🗑️ Clear Chat History"):
                clear_chat_history()
                st.success("Chat cleared!")
                st.rerun()

        # Show mode
        if st.session_state.openai_api_key:
            st.success("🤖 AI Mode: Full GPT")
        else:
            st.info("🔧 Rule-based mode\n(Add API key in sidebar for full AI)")

    with col_chat:
        # ── Load and display chat history ──────────────────────────────────────
        history = get_chat_history(limit=60)

        chat_html = '<div class="chat-container" id="chat-box">'
        if not history:
            chat_html += '<div style="text-align:center;color:#9aa8b8;padding:2rem;">👋 Say hello to get started!</div>'
        else:
            for role_msg, content, ts in history:
                # Format timestamp
                try:
                    dt_obj = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
                    ts_display = dt_obj.strftime("%I:%M %p")
                except Exception:
                    ts_display = ts

                if role_msg == "user":
                    chat_html += f'''
                    <div class="chat-msg-user">
                        {content}
                        <div class="chat-time" style="color:rgba(255,255,255,0.6);text-align:right">{ts_display}</div>
                    </div>'''
                else:
                    # Replace newlines with HTML breaks for display
                    content_html = content.replace('\n', '<br>')
                    chat_html += f'''
                    <div class="chat-msg-assistant">
                        {content_html}
                        <div class="chat-time">{ts_display}</div>
                    </div>'''

        chat_html += '</div>'
        st.markdown(chat_html, unsafe_allow_html=True)

        # Auto-scroll to bottom
        st.markdown("""
        <script>
            var chatBox = document.getElementById('chat-box');
            if (chatBox) chatBox.scrollTop = chatBox.scrollHeight;
        </script>
        """, unsafe_allow_html=True)

        # ── Input area ─────────────────────────────────────────────────────────
        prefill = st.session_state.pop('prefill_chat', "")

        with st.form("chat_form", clear_on_submit=True):
            user_input = st.text_input(
                "Message",
                value=prefill,
                placeholder="Type your message... (e.g., 'Remove Paracetamol' or 'What are my reminders?')",
                label_visibility="collapsed",
            )
            send_btn = st.form_submit_button("📤 Send", use_container_width=True)

        if send_btn and user_input.strip():
            with st.spinner("HealthGuard is thinking..."):
                if st.session_state.openai_api_key:
                    response = run_agent_with_history(
                        user_input.strip(),
                        st.session_state.openai_api_key
                    )
                else:
                    response = run_simple_chat(user_input.strip())
            st.rerun()

# ─── Footer ────────────────────────────────────────────────────────────────────
st.sidebar.divider()
st.sidebar.markdown("### ℹ️ About")
st.sidebar.caption("""
**HealthGuard** v2.0  
Built with Streamlit + Python  
Healthcare Monitoring System

⚠️ For informational purposes only.  
Always consult your doctor.
""")