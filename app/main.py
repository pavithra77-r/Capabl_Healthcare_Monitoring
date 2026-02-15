import streamlit as st
import pandas as pd
import os

# ==============================
# CONFIG
# ==============================
DATA_PATH = "data/medications.csv"

# Ensure data folder exists
os.makedirs("data", exist_ok=True)

# ==============================
# MOCK AI FUNCTION
# ==============================
def mock_ai_response(question):
    question = question.lower()

    if "paracetamol" in question:
        return "Paracetamol is commonly used to relieve mild to moderate pain and reduce fever. It is generally safe when taken within recommended dosage limits."

    elif "metformin" in question:
        return "Metformin is used to manage type 2 diabetes. It helps control blood sugar levels by improving insulin sensitivity."

    elif "side effect" in question:
        return "Common medication side effects may include nausea, dizziness, or mild stomach upset. Always consult a healthcare professional for serious symptoms."

    elif "dosage" in question:
        return "Dosage depends on the medication type, patient age, and medical condition. Always follow your doctor's prescription instructions."

    elif "food" in question:
        return "Some medications should be taken with food to avoid stomach irritation, while others require an empty stomach. Please check your prescription guidelines."

    else:
        return "I am a virtual medication assistant. I can provide general information about common medications, usage, and precautions."


# ==============================
# SIDEBAR NAVIGATION
# ==============================
st.sidebar.title("💊 Healthcare Monitoring System")

page = st.sidebar.radio(
    "Navigate",
    ["🏠 Dashboard", "➕ Add Medication", "🤖 AI Assistant"]
)

# ==============================
# DASHBOARD
# ==============================
if page == "🏠 Dashboard":

    st.title("📊 Medication Dashboard")

    if os.path.exists(DATA_PATH):
        df = pd.read_csv(DATA_PATH)

        if not df.empty:

            # ===== METRICS =====
            total_meds = len(df)
            unique_meds = df["name"].nunique()

            # Count today's medications
            from datetime import datetime
            current_time = datetime.now().strftime("%H:%M")
            today_count = len(df[df["time"] == current_time])

            col1, col2, col3 = st.columns(3)

            col1.metric("💊 Total Entries", total_meds)
            col2.metric("🧾 Unique Medications", unique_meds)
            col3.metric("⏰ Scheduled Now", today_count)

            st.divider()

            # ===== TABLE =====
            st.subheader("📋 Your Medications")
            st.dataframe(df, use_container_width=True)

        else:
            st.info("No medications added yet.")
    else:
        st.warning("Medication file not found.")

# ==============================
# ADD MEDICATION
# ==============================
elif page == "➕ Add Medication":

    st.title("➕ Add Medication")

    with st.form("med_form"):
        name = st.text_input("Medication Name")
        time = st.time_input("Time to take medication")
        dosage = st.text_input("Dosage (e.g., 1 tablet, 5ml)")

        submit = st.form_submit_button("Add Medication")

    if submit:
        if name.strip() != "" and dosage.strip() != "":
            new_data = pd.DataFrame(
                [[name, time.strftime("%H:%M"), dosage]],
                columns=["name", "time", "dosage"]
            )

            if os.path.exists(DATA_PATH):
                new_data.to_csv(DATA_PATH, mode="a", header=False, index=False)
            else:
                new_data.to_csv(DATA_PATH, index=False)

            st.success("Medication added successfully ✅")
            st.rerun()
        else:
            st.error("Please fill all fields ❌")


# ==============================
# AI ASSISTANT
# ==============================
elif page == "🤖 AI Assistant":

    st.title("🤖 AI Medication Assistant")

    user_question = st.text_area("Ask a question about any medication")

    if st.button("Ask AI"):
        if user_question.strip() != "":
            with st.spinner("Analyzing..."):
                response = mock_ai_response(user_question)
                st.success(response)
        else:
            st.warning("Please enter a question.")
