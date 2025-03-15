from flask import Flask, request, jsonify
from flask_cors import CORS
import mongoengine as db
from os import environ
import os

app = Flask(__name__)

CORS(app)

db.connect(host=os.getenv('MONGO_URI')) # Set this in your .env file

class Seat(db.Document): # tell flask what are the fields in your database
    eventID = db.StringField(required = True)
    seatNo = db.IntField(required = True)
    category = db.StringField()
    price = db.FloatField()
    status = db.StringField()

    #ensure eventID, seatNo pair is unique
    meta = {
        'indexes': [
            {'fields': ['eventID', 'seatNo'], 'unique': True}  # Enforce uniqueness
        ]
    }

    def to_json(self):
        return {
            "eventID": self.eventID,
            "seatNo": self.seatNo,
            "category": self.category,
            "price": self.price,
            "status": self.status
        }

@app.route('/event/<string:eventID>/<int:seatNo>', methods=['PUT'])
def update_seat(eventID, seatNo):
    '''update seat status'''
    seat = Seat.objects(eventID=eventID, seatNo=seatNo).first()

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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002, debug=True)