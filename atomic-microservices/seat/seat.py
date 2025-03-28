from flask import Flask, request, jsonify
from flask_cors import CORS
import mongoengine as db
from os import environ
import os
from datetime import datetime
import urllib.parse
from flasgger import Swagger
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
swagger = Swagger(app)

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
    seatNo = db.IntField(required=True)
    category = db.StringField()
    price = db.FloatField()
    status = db.StringField()
    
    # Make eventDateTime optional or remove it
    eventDateTime = db.DateTimeField(required=False)
    
    meta = {
        'collection': 'Seat',  # Specify exact collection name
        'indexes': [
            {'fields': ['eventID', 'seatNo'], 'unique': True}
        ]
    }

    def to_json(self):
        return {
            "eventID": self.eventID,
            "eventDateTime": self.eventDateTime,
            "seatNo": self.seatNo,
            "category": self.category,
            "price": self.price,
            "status": self.status
        }

@app.route('/event/<string:eventID>/<string:eventDateTime>/<int:seatNo>', methods=['PUT'])
def update_seat(eventID, eventDateTime, seatNo):
    '''update seat status'''
    seat = Seat.objects(eventID=eventID, eventDateTime=eventDateTime, seatNo=seatNo).first()

    # Get the request data (seat status)
    data = request.get_json()

    # Check if the status field is in the request
    if 'status' not in data:
        return jsonify({"code": 400, "message": "Status field is required."}), 400
    
    # Check if the seat is already booked
    if data["status"] == seat.status:
        return jsonify({
            "code": 409,
            "data": {"eventID": eventID, "seatNo": seatNo},
            "message": f"Seat already {seat.status}."
        }), 409
    
    # Update the seat status
    seat.update(status=data["status"])

    # Return a success response
    return jsonify({
        "code": 200,
        "data": {
            "eventID": eventID,
            "seatNo": seatNo,
            "status": data["status"]
        }
    }), 200

#displays the seats in json 
#can view the json format of data via http://localhost:5002/seats
@app.route('/seats', methods=['GET'])
def get_all_seats():
    try:
        seats = Seat.objects()
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


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002, debug=True)