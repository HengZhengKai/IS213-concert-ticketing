from flask import Flask, request, jsonify
from flask_cors import CORS
import mongoengine as db
from datetime import datetime
from os import environ
import os
from flasgger import Swagger
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
swagger = Swagger(app)

CORS(app)

# db.connect(host=os.getenv('MONGO_URI')) # Set this in your .env file
# MongoDB Atlas connection string
# Format: mongodb+srv://breannong2023:ERyiUfOe90qOnf4Y@ticketing-db.qqamb.mongodb.net/test?retryWrites=true&w=majority
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/event_service')

try:
    # Connect to MongoDB Atlas
    logger.info(f"Connecting to MongoDB at: {MONGO_URI.split('@')[1] if '@' in MONGO_URI else MONGO_URI}")
    db.connect(host=MONGO_URI)
    logger.info("Connected to MongoDB successfully")
except Exception as e:
    logger.error(f"Failed to connect to MongoDB: {e}")

class Event(db.Document): # tell flask what are the fields in your database
    eventID = db.StringField(primary_key = True)
    eventName = db.StringField(required=True)
    venue = db.StringField(required=True)
    description = db.StringField()
    totalSeats = db.IntField(required=True)

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
            "event": self.event.eventID,
            "eventDateTime": self.eventDateTime.isoformat() if self.eventDateTime else None,
            "availableSeats": self.availableSeats
        }

@app.route("/event")
def get_all_events():
    """
    Get all events
    ---
    responses:
        200:
            description: List of all events
        404:
            description: No events found
    """
    try:
        events = Event.objects()  # Fetch all events
        logger.info(f"Found {len(events)} events")

        if events:
            event_data = []
            
            for event in events:
                event_dates = EventDate.objects(event=event)  # Get dates for each event
                
                # Process each event
                event_info = {
                    "eventID": event.eventID,
                    "eventName": event.eventName,
                    "venue": event.venue,
                    "description": event.description,
                    "totalSeats": event.totalSeats,
                    "dates": []
                }
                
                # Add date information
                for date in event_dates:
                    event_info["dates"].append({
                        "eventDateTime": date.eventDateTime.isoformat() if date.eventDateTime else None,
                        "availableSeats": date.availableSeats
                    })
                
                event_data.append(event_info)
            
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
    except Exception as e:
        logger.error(f"Error in get_all_events: {e}")
        return jsonify(
            {
                "code": 500,
                "message": f"Internal server error: {str(e)}"
            }
        ), 500

@app.route("/event/<string:eventID>")
def select_event(eventID):
    """
    Get details of a specific event
    ---
    parameters:
        - name: eventID
        in: path
        type: string
        required: true
        description: The ID of the event
    responses:
        200:
            description: Event details
        404:
            description: Event not found
    """
    
    try:
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
    
    except Exception as e:
        logger.error(f"Error in select_event: {e}")
        return jsonify(
            {
                "code": 500,
                "message": f"Internal server error: {str(e)}"
            }
        ), 500


@app.route("/event/<string:eventID>/<string:eventDateTime>")
def select_event_date(eventID, eventDateTime):
    """
    Get details of a specific event date
    ---
    parameters:
        - name: eventID
            in: path
            type: string
            required: true
            description: The ID of the event
        - name: eventDateTime
            in: path
            type: string
            required: true
            description: The date and time of the event
        responses:
        200:
            description: Event date details
        400:
            description: Invalid date format
        404:
            description: Event or event date not found
    """
    # Convert eventDateTime string to datetime object
    try:
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
    except Exception as e:
        logger.error(f"Error in select_event_date: {e}")
        return jsonify(
            {
                "code": 500,
                "message": f"Internal server error: {str(e)}"
            }
        ), 500

@app.route("/event/<string:eventID>/<string:eventDateTime>", methods = ["PUT"])
def update_event(eventID, eventDateTime):
    """
    Update available seats for a specific event date
    ---
    parameters:
        - name: eventID
            in: path
            type: string
            required: true
            description: The ID of the event
        - name: eventDateTime
            in: path
            type: string
            required: true
            description: The date and time of the event
        - name: body
            in: body
            required: true
            schema:
            type: object
            properties:
                availableSeats:
                type: integer
                description: The number of available seats for this event date
        responses:
        200:
            description: Successfully updated available seats
        400:
            description: Bad request (Invalid or missing parameters)
        404:
            description: Event or event date not found
    """
    try:
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

        # Get JSON data from request body
        data = request.get_json()

        # Validate input
        if "availableSeats" not in data:
            return jsonify(
                {
                    "code": 400,
                    "message": "Missing 'availableSeats' field."
                }
            ), 400

        if not isinstance(data["availableSeats"], int) or data["availableSeats"] < 0:
            return jsonify(
                {
                    "code": 400,
                    "data": {"availableSeats": data["availableSeats"]},
                    "message": "Number of available seats cannot be negative."
                }
            ), 400

        # Update available seats
        event_date.availableSeats = data["availableSeats"]
        event_date.save()

        # Return updated event date
        return jsonify(
            {
                "code": 200,
                "data": event_date.to_json()
            }
        )
    except Exception as e:
        logger.error(f"Error in update_event_seats: {e}")
        return jsonify(
            {
                "code": 500,
                "message": f"Internal server error: {str(e)}"
            }
        ), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)

# # @app.route("/event/<string:eventID>")
# # def get_event(eventID):
# #     '''return details of selected event'''
# #     event = Event.objects(eventID=eventID).first()  # MongoEngine query

# #     if event:
# #         return jsonify(
# #             {
# #                 "code": 200,
# #                 "data": event.to_json()  # Use `to_json()` method of event class
# #             }
# #         )
    
# #     return jsonify(
# #         {
# #             "code": 404,
# #             "message": "Event not found."
# #         }
# #     ), 404