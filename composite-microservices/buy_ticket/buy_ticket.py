from flask import Flask, request, jsonify
from flask_cors import CORS
import os, sys
import requests
from invokes import invoke_http

app = Flask(__name__)

CORS(app)

event_URL = "http://localhost:5001/event"
seat_URL = "http://localhost:5002/seat"
ticket_URL = "http://localhost:5004/ticket"
transaction_URL = "http://localhost:5005/transaction"
user_URL = "http://localhost:5006/user"
payment_URL = "http://localhost:5007/payment"

@app.route("/buyticket/<string:ticketID>", methods=['POST'])
def buy_ticket(ticketID):
    pass

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5100, debug=True)