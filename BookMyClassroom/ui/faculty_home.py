import streamlit as st

def faculty_home():
    st.subheader("Welcome to Faculty Dashboard")

    option = st.selectbox("Choose an option", [
        "View Available Classrooms",
        "Book a Classroom",
        "Logout"
    ])

    if option == "View Available Classrooms":
        st.info("Show available classrooms from database here.")
    
    elif option == "Book a Classroom":
        st.info("Form to book classroom goes here.")
    
    elif option == "Logout":
        st.session_state.logged_in = False
        st.rerun()
