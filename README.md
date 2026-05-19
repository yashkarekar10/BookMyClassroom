# BookMyClassroom – Project Description

## 📌 Project Overview

**BookMyClassroom** is a smart classroom and laboratory booking management system developed for colleges and educational institutions. The system allows faculty members to efficiently reserve classrooms and computer labs based on availability, date, floor, and time slots while preventing scheduling conflicts.

The project is designed to digitize the traditional manual classroom allocation process and provide a centralized platform for booking management, cancellation handling, notifications, analytics, and timetable visibility.

The application is developed using:

* **Frontend:** HTML, CSS, JavaScript, Bootstrap
* **Backend:** Flask (Python)
* **Database:** MySQL
* **Authentication & Security:** bcrypt password hashing, session management
* **Additional Features:** Notifications, Calendar View, Analytics Dashboard, Conflict Detection System

---

# 🎯 Main Objectives

* Eliminate classroom booking clashes
* Provide a real-time booking system
* Allow faculty to reserve classrooms/labs online
* Give administrators centralized control
* Improve classroom utilization efficiency
* Maintain secure authentication and booking records

---

# ⚙️ Core Functionalities

## 👨‍🏫 Faculty Features

### 1. User Registration & Login

* Faculty can create accounts securely
* Passwords are encrypted using **bcrypt hashing**
* Session-based authentication system

### 2. Classroom Booking

Faculty can:

* Select floor and classroom
* Choose booking date
* Select start and end time
* Add booking description/purpose

The system automatically:

* Checks classroom availability
* Prevents overlapping bookings
* Stores booking history

---

## 💻 Laboratory Booking

* Separate lab booking module
* Labs stored in a dedicated `labs` table
* Supports lab capacities and features
* Similar conflict detection logic as classroom booking

---

## 📅 Calendar System

Interactive monthly calendar showing:

* Daily bookings
* Classroom schedules
* Lab schedules
* User-wise booking visibility

Admins can view all bookings while faculty see only their own schedules.

---

## 🔔 Notification System

The application includes a dynamic notification system:

* Booking confirmation notifications
* Cancellation approval/rejection alerts
* Unread notification counters
* Automatic notification updates across pages

---

## ❌ Cancellation Request Workflow

Faculty members cannot directly delete bookings.

Instead:

1. Faculty sends cancellation request
2. Admin reviews request
3. Admin approves/rejects cancellation
4. User receives notification

This ensures proper booking control and accountability.

---

## 👨‍💼 Admin Features

### Admin Dashboard

Admins can:

* View all bookings
* Monitor cancellation requests
* Manage booking approvals
* Access analytics dashboard

---

## 📊 Analytics Dashboard

The analytics module provides:

* Total classroom bookings
* Total lab bookings
* Active users
* Peak booking hours
* Most used classrooms/labs
* Daily booking statistics

This helps institutions analyze resource utilization.

---

# 🔥 New Updates Added to the Project

## ✅ 1. Separate Lab Booking System

* Labs separated from classrooms
* Dedicated `labs` and `lab_bookings` tables
* Better database normalization

---

## ✅ 2. Clash Detection System

Advanced SQL conflict detection query prevents overlapping bookings.

Features:

* Same-room validation
* Same-date validation
* Time interval overlap checking
* Optimized using `LIMIT 1`

---

## ✅ 3. Notification System

Implemented:

* Notification database table
* Unread notification badge
* Auto mark-as-read functionality
* Context processor for global notification updates

---

## ✅ 4. Calendar View Module

Added:

* Monthly booking visualization
* Faculty and admin-specific views
* JSON serialization fixes for MySQL dates/time

---

## ✅ 5. Cancellation Management Workflow

Implemented:

* Separate cancellation request tables
* Admin approval/rejection system
* Automated notification triggers

---

## ✅ 6. Password Security Using bcrypt

Passwords are:

* Never stored in plain text
* Securely hashed using bcrypt
* Protected against password leakage attacks

---

## ✅ 7. Student Public View

Added public student dashboard:

* No login required
* Students can view classroom/lab occupancy
* Helps students locate ongoing lectures/labs

---

## ✅ 8. Dashboard Improvements

Enhanced faculty dashboard with:

* Upcoming bookings
* Total booking statistics
* Pending request tracking
* Recent activities

---

## ✅ 9. API Endpoints for Dynamic Updates

Created APIs:

* `/api/rooms`
* `/api/floor-status`

Used for:

* Dynamic room availability
* Real-time room updates

---

## ✅ 10. ACID-Compliant Transaction Handling

Implemented:

* `commit()`
* `rollback()`
* Transaction-safe booking operations

Ensures:

* Data consistency
* Reliable booking management
* Safe concurrent operations

---

# 🛡️ Security Features

* bcrypt password hashing
* Session-based authentication
* Role-based access control
* Admin-only protected routes
* SQL parameterized queries (prevents SQL injection)

---

# 🗄️ Database Tables Used

Main tables:

* `faculty`
* `classrooms`
* `labs`
* `bookings`
* `lab_bookings`
* `notifications`
* `cancel_requests`
* `cancel_lab_requests`

---

# 📈 Benefits of the System

* Reduces manual scheduling errors
* Prevents double booking
* Improves classroom utilization
* Provides centralized management
* Saves faculty time
* Enhances transparency in booking operations

---

# 🚀 Future Enhancements

Possible future upgrades:

* Email OTP verification
* QR-based classroom access
* Real-time WebSocket notifications
* AI-based room recommendations
* Mobile application support
* Timetable integration
* Attendance tracking system

---

# 🎓 Conclusion

BookMyClassroom is a complete web-based classroom and laboratory reservation system that modernizes campus resource management. With secure authentication, conflict-free scheduling, notifications, analytics, cancellation workflows, and calendar integration, the system provides an efficient, scalable, and user-friendly solution for educational institutions.
