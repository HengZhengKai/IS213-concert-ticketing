from flask import Flask, request, jsonify
from flask_cors import CORS
import mongoengine as db
from datetime import datetime
from os import environ
import os

app = Flask(__name__)

CORS(app)

db.connect(host=os.getenv('MONGO_URI')) # Set this in your .env file

class Waitlist(db.Document): # tell flask what are the fields in your database
    eventID = db.StringField(required = True)
    userID = db.StringField(required = True)
    waitlistDate = db.DateTimeField()

    #ensure eventID, userID pair is unique
    meta = {
        'indexes': [
            {'fields': ['eventID', 'userID'], 'unique': True}  # Enforce uniqueness
        ]
    }

    def to_json(self):
        return {
            "eventID": self.eventID,
            "userID": self.userID,
            "waitlistDate": self.waitlistDate.isoformat() if self.waitlistDate else None
        }

@app.route("/event/<string:eventID>/waitlist")
def get_waitlist(eventID):
    event_waitlist = Waitlist.objects(eventID=eventID).only("userID", "waitlistDate")
    
    if not event_waitlist:
        return jsonify({"code": 404, "message": "No users on waitlist."}), 404
    
    return jsonify({
        "status": 200,
        "eventID": eventID,
        "waitlist": [{"userID": w.userID, "waitlistDate": w.waitlistDate.isoformat()} for w in event_waitlist]
    }), 200

@app.route('/event/<string:eventID>/waitlist', methods=['POST'])
def add_to_waitlist(eventID):
    data = request.get_json()
    if not data or "userID" not in data:
        return jsonify({"code": 400, "message": "Missing userID in request body."}), 400
    
    userID = data["userID"]
    
    # Check if user is already on waitlist
    if Waitlist.objects(eventID=eventID, userID=userID).first():
        return jsonify({
            "code": 409,
            "data": {"eventID": eventID, "userID": userID},
            "message": "User already in waitlist."
        }), 409
    
    waitlist = Waitlist(eventID=eventID, userID=userID, waitlistDate=datetime.now())
    waitlist.save()
    
    return jsonify({
        "code": 201,
        "data": {
            "userID": userID,
            "waitlistDate": waitlist.waitlistDate.strftime('%Y-%m-%d %H:%M:%S')
        }
    }), 201

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5003, debug=True)