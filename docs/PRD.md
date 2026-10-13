# SITNEAT Product Requirements Document:


Version 1.0. Status is draft for review. Date is October 2026. Technology is React.js with TypeScript for the frontend, FastAPI with Python for the backend, and PostgreSQL for the database. This document is for a university full-stack web application. It is written in clear, practical English. It describes planned behavior and does not claim that the application has already been built or tested.

# Executive Summary: 


SitNeat is a booking app for one restaurant. The idea is simple. Instead of calling the restaurant to reserve a table, customers open the website, pick a date and time, and book their seat online. They also tell the restaurant if they want vegetarian or non-vegetarian food. And they can say if they have any food allergies. Restaurant staff use the same app to see who is coming today and manage the tables. The manager controls seats, staff accounts, opening hours, and booking rules. This is a course project. I am not building a huge restaurant platform. I am building a clean, secure, complete web app that shows what I learned. It uses React.js with TypeScript on the frontend, FastAPI with Python on the backend, REST APIs, PostgreSQL for data, plus authentication, role-based access control, security scopes, and ownership checks.

# The Problem and My Solution:


Many small restaurants manage bookings through phone calls, text messages, or paper notes. This causes double-bookings where two people get the same seat. It also causes lost food preferences, missed allergy notes, and no clear view of the day's schedule. My solution is SitNeat. It puts all bookings in one place. Customers book online without calling. The backend checks availability and stops double-bookings automatically. Food preference and allergy info are stored separately and clearly. Staff get a simple daily view. Managers control everything from one dashboard.


# Goals and How I Measure Success:

The first goal is that customers can register and book online. I will check this by seeing if a customer completes the full booking flow. The second goal is to stop double-booking. I will check this by trying two overlapping requests for the same seat and making sure only one succeeds. The third goal is to record dietary information clearly. I will check this by making sure food preference and allergy declaration are separate required fields. The fourth goal is to help daily restaurant work. I will check this by making sure staff can view today's bookings and update statuses. The fifth goal is to give managers basic control. I will check this by making sure a manager can manage seats, staff, hours, and booking rules. The sixth goal is to protect accounts and data. I will check this by running tests that show forbidden actions are blocked. The seventh goal is to keep the project realistic. I will check this by completing the MVP without adding extra features.

# Who Uses SitNeat

There are three types of users. Each has different powers.

A customer is a regular person. They can sign up and log in. They can search for available seats. They can book, change, or cancel their own bookings. They can enter food preference like vegetarian or non-vegetarian. They can enter allergy information. They cannot see other customers' bookings. They cannot manage seats, staff, or settings.

A staff member is a restaurant worker. They can see today's bookings. They can see food and allergy details so they can prepare. They can mark guests as seated or completed. They can cancel a confirmed booking if a guest asks. They cannot manage accounts or change roles. They cannot manage seats or settings.

A manager is the boss. They can do everything staff can do. They can view and filter all bookings. They can add, edit, or deactivate seats. They can create and manage staff accounts. They can change restaurant hours and booking rules. They can see simple booking summaries. They cannot create or promote other managers through the app.

One important rule is that when someone signs up, they always become a customer. Staff accounts are created by a manager. Manager accounts are set up through a special controlled process outside the normal app.


# What Is In and What Is Out

The first version includes customer registration, login, logout, and profile viewing. It includes a seat list and availability search by date, time, and party size. It includes creating, viewing, editing, and cancelling own reservations. It includes food preference and allergy fields. It includes a staff daily dashboard with status updates. It includes manager tools for seats, staff, hours, booking rules, and summaries. It includes backend security with authentication, role-based access control, security scopes, ownership checks, and double-booking prevention.

The first version does not include online payments, deposits, or refunds. It does not include email, SMS, or push notifications. It does not include multiple restaurant branches. It does not include waitlists or loyalty programs. It does not include menu management, food ordering, or delivery. It does not include AI, machine learning, large language models, native mobile apps, social login, or advanced analytics. It does not include drag-and-drop floor plans or microservices.


# Main Features

The first feature is accounts and login. Customers sign up with name, email, and password. Passwords are stored safely using hashing and never as plain text. All three roles log in, but each sees different things based on their role.

The second feature is seat availability. Users pick a date, a start time, and a party size. SitNeat shows active seats that fit the party and are free for the full booking time. Availability is checked again when saving the booking in case someone else grabbed the seat.

The third feature is reservations. Customers pick a seat, enter food details, review, and submit. A successful booking is automatically marked as confirmed. The backend calculates the end time from the restaurant's configured duration.

The fourth feature is food and allergy information. Customers choose vegetarian or non-vegetarian for food preference. They also choose no known allergies or allergies specified for allergy declaration. If they pick allergies specified, they must write the details. It is important to know that vegetarian does not mean allergy-free. These are two separate things.

The fifth feature is the staff dashboard. Staff see confirmed and seated bookings for today. They can mark confirmed as seated. They can mark seated as completed. They can cancel a confirmed booking on a guest's behalf.

The sixth feature is the manager dashboard. Managers can view and filter bookings. They can manage seats. They can manage staff accounts. They can set hours and rules. They can see summary counts.

The seventh feature is booking status rules. There are four statuses. Confirmed means the booking is locked in. Seated means the guest has arrived and sat down. Completed means the guest finished their meal. Cancelled means the booking was cancelled. There is no pending status. A booking is confirmed immediately after saving.


# User Stories

As a customer, I want to register and log in so I can make bookings. This is a must. As a customer, I want to see seats available for my time and party size. This is a must. As a customer, I want to book a seat and get confirmation. This is a must. As a customer, I want to record food preference and allergy info separately. This is a must. As a customer, I want to view, edit, or cancel my bookings. This is a must. As staff, I want to see today's bookings and food notes. This is a must. As staff, I want to update booking status or cancel for a guest. This is a must. As manager, I want to manage seats and staff accounts. This is a must. As manager, I want to change opening hours and booking rules. This is a must. As manager, I want to view booking counts for a date range. This should be done.

Acceptance Criteria

Public registration always creates a customer no matter what role the browser tries to send. Bad passwords, expired tokens, and inactive accounts are rejected. Customers can only access their own bookings. Availability shows active seats with enough capacity and no overlap. When saving, the backend checks availability again. If there is a conflict, it returns a clear error. The backend calculates the end time and customers do not send it. Food preference and allergy declaration are both required. If allergies specified is chosen, details are required. Customers can edit or cancel only before the cutoff time. Staff can only do their allowed actions. Only managers can manage seats, staff, and settings. Completed and cancelled bookings cannot be reopened. The app clearly says allergy info is customer-declared and does not guarantee allergen-free food.

Main User Journeys

The first journey is a customer booking a seat. The customer logs in and picks a date, time, and party size. SitNeat shows available seats. The customer picks a seat, food preference, and allergy info. The customer reviews and submits. The backend validates, saves as confirmed, and returns confirmation.

The second journey is staff handling service. Staff open today's bookings. Staff check the booking and food notes. Staff mark the guest as seated. Later staff mark the booking as completed. If needed, staff can cancel a confirmed booking for a guest.

The third journey is manager setup. The manager updates seats or staff accounts. The manager sets hours and booking rules. The manager reviews bookings and summaries.

# Business Rules

The MVP supports one restaurant and one time zone. Each reservation uses exactly one seat. Party size must fit the seat's capacity. End time equals start time plus the configured duration. A seat must be active and free for the whole booking time. Confirmed and seated bookings block overlapping bookings for the same seat. New bookings are confirmed immediately with no pending status. The allowed flow is confirmed to seated to completed. Confirmed can also become cancelled. Seated bookings cannot be cancelled in this MVP. Completed and cancelled are final statuses. Customers can edit or cancel their own confirmed booking before the cutoff. Staff and managers can cancel a confirmed booking on a guest's behalf. Allergy details are private and must never be written to routine logs. Allergy info is customer-declared and SitNeat does not guarantee allergen-free food.

Priorities and Milestones

The must-have features are authentication, roles and scopes, seat availability, reservation create view edit and cancel, food and allergy fields, staff dashboard, manager tools for seats staff and settings, and core tests. The should-have features are summary reports, date and status filters, and clear loading empty and error messages. The later features that are out of scope are payments, notifications, multiple branches, AI, machine learning, mobile app, and advanced analytics.
Priorities and Milestones

The must-have features are authentication, roles and scopes, seat availability, reservation create view edit and cancel, food and allergy fields, staff dashboard, manager tools for seats staff and settings, and core tests. The should-have features are summary reports, date and status filters, and clear loading empty and error messages. The later features that are out of scope are payments, notifications, multiple branches, AI, machine learning, mobile app, and advanced analytics.

The timeline is as follows. First I agree on the PRD, SRS, TDD, and booking rules. Second I build the database, migrations, authentication, roles, and scopes. Third I build the seat and reservation APIs with conflict prevention. Fourth I build the React pages and connect them to FastAPI. Fifth I test permissions, booking conflicts, and main user journeys. Sixth I review documentation and add the required GitHub issue and pull request links.

# Risks and Assumptions

For double-booking, I will use backend validation and a database-level conflict protection strategy. For too much scope, I will stick to the MVP list and defer extra features. For wrong permissions, I will test allowed and forbidden actions for every role. For allergy privacy, I will limit access and keep allergy details out of logs. For time zone confusion, I will use one restaurant time zone and consistent timestamp handling.

Assumptions to confirm before coding are opening hours, slot interval, lead time, advance-booking window, customer change cutoff, and time zone.
