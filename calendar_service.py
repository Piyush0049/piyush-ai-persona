import os
import json
import datetime
import httpx
from typing import List, Dict, Any
from config import settings

CALENDAR_DB_PATH = "data/calendar_db.json"

class CalendarService:
    def __init__(self):
        self.ensure_db()

    def ensure_db(self):
        if not os.path.exists("data"):
            os.makedirs("data")
        if not os.path.exists(CALENDAR_DB_PATH):
            with open(CALENDAR_DB_PATH, "w", encoding="utf-8") as f:
                json.dump({"bookings": []}, f, indent=2)

    def get_booked_slots(self) -> List[Dict[str, str]]:
        try:
            with open(CALENDAR_DB_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("bookings", [])
        except Exception:
            return []

    def save_booking_local(self, booking: Dict[str, Any]):
        try:
            with open(CALENDAR_DB_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["bookings"].append(booking)
            with open(CALENDAR_DB_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving local booking: {e}")

    def get_available_slots(self, date_str: str = None) -> List[Dict[str, str]]:
        """
        Propose slots for the given date. If no date is given, proposes slots for
        the next 3 days.
        Slots are 30 mins each:
        - 10:00 AM - 10:30 AM
        - 02:00 PM - 02:30 PM
        - 04:00 PM - 04:30 PM
        """
        # If Cal.com API key is provided, we can fetch Cal.com availability
        if settings.CAL_API_KEY and settings.CAL_EVENT_TYPE_ID:
            try:
                # Cal.com API availability check
                # For demo purposes, we fetch from cal.com, fallback to mock if API fails
                url = f"https://api.cal.com/v1/slots?apiKey={settings.CAL_API_KEY}&eventTypeId={settings.CAL_EVENT_TYPE_ID}"
                # Get next 3 days
                start_date = datetime.date.today().isoformat()
                end_date = (datetime.date.today() + datetime.timedelta(days=4)).isoformat()
                response = httpx.get(f"{url}&startTime={start_date}T00:00:00Z&endTime={end_date}T23:59:59Z", timeout=5.0)
                if response.status_code == 200:
                    slots_data = response.json().get("slots", {})
                    # Process slots_data
                    slots = []
                    for date, day_slots in slots_data.items():
                        for slot in day_slots[:3]: # Propose top 3 slots per day
                            slots.append({
                                "start": slot["time"],
                                "end": (datetime.datetime.fromisoformat(slot["time"].replace("Z", "+00:00")) + datetime.timedelta(minutes=30)).isoformat(),
                                "formatted": datetime.datetime.fromisoformat(slot["time"].replace("Z", "+00:00")).strftime("%A, %b %d at %I:%M %p")
                            })
                    if slots:
                        return slots
            except Exception as e:
                print(f"Cal.com fetch failed, using fallback: {e}")

        # Fallback / Mock Availability
        booked = self.get_booked_slots()
        booked_starts = {b["start"] for b in booked}

        base_date = datetime.date.today()
        # If a specific date is requested, parse it
        if date_str:
            try:
                base_date = datetime.date.fromisoformat(date_str)
            except ValueError:
                pass

        slots = []
        days_to_check = 1 if date_str else 3
        current_day = base_date
        max_days_scanned = 0  # Safety guard to prevent infinite loop

        while len(slots) < 6 and len(slots) < (days_to_check * 3) and max_days_scanned < 30:
            max_days_scanned += 1
            # Skip weekends (Saturday=5, Sunday=6)
            if current_day.weekday() in (5, 6):
                current_day += datetime.timedelta(days=1)
                continue
                
            # Propose three times for each day
            times = ["10:00", "14:00", "16:00"]
            for t in times:
                hr, mn = map(int, t.split(":"))
                start_dt = datetime.datetime.combine(current_day, datetime.time(hr, mn))
                end_dt = start_dt + datetime.timedelta(minutes=30)
                
                # Format ISO
                start_iso = start_dt.isoformat()
                end_iso = end_dt.isoformat()
                
                # Check if already booked
                if start_iso not in booked_starts:
                    formatted_time = start_dt.strftime("%A, %b %d at %I:%M %p")
                    slots.append({
                        "start": start_iso,
                        "end": end_iso,
                        "formatted": formatted_time
                    })
            current_day += datetime.timedelta(days=1)

        return slots

    async def book_meeting(self, name: str, email: str, start_time: str, end_time: str) -> Dict[str, Any]:
        """
        Books a meeting. If Cal.com or Google Calendar is configured, updates them.
        Always saves locally in calendar_db.json.
        """
        # Parse times
        try:
            start_dt = datetime.datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            end_dt = datetime.datetime.fromisoformat(end_time.replace("Z", "+00:00"))
        except Exception:
            start_dt = datetime.datetime.fromisoformat(start_time)
            end_dt = datetime.datetime.fromisoformat(end_time)

        booking_id = f"book_{int(datetime.datetime.now().timestamp())}"
        
        booking_result = {
            "success": True,
            "booking_id": booking_id,
            "name": name,
            "email": email,
            "start": start_time,
            "end": end_time,
            "formatted_time": start_dt.strftime("%A, %b %d at %I:%M %p"),
            "provider": "mock"
        }

        # 1. Cal.com booking
        if settings.CAL_API_KEY and settings.CAL_EVENT_TYPE_ID:
            try:
                # Call Cal.com API to book
                async with httpx.AsyncClient() as client:
                    payload = {
                        "eventTypeId": int(settings.CAL_EVENT_TYPE_ID),
                        "start": start_time,
                        "end": end_time,
                        "responses": {
                            "name": name,
                            "email": email
                        },
                        "metadata": {},
                        "timeZone": "Asia/Kolkata",
                        "language": "en"
                    }
                    resp = await client.post(
                        f"https://api.cal.com/v1/bookings?apiKey={settings.CAL_API_KEY}",
                        json=payload,
                        timeout=10.0
                    )
                    if resp.status_code in (200, 201):
                        cal_data = resp.json().get("booking", {})
                        booking_result["provider"] = "cal.com"
                        booking_result["booking_id"] = cal_data.get("id", booking_id)
                        booking_result["web_link"] = cal_data.get("receiptUrl")
            except Exception as e:
                print(f"Cal.com booking request failed: {e}")

        # 2. Google Calendar booking
        elif settings.GOOGLE_CALENDAR_ID and os.path.exists("google_credentials.json"):
            try:
                from google.oauth2 import service_account
                from googleapiclient.discovery import build
                
                SCOPES = ['https://www.googleapis.com/auth/calendar']
                creds = service_account.Credentials.from_service_account_file(
                    'google_credentials.json', scopes=SCOPES
                )
                service = build('calendar', 'v3', credentials=creds)
                
                event = {
                    'summary': f'Interview with {name} (Piyush Joshi AI Rep)',
                    'description': f'Automatically booked interview for {name} ({email}). Generated by AI representative.',
                    'start': {
                        'dateTime': start_time,
                        'timeZone': 'Asia/Kolkata',
                    },
                    'end': {
                        'dateTime': end_time,
                        'timeZone': 'Asia/Kolkata',
                    },
                    'attendees': [
                        {'email': email},
                        {'email': 'piyushjoshi81204@gmail.com'}
                    ],
                }
                
                created_event = service.events().insert(
                    calendarId=settings.GOOGLE_CALENDAR_ID, body=event
                ).execute()
                
                booking_result["provider"] = "google_calendar"
                booking_result["booking_id"] = created_event.get("id")
                booking_result["web_link"] = created_event.get("htmlLink")
            except Exception as e:
                print(f"Google Calendar booking failed: {e}")

        # Always save locally
        self.save_booking_local(booking_result)
        return booking_result

# Global calendar service
calendar_service = CalendarService()
