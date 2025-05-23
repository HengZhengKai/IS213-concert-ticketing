from flask import Flask, request, jsonify
from flask_cors import CORS
import mongoengine as db
from datetime import datetime
import pytz
from os import environ
import os
import urllib.parse
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

CORS(app)

# MongoDB connection details from environment variables
username = os.getenv("MONGO_USERNAME")
password = urllib.parse.quote_plus(os.getenv("MONGO_PASSWORD"))
cluster = os.getenv("MONGO_CLUSTER")
database = os.getenv("MONGO_DATABASE")

# Use the MONGO_URI directly from environment if available, otherwise construct it
MONGO_URI = os.getenv("MONGO_URI") or f"mongodb+srv://{username}:{password}@{cluster}/{database}?retryWrites=true&w=majority"

try:
    # Connect to MongoDB Atlas
    logger.info(f"Connecting to MongoDB at: {cluster}")
    db.connect(host=MONGO_URI, alias='default')
    logger.info("Connected to MongoDB successfully")
except Exception as e:
    logger.error(f"Failed to connect to MongoDB: {e}")
    raise  # Re-raise the exception to prevent the service from starting with a bad connection

class Event(db.Document): # tell flask what are the fields in your database
    eventID = db.StringField(required = True)
    eventName = db.StringField(required=True)
    imageBase64 = db.StringField()
    venue = db.StringField(required=True)
    description = db.StringField()
    totalSeats = db.IntField(required=True)

    meta = {'collection': 'Event'} 

    def to_json(self):
        return {
            "eventID": self.eventID,
            "eventName": self.eventName,
            "imageBase64": self.imageBase64,
            "venue": self.venue,
            "description": self.description,
            "totalSeats": self.totalSeats,
        }

class EventDate(db.Document): # tell flask what are the fields in your database
    # eventID = db.StringField(required=True)  # Links to Event
    event = db.ReferenceField('Event', required=True, dbref=True, reverse_delete_rule=db.CASCADE)  # Link to Event
    eventDateID = db.StringField()
    eventID = db.StringField()
    eventDateTime = db.DateTimeField(required=True)
    availableSeats = db.IntField()

    meta = {
        'collection': 'EventDate', 
        'indexes': [
            {'fields': ['event', 'eventDateID'], 'unique': True},
        ]
    }

    def to_json(self):
        return {
            "eventDateID": self.eventDateID,
            "eventDateTime": self.eventDateTime.isoformat() if self.eventDateTime else None,
            "availableSeats": self.availableSeats
        }

    def save(self, *args, **kwargs):
        # Ensure eventID is set when saving
        if self.event and not self.eventID:
            self.eventID = self.event.eventID
        super().save(*args, **kwargs)

# Verify database connection after class definitions
try:
    if Event.objects.count() >= 0:
        logger.info("Successfully verified database connection by querying events")
    else:
        logger.warning("Database connection verified but no events found")
except Exception as e:
    logger.error(f"Failed to verify database connection: {e}")
    raise

#Route 1
@app.route("/event")
def get_all_events():
    try:
        events = Event.objects()  # Fetch all events
        logger.info(f"Found {len(events)} events")

        if events:
            event_data = []
            
            for event in events:
                logger.info(f"Processing Event: {event.eventID}, Name: {event.eventName}")

                # Retrieve event dates by using the reference field
                event_dates = EventDate.objects(eventID=event.eventID)  # Corrected query
                
                # Log the number of dates for this event
                logger.info(f"Dates for {event.eventID}: {len(event_dates)}")
                
                # Process each event
                event_info = {
                    "eventID": event.eventID,
                    "eventName": event.eventName,
                    "imageBase64": event.imageBase64,
                    "venue": event.venue,
                    "description": event.description,
                    "totalSeats": event.totalSeats,
                    "dates": []
                }
                
                # Add date information
                for date in event_dates:
                    sgt_time = date.eventDateTime.replace(tzinfo=pytz.UTC).astimezone(pytz.timezone('Asia/Singapore'))
                    event_info["dates"].append({
                        "eventDateID": date.eventDateID,
                        "eventDateTime": sgt_time.isoformat(),
                        "availableSeats": date.availableSeats or 0,
                        "formattedDateTime": sgt_time.strftime("%d %B %Y at %I:%M %p SGT")
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

#Route 2
@app.route("/event/<string:eventID>")
def select_event(eventID):
    try:
        event = Event.objects(eventID=eventID).first()

        if not event:
            return jsonify({"code": 404, "message": "Event not found"}), 404
        
        event_id = event.eventID
        event_dates = EventDate.objects(eventID=event_id)

        return jsonify(
            {
                "code": 200,
                "data": {
                    "eventID": event.eventID,
                    "eventName": event.eventName,
                    "imageBase64": event.imageBase64,
                    "venue": event.venue,
                    "description": event.description,
                    "totalSeats": event.totalSeats,
                    "dates": [date.to_json() for date in event_dates]
                }
            }
        )
    except Exception as e:
        return jsonify({"code": 500, "message": str(e)}), 500
    

#Route 3
@app.route("/event/<string:eventID>/<string:eventDateTime>")
def select_event_date(eventID, eventDateTime):
    try:        
        # Find the Event document
        event = Event.objects(eventID=eventID).first()
        if not event:
            logger.warning(f"Event with eventID {eventID} not found")
            return jsonify(
                {
                    "code": 404,
                    "message": f"Event with eventID {eventID} not found."
                }
            ), 404

        # Log all event dates for this event
        all_dates = EventDate.objects(eventID=eventID)
        logger.info(f"Found {len(all_dates)} dates for event {eventID}")
        for date in all_dates:
            logger.info(f"Available date: {date.eventDateTime.isoformat() if date.eventDateTime else None}")

        # Parse the input datetime string
        try:
            search_datetime = datetime.fromisoformat(eventDateTime.replace('Z', '+00:00'))
        except ValueError as e:
            logger.error(f"Error parsing datetime: {e}")
            return jsonify(
                {
                    "code": 400,
                    "message": f"Invalid datetime format: {eventDateTime}"
                }
            ), 400

        # Find the specific EventDate
        event_date = EventDate.objects(eventID=eventID, eventDateTime=search_datetime).first()

        if not event_date:
            logger.warning(f"No event date found for eventID {eventID} on {search_datetime.isoformat()}")
            return jsonify(
                {
                    "code": 404,
                    "message": f"No event date found for eventID {eventID} on {eventDateTime}.",
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

#Route 4
@app.route("/event/<string:eventID>/<string:eventDateTime>", methods = ["PUT"])
def update_event(eventID, eventDateTime):
    try:        
        # Find the Event document
        event = Event.objects(eventID=eventID).first()
        if not event:
            logger.warning(f"Event with eventID {eventID} not found")
            return jsonify(
                {
                    "code": 404,
                    "message": f"Event with eventID {eventID} not found."
                }
            ), 404

        # Parse the input datetime string
        try:
            search_datetime = datetime.fromisoformat(eventDateTime.replace('Z', '+00:00'))
            logger.info(f"Parsed search datetime: {search_datetime.isoformat()}")
        except ValueError as e:
            logger.error(f"Error parsing datetime: {e}")
            return jsonify(
                {
                    "code": 400,
                    "message": f"Invalid datetime format: {eventDateTime}"
                }
            ), 400

        # Find the specific EventDate
        event_date = EventDate.objects(eventID=eventID, eventDateTime=search_datetime).first()

        if not event_date:
            logger.warning(f"No event date found for eventID {eventID} on {search_datetime.isoformat()}")
            return jsonify(
                {
                    "code": 404,
                    "message": f"No event date found for eventID {eventID} on {eventDateTime}.",
                }
            ), 404

        # Get JSON data from request body
        data = request.get_json()
        logger.info(f"Received update data: {data}")

        # Validate input
        if "availableSeats" not in data:
            logger.warning("Missing 'availableSeats' field in request")
            return jsonify(
                {
                    "code": 400,
                    "message": "Missing 'availableSeats' field."
                }
            ), 400

        if not isinstance(data["availableSeats"], int):
            logger.warning(f"Invalid availableSeats type: {type(data['availableSeats'])}")
            return jsonify(
                {
                    "code": 400,
                    "message": "availableSeats must be an integer."
                }
            ), 400

        # Update available seats
        event_date.availableSeats = data["availableSeats"]
        event_date.event = event

        try:
            event_date.save()
            logger.info(f"Successfully updated event date with new available seats: {data['availableSeats']}")
        except Exception as e:
            logger.error(f"Failed to save event date update: {e}")
            return jsonify(
                {
                    "code": 500,
                    "message": f"Failed to save event date update: {str(e)}"
                }
            ), 500

        # Return updated event date
        return jsonify(
            {
                "code": 200,
                "data": event_date.to_json()
            }
        )
    except Exception as e:
        logger.error(f"Error in update_event: {e}")
        return jsonify(
            {
                "code": 500,
                "message": f"Internal server error: {str(e)}"
            }
        ), 500
    
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)