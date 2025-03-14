from flask import Flask, request, jsonify
from flask_cors import CORS
import mongoengine as db
from os import environ
import os

app = Flask(__name__)

CORS(app)

db.connect(host=os.getenv('MONGO_URI')) # Set this in your .env file

class Event(db.Document): # tell flask what are the fields in your database
    eventID = db.StringField(primary_key = True)
    eventName = db.StringField()
    eventDate = db.DateTimeField()
    venue = db.StringField()
    desc = db.StringField()
    totalSeats = db.IntField()
    availableSeats = db.IntField()

    def to_json(self):
        return {
            "eventID": self.eventID,
            "eventName": self.eventName,
            "eventDate": self.eventDate.isoformat() if self.eventDate else None,
            "venue": self.venue,
            "desc": self.desc,
            "totalSeats": self.totalSeats,
            "availableSeats": self.availableSeats
        }
    
@app.route("/event/<string:eventID>")
def get_event(eventID):
    '''return details of selected event'''
    event = Event.objects(eventID=eventID).first()  # MongoEngine query

    if event:
        return jsonify(
            {
                "code": 200,
                "data": event.to_json()  # Use `to_json()` method of event class
            }
        )
    
    return jsonify(
        {
            "code": 404,
            "message": "Event not found."
        }
    ), 404

@app.route("/event/<string:eventID>", methods = ["PUT"])
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
    app.run(host='0.0.0.0', port=5000, debug=True)