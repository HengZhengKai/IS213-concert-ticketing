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

#app route: http://localhost:5100/buyticket
@app.route("/buyticket", methods=['POST'])
def buy_ticket():
    data = request.get_json()
    required_fields = ["eventID", "eventDate", "seatNo"]
    
    if not all(field in data for field in required_fields):
        return jsonify({"code": 400, "message": "Missing required fields."}), 400
    

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5100, debug=True)