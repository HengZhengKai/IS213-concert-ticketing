from flask import Flask, jsonify, request
from flask_cors import CORS
#import stripe
import os
import logging
import urllib.parse
import mongoengine as db
from dotenv import load_dotenv
load_dotenv()
import requests

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

CORS(app)


# newpayment = "https://personal-5nnqipga.outsystemscloud.com/Stripe/rest/payments/newpayment"

# headers = {
#     "Content-Type": "application/json",
#     "Authorization": "Bearer sk_test_51R3vExQSvUjndICG0rAbAi8GNiUDAtQZhgOCHY1uSfnmPjSaZbhb51aCYhglY671WKvvb4H7RWEKklheuX0WCA0I00hTQYEDxm",  # testing key
# }

# data = {
#   "amount": 2000, #change to variable
#   "currency": "sgd", #change to variable
#   "payment_method": "pm_card_visa", #change to variable
#   "customer":"cus_S1J0TldFSJlleW", #change to variable
#   "confirm": True,
#   "off_session": True,
#   "automatic_payment_methods": {
#     "enabled": True,
#     "allow_redirects": "never"
#   }
# }

# response = requests.post(newpayment, json=data, headers=headers)
# print(response.status_code)
# print(response.json())


# username = os.getenv("MONGO_USERNAME")
# password = urllib.parse.quote_plus(os.getenv("MONGO_PASSWORD"))
# cluster = os.getenv("MONGO_CLUSTER")
# database = os.getenv("MONGO_DATABASE")

# # Construct connection string
# MONGO_URI = f"mongodb+srv://{username}:{password}@{cluster}/{database}?retryWrites=true&w=majority&authSource=admin"

# try:
#     # Connect to MongoDB Atlas
#     logger.info(f"Connecting to MongoDB at: {cluster}")
#     db.connect(host=MONGO_URI, alias='default')
#     logger.info("Connected to MongoDB successfully")
# except Exception as e:
#     logger.error(f"Failed to connect to MongoDB: {e}")

# class Payment(db.Document): # tell flask what are the fields in your database
#     eventID = db.StringField(primary_key = True)
#     eventName = db.StringField(required=True)
#     imageBase64 = db.StringField()
#     venue = db.StringField(required=True)
#     description = db.StringField()
#     totalSeats = db.IntField(required=True)

#     meta = {'collection': 'Event',
#             'indexes': [
#             {'fields': ['eventID'], 'unique': True}
#         ]
#     } 

#     def to_json(self):
#         return {
#             "eventID": self.eventID,
#             "eventName": self.eventName,
#             "imageBase64": self.imageBase64,
#             "venue": self.venue,
#             "description": self.description,
#             "totalSeats": self.totalSeats,
#         }

@app.route('/makepayment', methods=['POST'])
def make_payment():
    try:
        # Extracting data from request body
        req_data = request.get_json()
        stripe_key = os.getenv("STRIPE_SECRET_KEY")


        amount = req_data.get('amount')
        currency = req_data.get('currency', 'sgd')  # default to SGD
        payment_method = req_data.get('payment_method')
        customer = req_data.get('customer')

        # Check required fields
        if not all([amount, currency, payment_method, customer]):
            return jsonify({"error": "Missing required payment fields"}), 400

        newpayment_url = "https://personal-5nnqipga.outsystemscloud.com/Stripe/rest/payments/newpayment"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {stripe_key}"}

        payload = {
            "amount": amount,
            "currency": currency,
            "payment_method": payment_method,
            "customer": customer,
            "confirm": True,
            "off_session": True,
            "automatic_payment_methods": {
                "enabled": True,
                "allow_redirects": "never"
            }
        }

        response = requests.post(newpayment_url, json=payload, headers=headers)

        if response.status_code == 200:
            return jsonify({"success": True, "data": response.json()})
        else:
            return jsonify({"error": "Payment failed", "details": response.text}), response.status_code

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    


@app.route('/makerefund', methods=['POST'])
def make_refund():
        try:
            # Get Stripe secret key from environment variable
            stripe_key = os.getenv("STRIPE_SECRET_KEY")

            # Get refund request data
            req_data = request.get_json()
            payment_intent = req_data.get("payment_intent")
            reason = req_data.get("reason", "")  # Optional

            if not payment_intent:
                return jsonify({"error": "Missing required field: payment_intent"}), 400

            refund_url = "https://personal-5nnqipga.outsystemscloud.com/Stripe/rest/payments/refund"
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {stripe_key}"
            }

            payload = {
                "payment_intent": payment_intent,
                "reason": reason
            }

            response = requests.post(refund_url, json=payload, headers=headers)

            if response.status_code == 200:
                return jsonify({"success": True, "refund": response.json()}), 200
            else:
                return jsonify({"error": "Refund failed", "details": response.text}), response.status_code

        except Exception as e:
            return jsonify({"error": str(e)}), 500