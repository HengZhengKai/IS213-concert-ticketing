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

@app.route('/transaction', methods=['POST'])
def create_transaction():
    data = request.get_json()
    required_fields = ["transactionID", "type", "userID", "ticketID", "chargeID", "amount"]
    
    if not all(field in data for field in required_fields):
        return jsonify({"code": 400, "message": "Missing required fields."}), 400
    
    if data["type"] not in ["purchase", "refund"]:
        return jsonify({"code": 400, "message": "Invalid transaction type."}), 400
    
    if Transaction.objects(transactionID=data["transactionID"]).first():
        return jsonify({"code": 409, "message": "Transaction ID already exists."}), 409
    
    transaction = Transaction(
        transactionID=data["transactionID"],
        type=data["type"],
        userID=data["userID"],
        ticketID=data["ticketID"],
        chargeID=data["chargeID"],
        amount=data["amount"],
        transactionDate=datetime.now()
    )
    transaction.save()
    
    return jsonify({
        "code": 201,
        "data": {
            "transactionID": transaction.transactionID,
            "type": transaction.type,
            "userID": transaction.userID,
            "ticketID": transaction.ticketID,
            "chargeID": transaction.chargeID,
            "amount": transaction.amount,
            "transactionDate": transaction.transactionDate.strftime('%Y-%m-%d %H:%M:%S')
        }
    }), 201

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5005, debug=True)