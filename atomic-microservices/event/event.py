from flask import Flask, request, jsonify
from flask_cors import CORS
import mongoengine as db
from datetime import datetime
from os import environ
import os

app = Flask(__name__)

CORS(app)

db.connect(host=os.getenv('MONGO_URI')) # Set this in your .env file

class Event(db.Document): # tell flask what are the fields in your database
    eventID = db.StringField(primary_key = True)
    eventName = db.StringField()
    venue = db.StringField()
    description = db.StringField()
    totalSeats = db.IntField()

    def to_json(self):
        return {
            "eventID": self.eventID,
            "eventName": self.eventName,
            "venue": self.venue,
            "description": self.description,
            "totalSeats": self.totalSeats,
        }


class EventDate(db.Document): # tell flask what are the fields in your database
    # eventID = db.StringField(required=True)  # Links to Event
    event = db.ReferenceField('Event', required=True, reverse_delete_rule=db.CASCADE)  # Link to Event
    eventDateTime = db.DateTimeField(required=True)
    availableSeats = db.IntField()

    meta = {
        'indexes': [
            {'fields': ['event', 'eventDateTime'], 'unique': True}  # Enforce uniqueness
        ]
    }

    def to_json(self):
        return {
            "event": self.event,
            "eventDateTime": self.eventDateTime.isoformat() if self.eventDateTime else None,
            "availableSeats": self.availableSeats
        }

@app.route("/event")
def get_all_events():
    events = Event.objects()  # Fetch all events

    if events:
        event_data = []
        
        for event in events:
            event_dates = EventDate.objects(event=event)  # Get dates for each event
            
            event_data.append({
                "eventID": event.eventID,
                "eventName": event.eventName,
                "venue": event.venue,
                "description": event.description,
                "totalSeats": event.totalSeats,
                "dates": [date.to_json() for date in event_dates]  # Convert event dates to JSON
            })
        
        return jsonify(
            {
                "code": 200,
                "data": {
                    "events": event_data
                }
            }
        )

    return jsonify(
        {
            "code": 404,
            "message": "No events found."
        }
    ), 404

@app.route("/event/<string:eventID>")
def select_event(eventID):
    '''return details of selected event'''
    event = Event.objects(eventID=eventID).first()

    if not event:
        return jsonify(
            {
                "code": 404,
                "message": f"Event with eventID {eventID} not found."
            }
        ), 404

    # Fetch associated event dates
    event_dates = EventDate.objects(event=event)

    return jsonify(
        {
            "code": 200,
            "data": {
                "eventID": event.eventID,
                "eventName": event.eventName,
                "venue": event.venue,
                "description": event.description,
                "totalSeats": event.totalSeats,
                "dates": [date.to_json() for date in event_dates]  # Convert dates to JSON
            }
        }
    )

@app.route("/event/<string:eventID>/<string:eventDateTime>")
def select_event_date(eventID, eventDateTime):
    '''get eventDate, shows number of available seats, allows you to book a seat etc'''
    # Convert eventDateTime string to datetime object
    try:
        event_date_obj = datetime.fromisoformat(eventDateTime)
    except ValueError:
        return jsonify(
            {
                "code": 400,
                "message": "Invalid date format. Use ISO format: YYYY-MM-DDTHH:MM:SS"
            }
        ), 400

    # Find the Event document
    event = Event.objects(eventID=eventID).first()
    if not event:
        return jsonify(
            {
                "code": 404,
                "message": f"Event with eventID {eventID} not found."
            }
        ), 404

    # Find the specific EventDate
    event_date = EventDate.objects(event=event, eventDateTime=event_date_obj).first()
    if not event_date:
        return jsonify(
            {
                "code": 404,
                "message": f"No event date found for eventID {eventID} on {eventDateTime}."
            }
        ), 404

    return jsonify(
        {
            "code": 200,
            "data": event_date.to_json()
        }
    )



@app.route("/event/<string:eventID>/<string:eventDateTime>", methods = ["PUT"])
def update_event(eventID):
    event = Event.objects(eventID=eventID).first()

    if not event:
        return jsonify({"code": 404, "message": "Event not found."}), 404
    
    # Get JSON data from request body
    data = request.get_json()

    # Validate input
    if "availableSeats" not in data:
        return jsonify({"code": 400, "message": "Missing 'availableSeats' field."}), 400

    if not isinstance(data["availableSeats"], int) or data["availableSeats"] < 0:
        return jsonify({
            "code": 400,
            "data": {"availableSeats": data["availableSeats"]},
            "message": "Number of available seats cannot be negative."
        }), 400

    # Update available seats
    event.availableSeats = data["availableSeats"]
    event.save()

    # Return updated event
    return jsonify({"code": 200, "data": event.to_json()}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)



# @app.route("/event/<string:eventID>")
# def get_event(eventID):
#     '''return details of selected event'''
#     event = Event.objects(eventID=eventID).first()  # MongoEngine query

#     if event:
#         return jsonify(
#             {
#                 "code": 200,
#                 "data": event.to_json()  # Use `to_json()` method of event class
#             }
#         )
    
#     return jsonify(
#         {
#             "code": 404,
#             "message": "Event not found."
#         }
#     ), 404