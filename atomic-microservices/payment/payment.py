from flask import Flask, jsonify
from flask_cors import CORS
#import stripe
import os

app = Flask(__name__)

CORS(app)

import requests

newpayment = "https://personal-5nnqipga.outsystemscloud.com/Stripe/rest/payments/newpayment"

headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer sk_test_51R3vExQSvUjndICG0rAbAi8GNiUDAtQZhgOCHY1uSfnmPjSaZbhb51aCYhglY671WKvvb4H7RWEKklheuX0WCA0I00hTQYEDxm",  # testing key
}

data = {
  "amount": 2000, #change to variable
  "currency": "sgd", #change to variable
  "payment_method": "pm_card_visa", #change to variable
  "customer":"cus_S1J0TldFSJlleW", #change to variable
  "confirm": True,
  "off_session": True,
  "automatic_payment_methods": {
    "enabled": True,
    "allow_redirects": "never"
  }
}

response = requests.post(newpayment, json=data, headers=headers)
print(response.status_code)
print(response.json())
