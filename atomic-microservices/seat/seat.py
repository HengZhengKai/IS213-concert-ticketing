from flask import Flask, request, jsonify
from flask_cors import CORS
import mongoengine as db
from os import environ
import os
from datetime import datetime
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

class Seat(db.Document):
    eventID = db.StringField(required=True)
    eventDateID = db.StringField()
    eventDateTime = db.DateTimeField(required=True)
    seatNo = db.IntField(required=True)
    category = db.StringField()
    price = db.FloatField()
    status = db.StringField()
    
    # Make eventDateTime optional or remove it
    
    meta = {
        'collection': 'Seat',  # Specify exact collection name
        'indexes': [
            {'fields': ['eventDateID', 'eventDateTime', 'seatNo'], 'unique': True}
        ]
    }

    def to_json(self):
        return {
            "eventID": self.eventID,
            "eventDateID": self.eventDateID,
            "eventDateTime": self.eventDateTime,
            "seatNo": self.seatNo,
            "category": self.category,
            "price": self.price,
            "status": self.status
        }

#Route 1
@app.route('/seat', methods=['PUT'])
def update_seat():
    '''Update seat status'''
    # Get the request data (seat status and other necessary details)
    data = request.get_json()
    required_fields = ["eventID", "eventDateTime", "seatNo", "status"]
    
    # Check if all necessary fields are present
    if 'status' not in data:
        return jsonify({"code": 400, "message": "Missing status."}), 400

    if not all(field in data for field in required_fields):
        return jsonify({"code": 400, "message": "Missing required fields."}), 400
    
    seat = Seat.objects(eventID=data['eventID'], eventDateTime=data['eventDateTime'], seatNo=data['seatNo']).first()

    # Check if the seat is already reserved
    # if data["status"] == seat.status:
    #     return jsonify({
    #         "code": 409,
    #         "data": {"eventID": data['eventID'], "seatNo": data['seatNo']},
    #         "message": f"Seat already {seat.status}."
    #     }), 409
    
    category = seat.category
    price = seat.price

    # Update the seat status
    seat.update(status=data["status"])

    # Return a success response
    return jsonify({
        "code": 200,
        "data": {
            "eventID": data['eventID'],
            "eventDateID": data['eventDateID'],
            "eventDateTime": data['eventDateTime'],
            "seatNo": data['seatNo'],
            "category": data['category'],
            "price": data['price'],
            "status": data["status"]
        }
    }), 200

#displays the seats in json 
#can view the json format of data via http://localhost:5002/seats
@app.route('/seats', methods=['GET'])
def get_all_seats():
    try:
        seats = Seat.objects()
        if not seats:
            return jsonify(
                {
                    "code": 404,
                    "message": f"No seats found."
                }
            ), 404

        return jsonify({
            "code": 200,
            "data": {
                "seats": [seat.to_json() for seat in seats]
            }
        })
    except Exception as e:
        return jsonify({
            "code": 500,
            "message": f"Error retrieving seats: {str(e)}"
        }), 500

@app.route('/seats/<string:eventID>/<path:eventDateTime>')
def get_seats_for_event(eventID, eventDateTime):
    try:
        # Fix for URL-encoded '+' -> ' ' issue
        eventDateTime = eventDateTime.replace(' ', '+')

        dt = datetime.fromisoformat(eventDateTime)
        dt = dt.replace(microsecond=0)

        seats = Seat.objects(eventID=eventID, eventDateTime=dt)
        if not seats:
            return jsonify(
                {
                    "code": 404,
                    "message": f"No seats found."
                }
            ), 404


        return jsonify({
            "code": 200,
            "data": [seat.to_json() for seat in seats]
        })
    except Exception as e:
        return jsonify({
            "code": 500,
            "message": f"Error retrieving seats: {str(e)}"
        }), 500




if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002, debug=True)