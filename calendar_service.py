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
        the next 14 workdays (full 2 weeks).
        Always filters out slots in the past and slots that overlap with existing bookings.
        """
        kolkata_tz = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
        now_kolkata = datetime.datetime.now(kolkata_tz)

        # Parse booked intervals in Kolkata timezone for overlap checks
        booked = self.get_booked_slots()
        booked_intervals = []
        for b in booked:
            try:
                b_start = datetime.datetime.fromisoformat(b["start"].replace("Z", "+00:00")).astimezone(kolkata_tz)
                b_end = datetime.datetime.fromisoformat(b["end"].replace("Z", "+00:00")).astimezone(kolkata_tz)
                booked_intervals.append((b_start, b_end))
            except Exception:
                continue

        if settings.CAL_API_KEY and settings.CAL_EVENT_TYPE_ID:
            try:
                url = f"https://api.cal.com/v1/slots?apiKey={settings.CAL_API_KEY}&eventTypeId={settings.CAL_EVENT_TYPE_ID}"
                start_date = datetime.date.today().isoformat()
                end_date = (datetime.date.today() + datetime.timedelta(days=14)).isoformat()
                response = httpx.get(f"{url}&startTime={start_date}T00:00:00Z&endTime={end_date}T23:59:59Z", timeout=5.0)
                if response.status_code == 200:
                    slots_data = response.json().get("slots", {})
                    slots = []
                    for date, day_slots in slots_data.items():
                        for slot in day_slots:
                            dt_utc = datetime.datetime.fromisoformat(slot["time"].replace("Z", "+00:00"))
                            dt_kolkata = dt_utc.astimezone(kolkata_tz)
                            
                            # Filter out past slots
                            if dt_kolkata <= now_kolkata:
                                continue
                                
                            # Filter out occupied slots
                            end_kolkata = dt_kolkata + datetime.timedelta(minutes=30)
                            is_occupied = False
                            for b_start, b_end in booked_intervals:
                                if dt_kolkata < b_end and end_kolkata > b_start:
                                    is_occupied = True
                                    break
                            
                            if not is_occupied:
                                slots.append({
                                    "start": dt_kolkata.isoformat(),
                                    "end": end_kolkata.isoformat(),
                                    "formatted": dt_kolkata.strftime("%A, %b %d at %I:%M %p (IST)")
                                })
                    if slots:
                        return slots
            except Exception as e:
                print(f"Cal.com fetch failed, using fallback: {e}")

        base_date = datetime.date.today()
        if date_str:
            try:
                base_date = datetime.date.fromisoformat(date_str)
            except ValueError:
                pass

        slots = []
        days_to_check = 1 if date_str else 14  # Show 14 workdays
        current_day = base_date
        max_days_scanned = 0
        times = ["09:00", "10:00", "11:00", "12:00", "14:00", "15:00", "16:00", "17:00"]

        while max_days_scanned < (30 if not date_str else 1):
            if not date_str and len(slots) >= (days_to_check * len(times)):
                break
                
            max_days_scanned += 1
            if current_day.weekday() in (5, 6):
                current_day += datetime.timedelta(days=1)
                continue
                
            for t in times:
                hr, mn = map(int, t.split(":"))
                start_dt = datetime.datetime.combine(current_day, datetime.time(hr, mn))
                start_dt = start_dt.replace(tzinfo=kolkata_tz)
                
                # Filter out past slots
                if start_dt <= now_kolkata:
                    continue
                    
                end_dt = start_dt + datetime.timedelta(minutes=30)
                
                # Filter out occupied slots
                is_occupied = False
                for b_start, b_end in booked_intervals:
                    if start_dt < b_end and end_dt > b_start:
                        is_occupied = True
                        break
                
                if not is_occupied:
                    slots.append({
                        "start": start_dt.isoformat(),
                        "end": end_dt.isoformat(),
                        "formatted": start_dt.strftime("%A, %b %d at %I:%M %p (IST)")
                    })
            current_day += datetime.timedelta(days=1)

        return slots

    async def book_meeting(self, name: str, email: str, start_time: str, end_time: str, title: str = None) -> Dict[str, Any]:
        """
        Books a meeting. If Cal.com or Google Calendar is configured, updates them.
        Always saves locally in calendar_db.json.
        Prevents double bookings.
        """
        kolkata_tz = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
        try:
            start_dt = datetime.datetime.fromisoformat(start_time.replace("Z", "+00:00")).astimezone(kolkata_tz)
            end_dt = datetime.datetime.fromisoformat(end_time.replace("Z", "+00:00")).astimezone(kolkata_tz)
        except Exception:
            start_dt = datetime.datetime.fromisoformat(start_time).replace(tzinfo=kolkata_tz)
            end_dt = datetime.datetime.fromisoformat(end_time).replace(tzinfo=kolkata_tz)

        # Check for conflicts with existing bookings
        existing_bookings = self.get_booked_slots()
        for booking in existing_bookings:
            try:
                existing_start = datetime.datetime.fromisoformat(booking["start"].replace("Z", "+00:00")).astimezone(kolkata_tz)
                existing_end = datetime.datetime.fromisoformat(booking["end"].replace("Z", "+00:00")).astimezone(kolkata_tz)

                # Check if time slots overlap
                if (start_dt < existing_end and end_dt > existing_start):
                    raise Exception(f"Time slot already booked. Please choose another time.")
            except KeyError:
                continue

        booking_id = f"book_{int(datetime.datetime.now().timestamp())}"
        
        booking_result = {
            "success": True,
            "booking_id": booking_id,
            "name": name,
            "email": email,
            "title": title or "Interview",
            "start": start_time,
            "end": end_time,
            "formatted_time": start_dt.strftime("%A, %b %d at %I:%M %p (IST)"),
            "provider": "mock"
        }

        booked_via_cal = False
        if settings.CAL_API_KEY and settings.CAL_EVENT_TYPE_ID:
            try:
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
                        booked_via_cal = True
            except Exception as e:
                print(f"Cal.com booking request failed: {e}")

        if not booked_via_cal and settings.GOOGLE_CALENDAR_ID and os.path.exists("google_credentials.json"):
            try:
                print(f"[GOOGLE CAL] Attempting to book with Google Calendar API")
                from google.oauth2 import service_account
                from googleapiclient.discovery import build
                import asyncio

                SCOPES = ['https://www.googleapis.com/auth/calendar']
                creds = service_account.Credentials.from_service_account_file(
                    'google_credentials.json', scopes=SCOPES
                )
                service = build('calendar', 'v3', credentials=creds)

                event = {
                    'summary': title or f'Interview with {name}',
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
                        {'email': email}
                    ],
                }

                print(f"[GOOGLE CAL] Event payload: {event}")

                # Run the synchronous Google API call in a thread pool to avoid blocking
                loop = asyncio.get_event_loop()
                created_event = await loop.run_in_executor(
                    None,
                    lambda: service.events().insert(
                        calendarId=settings.GOOGLE_CALENDAR_ID, body=event
                    ).execute()
                )

                print(f"[GOOGLE CAL] Successfully created event: {created_event.get('id')}")

                booking_result["provider"] = "google_calendar"
                booking_result["booking_id"] = created_event.get("id")
                booking_result["web_link"] = created_event.get("htmlLink")
            except Exception as e:
                import traceback
                print(f"[GOOGLE CAL ERROR] Google Calendar booking failed: {e}")
                print(f"[GOOGLE CAL ERROR] Traceback: {traceback.format_exc()}")

        self.save_booking_local(booking_result)
        return booking_result

calendar_service = CalendarService()
