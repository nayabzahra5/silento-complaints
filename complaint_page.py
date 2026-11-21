"""
Silento public complaint page (Streamlit).
Sends each complaint to the API; the API saves it to the S3 raw zone.

Secrets needed (Streamlit "Secrets" settings, never in the code):
  API_URL    = "https://xxxx.execute-api.ap-south-1.amazonaws.com/complaints"
  API_SECRET = "the same long random string you set on the Lambda"
"""
import requests
import streamlit as st

API_URL = st.secrets["API_URL"]
API_SECRET = st.secrets["API_SECRET"]

AREAS = [
    "Kot Lakhpat", "Gulberg", "DHA", "Johar Town", "Model Town", "Township",
    "Shahdara", "Iqbal Town", "Samanabad", "Ravi Road", "Walled City", "Cantt",
    "Wapda Town", "Bahria Town", "Other",
]
NOISE_TYPES = [
    "Factory / industry", "Traffic / horns", "Construction",
    "Loudspeaker / event", "Generator", "Other",
]

st.set_page_config(page_title="Silento: Report noise", layout="centered")
st.title("Report a noise problem")
st.write(
    "Tell us where the noise is and what is causing it. "
    "You can write in English or Roman Urdu."
)

with st.form("complaint_form", clear_on_submit=True):
    text = st.text_area(
        "What is happening?",
        placeholder="e.g. kot lakhpat marbal factory k pas bht shor ho ra h",
        max_chars=1000,
    )
    area = st.selectbox("Area", AREAS)
    noise_type = st.selectbox("Type of noise", NOISE_TYPES)
    with st.expander("Add exact location (optional)"):
        lat = st.text_input("Latitude", placeholder="31.5204")
        lon = st.text_input("Longitude", placeholder="74.3587")
    submitted = st.form_submit_button("Submit complaint")

if submitted:
    if len(text.strip()) < 5:
        st.error("Please describe the problem in a few words.")
    else:
        payload = {
            "text": text.strip(),
            "area": area,
            "noise_type": noise_type,
            "lat": lat.strip() or None,
            "lon": lon.strip() or None,
        }
        try:
            resp = requests.post(
                API_URL,
                json=payload,
                headers={"x-api-secret": API_SECRET},
                timeout=15,
            )
            if resp.status_code == 200:
                cid = resp.json().get("complaint_id", "")
                st.success(f"Thank you. Your complaint has been received. ID: {cid}")
            else:
                st.error("Sorry, we could not save your complaint. Please try again.")
        except requests.RequestException:
            st.error("Could not reach the server. Please try again later.")

st.caption("Please do not include phone numbers or other personal details.")
