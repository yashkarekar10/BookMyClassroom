import streamlit as st

# Dummy credentials for testing
USERS = {
    "admin": "admin123",
    "faculty1": "password1"
}

def login_window():
    st.subheader("Login to BookMyClassroom")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        if username in USERS and USERS[username] == password:
            st.success("Login successful!")
            st.session_state.logged_in = True
        else:
            st.error("Invalid username or password")
