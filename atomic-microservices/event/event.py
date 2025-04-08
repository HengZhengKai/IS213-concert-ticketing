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

# Construct connection string
MONGO_URI = f"mongodb+srv://{username}:{password}@{cluster}/{database}?retryWrites=true&w=majority&authSource=admin"

try:
    # Connect to MongoDB Atlas
    logger.info(f"Connecting to MongoDB at: {cluster}")
    db.connect(host=MONGO_URI, alias='default')
    logger.info("Connected to MongoDB successfully")
except Exception as e:
    logger.error(f"Failed to connect to MongoDB: {e}")

class Event(db.Document): # tell flask what are the fields in your database
    eventID = db.StringField(primary_key = True)
    eventName = db.StringField(required=True)
    imageBase64 = db.StringField()
    venue = db.StringField(required=True)
    description = db.StringField()
    totalSeats = db.IntField(required=True)

    meta = {'collection': 'Event',
            'indexes': [
            {'fields': ['eventID'], 'unique': True}
        ]
    } 

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
    eventID = db.StringField()
    eventDateTime = db.DateTimeField(required=True)
    availableSeats = db.IntField()

    meta = {
        'collection': 'EventDate', 
        'indexes': [
            {'fields': ['event', 'eventDateTime'], 'unique': True},
            {'fields': ['eventID']}
        ]
    }

    def to_json(self):
        return {
            "event": self.event.eventID,
            "eventDateTime": self.eventDateTime.isoformat() if self.eventDateTime else None,
            "availableSeats": self.availableSeats
        }

    def save(self, *args, **kwargs):
        # Ensure eventID is set when saving
        if self.event and not self.eventID:
            self.eventID = self.event.eventID
        super().save(*args, **kwargs)

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

                #retrieve event dates by matching eventID in event microservice
                event_dates= EventDate.objects(eventID=event.eventID)
                
                # Log the number of dates for this event
                logger.info(f"Dates by ID for {event.eventID}: {len(event_dates)}")
                
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
                    # event_info["dates"].append({
                    #     "eventDateTime": date.eventDateTime.isoformat() if date.eventDateTime else None,
                    #     "availableSeats": date.availableSeats or 0
                    # })
                    if date.eventDateTime:
                        sgt_time = date.eventDateTime.replace(tzinfo=pytz.UTC).astimezone(pytz.timezone('Asia/Singapore'))
                        event_info["dates"].append({
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
                    "imageBase64": event.imageBase64,
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

#Route 3
@app.route("/event/<string:eventID>/<string:eventDateTime>")
def select_event_date(eventID, eventDateTime):
    # Convert eventDateTime string to datetime object
    try:
        try:
            decoded_dt = urllib.parse.unquote(eventDateTime)
            event_date_obj = datetime.fromisoformat(decoded_dt)
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

#Route 4
@app.route("/event/<string:eventID>/<string:eventDateTime>", methods = ["PUT"])
def update_event(eventID, eventDateTime):
    try:
        # Convert eventDateTime string to datetime object
        try:
            decoded_dt = urllib.parse.unquote(eventDateTime)
            event_date_obj = datetime.fromisoformat(decoded_dt)
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
    
# Add this to your Flask app temporarily to debug
@app.route("/debug")
def debug_db():
    try:
        db_info = {
            "database": db.connection.get_database().name,
            "collections": db.connection.get_database().list_collection_names(),
            "event_count": Event.objects.count()
        }
        return jsonify(db_info)
    except Exception as e:
        return jsonify({"error": str(e)})
    
@app.route("/detailed-diagnostic")
def detailed_diagnostic():
    """
    Comprehensive diagnostic route to investigate event and event date relationships
    """
    try:
        # Collect detailed diagnostic information
        diagnostic_info = {
            "total_events": Event.objects().count(),
            "total_event_dates": EventDate.objects().count(),
            "events": []
        }

        # Fetch all events with their dates
        events = Event.objects()
        
        for event in events:
            # Find all event dates for this event using different methods
            event_dates_by_ref = EventDate.objects(event=event)
            event_dates_by_id = EventDate.objects(eventID=event.eventID)
            
            event_info = {
                "event_details": {
                    "eventID": event.eventID,
                    "eventName": event.eventName,
                    "venue": event.venue
                },
                "dates_by_reference": [],
                "dates_by_id": []
            }
            
            # Log dates found by reference
            for date in event_dates_by_ref:
                event_info["dates_by_reference"].append({
                    "datetime": date.eventDateTime.isoformat() if date.eventDateTime else None,
                    "available_seats": date.availableSeats,
                    "event_ref_str": str(date.event)
                })
            
            # Log dates found by eventID
            for date in event_dates_by_id:
                event_info["dates_by_id"].append({
                    "datetime": date.eventDateTime.isoformat() if date.eventDateTime else None,
                    "available_seats": date.availableSeats
                })
            
            diagnostic_info["events"].append(event_info)
        
        return jsonify(diagnostic_info)
    
    except Exception as e:
        return jsonify({
            "error": str(e),
            "traceback": traceback.format_exc()
        }),

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)