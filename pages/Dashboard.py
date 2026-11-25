import hmac
import time

import boto3
import pandas as pd
import streamlit as st

REGION = "ap-south-1"
DATABASE = "silento"
OUTPUT = "s3://silento-data-lake/athena-results/"

st.set_page_config(page_title="Silento - Lahore Noise", page_icon="🔊", layout="wide")


@st.cache_resource
def athena_client():
    return boto3.client(
        "athena",
        region_name=REGION,
        aws_access_key_id=st.secrets["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=st.secrets["AWS_SECRET_ACCESS_KEY"],
    )


@st.cache_data(ttl=600, show_spinner="Querying Athena...")
def query(sql):
    client = athena_client()
    qid = client.start_query_execution(
        QueryString=sql,
        QueryExecutionContext={"Database": DATABASE},
        ResultConfiguration={"OutputLocation": OUTPUT},
        WorkGroup="primary",
    )["QueryExecutionId"]
    for _ in range(60):
        status = client.get_query_execution(QueryExecutionId=qid)["QueryExecution"]["Status"]
        if status["State"] in ("SUCCEEDED", "FAILED", "CANCELLED"):
            break
        time.sleep(1)
    if status["State"] != "SUCCEEDED":
        raise RuntimeError(status.get("StateChangeReason", status["State"]))
    rows, header = [], None
    for page in client.get_paginator("get_query_results").paginate(QueryExecutionId=qid):
        for r in page["ResultSet"]["Rows"]:
            vals = [c.get("VarCharValue") for c in r["Data"]]
            if header is None:
                header = vals
            else:
                rows.append(vals)
    df = pd.DataFrame(rows, columns=header)
    for c in df.columns:
        try:
            df[c] = pd.to_numeric(df[c])
        except (ValueError, TypeError):
            pass
    return df


def public_view():
    st.title("🔊 Silento: Lahore noise dashboard")
    st.caption("Noise measurements (NoiseCapture) and citizen complaints, "
               "processed automatically on AWS. Aggregated data only.")
    st.page_link("complaint_page.py", label="Report a noise complaint", icon="📢")

    summary = query("SELECT * FROM area_summary")
    centres = query("SELECT * FROM area_lookup")
    scored = summary.dropna(subset=["avg_db"])

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Noise measurements", int(summary["points"].fillna(0).sum()))
    c2.metric("Complaints", int(summary["complaints"].fillna(0).sum()))
    c3.metric("High-severity complaints", int(summary["high_complaints"].fillna(0).sum()))
    if len(scored):
        top = scored.sort_values("hotspot_rank").iloc[0]
        c4.metric("Noisiest area", top["area"], f"{top['avg_db']} dB")

    st.subheader("Average noise by area")
    m = scored.merge(centres, on="area").rename(columns={"c_lat": "lat", "c_lon": "lon"})
    m["size"] = (m["avg_db"] - m["avg_db"].min() + 1) * 150
    left, right = st.columns([3, 2])
    left.map(m, latitude="lat", longitude="lon", size="size")
    right.dataframe(
        scored.sort_values("hotspot_rank")[["hotspot_rank", "area", "avg_db", "max_db",
                                            "complaints"]],
        hide_index=True, use_container_width=True)

    st.subheader("Noise over the day")
    hourly = query("SELECT hour, ROUND(SUM(avg_db * points) / SUM(points), 1) AS avg_db "
                   "FROM area_noise_hourly GROUP BY hour ORDER BY hour")
    st.line_chart(hourly, x="hour", y="avg_db")

    st.subheader("Noise by month")
    monthly = query("SELECT year_month, ROUND(SUM(avg_db * points) / SUM(points), 1) AS avg_db "
                    "FROM area_noise_monthly GROUP BY year_month ORDER BY year_month")
    st.bar_chart(monthly, x="year_month", y="avg_db")

    st.subheader("Complaints")
    a, b = st.columns(2)
    src = query("SELECT noise_source, SUM(complaints) AS complaints "
                "FROM complaints_by_area_source GROUP BY noise_source ORDER BY 2 DESC")
    a.caption("By noise source")
    a.bar_chart(src, x="noise_source", y="complaints")
    daily = query("SELECT CAST(received_date AS varchar) AS day, complaints "
                  "FROM complaints_daily ORDER BY 1")
    b.caption("Per day")
    b.bar_chart(daily, x="day", y="complaints")


def epa_view():
    st.title("🛡️ EPA view: hotspots and complaint analysis")
    summary = query("SELECT * FROM area_summary")
    st.subheader("Hotspot ranking")
    st.dataframe(summary.sort_values("hotspot_rank", na_position="last"),
                 hide_index=True, use_container_width=True)
    st.download_button("Download ranking (CSV)", summary.to_csv(index=False),
                       "hotspots.csv", "text/csv")

    st.subheader("Complaints by area, source and severity")
    cs = query("SELECT area, noise_source, severity, SUM(complaints) AS complaints "
               "FROM complaints_by_area_source GROUP BY 1, 2, 3 ORDER BY 4 DESC")
    st.dataframe(cs, hide_index=True, use_container_width=True)

    st.subheader("Night-time noise vs average (dB)")
    night = summary.dropna(subset=["night_avg_db"])[["area", "avg_db", "night_avg_db"]]
    st.bar_chart(night, x="area")


page = st.sidebar.radio("View", ["Public", "EPA login"])
try:
    if page == "Public":
        public_view()
    else:
        pw = st.sidebar.text_input("EPA password", type="password")
        expected = st.secrets.get("EPA_PASSWORD", "")
        if pw and expected and hmac.compare_digest(pw, expected):
            epa_view()
        else:
            st.info("Enter the EPA password in the sidebar.")
except Exception as e:
    st.error(f"Could not load data: {e}")
