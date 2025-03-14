from flask import Flask, request, jsonify
from flask_cors import CORS
import mongoengine as db
from os import environ
import os

app = Flask(__name__)

CORS(app)

db.connect(host=os.getenv('MONGO_URI')) # Set this in your .env file

class Transaction(db.Document): # tell flask what are the fields in your database
    transactionID = db.StringField(primary_key = True)
    type = db.StringField(choices=["purchase", "refund"], required=True)  # Restrict values
    userID = db.StringField()
    ticketID = db.StringField()
    chargeID = db.StringField()
    amount = db.FloatField(min_value=0.0)
    transactionDate = db.DateTimeField()

    def to_json(self):
        return {
           "transactionID": self.transactionID,
            "type": self.type,
            "userID": self.userID,
            "ticketID": self.ticketID,
            "chargeID": self.chargeID,
            "amount": self.amount,
            "transactionDate": self.transactionDate.isoformat() if self.transactionDate else None
        }
