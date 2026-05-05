CREATE TABLE IF NOT EXISTS bookings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(255),
    room_name VARCHAR(255),
    floor VARCHAR(50),
    date DATE,
    start_time TIME,
    end_time TIME,
    duration VARCHAR(20)
);
