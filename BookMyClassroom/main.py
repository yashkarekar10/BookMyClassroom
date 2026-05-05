import streamlit as st
import mysql.connector
import datetime
import pandas as pd

# ── V2 feature imports ────────────────────────────────────────
import bcrypt
import smtplib
import threading
import streamlit.components.v1 as components
import plotly.express as px
import plotly.graph_objects as go
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# =========================================================
# DB CONNECTION  (unchanged)
# =========================================================
def get_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="nidhi06yash",
        database="bookmyclassroom"
    )

def _username_of(user):
    if isinstance(user, dict):
        return user.get("username")
    return user

# =========================================================
# BOOKING HELPERS  (unchanged)
# =========================================================
def _times_overlap(existing_start, existing_end, new_start, new_end):
    return not (existing_end <= new_start or existing_start >= new_end)

def is_booking_available(room, date, start, end):
    if start >= end:
        return False
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 1
        FROM bookings
        WHERE room_name = %s
          AND date = %s
          AND NOT (end_time <= %s OR start_time >= %s)
        LIMIT 1
    """, (room, date, start, end))
    conflict = cursor.fetchone()
    conn.close()
    return conflict is None

def book_room(user, room, floor, date, start, end, duration, description):
    username = _username_of(user)
    if not username:
        st.error("No user in session—please log in again.")
        return False
    if start >= end:
        st.error("End time must be after start time.")
        return False
    if date < datetime.date.today():
        st.error("Date cannot be in the past.")
        return False

    conn = get_connection()
    cursor = conn.cursor()
    try:
        conn.start_transaction()
        if not is_booking_available(room, date, start, end):
            conn.rollback()
            st.error("This classroom is already booked for the selected time slot.")
            return False
        cursor.execute("""
            INSERT INTO bookings (username, room_name, floor, date, start_time, end_time, duration, description)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (username, room, floor, date, start, end, duration, description))
        conn.commit()
        # ── V2: notify on confirmed classroom booking ──
        notify_booking_confirmed(username, room, date, start, end, "Classroom")
        return True
    except Exception as e:
        conn.rollback()
        st.error(f"Booking failed: {e}")
        return False
    finally:
        conn.close()

# =========================================================
# ── FEATURE 1: bcrypt helpers ─────────────────────────────
# =========================================================
_MIN_PASSWORD_LEN = 8

def _hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()

def _verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())

# =========================================================
# AUTH  (login/register upgraded with bcrypt – same UI)
# =========================================================
def login():
    st.subheader("Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        # ── V2: fetch by username only, verify hash separately ──
        cursor.execute("SELECT * FROM faculty WHERE username = %s", (username,))
        user = cursor.fetchone()
        conn.close()

        if user and _verify_password(password, user["password"]):
            st.session_state["user"] = user["username"]
            st.session_state["role"] = user["role"]
            st.success(f"Logged in as {user['role']}")
            st.rerun()
        else:
            st.error("Invalid username or password")

def register():
    st.subheader("Faculty Registration")
    name     = st.text_input("Name")
    username = st.text_input("Username")
    # ── V2: password confirm + minimum length ──
    password = st.text_input("Password", type="password",
                             help=f"Minimum {_MIN_PASSWORD_LEN} characters")
    confirm  = st.text_input("Confirm Password", type="password")
    role     = st.selectbox("Role", ["teacher", "admin"])
    if st.button("Register"):
        if not name or not username or not password:
            st.error("All fields are required.")
            return
        if len(password) < _MIN_PASSWORD_LEN:
            st.error(f"Password must be at least {_MIN_PASSWORD_LEN} characters.")
            return
        if password != confirm:
            st.error("Passwords do not match.")
            return
        hashed = _hash_password(password)
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO faculty (name, username, password, role)
                VALUES (%s, %s, %s, %s)
            """, (name, username, hashed, role))
            conn.commit()
            st.success("Registration successful. Please login.")
        except Exception as e:
            conn.rollback()
            st.error(f"Registration failed: {e}")
        finally:
            conn.close()

# =========================================================
# BOOKING PAGE  (unchanged logic + floor map + notification)
# =========================================================
def booking_page(user):
    st.subheader("Book a Classroom")
    floor = st.selectbox("Select Floor", ["1st","2nd","3rd", "4th"])
    date  = st.date_input("Date", min_value=datetime.date.today())
    start = st.time_input("Start Time")
    default_end = (datetime.datetime.combine(datetime.date.today(), start) + datetime.timedelta(hours=1)).time()
    end   = st.time_input("End Time", value=default_end)
    description = st.text_area("Description (optional):", "")

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT room_name
        FROM classrooms
        WHERE floor = %s
          AND room_name NOT IN (
                SELECT room_name
                FROM bookings
                WHERE date = %s
                  AND NOT (end_time <= %s OR start_time >= %s)
          )
        ORDER BY room_name
    """, (floor, date, start, end))
    rooms = [row[0] for row in cursor.fetchall()]
    conn.close()

    if not rooms:
        st.warning("No classrooms available for the selected slot.")
    else:
        room = st.selectbox("Available Rooms", rooms)
        if st.button("Book Now"):
            duration = str(
                datetime.datetime.combine(datetime.date.today(), end)
                - datetime.datetime.combine(datetime.date.today(), start)
            )
            success = book_room(user, room, floor, date, start, end, duration, description)
            if success:
                st.success(f"Classroom {room} booked successfully!")

    # ── V2: interactive floor map below the booking form ──
    floor_map_view(floor=floor, date=date)

# =========================================================
# LAB BOOKING DASHBOARD  (unchanged logic + notification)
# =========================================================
def lab_booking_dashboard(user):
    st.header("Lab Booking Dashboard")

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM labs ORDER BY lab_name")
    labs = cursor.fetchall()
    lab_names = [lab['lab_name'] for lab in labs]
    selected_lab = st.selectbox("Select Lab", lab_names)

    date       = st.date_input("Select Date", min_value=datetime.date.today(), key="lab_date_input")
    start_time = st.time_input("Start Time", key="lab_start_time")
    end_time   = st.time_input("End Time",   key="lab_end_time")

    if start_time and end_time:
        start_dt = datetime.datetime.combine(datetime.date.today(), start_time)
        end_dt   = datetime.datetime.combine(datetime.date.today(), end_time)
        duration = str(end_dt - start_dt)
    else:
        duration = ""

    description = st.text_area("Purpose / Description")

    selected_lab_info = next((lab for lab in labs if lab["lab_name"] == selected_lab), None)
    floor = selected_lab_info["floor"] if selected_lab_info else ""

    if st.button("Book Lab"):
        cursor.execute("""
            SELECT 1
            FROM lab_bookings
            WHERE lab_name = %s
              AND date = %s
              AND NOT (end_time <= %s OR start_time >= %s)
            LIMIT 1
        """, (selected_lab, date, start_time, end_time))
        clashes = cursor.fetchone()

        if clashes:
            st.error("This lab is already booked for the selected time slot.")
        else:
            cursor.execute("""
                INSERT INTO lab_bookings (username, lab_name, floor, date, start_time, end_time, duration, description)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (_username_of(user), selected_lab, floor, date, start_time, end_time, duration, description))
            conn.commit()
            st.success("Lab booked successfully.")
            # ── V2: notify on confirmed lab booking ──
            notify_booking_confirmed(_username_of(user), selected_lab, date,
                                     start_time, end_time, "Lab")

    st.subheader("My Lab Bookings")

    if user["role"] == "admin":
        cursor.execute("""
            SELECT * FROM lab_bookings
            WHERE (date > CURDATE() OR (date = CURDATE() AND end_time > CURTIME()))
            ORDER BY date DESC, start_time DESC
        """)
    else:
        cursor.execute("""
            SELECT * FROM lab_bookings
            WHERE username = %s
                AND (date > CURDATE() OR (date = CURDATE() AND end_time > CURTIME()))
            ORDER BY date DESC, start_time DESC
        """, (_username_of(user),))

    bookings = cursor.fetchall()
    df = pd.DataFrame(bookings)
    if not df.empty:
        st.dataframe(df)

        if user["role"] == "teacher":
            booking_ids = [f"{b['id']} - {b['lab_name']} ({b['date']})" for b in bookings]
            selected = st.selectbox("Select Booking to Cancel", [""] + booking_ids)
            if selected and st.button("Send Cancel Request"):
                selected_id = int(selected.split(" - ")[0])
                cursor.execute("""
                    INSERT INTO cancel_lab_requests (lab_booking_id, teacher_username, reason)
                    VALUES (%s, %s, %s)
                """, (selected_id, _username_of(user), "Requested by user"))
                conn.commit()
                st.success("Cancellation request sent.")

    if user["role"] == "admin":
        st.subheader("Lab Cancellation Requests")
        cursor.execute("SELECT * FROM cancel_lab_requests WHERE status = 'Pending'")
        requests = cursor.fetchall()
        for req in requests:
            st.write(f"Request ID: {req['id']} | Booking ID: {req['lab_booking_id']} | Teacher: {req['teacher_username']}")
            col1, col2 = st.columns(2)
            if col1.button(f"Approve {req['id']}"):
                cursor.execute("DELETE FROM lab_bookings WHERE id = %s", (req["lab_booking_id"],))
                cursor.execute("UPDATE cancel_lab_requests SET status = 'Approved' WHERE id = %s", (req["id"],))
                conn.commit()
                st.success(f"Booking {req['lab_booking_id']} cancelled.")
            if col2.button(f"Reject {req['id']}"):
                cursor.execute("UPDATE cancel_lab_requests SET status = 'Rejected' WHERE id = %s", (req["id"],))
                conn.commit()
                st.info(f"Request {req['id']} rejected.")

    cursor.close()
    conn.close()

# =========================================================
# BOOKING HISTORY  (unchanged)
# =========================================================
def booking_history(user, role=None):
    st.subheader("📖 Booking History")

    show_past = st.checkbox("Show past bookings", value=False)

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    if show_past:
        cursor.execute("""
            SELECT * FROM bookings
            WHERE username = %s
            ORDER BY date DESC, start_time DESC
        """, (_username_of(user),))
    else:
        cursor.execute("""
            SELECT * FROM bookings
            WHERE username = %s
              AND (date > CURDATE() OR (date = CURDATE() AND end_time > CURTIME()))
            ORDER BY date ASC, start_time ASC
        """, (_username_of(user),))
    classroom_bookings = cursor.fetchall()
    cursor.close()
    conn.close()

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    if show_past:
        cursor.execute("""
            SELECT * FROM lab_bookings
            WHERE username = %s
            ORDER BY date DESC, start_time DESC
        """, (_username_of(user),))
    else:
        cursor.execute("""
            SELECT * FROM lab_bookings
            WHERE username = %s
              AND (date > CURDATE() OR (date = CURDATE() AND end_time > CURTIME()))
            ORDER BY date ASC, start_time ASC
        """, (_username_of(user),))
    lab_bookings = cursor.fetchall()
    cursor.close()
    conn.close()

    if classroom_bookings:
        st.write("🏫 Classroom Bookings")
        st.table(classroom_bookings)
    else:
        st.info("No classroom bookings found.")

    if lab_bookings:
        st.write("🧪 Lab Bookings")
        st.table(lab_bookings)
    else:
        st.info("No lab bookings found.")

    if role == "teacher":
        st.write("---")
        st.write("### Request Cancellation")
        booking_type = st.radio("Select booking type:", ["Classroom", "Lab"])
        booking_id   = st.number_input("Enter Booking ID to Request Cancellation", min_value=1, step=1)
        reason       = st.text_area("Reason for cancellation:")
        if st.button("Send Request"):
            conn = get_connection()
            cursor = conn.cursor()
            try:
                if booking_type == "Classroom":
                    cursor.execute("""
                        INSERT INTO cancel_requests (booking_id, teacher_username, reason)
                        VALUES (%s, %s, %s)
                    """, (booking_id, _username_of(user), reason))
                else:
                    # FIX: use lab_booking_id instead of booking_id for lab cancellation requests
                    cursor.execute("""
                        INSERT INTO cancel_lab_requests (lab_booking_id, teacher_username, reason)
                        VALUES (%s, %s, %s)
                    """, (booking_id, _username_of(user), reason))
                conn.commit()
                st.success("Cancellation request sent successfully ✅")
            except Exception as e:
                conn.rollback()
                st.error(f"Failed to send request: {e}")
            finally:
                conn.close()

# =========================================================
# CANCELLATION MANAGEMENT  (unchanged logic + notification)
# =========================================================
def manage_cancellations():
    st.subheader("Manage Cancellation Requests (Admin Only)")

    request_type = st.radio("Select Request Type:", ["Classroom", "Lab"])

    conn = get_connection()
    try:
        if request_type == "Classroom":
            requests_df = pd.read_sql("SELECT * FROM cancel_requests WHERE status = 'Pending'", conn)
        else:
            requests_df = pd.read_sql("SELECT * FROM cancel_lab_requests WHERE status = 'Pending'", conn)
    finally:
        conn.close()

    if requests_df.empty:
        st.info("No pending requests.")
        return

    st.dataframe(requests_df)

    req_id = st.number_input("Request ID to process", min_value=1, step=1)
    action = st.selectbox("Action", ["Approve", "Reject"])

    if st.button("Process Request"):
        conn = get_connection()
        cursor = conn.cursor()
        try:
            if request_type == "Classroom":
                if action == "Approve":
                    cursor.execute("SELECT booking_id FROM cancel_requests WHERE id=%s", (req_id,))
                    row = cursor.fetchone()
                    if row:
                        booking_id = row[0]
                        # fetch teacher + resource for notification
                        cursor.execute("SELECT username, room_name, date FROM bookings WHERE id=%s", (booking_id,))
                        brow = cursor.fetchone()
                        cursor.execute("DELETE FROM bookings WHERE id=%s", (booking_id,))
                        cursor.execute("UPDATE cancel_requests SET status='Approved' WHERE id=%s", (req_id,))
                        conn.commit()
                        st.success(f"Classroom booking {booking_id} cancelled successfully.")
                        # ── V2: notify teacher of approval ──
                        if brow:
                            notify_cancellation_result(brow[0], brow[1], brow[2], approved=True)
                    else:
                        st.error("Request not found.")
                else:
                    cursor.execute("SELECT teacher_username FROM cancel_requests WHERE id=%s", (req_id,))
                    trow = cursor.fetchone()
                    cursor.execute("UPDATE cancel_requests SET status='Rejected' WHERE id=%s", (req_id,))
                    conn.commit()
                    st.info("Request rejected.")
                    # ── V2: notify teacher of rejection ──
                    if trow:
                        notify_cancellation_result(trow[0], "classroom booking", datetime.date.today(), approved=False)

            else:
                if action == "Approve":
                    # FIX: use lab_booking_id instead of booking_id for lab cancellation requests
                    cursor.execute("SELECT lab_booking_id FROM cancel_lab_requests WHERE id=%s", (req_id,))
                    row = cursor.fetchone()
                    if row:
                        booking_id = row[0]
                        cursor.execute("SELECT username, lab_name, date FROM lab_bookings WHERE id=%s", (booking_id,))
                        brow = cursor.fetchone()
                        cursor.execute("DELETE FROM lab_bookings WHERE id=%s", (booking_id,))
                        cursor.execute("UPDATE cancel_lab_requests SET status='Approved' WHERE id=%s", (req_id,))
                        conn.commit()
                        st.success(f"Lab booking {booking_id} cancelled successfully.")
                        if brow:
                            notify_cancellation_result(brow[0], brow[1], brow[2], approved=True)
                    else:
                        st.error("Request not found.")
                else:
                    # FIX: use teacher_username from cancel_lab_requests (was already correct but kept consistent)
                    cursor.execute("SELECT teacher_username FROM cancel_lab_requests WHERE id=%s", (req_id,))
                    trow = cursor.fetchone()
                    cursor.execute("UPDATE cancel_lab_requests SET status='Rejected' WHERE id=%s", (req_id,))
                    conn.commit()
                    st.info("Request rejected.")
                    if trow:
                        notify_cancellation_result(trow[0], "lab booking", datetime.date.today(), approved=False)

        except Exception as e:
            conn.rollback()
            st.error(f"Action failed: {e}")
        finally:
            conn.close()

# =========================================================
# STUDENT DASHBOARD  – booking cards (no login required)
# =========================================================
def _student_booking_card(resource: str, btype: str,
                           start, end, description: str) -> None:
    """Render a single booking detail card for students."""
    icon  = "🏫" if btype == "Classroom" else "🧪"
    color = "#EBF4FF" if btype == "Classroom" else "#F0FFF4"
    bdr   = "#3182CE" if btype == "Classroom" else "#38A169"

    def fmt(t):
        if isinstance(t, datetime.timedelta):
            total = int(t.total_seconds())
            h, m  = divmod(total // 60, 60)
            return f"{h:02d}:{m:02d}"
        return t.strftime("%H:%M") if hasattr(t, "strftime") else str(t)

    s    = fmt(start)
    e    = fmt(end)
    desc = str(description).strip() if description else "—"

    st.markdown(f"""
    <div style="background:{color};border-left:4px solid {bdr};
                border-radius:6px;padding:10px 14px;margin-bottom:10px;">
      <div style="font-size:15px;font-weight:700;color:#1A202C;margin-bottom:4px;">
        {icon} {resource}
        <span style="font-size:12px;font-weight:400;color:#718096;">({btype})</span>
      </div>
      <div style="font-size:13px;color:#2D3748;">🕐 <b>{s} – {e}</b></div>
      <div style="font-size:13px;color:#4A5568;margin-top:3px;">📝 {desc}</div>
    </div>
    """, unsafe_allow_html=True)


def student_dashboard():
    st.subheader("🎓 Student Dashboard – View Bookings")
    date  = st.date_input("Select Date", min_value=datetime.date.today())
    floor = st.selectbox("Select Floor (for classrooms only)", ["1st","2nd","3rd","4th"])
    conn  = get_connection()

    df_class = pd.read_sql("""
        SELECT room_name, start_time, end_time, description
        FROM bookings
        WHERE date = %s AND floor = %s
          AND (date > CURDATE() OR (date = CURDATE() AND end_time > CURTIME()))
        ORDER BY start_time
    """, conn, params=(date, floor))

    df_lab = pd.read_sql("""
        SELECT lab_name, start_time, end_time, description
        FROM lab_bookings
        WHERE date = %s
          AND (date > CURDATE() OR (date = CURDATE() AND end_time > CURTIME()))
        ORDER BY start_time
    """, conn, params=(date,))
    conn.close()

    # ── Classroom bookings ─────────────────────────────────
    st.markdown(
        f"<h4 style='margin:14px 0 8px;color:#2D3748;'>"
        f"🏫 Bookings on {date.strftime('%A, %d %B %Y')} — {floor} Floor</h4>",
        unsafe_allow_html=True
    )
    if df_class.empty:
        st.info("No classroom bookings for this floor on this date.")
    else:
        for _, row in df_class.iterrows():
            _student_booking_card(
                row["room_name"], "Classroom",
                row["start_time"], row["end_time"],
                row.get("description", "")
            )
        st.caption(f"📊 {len(df_class)} classroom booking(s) on this floor")

    st.markdown("---")

    # ── Lab bookings ───────────────────────────────────────
    st.markdown(
        f"<h4 style='margin:14px 0 8px;color:#2D3748;'>"
        f"🧪 Lab Bookings on {date.strftime('%A, %d %B %Y')}</h4>",
        unsafe_allow_html=True
    )
    if df_lab.empty:
        st.info("No lab bookings for this date.")
    else:
        for _, row in df_lab.iterrows():
            _student_booking_card(
                row["lab_name"], "Lab",
                row["start_time"], row["end_time"],
                row.get("description", "")
            )
        st.caption(f"📊 {len(df_lab)} lab booking(s) on this date")

# =========================================================
# ── FEATURE 2: Interactive Floor Map ──────────────────────
# =========================================================
_FLOOR_LAYOUTS = {
    # 1st floor: Room 10-19 (2 rows of 5)
    "1st": {
        "Room 10": (30,  55, 100, 62),
        "Room 11": (145, 55, 100, 62),
        "Room 12": (260, 55, 100, 62),
        "Room 13": (375, 55, 100, 62),
        "Room 14": (490, 55, 100, 62),
        "Room 15": (30,  140, 100, 62),
        "Room 16": (145, 140, 100, 62),
        "Room 17": (260, 140, 100, 62),
        "Room 18": (375, 140, 100, 62),
        "Room 19": (490, 140, 100, 62),
    },
    # 2nd floor: Room 20-29 (2 rows of 5)
    "2nd": {
        "Room 20": (30,  55, 100, 62),
        "Room 21": (145, 55, 100, 62),
        "Room 22": (260, 55, 100, 62),
        "Room 23": (375, 55, 100, 62),
        "Room 24": (490, 55, 100, 62),
        "Room 25": (30,  140, 100, 62),
        "Room 26": (145, 140, 100, 62),
        "Room 27": (260, 140, 100, 62),
        "Room 28": (375, 140, 100, 62),
        "Room 29": (490, 140, 100, 62),
    },
    # 3rd floor: Room 31-34 (single row)
    "3rd": {
        "Room 31": (50,  70, 115, 68),
        "Room 32": (195, 70, 115, 68),
        "Room 33": (340, 70, 115, 68),
        "Room 34": (485, 70, 115, 68),
    },
    # 4th floor: Room 41-48 (3 rows)
    "4th": {
        "Room 41":  (50,  55, 105, 62),
        "Room 41a": (50,  135, 105, 62),
        "Room 42":  (180, 55, 105, 62),
        "Room 43":  (180, 135, 105, 62),
        "Room 44":  (310, 55, 105, 62),
        "Room 44a": (310, 135, 105, 62),
        "Room 45":  (440, 55, 105, 62),
        "Room 46":  (440, 135, 105, 62),
        "Room 47":  (50,  230, 105, 62),
        "Room 48":  (180, 230, 105, 62),
    },
}

def _room_status(floor: str, date: datetime.date) -> dict:
    """Any booking on this floor+date marks the room as booked."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT room_name
        FROM bookings
        WHERE floor = %s AND date = %s
    """, (floor, date))
    rows = cursor.fetchall()
    conn.close()
    return {row[0]: "booked" for row in rows}

def _build_floor_svg(floor: str, status: dict) -> str:
    rooms  = _FLOOR_LAYOUTS.get(floor, {})
    height = 330 if floor in ("4th", "1st", "2nd") else 210
    COLOR  = {
        "free":   ("#C8E6C9", "#388E3C", "#1B5E20"),
        "booked": ("#FFCDD2", "#E53935", "#B71C1C"),
    }
    parts = [
        f'<svg width="100%" viewBox="0 0 660 {height}" xmlns="http://www.w3.org/2000/svg" '
        f'style="font-family:sans-serif;background:#f4f6f9;border-radius:12px;">'
    ]
    cy = height - 28
    parts.append(f'<line x1="30" y1="{cy}" x2="630" y2="{cy}" stroke="#ccc" stroke-width="1.5" stroke-dasharray="6 4"/>')
    parts.append(f'<text x="330" y="{cy+16}" text-anchor="middle" font-size="11" fill="#aaa">— Corridor —</text>')
    for room, (x, y, w, h) in rooms.items():
        s = status.get(room, "free")
        fill, stroke, tc = COLOR[s]
        parts += [
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>',
            f'<text x="{x+w//2}" y="{y+h//2-7}" text-anchor="middle" font-size="13" font-weight="600" fill="{tc}">{room}</text>',
            f'<text x="{x+w//2}" y="{y+h//2+11}" text-anchor="middle" font-size="11" fill="{tc}">{s.capitalize()}</text>',
        ]
    parts.append(f'<text x="18" y="22" font-size="13" font-weight="700" fill="#555">{floor} Floor</text>')
    parts.append("</svg>")
    return "".join(parts)

_MAP_LEGEND = """
<div style="display:flex;gap:20px;font-size:13px;margin:6px 0;">
  <span><span style="display:inline-block;width:13px;height:13px;background:#C8E6C9;border:1.5px solid #388E3C;border-radius:3px;vertical-align:middle;margin-right:5px;"></span>Free</span>
  <span><span style="display:inline-block;width:13px;height:13px;background:#FFCDD2;border:1.5px solid #E53935;border-radius:3px;vertical-align:middle;margin-right:5px;"></span>Booked</span>
</div>
"""

def floor_map_view(floor: str = None, date: datetime.date = None):
    st.subheader("🗺️ Interactive Floor Map")
    if floor is None:
        floor = st.selectbox("Floor", list(_FLOOR_LAYOUTS.keys()), key="fm_floor")
    if date is None:
        date = st.date_input("Date", min_value=datetime.date.today(), key="fm_date")
    if floor not in _FLOOR_LAYOUTS:
        st.info("Floor map not available for this floor yet.")
        return
    status = _room_status(floor, date)
    st.markdown(_MAP_LEGEND, unsafe_allow_html=True)
    iframe_h = 400 if floor in ("1st", "2nd", "4th") else 250
    components.html(_build_floor_svg(floor, status), height=iframe_h, scrolling=False)
    directions = {
        "1st": "Ground floor — rooms 10–14 on the left wing, rooms 15–19 on the right wing.",
        "2nd": "Take the main staircase to the 2nd floor — rooms 20–24 left wing, 25–29 right wing.",
        "3rd": "Take the main staircase to the 3rd floor — all rooms are on the left wing.",
        "4th": "Take the main staircase to the 4th floor — rooms 41–46 straight ahead, 47–48 on the right.",
    }
    st.caption(f"📍 {directions.get(floor, '')}")

# =========================================================
# ── FEATURE 3: Month-View Calendar ────────────────────────
# =========================================================

def _fetch_month_bookings(username: str, role: str,
                           year: int, month: int) -> dict:
    """
    Returns a dict: { datetime.date -> list of booking dicts }
    Each booking dict has: resource, type, start_time, end_time,
                           description, username
    """
    import calendar as _cal
    first_day = datetime.date(year, month, 1)
    last_day  = datetime.date(year, month, _cal.monthrange(year, month)[1])
    conn = get_connection()

    if role == "admin":
        df_class = pd.read_sql("""
            SELECT username, room_name AS resource, 'Classroom' AS type,
                   date, start_time, end_time,
                   COALESCE(description,'') AS description
            FROM bookings
            WHERE date BETWEEN %s AND %s
            ORDER BY date, start_time
        """, conn, params=(first_day, last_day))
        df_lab = pd.read_sql("""
            SELECT username, lab_name AS resource, 'Lab' AS type,
                   date, start_time, end_time,
                   COALESCE(description,'') AS description
            FROM lab_bookings
            WHERE date BETWEEN %s AND %s
            ORDER BY date, start_time
        """, conn, params=(first_day, last_day))
    else:
        df_class = pd.read_sql("""
            SELECT username, room_name AS resource, 'Classroom' AS type,
                   date, start_time, end_time,
                   COALESCE(description,'') AS description
            FROM bookings
            WHERE username = %s AND date BETWEEN %s AND %s
            ORDER BY date, start_time
        """, conn, params=(username, first_day, last_day))
        df_lab = pd.read_sql("""
            SELECT username, lab_name AS resource, 'Lab' AS type,
                   date, start_time, end_time,
                   COALESCE(description,'') AS description
            FROM lab_bookings
            WHERE username = %s AND date BETWEEN %s AND %s
            ORDER BY date, start_time
        """, conn, params=(username, first_day, last_day))
    conn.close()

    df = pd.concat([df_class, df_lab], ignore_index=True)
    result = {}
    for _, row in df.iterrows():
        d = row["date"]
        if hasattr(d, "date"):
            d = d.date()
        result.setdefault(d, []).append(row.to_dict())
    return result


def _fmt_time(t) -> str:
    """Convert timedelta or time object to HH:MM string."""
    if isinstance(t, datetime.timedelta):
        total = int(t.total_seconds())
        h, m  = divmod(total // 60, 60)
        return f"{h:02d}:{m:02d}"
    if hasattr(t, "strftime"):
        return t.strftime("%H:%M")
    return str(t)


def _build_calendar_html(year: int, month: int,
                          bookings: dict, today: datetime.date) -> str:
    import calendar as _cal

    DAYS     = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    cal      = _cal.monthcalendar(year, month)
    month_nm = datetime.date(year, month, 1).strftime("%B %Y")

    # ── styles ────────────────────────────────────────────
    css = """
    <style>
    .bmc-cal{width:100%;border-collapse:collapse;table-layout:fixed;font-family:sans-serif;}
    .bmc-cal th{
        background:#4A5568;color:#fff;padding:8px 4px;
        font-size:13px;font-weight:600;text-align:center;
        border:1px solid #CBD5E0;
    }
    .bmc-cal td{
        vertical-align:top;border:1px solid #CBD5E0;
        padding:6px 5px;min-height:110px;height:110px;
        background:#fff;width:14.28%;
    }
    .bmc-cal td.today{background:#EBF8FF;border:2px solid #3182CE;}
    .bmc-cal td.empty{background:#F7FAFC;}
    .bmc-cal td.weekend{background:#FFFAF0;}
    .day-num{
        font-size:13px;font-weight:700;color:#2D3748;
        margin-bottom:4px;display:block;
    }
    .day-num.today-num{
        background:#3182CE;color:#fff;border-radius:50%;
        width:22px;height:22px;line-height:22px;
        text-align:center;display:inline-block;
    }
    .ev{
        font-size:10.5px;border-radius:4px;
        padding:2px 5px;margin-bottom:3px;
        line-height:1.4;display:block;word-break:break-word;
    }
    .ev-class{background:#C3DAFE;color:#1E3A8A;border-left:3px solid #3B82F6;}
    .ev-lab  {background:#BBF7D0;color:#14532D;border-left:3px solid #22C55E;}
    .ev-more {background:#E2E8F0;color:#4A5568;font-size:10px;
              border-radius:4px;padding:1px 4px;display:inline-block;}
    </style>
    """

    html = css + f"<p style='font-size:18px;font-weight:700;margin:8px 0 10px;color:#2D3748;'>{month_nm}</p>"
    html += '<table class="bmc-cal"><thead><tr>'
    for d in DAYS:
        html += f"<th>{d}</th>"
    html += "</tr></thead><tbody>"

    for week in cal:
        html += "<tr>"
        for col_idx, day in enumerate(week):
            is_weekend = col_idx >= 5
            if day == 0:
                html += '<td class="empty"></td>'
                continue

            this_date  = datetime.date(year, month, day)
            is_today   = this_date == today
            cell_class = "today" if is_today else ("weekend" if is_weekend else "")
            num_class  = "today-num" if is_today else ""

            html += f'<td class="{cell_class}">'
            html += f'<span class="day-num {num_class}">{day}</span>'

            day_bookings = bookings.get(this_date, [])
            # show max 3 pills, then "+N more"
            show    = day_bookings[:3]
            leftover = len(day_bookings) - 3

            for b in show:
                btype  = b.get("type", "Classroom")
                cls    = "ev-class" if btype == "Classroom" else "ev-lab"
                s      = _fmt_time(b["start_time"])
                e      = _fmt_time(b["end_time"])
                res    = b.get("resource", "")
                desc   = str(b.get("description", "")).strip()
                desc_s = f" — {desc[:30]}{'…' if len(desc)>30 else ''}" if desc else ""
                tip    = f"{btype}: {res} {s}–{e}{desc_s}"
                # truncate resource for pill
                res_short = res if len(res) <= 10 else res[:9] + "…"
                html += (f'<span class="ev {cls}" title="{tip}">'
                         f'🏫 {res_short} {s}' if btype == "Classroom" else
                         f'<span class="ev {cls}" title="{tip}">🧪 {res_short} {s}')
                html += "</span>"

            if leftover > 0:
                html += f'<span class="ev-more">+{leftover} more</span>'

            html += "</td>"
        html += "</tr>"

    html += "</tbody></table>"
    return html


def _booking_detail_table(bookings_on_day: list, selected_date: datetime.date) -> None:
    """Render a clean detail card for all bookings on a selected date."""
    st.markdown(
        f"<h4 style='margin:16px 0 8px;color:#2D3748;'>"
        f"📋 Bookings on {selected_date.strftime('%A, %d %B %Y')}</h4>",
        unsafe_allow_html=True
    )
    if not bookings_on_day:
        st.info("No bookings on this date.")
        return

    for b in bookings_on_day:
        btype = b.get("type", "Classroom")
        icon  = "🏫" if btype == "Classroom" else "🧪"
        color = "#EBF4FF" if btype == "Classroom" else "#F0FFF4"
        bdr   = "#3182CE" if btype == "Classroom" else "#38A169"
        s     = _fmt_time(b["start_time"])
        e     = _fmt_time(b["end_time"])
        desc  = str(b.get("description", "")).strip() or "—"
        user  = b.get("username", "—")
        res   = b.get("resource", "—")

        st.markdown(f"""
        <div style="background:{color};border-left:4px solid {bdr};
                    border-radius:6px;padding:10px 14px;margin-bottom:10px;">
          <div style="font-size:15px;font-weight:700;color:#1A202C;margin-bottom:4px;">
            {icon} {res} &nbsp;<span style="font-size:12px;font-weight:400;
            color:#718096;">({btype})</span>
          </div>
          <div style="font-size:13px;color:#2D3748;">
            🕐 <b>{s} – {e}</b>
          </div>
          <div style="font-size:13px;color:#4A5568;margin-top:3px;">
            👤 Booked by: <b>{user}</b>
          </div>
          <div style="font-size:13px;color:#4A5568;margin-top:3px;">
            📝 {desc}
          </div>
        </div>
        """, unsafe_allow_html=True)


def calendar_view(user, role: str):
    st.subheader("📅 My Calendar")

    today    = datetime.date.today()
    username = user["username"] if isinstance(user, dict) else user

    # ── Month navigation ──────────────────────────────────
    if "cal_year"  not in st.session_state:
        st.session_state.cal_year  = today.year
    if "cal_month" not in st.session_state:
        st.session_state.cal_month = today.month

    col_prev, col_title, col_next = st.columns([1, 4, 1])
    with col_prev:
        if st.button("◀ Prev", key="cal_prev"):
            if st.session_state.cal_month == 1:
                st.session_state.cal_month = 12
                st.session_state.cal_year -= 1
            else:
                st.session_state.cal_month -= 1
    with col_next:
        if st.button("Next ▶", key="cal_next"):
            if st.session_state.cal_month == 12:
                st.session_state.cal_month = 1
                st.session_state.cal_year += 1
            else:
                st.session_state.cal_month += 1
    with col_title:
        mn = datetime.date(st.session_state.cal_year,
                           st.session_state.cal_month, 1).strftime("%B %Y")
        st.markdown(
            f"<p style='text-align:center;font-size:17px;font-weight:700;"
            f"color:#2D3748;margin-top:6px;'>{mn}</p>",
            unsafe_allow_html=True
        )

    year  = st.session_state.cal_year
    month = st.session_state.cal_month

    # ── Fetch bookings for the month ──────────────────────
    bookings = _fetch_month_bookings(username, role, year, month)

    # ── Legend ────────────────────────────────────────────
    st.markdown("""
    <div style="display:flex;gap:16px;font-size:12px;margin:4px 0 10px;">
      <span><span style="display:inline-block;width:12px;height:12px;
        background:#C3DAFE;border-left:3px solid #3B82F6;
        border-radius:2px;vertical-align:middle;margin-right:4px;"></span>Classroom</span>
      <span><span style="display:inline-block;width:12px;height:12px;
        background:#BBF7D0;border-left:3px solid #22C55E;
        border-radius:2px;vertical-align:middle;margin-right:4px;"></span>Lab</span>
      <span style="color:#718096;">Today highlighted in blue</span>
    </div>
    """, unsafe_allow_html=True)

    # ── Render calendar grid ──────────────────────────────
    cal_html = _build_calendar_html(year, month, bookings, today)
    components.html(cal_html, height=580, scrolling=True)

    # ── Date picker to see full details ──────────────────
    st.markdown("---")
    st.markdown("**Click a date below to see full booking details:**")
    selected = st.date_input(
        "Select date",
        value=today,
        key="cal_detail_date",
        label_visibility="collapsed"
    )
    if selected:
        sd = selected if isinstance(selected, datetime.date) else selected
        _booking_detail_table(bookings.get(sd, []), sd)

    # ── Summary count ─────────────────────────────────────
    total = sum(len(v) for v in bookings.values())
    if total:
        st.caption(f"📊 {total} booking{'s' if total != 1 else ''} in {mn}"
                   + (" (all users)" if role == "admin" else ""))

# =========================================================
# ── FEATURE 4: Admin Analytics Dashboard ──────────────────
# =========================================================
def _kpis() -> dict:
    conn = get_connection()
    c    = conn.cursor()
    c.execute("SELECT COUNT(*) FROM bookings");          total_class   = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM lab_bookings");      total_lab     = c.fetchone()[0]
    c.execute("SELECT room_name, COUNT(*) AS cnt FROM bookings GROUP BY room_name ORDER BY cnt DESC LIMIT 1")
    top_room = c.fetchone()
    c.execute("SELECT lab_name, COUNT(*) AS cnt FROM lab_bookings GROUP BY lab_name ORDER BY cnt DESC LIMIT 1")
    top_lab = c.fetchone()
    c.execute("SELECT COUNT(DISTINCT username) FROM bookings"); active_users = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM cancel_requests WHERE status='Pending'"); pending = c.fetchone()[0]
    conn.close()
    return {"total_class": total_class, "total_lab": total_lab,
            "top_room": top_room[0] if top_room else "—",
            "top_lab":  top_lab[0]  if top_lab  else "—",
            "active_users": active_users, "pending_cancel": pending}

def _bookings_over_time() -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql("""
        SELECT date, COUNT(*) AS bookings FROM (
            SELECT date FROM bookings UNION ALL SELECT date FROM lab_bookings
        ) c GROUP BY date ORDER BY date
    """, conn); conn.close(); return df

def _top_rooms(n: int = 8) -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql(f"""
        SELECT resource, type, cnt FROM (
            SELECT room_name AS resource, 'Classroom' AS type, COUNT(*) AS cnt FROM bookings GROUP BY room_name
            UNION ALL
            SELECT lab_name AS resource, 'Lab' AS type, COUNT(*) AS cnt FROM lab_bookings GROUP BY lab_name
        ) t ORDER BY cnt DESC LIMIT {n}
    """, conn); conn.close(); return df

def _peak_hours() -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql("""
        SELECT HOUR(start_time) AS hour, COUNT(*) AS bookings FROM (
            SELECT start_time FROM bookings UNION ALL SELECT start_time FROM lab_bookings
        ) c GROUP BY hour ORDER BY hour
    """, conn); conn.close(); return df

def _heatmap_data() -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql("""
        SELECT DAYNAME(date) AS day_name, HOUR(start_time) AS hour, COUNT(*) AS bookings
        FROM (SELECT date, start_time FROM bookings UNION ALL SELECT date, start_time FROM lab_bookings) c
        GROUP BY day_name, hour
    """, conn); conn.close()
    days_order = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    df["day_name"] = pd.Categorical(df["day_name"], categories=days_order, ordered=True)
    return df.pivot_table(index="day_name", columns="hour", values="bookings", fill_value=0)

def _user_activity() -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql("""
        SELECT username, SUM(classroom_cnt) AS classrooms_booked,
               SUM(lab_cnt) AS labs_booked, SUM(classroom_cnt+lab_cnt) AS total
        FROM (
            SELECT username, COUNT(*) AS classroom_cnt, 0 AS lab_cnt FROM bookings GROUP BY username
            UNION ALL
            SELECT username, 0, COUNT(*) FROM lab_bookings GROUP BY username
        ) t GROUP BY username ORDER BY total DESC LIMIT 15
    """, conn); conn.close(); return df

def admin_analytics():
    st.subheader("📊 Admin Analytics Dashboard")
    kpi = _kpis()
    c1,c2,c3,c4,c5,c6 = st.columns(6)
    c1.metric("Classroom Bookings", kpi["total_class"])
    c2.metric("Lab Bookings",       kpi["total_lab"])
    c3.metric("Top Room",           kpi["top_room"])
    c4.metric("Top Lab",            kpi["top_lab"])
    c5.metric("Active Users",       kpi["active_users"])
    c6.metric("⚠️ Pending Cancels", kpi["pending_cancel"], delta_color="inverse")
    st.divider()
    df_time = _bookings_over_time()
    if not df_time.empty:
        fig = px.line(df_time, x="date", y="bookings", title="Bookings over time",
                      color_discrete_sequence=["#5C6BC0"])
        fig.update_layout(height=280, margin=dict(t=40,b=20))
        st.plotly_chart(fig, use_container_width=True)
    col1, col2 = st.columns(2)
    with col1:
        df_top = _top_rooms()
        if not df_top.empty:
            fig = px.bar(df_top, x="cnt", y="resource", orientation="h",
                         color="type", title="Most booked rooms & labs",
                         color_discrete_map={"Classroom":"#5C6BC0","Lab":"#26A69A"})
            fig.update_layout(height=320, margin=dict(t=40,b=20))
            st.plotly_chart(fig, use_container_width=True)
    with col2:
        df_peak = _peak_hours()
        if not df_peak.empty:
            fig = px.bar(df_peak, x="hour", y="bookings", title="Peak booking hours",
                         color_discrete_sequence=["#EF6C00"])
            fig.update_layout(height=320, margin=dict(t=40,b=20))
            st.plotly_chart(fig, use_container_width=True)
    st.subheader("Day × Hour usage heatmap")
    try:
        pivot = _heatmap_data()
        if not pivot.empty:
            fig = px.imshow(pivot, labels=dict(x="Hour",y="Day",color="Bookings"),
                            color_continuous_scale="Blues", aspect="auto")
            fig.update_layout(height=300, margin=dict(t=20,b=20))
            st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.info(f"Heatmap unavailable: {e}")
    st.subheader("User activity")
    df_u = _user_activity()
    if not df_u.empty:
        st.dataframe(df_u, use_container_width=True)

# =========================================================
# ── FEATURE 5: Notification System ────────────────────────
# =========================================================
_SMTP_CONFIG = {
    "host":     "smtp.gmail.com",
    "port":     587,
    "username": "your_email@gmail.com",   # ← change to your Gmail
    "password": "your_app_password",       # ← use a Gmail App Password
    "from":     "BookMyClassroom <your_email@gmail.com>",
}

def _send_email(to_address: str, subject: str, body_html: str):
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = _SMTP_CONFIG["from"]
        msg["To"]      = to_address
        msg.attach(MIMEText(body_html, "html"))
        with smtplib.SMTP(_SMTP_CONFIG["host"], _SMTP_CONFIG["port"]) as s:
            s.ehlo(); s.starttls()
            s.login(_SMTP_CONFIG["username"], _SMTP_CONFIG["password"])
            s.sendmail(_SMTP_CONFIG["username"], to_address, msg.as_string())
    except Exception as e:
        print(f"[Email] failed: {e}")

def _get_user_email(username: str):
    try:
        conn = get_connection(); c = conn.cursor()
        c.execute("SELECT email FROM faculty WHERE username = %s", (username,))
        row = c.fetchone(); conn.close()
        return row[0] if row else None
    except Exception:
        return None

def _push_in_app(username: str, message: str):
    try:
        conn = get_connection(); c = conn.cursor()
        c.execute("INSERT INTO notifications (username, message) VALUES (%s, %s)", (username, message))
        conn.commit(); conn.close()
    except Exception as e:
        print(f"[Notification] push failed: {e}")

def notify_booking_confirmed(username: str, resource: str,
                              date, start, end, booking_type: str = "Classroom"):
    msg = f"✅ Your {booking_type} booking for {resource} on {date} ({start}–{end}) is confirmed."
    _push_in_app(username, msg)
    email = _get_user_email(username)
    if email:
        body = f"""<p>Hi <b>{username}</b>,</p>
        <p>Booking confirmed: <b>{resource}</b> on <b>{date}</b> from {start} to {end}.</p>
        <p style="color:#888;font-size:12px;">— BookMyClassroom</p>"""
        threading.Thread(target=_send_email,
                         args=(email, f"Booking confirmed – {resource}", body),
                         daemon=True).start()

def notify_cancellation_result(username: str, resource: str, date, approved: bool):
    status = "approved ✅" if approved else "rejected ❌"
    msg = f"Your cancellation request for {resource} on {date} was {status}."
    _push_in_app(username, msg)
    email = _get_user_email(username)
    if email:
        color = "#2e7d32" if approved else "#c62828"
        body  = f"""<p>Hi <b>{username}</b>,</p>
        <p>Cancellation for <b>{resource}</b> on <b>{date}</b>:
           <span style="color:{color}"><b>{status}</b></span>.</p>
        <p style="color:#888;font-size:12px;">— BookMyClassroom</p>"""
        threading.Thread(target=_send_email,
                         args=(email, f"Cancellation {status} – {resource}", body),
                         daemon=True).start()

def _schedule_reminder_check():
    if st.session_state.get("_reminders_sent"):
        return
    now   = datetime.datetime.now()
    soon  = now + datetime.timedelta(hours=1)
    today = now.date()
    try:
        conn = get_connection(); c = conn.cursor(dictionary=True)
        c.execute("""SELECT username, room_name AS resource, start_time FROM bookings
                     WHERE date = %s AND start_time BETWEEN %s AND %s""",
                  (today, now.time(), soon.time()))
        upcoming = c.fetchall()
        c.execute("""SELECT username, lab_name AS resource, start_time FROM lab_bookings
                     WHERE date = %s AND start_time BETWEEN %s AND %s""",
                  (today, now.time(), soon.time()))
        upcoming += c.fetchall()
        conn.close()
        for row in upcoming:
            _push_in_app(row["username"],
                         f"⏰ Reminder: {row['resource']} starts at {row['start_time']} today.")
    except Exception as e:
        print(f"[Reminder] {e}")
    st.session_state["_reminders_sent"] = True

def notification_bell(user):
    username = user["username"] if isinstance(user, dict) else user
    try:
        conn = get_connection(); c = conn.cursor(dictionary=True)
        c.execute("""SELECT id, message, is_read, created_at FROM notifications
                     WHERE username = %s ORDER BY created_at DESC LIMIT 20""", (username,))
        notifs = c.fetchall(); conn.close()
    except Exception:
        notifs = []
    unread = sum(1 for n in notifs if not n["is_read"])
    label  = f"🔔 Notifications ({unread} new)" if unread else "🔔 Notifications"
    with st.sidebar.expander(label, expanded=False):
        if not notifs:
            st.caption("No notifications yet.")
        else:
            for n in notifs:
                st.markdown(
                    f"{'🆕 ' if not n['is_read'] else ''}{n['message']}  \n"
                    f"<span style='font-size:11px;color:#aaa;'>{n['created_at']}</span>",
                    unsafe_allow_html=True)
                st.divider()
            if st.button("Mark all read", key="notif_mark_read"):
                conn = get_connection(); c = conn.cursor()
                c.execute("UPDATE notifications SET is_read=TRUE WHERE username=%s", (username,))
                conn.commit(); conn.close(); st.rerun()

# =========================================================
# ── FEATURE 6: Mobile-Responsive UI CSS ───────────────────
# =========================================================
_MOBILE_CSS = """
<style>
@media (max-width: 768px) {
  section[data-testid="stSidebar"] {
    min-width:0!important;width:0!important;overflow:hidden!important;transition:width .3s ease;
  }
  section[data-testid="stSidebar"]:focus-within,
  section[data-testid="stSidebar"]:hover {
    width:80vw!important;min-width:200px!important;z-index:999;
    box-shadow:2px 0 12px rgba(0,0,0,.15);
  }
  .stButton>button{width:100%!important;min-height:48px!important;font-size:16px!important;border-radius:10px!important;}
  .stTextInput>div>input,.stSelectbox>div,.stDateInput>div>input,
  .stTimeInput>div>input,.stTextArea>div>textarea{
    width:100%!important;font-size:16px!important;min-height:44px!important;
  }
  div[data-testid="column"]{width:100%!important;flex:1 1 100%!important;min-width:0!important;}
  div[data-testid="metric-container"]{padding:12px!important;border-radius:10px!important;}
  div[data-testid="stDataFrame"]>div{overflow-x:auto!important;-webkit-overflow-scrolling:touch;}
  div[data-testid="stPlotlyChart"]{max-width:100vw!important;overflow-x:auto!important;}
  details>summary{padding:12px 8px!important;font-size:15px!important;}
  footer{display:none!important;}#MainMenu{display:none!important;}
}
@media (max-width:768px){
  .stRadio label,.stCheckbox label{padding:10px 0!important;font-size:15px!important;}
}
.stButton>button{border-radius:8px!important;font-weight:500!important;transition:opacity .15s ease!important;}
.stButton>button:hover{opacity:.85;}
div[data-testid="stSidebar"] .stButton>button{width:100%!important;}
</style>
"""

def _inject_mobile_css():
    st.markdown(_MOBILE_CSS, unsafe_allow_html=True)

# =========================================================
# MAIN  (original structure preserved, V2 features wired in)
# =========================================================
def main():
    # ── V2: mobile CSS + reminder check (run before anything else) ──
    _inject_mobile_css()
    _schedule_reminder_check()

    st.title("📚 BookMyClassroom")

    menu = st.sidebar.selectbox("Menu", ["Login", "Register", "Student Dashboard"])
    if menu == "Student Dashboard":
        student_dashboard()
        return

    if "user" not in st.session_state:
        if menu == "Login":
            login()
        elif menu == "Register":
            register()
    else:
        role = st.session_state["role"]
        user = {"username": st.session_state["user"], "role": st.session_state["role"]}

        # ── V2: notification bell in sidebar ──
        notification_bell(user)

        pages = ["Book Classroom", "Book Lab", "My Bookings", "My Calendar", "Logout"]
        if role == "admin":
            pages.insert(3, "Manage Cancellations")
            pages.insert(4, "Analytics")

        choice = st.sidebar.selectbox("Menu", pages)

        if choice == "Book Classroom":
            booking_page(user)
        elif choice == "Book Lab":
            lab_booking_dashboard(user)
        elif choice == "My Bookings":
            booking_history(user, role)
        elif choice == "My Calendar":
            # ── V2: weekly calendar view ──
            calendar_view(user, role)
        elif choice == "Manage Cancellations" and role == "admin":
            manage_cancellations()
        elif choice == "Analytics" and role == "admin":
            # ── V2: admin analytics dashboard ──
            admin_analytics()
        elif choice == "Logout":
            del st.session_state["user"]
            del st.session_state["role"]
            st.rerun()

if __name__ == "__main__":
    main()