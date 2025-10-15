import sqlite3

# Connect to (or create) the database
conn = sqlite3.connect("classrooms.db")
cursor = conn.cursor()

# Drop existing tables if they exist
cursor.execute("DROP TABLE IF EXISTS classrooms")

# Create classrooms table with floor column
cursor.execute("""
CREATE TABLE classrooms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    room_name TEXT NOT NULL,
    capacity INTEGER NOT NULL,
    features TEXT,
    floor TEXT
)
""")

# Insert 3rd floor data
cursor.executemany("""
INSERT INTO classrooms (room_name, capacity, features, floor)
VALUES (?, ?, ?, ?)
""", [
    ('Room 31', 85, 'computers, projector', '3rd'),
    ('Room 32', 85, 'computers, projector', '3rd'),
    ('Room 33', 75, 'computers, projector', '3rd'),
    ('Room 34', 95, 'computers, projector', '3rd')
])

# Insert 4th floor data
cursor.executemany("""
INSERT INTO classrooms (room_name, capacity, features, floor)
VALUES (?, ?, ?, ?)
""", [
    ('Room 41', 90, 'computers, projector', '4th'),
    ('Room 42', 90, 'computers, projector', '4th'),
    ('Room 43', 90, 'computers, projector', '4th'),
    ('Room 44a', 90, 'computers, projector', '4th'),
    ('Room 44', 60, 'computers, projector', '4th'),
    ('Room 45', 65, 'computers, projector', '4th'),
    ('Room 46', 65, 'computers, projector', '4th'),
    ('Room 47', 65, 'computers, projector', '4th'),
    ('Room 48', 65, 'computers, projector', '4th'),
    ('Room 41a', 80, 'computers, projector', '4th')
])

# Save changes
conn.commit()
conn.close()

print("✅ Database created successfully!")
