import streamlit as st
import pandas as pd
import os

from openai import OpenAI

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])


DATA_PATH = "data/medications.csv"

st.set_page_config(page_title="Medication Tracker")

st.title("💊 Medication Tracker")
st.write("Add and track your daily medications easily.")

# ------------------ ADD MEDICATION ------------------

st.subheader("➕ Add Medication")

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
    else:
        st.error("Please fill all fields ❌")

# ------------------ DISPLAY MEDICATIONS ------------------

st.subheader("📋 Your Medications")

if os.path.exists(DATA_PATH):
    df = pd.read_csv(DATA_PATH)

    if not df.empty:
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No medications added yet.")
else:
    st.warning("Medication file not found.")

# ------------------ AI MEDICATION ASSISTANT ------------------

st.subheader("🤖 Ask AI About Your Medication")

user_question = st.text_area("Ask a question about any medication")

if st.button("Ask AI"):
    if user_question.strip() != "":
        with st.spinner("Thinking..."):
            try:
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "You are a helpful medical assistant. Provide general medication information. Do not provide diagnosis."},
                        {"role": "user", "content": user_question}
                    ],
                )

                answer = response.choices[0].message.content
                st.success(answer)

            except Exception as e:
                st.error("Error: " + str(e))
    else:
        st.warning("Please enter a question.")
