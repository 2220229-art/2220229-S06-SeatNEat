# GitHub issue to submit

Create this issue on GitHub after the repository is pushed. The teacher needs the issue link, which looks like `https://github.com/2220229-art/2220229-S06-SeatNEat/issues/1`.

1. Push this project to `main`.
2. Open https://github.com/2220229-art/2220229-S06-SeatNEat/issues/new
3. Copy the title and body below.
4. Submit the new issue URL.

## Title

Implement full CRUD for reservations, seats, and staff

## Body

### Summary

SitNeat needs one complete feature where a user can create a record, open one record, see a list, update a record, and delete a record. The feature is restaurant reservations, with the same actions for seats and staff accounts.

The frontend is functional React with TypeScript. The backend is FastAPI. The database models are SQLModel tables used by the API.

### Frontend

- Create a reservation from the booking page.
- Read the customer's reservation list, today's staff list, and the manager's filtered list.
- Read one reservation, one seat, or one staff account from a View action that calls the single-record API.
- Update an eligible reservation, a seat, or a staff account.
- Delete a reservation permanently. Cancel stays as a separate action and keeps the booking with status cancelled.
- A manager can delete an unused seat or an unused staff account. If the record is already in use, the API asks them to deactivate it instead.

### Backend

All paths are under `/api/v1`.

Reservations:

- `POST /reservations` creates a confirmed booking.
- `GET /reservations/mine`, `GET /reservations/today`, and `GET /reservations` read lists.
- `GET /reservations/{id}` reads one booking the user is allowed to see.
- `PATCH /reservations/{id}` updates the customer's own confirmed booking before the cutoff.
- `DELETE /reservations/{id}` deletes the customer's own booking, or any booking when the user is a manager.

Seats:

- `POST /seats` creates a seat.
- `GET /seats` reads the list.
- `GET /seats/{id}` reads one seat.
- `PATCH /seats/{id}` updates a seat.
- `DELETE /seats/{id}` deletes a seat that has no reservations.

Staff:

- `POST /staff` creates a staff account.
- `GET /staff` reads the list.
- `GET /staff/{id}` reads one staff account.
- `PATCH /staff/{id}` updates a staff account.
- `DELETE /staff/{id}` deletes a staff account that has no activity.

### Database

The API uses the `users`, `seats`, `reservations`, and `restaurant_settings` models. Creating, reading, updating, and deleting goes through those tables. Customers can only read and delete their own reservations. Staff cannot permanently delete a reservation.

### Done when

- [ ] A customer can create, list, open, update, and delete a reservation in the React app.
- [ ] A manager can create, list, open, update, and delete a seat.
- [ ] A manager can create, list, open, update, and delete a staff account.
- [ ] FastAPI enforces roles, so a customer cannot manage seats or staff and cannot delete another customer's booking.
- [ ] The feature is merged into `main` before the assessment.
