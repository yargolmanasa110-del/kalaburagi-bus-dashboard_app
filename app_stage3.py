import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path
from io import BytesIO
import sqlite3
import uuid
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

# ------------------------------------------------------------
# PAGE CONFIG + STYLE
# ------------------------------------------------------------
st.set_page_config(
    page_title="Kalaburagi Bus Intelligence",
    page_icon="🚌",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .stApp { background: #f5f7fb; }
    .block-container { padding-top: 1.5rem; }
    .hero {
        padding: 1.35rem 1.6rem; border-radius: 16px;
        background: linear-gradient(110deg, #102a43, #176b87);
        color: white; margin-bottom: 1rem;
    }
    .hero h1 { color: white; margin: 0; }
    .hero p { color: #e6f3f7; margin: .35rem 0 0 0; }
    .portal-card {
        background: white; padding: 1.4rem; border-radius: 14px;
        border: 1px solid #e4eaf1; min-height: 170px;
    }
    div[data-testid="stMetric"] {
        background: white; padding: 14px; border-radius: 12px;
        border: 1px solid #e5eaf0;
    }
    .service-number {
        background: #e9f7ef; padding: 1rem; border-radius: 10px;
        border: 1px solid #a9dfbf; font-size: 1.2rem; font-weight: 700;
    }
</style>
""", unsafe_allow_html=True)

DATA_FILE = Path(__file__).parent / "bus_ticket_data.xlsx"
DB_FILE = Path(__file__).parent / "customer_requests.db"

# ------------------------------------------------------------
# CUSTOMER REQUEST DATABASE
# ------------------------------------------------------------
def db_connection():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

def initialise_db():
    with db_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS requests (
                service_no TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                passenger_name TEXT NOT NULL,
                contact TEXT,
                category TEXT NOT NULL,
                location TEXT,
                details TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Submitted'
            )
        """)
        conn.commit()

initialise_db()

# English / Kannada interface selector
if "language" not in st.session_state:
    st.session_state.language = "English"

def create_request(name, contact, category, location, details):
    service_no = "KKB-" + datetime.now().strftime("%y%m%d") + "-" + uuid.uuid4().hex[:6].upper()
    with db_connection() as conn:
        conn.execute(
            """INSERT INTO requests
            (service_no, created_at, passenger_name, contact, category, location, details, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'Submitted')""",
            (service_no, datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
             name, contact, category, location, details)
        )
        conn.commit()
    return service_no

def get_request(service_no):
    with db_connection() as conn:
        return pd.read_sql_query(
            "SELECT service_no, created_at, category, location, details, status FROM requests WHERE service_no = ?",
            conn, params=(service_no,)
        )

def get_all_requests():
    with db_connection() as conn:
        return pd.read_sql_query("SELECT * FROM requests ORDER BY created_at DESC", conn)

# ------------------------------------------------------------
# DATA LOADING / CLEANING
# ------------------------------------------------------------
REQUIRED = [
    "Waybill Number", "Ticket Number", "From Stop", "To Stop",
    "Date", "Time", "Total Psgr", "Coll Amt", "Uncoll Amt"
]

def clean_data(raw):
    raw = raw.copy()
    raw.columns = [str(c).strip() for c in raw.columns]
    missing = [c for c in REQUIRED if c not in raw.columns]
    if missing:
        raise ValueError("Missing expected columns: " + ", ".join(missing))
    d = raw[REQUIRED].copy()
    d["Date"] = pd.to_datetime(d["Date"], errors="coerce")
    # Handles Excel time objects, strings, and datetime values.
    d["Time"] = pd.to_datetime(d["Time"].astype(str), errors="coerce")
    for c in ["Total Psgr", "Coll Amt", "Uncoll Amt"]:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d["From Stop"] = d["From Stop"].astype("string").str.strip()
    d["To Stop"] = d["To Stop"].astype("string").str.strip()
    d["Hour"] = d["Time"].dt.hour
    d["Journey"] = d["From Stop"].fillna("Unknown") + " → " + d["To Stop"].fillna("Unknown")
    return d

@st.cache_data
def load_default_data(path_string):
    return clean_data(pd.read_excel(path_string))

def load_uploaded_data(uploaded_file):
    content = uploaded_file.getvalue()
    if uploaded_file.name.lower().endswith(".csv"):
        raw = pd.read_csv(BytesIO(content))
    else:
        raw = pd.read_excel(BytesIO(content))
    return clean_data(raw)

# ------------------------------------------------------------
# SESSION STATE + LOGIN
# ------------------------------------------------------------
if "portal" not in st.session_state:
    st.session_state.portal = "Welcome"
if "officer_authenticated" not in st.session_state:
    st.session_state.officer_authenticated = False
if "officer_name" not in st.session_state:
    st.session_state.officer_name = ""

def show_header():
    st.markdown("""
    <div class="hero">
      <h1>🚌 Kalaburagi Bus Intelligence</h1>
      <p>Intelligent public transport analytics • Solvathon 2026 • Problem Statement 3</p>
    </div>
    """, unsafe_allow_html=True)

def logout():
    st.session_state.officer_authenticated = False
    st.session_state.officer_name = ""
    st.session_state.portal = "Welcome"
    st.rerun()

# Demo credentials for local prototype. Configure secrets before public deployment.
try:
    OFFICER_USERNAME = st.secrets["officer"]["username"]
    OFFICER_PASSWORD = st.secrets["officer"]["password"]
except Exception:
    OFFICER_USERNAME = "officer"
    OFFICER_PASSWORD = "admin123"

if st.session_state.portal == "Welcome":
    show_header()
    st.title("Welcome")
    st.write("Choose the portal you want to access.")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        <div class="portal-card">
          <h2>🔐 Officer Portal</h2>
          <p>Ticket analytics, route insights, data uploads and service-request monitoring.</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Continue to Officer Login", use_container_width=True, type="primary"):
            st.session_state.portal = "Officer Login"
            st.rerun()
    with col2:
        st.markdown("""
        <div class="portal-card">
          <h2>🧑‍🤝‍🧑 Customer Portal</h2>
          <p>Submit a passenger facility request or complaint and track its service number.</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Open Customer Portal", use_container_width=True):
            st.session_state.portal = "Customer Portal"
            st.rerun()
    st.info("Prototype note: officer login is a demonstration login, not production-grade security. Do not publish with demo credentials.")

elif st.session_state.portal == "Officer Login":
    show_header()
    st.title("🔐 Officer Login")
    st.caption("Authorised transport department personnel")
    with st.form("officer_login_form"):
        username = st.text_input("Officer username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in", type="primary", use_container_width=True)
    if submitted:
        if username == OFFICER_USERNAME and password == OFFICER_PASSWORD:
            st.session_state.officer_authenticated = True
            st.session_state.officer_name = username
            st.session_state.portal = "Officer Portal"
            st.success("Login successful.")
            st.rerun()
        else:
            st.error("Incorrect username or password.")
    st.caption("Local demo credentials: username `officer` • password `admin123`")
    if st.button("← Back to portal selection"):
        st.session_state.portal = "Welcome"
        st.rerun()

elif st.session_state.portal == "Customer Portal":
    show_header()
    st.title("🧑‍🤝‍🧑 Passenger / Customer Portal")
    st.write("Submit a service request to the transport department or check an existing request.")
    submit_tab, track_tab = st.tabs(["Submit a request", "Track a request"])
    with submit_tab:
        with st.form("customer_request_form", clear_on_submit=True):
            name = st.text_input("Passenger name *")
            contact = st.text_input("Mobile number or email (optional)")
            category = st.selectbox("Request category", [
                "Bus facility", "Bus timing", "Route or stop", "Cleanliness",
                "Staff behaviour", "Accessibility assistance", "Lost property", "Other"
            ])
            location = st.text_input("Bus stop / route / location")
            details = st.text_area("Describe your complaint or request *", height=120)
            send = st.form_submit_button("Submit request", type="primary")
        if send:
            if not name.strip() or not details.strip():
                st.error("Please enter your name and describe your request.")
            else:
                number = create_request(name.strip(), contact.strip(), category, location.strip(), details.strip())
                st.success("Your request has been registered.")
                st.markdown(f'<div class="service-number">Your service number: {number}</div>', unsafe_allow_html=True)
                st.warning("Please save this number. You will need it to track your request.")
    with track_tab:
        service_no = st.text_input("Enter your service number")
        if st.button("Check status"):
            if service_no.strip():
                result = get_request(service_no.strip().upper())
                if result.empty:
                    st.error("No request found. Check the service number and try again.")
                else:
                    st.dataframe(result, use_container_width=True, hide_index=True)
            else:
                st.warning("Enter your service number first.")
    if st.button("← Back to portal selection"):
        st.session_state.portal = "Welcome"
        st.rerun()

elif st.session_state.portal == "Officer Portal":
    if not st.session_state.officer_authenticated:
        st.session_state.portal = "Officer Login"
        st.rerun()

    with st.sidebar:
        st.success(f"Signed in: {st.session_state.officer_name}")
        if st.button("Log out", use_container_width=True):
            logout()
        st.divider()
        st.header("ಭಾಷೆ / Language")
        st.session_state.language = st.selectbox(
            "Choose language / ಭಾಷೆ ಆಯ್ಕೆಮಾಡಿ",
            ["English", "ಕನ್ನಡ"],
            index=0 if st.session_state.language == "English" else 1
        )
        is_kn = st.session_state.language == "ಕನ್ನಡ"
        st.header("ದತ್ತಾಂಶ" if is_kn else "Data")
        uploaded = st.file_uploader("Upload updated Excel or CSV", type=["xlsx", "xls", "csv"])
        st.caption("Expected columns must match the ticket-machine export format.")
        st.header("ಫಿಲ್ಟರ್‌ಗಳು" if is_kn else "Filters")

    try:
        if uploaded is not None:
            d = load_uploaded_data(uploaded)
            st.sidebar.success(f"Loaded: {uploaded.name}")
        elif DATA_FILE.exists():
            d = load_default_data(str(DATA_FILE))
        else:
            st.error("bus_ticket_data.xlsx was not found beside app.py. Place the Excel file in the project folder or upload it in the sidebar.")
            st.stop()
    except Exception as e:
        st.error(f"Could not read the dataset: {e}")
        st.stop()

    show_header()
    st.title("ಅಧಿಕಾರಿ ಡ್ಯಾಶ್‌ಬೋರ್ಡ್" if is_kn else "Officer Dashboard")
    st.caption("ಟಿಕೆಟ್ ವಿಶ್ಲೇಷಣೆ • ಮಾರ್ಗ ಮತ್ತು ನಿಲ್ದಾಣ ಮಾಹಿತಿ • ಗ್ರಾಹಕ ಸೇವೆ" if is_kn else "Ticket analytics • Route and stop intelligence • Customer service monitoring")

    valid_dates = d["Date"].dropna()
    if valid_dates.empty:
        st.error("No valid dates found in the Date column.")
        st.stop()
    date_min, date_max = valid_dates.min().date(), valid_dates.max().date()
    date_range = st.sidebar.date_input(
        "Travel date range", value=(date_min, date_max),
        min_value=date_min, max_value=date_max
    )
    f = d.copy()
    if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
        f = f[(f["Date"].dt.date >= date_range[0]) & (f["Date"].dt.date <= date_range[1])]
    elif date_range:
        f = f[f["Date"].dt.date == date_range]

    stops = sorted(set(f["From Stop"].dropna().astype(str)) | set(f["To Stop"].dropna().astype(str)))
    chosen_stops = st.sidebar.multiselect("Stops (boarding or destination)", stops)
    if chosen_stops:
        f = f[f["From Stop"].isin(chosen_stops) | f["To Stop"].isin(chosen_stops)]

    # Additional filters
    with st.sidebar.expander("ಹೆಚ್ಚುವರಿ ಫಿಲ್ಟರ್‌ಗಳು" if is_kn else "More filters", expanded=False):
        from_options = ["All"] + sorted(f["From Stop"].dropna().astype(str).unique().tolist())
        to_options = ["All"] + sorted(f["To Stop"].dropna().astype(str).unique().tolist())
        from_choice = st.selectbox("From stop" if not is_kn else "ಪ್ರಾರಂಭ ನಿಲ್ದಾಣ", from_options)
        to_choice = st.selectbox("To stop" if not is_kn else "ಗಮ್ಯ ನಿಲ್ದಾಣ", to_options)
        if from_choice != "All":
            f = f[f["From Stop"] == from_choice]
        if to_choice != "All":
            f = f[f["To Stop"] == to_choice]
        hours = sorted(f["Hour"].dropna().astype(int).unique().tolist())
        if hours:
            hour_choice = st.multiselect("Travel / ticket hour" if not is_kn else "ಸಮಯ", hours)
            if hour_choice:
                f = f[f["Hour"].isin(hour_choice)]

    st.caption((f"{len(f):,} ಟಿಕೆಟ್ ದಾಖಲೆಗಳು" if is_kn else f"Showing {len(f):,} ticket records from {len(d):,} rows in the loaded file."))

    tabs = st.tabs(["Overview", "Stop & Journey Analysis", "Time Patterns", "Insights Assistant", "Customer Requests", "Data Quality"])
    a, b, c, e = st.columns(4)
    a.metric("Ticket records", f"{len(f):,}")
    b.metric("Passengers recorded", f"{int(f['Total Psgr'].fillna(0).sum()):,}")
    c.metric("Coll Amt total", f"₹{f['Coll Amt'].fillna(0).sum():,.0f}")
    e.metric("Uncoll Amt total", f"₹{f['Uncoll Amt'].fillna(0).sum():,.0f}")
    st.info("Data note: Coll Amt and Uncoll Amt retain their source column names. Confirm their accounting meaning with the department before describing either as revenue. One-day data cannot support reliable long-term forecasting.")

    with tabs[0]:
        left, right = st.columns(2)
        with left:
            by_from = f.groupby("From Stop", dropna=False)["Total Psgr"].sum().nlargest(12).reset_index()
            st.subheader("Top boarding stops by recorded passengers")
            if not by_from.empty:
                st.plotly_chart(px.bar(by_from, x="Total Psgr", y="From Stop", orientation="h", title="Top 12 boarding stops"), use_container_width=True)
        with right:
            by_to = f.groupby("To Stop", dropna=False)["Total Psgr"].sum().nlargest(12).reset_index()
            st.subheader("Top destination stops by recorded passengers")
            if not by_to.empty:
                st.plotly_chart(px.bar(by_to, x="Total Psgr", y="To Stop", orientation="h", title="Top 12 destination stops"), use_container_width=True)
        st.subheader("Collection fields by boarding stop")
        stop_money = f.groupby("From Stop", dropna=False)[["Coll Amt", "Uncoll Amt"]].sum().reset_index().sort_values("Coll Amt", ascending=False).head(15)
        st.plotly_chart(px.bar(stop_money, x="From Stop", y=["Coll Amt", "Uncoll Amt"], barmode="group"), use_container_width=True)

    with tabs[1]:
        st.subheader("Most common stop-to-stop journeys")
        journey = f.groupby("Journey", dropna=False).agg(
            Ticket_records=("Ticket Number", "size"),
            Recorded_passengers=("Total Psgr", "sum"),
            Coll_Amt=("Coll Amt", "sum"),
            Uncoll_Amt=("Uncoll Amt", "sum")
        ).reset_index().sort_values("Ticket_records", ascending=False).head(20)
        if not journey.empty:
            st.plotly_chart(px.bar(journey.sort_values("Ticket_records"), x="Ticket_records", y="Journey", orientation="h", title="Top 20 journeys by ticket-record count"), use_container_width=True)
        st.dataframe(journey, use_container_width=True, hide_index=True)

    with tabs[2]:
        st.subheader("Ticket activity by hour")
        hourly = f.dropna(subset=["Hour"]).groupby("Hour").agg(
            Ticket_records=("Ticket Number", "size"),
            Recorded_passengers=("Total Psgr", "sum")
        ).reset_index()
        if not hourly.empty:
            st.plotly_chart(px.line(hourly, x="Hour", y=["Ticket_records", "Recorded_passengers"], markers=True, title="Hourly ticket records and recorded passengers"), use_container_width=True)
            peak = hourly.loc[hourly["Ticket_records"].idxmax()]
            st.metric("Peak ticket-record hour", f"{int(peak['Hour']):02d}:00")
        else:
            st.warning("No usable time values found.")
        st.caption("The chart uses the Time field. Confirm with the department what event that timestamp represents.")

    with tabs[3]:
        st.subheader("📊 Daily service summary")
        if f.empty:
            st.info("No records match the current filters.")
        else:
            total_passengers = int(f["Total Psgr"].fillna(0).sum())
            top_board = f.groupby("From Stop")["Total Psgr"].sum().sort_values(ascending=False)
            top_dest = f.groupby("To Stop")["Total Psgr"].sum().sort_values(ascending=False)
            hourly_assist = f.dropna(subset=["Hour"]).groupby("Hour")["Ticket Number"].count()
            summary_lines = [
                f"Current selection contains {len(f):,} ticket records.",
                f"Recorded passenger total: {total_passengers:,}.",
                (f"Top boarding stop by recorded passengers: {top_board.index[0]} ({int(top_board.iloc[0]):,})." if not top_board.empty else "No boarding-stop values available."),
                (f"Top destination by recorded passengers: {top_dest.index[0]} ({int(top_dest.iloc[0]):,})." if not top_dest.empty else "No destination values available."),
                (f"Peak ticket-record hour: {int(hourly_assist.idxmax()):02d}:00 ({int(hourly_assist.max()):,} records)." if not hourly_assist.empty else "No usable time values available.")
            ]
            for line in summary_lines:
                st.write("• " + line)
            st.download_button(
                "⬇️ Download text summary",
                data="\\n".join(summary_lines).encode("utf-8"),
                file_name="kalaburagi_service_summary.txt",
                mime="text/plain"
            )
        st.divider()
        st.subheader("💬 Ask the data assistant")
        st.caption("This first version answers common questions directly from the currently filtered data. It is a rule-based helper, not a connected generative AI service.")
        question = st.text_input("Ask about passengers, tickets, busiest stop, top route, or peak hour", key="data_assistant_question")
        if st.button("Get answer", key="data_assistant_button"):
            q = question.lower().strip()
            if not q:
                st.warning("Type a question first.")
            elif any(word in q for word in ["passenger", "ಜನ", "ಪ್ರಯಾಣಿಕ"]):
                st.info(f"Recorded passengers in the current selection: {int(f['Total Psgr'].fillna(0).sum()):,}.")
            elif any(word in q for word in ["ticket", "record", "ಟಿಕೆಟ್"]):
                st.info(f"Ticket records in the current selection: {len(f):,}.")
            elif any(word in q for word in ["hour", "time", "peak", "busy time", "ಸಮಯ"]):
                h = f.dropna(subset=["Hour"]).groupby("Hour")["Ticket Number"].count()
                if h.empty:
                    st.info("There are no usable time values in this selection.")
                else:
                    st.info(f"Peak ticket-record hour: {int(h.idxmax()):02d}:00, with {int(h.max()):,} records.")
            elif any(word in q for word in ["boarding", "from stop", "start", "ಹತ್ತುವ"]):
                x = f.groupby("From Stop")["Total Psgr"].sum().sort_values(ascending=False)
                st.info(f"Top boarding stop: {x.index[0]} ({int(x.iloc[0]):,} recorded passengers)." if not x.empty else "No boarding-stop data found.")
            elif any(word in q for word in ["destination", "to stop", "end", "ಇಳಿಯುವ"]):
                x = f.groupby("To Stop")["Total Psgr"].sum().sort_values(ascending=False)
                st.info(f"Top destination: {x.index[0]} ({int(x.iloc[0]):,} recorded passengers)." if not x.empty else "No destination data found.")
            elif any(word in q for word in ["route", "journey", "ಮಾರ್ಗ"]):
                x = f.groupby("Journey").size().sort_values(ascending=False)
                st.info(f"Most frequent recorded journey: {x.index[0]} ({int(x.iloc[0]):,} ticket records)." if not x.empty else "No journey data found.")
            else:
                st.warning("I can answer questions about passenger totals, ticket records, busiest boarding stop, destination, common journey, and peak hour.")
        st.caption("Important: answers describe the loaded ticket records only. They are not live bus locations, verified passenger counts, or forecasts.")

    with tabs[4]:
        st.subheader("Passenger service requests")
        requests = get_all_requests()
        if requests.empty:
            st.info("No customer requests have been submitted yet.")
        else:
            st.metric("Total requests", len(requests))
            st.dataframe(requests, use_container_width=True, hide_index=True)
            st.caption("This prototype displays requests. Workflow actions and notifications can be added in the next stage.")

    with tabs[4]:
        st.subheader("Data quality checks")
        quality = pd.DataFrame({
            "Check": [
                "Rows loaded", "Missing destination", "Missing date", "Unparseable time",
                "Zero passenger rows", "Duplicate (Waybill Number + Ticket Number)",
                "Rows with negative Coll/Uncoll amount"
            ],
            "Result": [
                len(d), int(d["To Stop"].isna().sum()), int(d["Date"].isna().sum()),
                int(d["Time"].isna().sum()), int((d["Total Psgr"] == 0).sum()),
                int(d.duplicated(["Waybill Number", "Ticket Number"]).sum()),
                int(((d[["Coll Amt", "Uncoll Amt"]] < 0).any(axis=1)).sum())
            ]
        })
        st.dataframe(quality, use_container_width=True, hide_index=True)
        st.subheader("Filtered ticket records")
        export_df = f.drop(columns=["Hour", "Journey"], errors="ignore")
        st.download_button(
            "⬇️ Download filtered records as CSV",
            data=export_df.to_csv(index=False).encode("utf-8"),
            file_name="kalaburagi_filtered_ticket_records.csv",
            mime="text/csv"
        )
        st.dataframe(export_df, use_container_width=True, hide_index=True)

        # Excel export
        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            export_df.to_excel(writer, index=False, sheet_name="Filtered Tickets")
            quality.to_excel(writer, index=False, sheet_name="Data Quality")
        st.download_button(
            "⬇️ Download Excel report",
            data=excel_buffer.getvalue(),
            file_name="kalaburagi_daily_report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        # Simple PDF summary
        pdf_buffer = BytesIO()
        pdf = canvas.Canvas(pdf_buffer, pagesize=A4)
        pdf.setFont("Helvetica-Bold", 16)
        pdf.drawString(45, 800, "Kalaburagi Bus Intelligence - Daily Summary")
        pdf.setFont("Helvetica", 10)
        lines = [
            f"Ticket records: {len(f):,}",
            f"Recorded passengers: {int(f['Total Psgr'].fillna(0).sum()):,}",
            f"Coll Amt total: Rs. {f['Coll Amt'].fillna(0).sum():,.0f}",
            f"Uncoll Amt total: Rs. {f['Uncoll Amt'].fillna(0).sum():,.0f}",
            f"Rows in source file: {len(d):,}",
            "Note: Coll Amt and Uncoll Amt retain original source labels.",
            "The supplied sample contains one service date; long-term forecasts need more history."
        ]
        y = 770
        for line in lines:
            pdf.drawString(45, y, line)
            y -= 22
        pdf.save()
        st.download_button(
            "⬇️ Download PDF summary",
            data=pdf_buffer.getvalue(),
            file_name="kalaburagi_daily_summary.pdf",
            mime="application/pdf"
        )

    st.divider()
    st.caption("Prototype for Kalaburagi city-service ticket data. The supplied workbook contains one service date; multi-day history is required for defensible forecasting.")
