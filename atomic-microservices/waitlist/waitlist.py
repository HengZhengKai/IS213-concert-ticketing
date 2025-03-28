from flask import Flask, request, jsonify
from flask_cors import CORS
import mongoengine as db
from datetime import datetime
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

class Waitlist(db.Document): # tell flask what are the fields in your database
    eventID = db.StringField(required = True)
    eventDateTime = db.DateTimeField(required=True)
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
            "eventDateTime": self.eventDateTime,
            "userID": self.userID,
            "waitlistDate": self.waitlistDate.isoformat() if self.waitlistDate else None
        }

@app.route("/event/<string:eventID>/<string:eventDateTime>/waitlist")
def get_waitlist(eventID, eventDateTime):
    '''get all users in waitlist'''
    event_waitlist = Waitlist.objects(eventID=eventID, eventDateTime=eventDateTime).only("userID", "waitlistDate")
    
    if not event_waitlist:
        return jsonify({"code": 404, "message": "No users on waitlist."}), 404
    
    return jsonify({
        "status": 200,
        "eventID": eventID,
        "waitlist": [{"userID": w.userID, "waitlistDate": w.waitlistDate.isoformat()} for w in event_waitlist]
    }), 200

@app.route('/event/<string:eventID>/<string:eventDateTime>/waitlist', methods=['POST'])
def add_to_waitlist(eventID, eventDateTime):
    data = request.get_json()
    if not data or "userID" not in data:
        return jsonify({"code": 400, "message": "Missing userID in request body."}), 400
    
    userID = data["userID"]
    
    # Check if user is already on waitlist
    if Waitlist.objects(eventID=eventID, eventDateTime=eventDateTime, userID=userID).first():
        return jsonify({
            "code": 409,
            "data": {"eventID": eventID, "userID": userID},
            "message": "User already in waitlist."
        }), 409
    
    waitlist = Waitlist(eventID=eventID, eventDateTime=eventDateTime, userID=userID, waitlistDate=datetime.now())
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