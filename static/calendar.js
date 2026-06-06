// Calendar Widget with Date Selection and Time Slot Picking

class CalendarWidget {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.currentDate = new Date();
        this.selectedDate = null;
        this.selectedSlot = null;
        this.bookedSlots = [];
        this.init();
    }

    async init() {
        await this.loadBookedSlots();
        this.render();
    }

    async loadBookedSlots() {
        try {
            const response = await fetch('/api/bookings');
            const data = await response.json();
            if (data.success) {
                this.bookedSlots = data.bookings.map(b => ({
                    start: new Date(b.start),
                    end: new Date(b.end),
                    name: b.name
                }));
            }
        } catch (err) {
            console.error('Failed to load booked slots:', err);
        }
    }

    render() {
        this.container.innerHTML = `
            <div class="calendar-widget-full">
                <div class="calendar-header">
                    <button class="calendar-nav-btn" id="prev-month">
                        <i data-lucide="chevron-left" style="width: 18px; height: 18px;"></i>
                    </button>
                    <h3 class="calendar-title" id="calendar-month-year"></h3>
                    <button class="calendar-nav-btn" id="next-month">
                        <i data-lucide="chevron-right" style="width: 18px; height: 18px;"></i>
                    </button>
                </div>
                <div class="calendar-grid" id="calendar-days"></div>
                <div class="time-slots-section" id="time-slots" style="display: none;">
                    <div class="time-slots-header">
                        <h4>Available Times</h4>
                        <p class="selected-date-display" id="selected-date-text"></p>
                    </div>
                    <div class="time-slots-grid" id="time-slots-grid"></div>
                </div>
                <div class="booking-form-section" id="booking-form" style="display: none;">
                    <h4>Complete Booking</h4>
                    <p class="selected-time-display" id="selected-time-text"></p>
                    <div class="form-group">
                        <label>Interview Title</label>
                        <input type="text" id="booking-title" class="form-input" value="Interview with Piyush Joshi" required>
                    </div>
                    <div class="form-group">
                        <label>Your Full Name</label>
                        <input type="text" id="booking-name" class="form-input" placeholder="e.g. John Doe" required>
                    </div>
                    <div class="form-group">
                        <label>Your Email</label>
                        <input type="email" id="booking-email" class="form-input" placeholder="e.g. john@company.com" required>
                    </div>
                    <button class="booking-submit-btn" id="confirm-booking">
                        <i data-lucide="check-circle" style="width: 14px; height: 14px;"></i>
                        <span>Confirm Booking</span>
                    </button>
                </div>
            </div>
        `;

        this.attachEventListeners();
        this.renderCalendarDays();
        lucide.createIcons();
    }

    attachEventListeners() {
        document.getElementById('prev-month').addEventListener('click', () => {
            this.currentDate.setMonth(this.currentDate.getMonth() - 1);
            this.renderCalendarDays();
        });

        document.getElementById('next-month').addEventListener('click', () => {
            this.currentDate.setMonth(this.currentDate.getMonth() + 1);
            this.renderCalendarDays();
        });

        document.getElementById('confirm-booking').addEventListener('click', () => {
            this.submitBooking();
        });
    }

    renderCalendarDays() {
        const monthYear = document.getElementById('calendar-month-year');
        const daysContainer = document.getElementById('calendar-days');

        const year = this.currentDate.getFullYear();
        const month = this.currentDate.getMonth();

        monthYear.textContent = new Date(year, month).toLocaleDateString('en-US', {
            month: 'long',
            year: 'numeric'
        });

        // Get first day of month and number of days
        const firstDay = new Date(year, month, 1).getDay();
        const daysInMonth = new Date(year, month + 1, 0).getDate();
        const today = new Date();
        today.setHours(0, 0, 0, 0);

        let html = '';

        // Day headers
        const dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
        dayNames.forEach(day => {
            html += `<div class="calendar-day-header">${day}</div>`;
        });

        // Empty cells for days before month starts
        for (let i = 0; i < firstDay; i++) {
            html += `<div class="calendar-day-cell empty"></div>`;
        }

        // Days of the month
        for (let day = 1; day <= daysInMonth; day++) {
            const date = new Date(year, month, day);
            date.setHours(0, 0, 0, 0);

            const isPast = date < today;
            const isToday = date.getTime() === today.getTime();
            const isSelected = this.selectedDate && date.getTime() === this.selectedDate.getTime();

            let classes = 'calendar-day-cell';
            if (isPast) classes += ' past';
            if (isToday) classes += ' today';
            if (isSelected) classes += ' selected';
            if (!isPast) classes += ' clickable';

            html += `
                <div class="${classes}" data-date="${date.toISOString()}" ${!isPast ? 'onclick="calendarWidget.selectDate(this)"' : ''}>
                    <span class="day-number">${day}</span>
                </div>
            `;
        }

        daysContainer.innerHTML = html;
        lucide.createIcons();
    }

    async selectDate(element) {
        // Remove previous selection
        document.querySelectorAll('.calendar-day-cell').forEach(cell => {
            cell.classList.remove('selected');
        });

        // Add selection to clicked date
        element.classList.add('selected');

        const dateStr = element.getAttribute('data-date');
        this.selectedDate = new Date(dateStr);

        // Show time slots section
        const timeSlotsSection = document.getElementById('time-slots');
        const bookingForm = document.getElementById('booking-form');

        timeSlotsSection.style.display = 'block';
        bookingForm.style.display = 'none';

        // Update selected date display
        document.getElementById('selected-date-text').textContent =
            this.selectedDate.toLocaleDateString('en-US', {
                weekday: 'long',
                month: 'long',
                day: 'numeric',
                year: 'numeric'
            });

        // Load and display time slots for selected date
        await this.loadTimeSlotsForDate();
    }

    async loadTimeSlotsForDate() {
        const timeSlotsGrid = document.getElementById('time-slots-grid');
        timeSlotsGrid.innerHTML = '<div class="loading-slots">Loading available times...</div>';

        try {
            // Format date as YYYY-MM-DD
            const dateStr = this.selectedDate.toISOString().split('T')[0];
            const response = await fetch(`/api/slots?date=${dateStr}`);
            const data = await response.json();

            if (data.success && data.slots && data.slots.length > 0) {
                let html = '';
                data.slots.forEach(slot => {
                    const startTime = new Date(slot.start);
                    const timeStr = startTime.toLocaleTimeString('en-US', {
                        hour: 'numeric',
                        minute: '2-digit',
                        hour12: true
                    });

                    html += `
                        <button class="time-slot-btn"
                                data-start="${slot.start}"
                                data-end="${slot.end}"
                                data-formatted="${slot.formatted}"
                                onclick="calendarWidget.selectTimeSlot(this)">
                            <i data-lucide="clock" style="width: 14px; height: 14px;"></i>
                            <span>${timeStr}</span>
                        </button>
                    `;
                });
                timeSlotsGrid.innerHTML = html;
            } else {
                timeSlotsGrid.innerHTML = `
                    <div class="no-slots">
                        <i data-lucide="calendar-x" style="width: 24px; height: 24px; color: var(--text-muted);"></i>
                        <p>No available slots for this date</p>
                    </div>
                `;
            }

            lucide.createIcons();
        } catch (err) {
            timeSlotsGrid.innerHTML = `
                <div class="error-slots">
                    <i data-lucide="alert-circle" style="width: 24px; height: 24px; color: #ef4444;"></i>
                    <p>Failed to load time slots</p>
                </div>
            `;
            lucide.createIcons();
        }
    }

    selectTimeSlot(button) {
        // Remove previous selection
        document.querySelectorAll('.time-slot-btn').forEach(btn => {
            btn.classList.remove('selected');
        });

        // Add selection
        button.classList.add('selected');

        this.selectedSlot = {
            start: button.getAttribute('data-start'),
            end: button.getAttribute('data-end'),
            formatted: button.getAttribute('data-formatted')
        };

        // Show booking form
        const bookingForm = document.getElementById('booking-form');
        bookingForm.style.display = 'block';

        document.getElementById('selected-time-text').textContent =
            `Selected: ${this.selectedSlot.formatted}`;

        // Smooth scroll to form
        bookingForm.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    async submitBooking() {
        const name = document.getElementById('booking-name').value.trim();
        const email = document.getElementById('booking-email').value.trim();
        const title = document.getElementById('booking-title').value.trim();

        if (!name || !email) {
            alert('Please fill in your name and email');
            return;
        }

        if (!this.selectedSlot) {
            alert('Please select a time slot');
            return;
        }

        const confirmBtn = document.getElementById('confirm-booking');
        const originalHtml = confirmBtn.innerHTML;
        confirmBtn.disabled = true;
        confirmBtn.innerHTML = `
            <i data-lucide="loader-2" class="animate-spin" style="width: 14px; height: 14px;"></i>
            <span>Booking...</span>
        `;
        lucide.createIcons();

        try {
            const response = await fetch('/api/book', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name: name,
                    email: email,
                    start_time: this.selectedSlot.start,
                    end_time: this.selectedSlot.end,
                    title: title || 'Interview with Piyush Joshi'
                })
            });

            const data = await response.json();

            if (data.success) {
                const booking = data.booking;

                // Show success message
                const bookingForm = document.getElementById('booking-form');
                bookingForm.innerHTML = `
                    <div class="booking-success">
                        <i data-lucide="check-circle" style="width: 48px; height: 48px; color: #10b981;"></i>
                        <h3>Booking Confirmed!</h3>
                        <p>Your interview has been scheduled for:</p>
                        <p class="booking-time"><strong>${booking.formatted_time}</strong></p>
                        <p class="booking-details">Booking ID: <code>${booking.booking_id}</code></p>
                        <p class="booking-details">A confirmation has been sent to <strong>${email}</strong></p>
                        <button class="booking-submit-btn" onclick="calendarWidget.reset()">
                            Book Another Slot
                        </button>
                    </div>
                `;
                lucide.createIcons();

                // Reload booked slots to update calendar
                await this.loadBookedSlots();
            } else {
                alert(`Booking failed: ${data.error}`);
                confirmBtn.disabled = false;
                confirmBtn.innerHTML = originalHtml;
                lucide.createIcons();
            }
        } catch (err) {
            alert('Booking request failed. Please try again.');
            confirmBtn.disabled = false;
            confirmBtn.innerHTML = originalHtml;
            lucide.createIcons();
        }
    }

    reset() {
        this.selectedDate = null;
        this.selectedSlot = null;
        this.init();
    }
}

// Global instance
let calendarWidget = null;

// Initialize calendar when page loads
document.addEventListener('DOMContentLoaded', () => {
    const calendarContainer = document.getElementById('calendar-widget-container');
    if (calendarContainer) {
        calendarWidget = new CalendarWidget('calendar-widget-container');
    }
});
