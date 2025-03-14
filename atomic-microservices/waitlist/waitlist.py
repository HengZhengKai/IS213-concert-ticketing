from flask import Flask, request, jsonify
from flask_cors import CORS
import mongoengine as db
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
