import streamlit as st
import mysql.connector
import datetime
import pandas as pd

# =========================================================
# DB CONNECTION
# =========================================================
def get_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="nidhi06yash",   # <-- adjust if needed
        database="bookmyclassroom"
    )

# Small helper so we can accept either a dict {"username": "..."} or a string "..."
def _username_of(user):
    if isinstance(user, dict):
        return user.get("username")
    return user

# =========================================================
# BOOKING HELPERS (time overlap, validation)
# =========================================================
def _times_overlap(existing_start, existing_end, new_start, new_end):
    """
    Overlap rule (half-open intervals): [start, end)
    Two slots overlap if NOT (existing_end <= new_start OR existing_start >= new_end)
    """
    return not (existing_end <= new_start or existing_start >= new_end)

def is_booking_available(room, date, start, end):
    """
    Correct overlap check for the given room/date/time window.
    """
    if start >= end:
        return False  # invalid time range

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
    """
    Inserts a classroom booking after checking overlap and validating inputs.
    Accepts user as dict({"username": ...}) or plain string username.
    """
    username = _username_of(user)

    # Basic validations
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
        return True
    except Exception as e:
        conn.rollback()
        st.error(f"Booking failed: {e}")
        return False
    finally:
        conn.close()

# =========================================================
# AUTH
# =========================================================
def login():
    st.subheader("Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM faculty WHERE username = %s AND password = %s", (username, password))
        user = cursor.fetchone()
        conn.close()

        if user:
            st.session_state["user"] = user["username"]
            st.session_state["role"] = user["role"]
            st.success(f"Logged in as {user['role']}")
            st.rerun()
        else:
            st.error("Invalid username or password")

def register():
    st.subheader("Faculty Registration")
    name = st.text_input("Name")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    role = st.selectbox("Role", ["teacher", "admin"])
    if st.button("Register"):
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO faculty (name, username, password, role)
                VALUES (%s, %s, %s, %s)
            """, (name, username, password, role))
            conn.commit()
            st.success("Registration successful. Please login.")
        except Exception as e:
            conn.rollback()
            st.error(f"Registration failed: {e}")
        finally:
            conn.close()

# =========================================================
# BOOKING PAGE (Classroom Only) – for teacher/admin
# =========================================================
def booking_page(user):
    st.subheader("Book a Classroom")
    floor = st.selectbox("Select Floor", ["1st","2nd","3rd", "4th"])
    date = st.date_input("Date", min_value=datetime.date.today())
    start = st.time_input("Start Time")
    default_end = (datetime.datetime.combine(datetime.date.today(), start) + datetime.timedelta(hours=1)).time()
    end = st.time_input("End Time", value=default_end)
    description = st.text_area("Description (optional):", "")

    # Fetch available rooms on that floor by excluding rooms with overlapping bookings
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
        return

    room = st.selectbox("Available Rooms", rooms)

    if st.button("Book Now"):
        duration = str(
            datetime.datetime.combine(datetime.date.today(), end)
            - datetime.datetime.combine(datetime.date.today(), start)
        )
        success = book_room(user, room, floor, date, start, end, duration, description)
        if success:
            st.success(f"Classroom {room} booked successfully!")

# =========================================================
# LAB BOOKING DASHBOARD – for teacher/admin
# =========================================================
def lab_booking_dashboard(user):
    st.header("Lab Booking Dashboard")

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # Get all labs (no floor filter)
    cursor.execute("SELECT * FROM labs ORDER BY lab_name")
    labs = cursor.fetchall()
    lab_names = [lab['lab_name'] for lab in labs]
    selected_lab = st.selectbox("Select Lab", lab_names)

    date = st.date_input("Select Date", min_value=datetime.date.today(), key="lab_date_input")
    start_time = st.time_input("Start Time", key="lab_start_time")
    end_time = st.time_input("End Time", key="lab_end_time")

    # Calculate duration
    if start_time and end_time:
        start_dt = datetime.datetime.combine(datetime.date.today(), start_time)
        end_dt = datetime.datetime.combine(datetime.date.today(), end_time)
        duration = str(end_dt - start_dt)
    else:
        duration = ""

    description = st.text_area("Purpose / Description")

    # Get floor for selected lab (if any)
    selected_lab_info = next((lab for lab in labs if lab["lab_name"] == selected_lab), None)
    floor = selected_lab_info["floor"] if selected_lab_info else ""

    if st.button("Book Lab"):
        # Clash check using proper overlap logic
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

    # Show existing bookings
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
# BOOKING HISTORY (Teachers can request cancellations)
# =========================================================
def booking_history(user, role=None):
    st.subheader("📖 Booking History")

    # Checkbox to toggle past bookings
    show_past = st.checkbox("Show past bookings", value=False)

    # --- Classroom bookings ---
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

    # --- Lab bookings ---
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

    # --- Display results ---
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

    # Teachers can request cancellations
    if role == "teacher":
        st.write("---")
        st.write("### Request Cancellation")

        booking_type = st.radio("Select booking type:", ["Classroom", "Lab"])
        booking_id = st.number_input("Enter Booking ID to Request Cancellation", min_value=1, step=1)
        reason = st.text_area("Reason for cancellation:")

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
                    cursor.execute("""
                        INSERT INTO cancel_lab_requests (booking_id, teacher_username, reason)
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
# CANCELLATION MANAGEMENT (Admin Only)
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
                        cursor.execute("DELETE FROM bookings WHERE id=%s", (booking_id,))
                        cursor.execute("UPDATE cancel_requests SET status='Approved' WHERE id=%s", (req_id,))
                        conn.commit()
                        st.success(f"Classroom booking {booking_id} cancelled successfully.")
                    else:
                        st.error("Request not found.")
                else:
                    cursor.execute("UPDATE cancel_requests SET status='Rejected' WHERE id=%s", (req_id,))
                    conn.commit()
                    st.info("Request rejected.")

            else:  # Lab cancellations
                if action == "Approve":
                    cursor.execute("SELECT booking_id FROM cancel_lab_requests WHERE id=%s", (req_id,))
                    row = cursor.fetchone()
                    if row:
                        booking_id = row[0]
                        cursor.execute("DELETE FROM lab_bookings WHERE id=%s", (booking_id,))
                        cursor.execute("UPDATE cancel_lab_requests SET status='Approved' WHERE id=%s", (req_id,))
                        conn.commit()
                        st.success(f"Lab booking {booking_id} cancelled successfully.")
                    else:
                        st.error("Request not found.")
                else:
                    cursor.execute("UPDATE cancel_lab_requests SET status='Rejected' WHERE id=%s", (req_id,))
                    conn.commit()
                    st.info("Request rejected.")

        except Exception as e:
            conn.rollback()
            st.error(f"Action failed: {e}")
        finally:
            conn.close()

# =========================================================
# STUDENT DASHBOARD – view all labs (no floor filter)
# =========================================================
def student_dashboard():
    st.subheader("🎓 Student Dashboard – View Bookings")
    date = st.date_input("Select Date", min_value=datetime.date.today())
    floor = st.selectbox("Select Floor (for classrooms only)", ["1st","2nd","3rd", "4th"])
    conn = get_connection()

    # Classrooms filtered by floor
    query_class = """
        SELECT room_name AS Room, start_time AS Start, end_time AS End, description AS Description
        FROM bookings
        WHERE date = %s AND floor = %s
            AND (date > CURDATE() OR (date = CURDATE() AND end_time > CURTIME()))
        ORDER BY start_time
    """
    df_class = pd.read_sql(query_class, conn, params=(date, floor))

    # Labs – show all labs by date (no floor filter)
    query_lab = """
        SELECT lab_name AS Lab, start_time AS Start, end_time AS End, description AS Description
        FROM lab_bookings
        WHERE date = %s
            AND (date > CURDATE() OR (date = CURDATE() AND end_time > CURTIME()))
        ORDER BY start_time
    """

    df_lab = pd.read_sql(query_lab, conn, params=(date,))

    conn.close()

    st.write("### 🏫 Classroom Bookings")
    if df_class.empty:
        st.info("No classroom bookings for this floor on this date.")
    else:
        st.dataframe(df_class)

    st.write("### 🧪 Lab Bookings")
    if df_lab.empty:
        st.info("No lab bookings for this date.")
    else:
        st.dataframe(df_lab)

# =========================================================
# MAIN
# =========================================================
def main():
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

        pages = ["Book Classroom", "Book Lab", "My Bookings", "Logout"]
        if role == "admin":
            pages.insert(3, "Manage Cancellations")  # Admin-only

        choice = st.sidebar.selectbox("Menu", pages)

        if choice == "Book Classroom":
            booking_page(user)
        elif choice == "Book Lab":
            lab_booking_dashboard(user)
        elif choice == "My Bookings":
            booking_history(user, role)
        elif choice == "Manage Cancellations" and role == "admin":
            manage_cancellations()
        elif choice == "Logout":
            del st.session_state["user"]
            del st.session_state["role"]
            st.rerun()

if __name__ == "__main__":
    main()