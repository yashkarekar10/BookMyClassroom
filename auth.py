from db import connect

def register_faculty(email, password):
    conn = connect()
    c = conn.cursor()

    try:
        c.execute("INSERT INTO faculty (email, password) VALUES (%s, %s)", (email, password))
        conn.commit()
        conn.close()
        return True
    except:
        return False  # Email already exists

def validate_faculty_login(email, password):
    conn = connect()
    c = conn.cursor()
    c.execute("SELECT * FROM faculty WHERE email=%s AND password=%s", (email, password))
    user = c.fetchone()
    conn.close()
    return user
