from flask import Flask, request, jsonify
from flask_cors import CORS
import uuid
import os, sys
import requests
import pika
import json
from invokes import invoke_http
import time

app = Flask(__name__)

CORS(app)

rabbitmq_host = os.getenv("RABBITMQ_HOST", "rabbitmq")
credentials = pika.PlainCredentials('guest', 'guest')

for attempt in range(5):
    try:
        print(f"Connecting to RabbitMQ at {rabbitmq_host} (Attempt {attempt + 1})...")
        parameters = pika.ConnectionParameters(host=rabbitmq_host, credentials=credentials)
        connection = pika.BlockingConnection(parameters)
        channel = connection.channel()
        print("Successfully connected to RabbitMQ.")
        break
    except pika.exceptions.AMQPConnectionError as e:
        print(f"Connection failed: {e}")
        time.sleep(5)
else:
    raise Exception("Could not connect to RabbitMQ after multiple attempts.")
    exit(1)

event_URL = "http://localhost:5001/event"
seat_URL = "http://localhost:5002/seat"
ticket_URL = "http://localhost:5004/"
transaction_URL = "http://localhost:5005/transaction"
user_URL = "http://localhost:5006/user"
payment_URL = "http://localhost:5007/payment"
email_URL = "http://localhost:5008/email"

#app route: http://localhost:5100/buyticket
@app.route("/buyticket", methods=['POST'])
def buy_ticket():
    if request.is_json:
        try:
            data = request.get_json()
            required_fields = ["userID",
                               "eventName",
                               "eventID",
                               "eventDateTime",
                               "seatNo",
                               "seatCategory",
                               "price",
                               "paymentID"] # userID + eventName + paymentID + all fields in seat except for status
    
            if not all(field in data for field in required_fields):
                return jsonify({"code": 400, "message": "Missing required fields."}), 400

            # 1. Send seat info
            userID = data["userID"]
            eventName = data["eventName"]
            eventID = data["eventID"]
            eventDateTime = data["eventDateTime"]
            seatNo = data["seatNo"]
            seatCategory = data["seatCategory"]
            price = data["price"]
            paymentID = data["paymentID"]            

            result = process_buy_ticket(userID, eventName, eventID, eventDateTime, seatNo, seatCategory, price, paymentID)
            return jsonify(result), result["code"]

        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            ex_str = str(e) + " at " + str(exc_type) + ": " + fname + ": line " + str(exc_tb.tb_lineno)
            print(ex_str)

            return jsonify({
                "code": 500,
                "message": f"Unexpected error: {str(e)}"
            }), 500


    # if reached here, not a JSON request.
    return jsonify({
        "code": 400,
        "message": "Invalid JSON input: " + str(request.get_data())
    }), 400

def process_buy_ticket(userID, eventName, eventID, eventDateTime, seatNo, seatCategory, price, paymentID):
    try:
        # Step 2-3: Update event availableSeats
        print('\n-----Invoking event microservice-----')
        event = invoke_http(f"{event_URL}/{eventID}/{eventDateTime}")
        
        if "data" not in event or "availableSeats" not in event["data"]:
            return {
                "code": 500,
                "message": "Event data not found or unavailable."
            }

        availableSeats = event["data"]["availableSeats"]
        newSeats = availableSeats - 1
        event_result = invoke_http(f"{event_URL}/{eventID}/{eventDateTime}", method="PUT", json={"availableSeats": newSeats})

        if event_result["code"] not in range(200, 300):
            return {
                "code": 500,
                "message": "Failed to update event, check event microservice."
            }

        # Step 4-5: Get user name and email from userID
        print('\n-----Invoking user microservice-----')
        user = invoke_http(f"{user_URL}/{userID}")
        
        if "data" not in user or "name" not in user["data"] or "email" not in user["data"]:
            return {
                "code": 500,
                "message": "User data not found."
            }

        userName = user["data"]["name"]
        userEmail = user["data"]["email"]

        # Step 6-7: Create new ticket
        print('\n-----Invoking ticket microservice-----')
        ticketID = None
        for i in range(5):  # max 5 attempts
            temp_ticketID = "T" + str(uuid.uuid4())[:4]
            ticket_data = {
                "ownerID": userID,
                "ownerName": userName,
                "eventID": eventID,
                "eventName": eventName,
                "eventDateTime": eventDateTime,
                "seatNo": seatNo,
                "seatCategory": seatCategory,
                "price": price,
                "resalePrice": None,
                "status": "paid",
                "paymentID": paymentID,
                "isCheckedIn": False
            }

            ticket_result = invoke_http(f"{ticket_URL}/{temp_ticketID}", method="POST", json=ticket_data)
            if ticket_result["code"] == 201:
                ticketID = temp_ticketID
                break

        if ticketID is None:
            return {
                "code": 500,
                "message": "Failed to create ticket after multiple attempts."
            }

        # Step 8-9: Create new transaction
        print('\n-----Invoking transaction microservice-----')
        transaction_code = None
        while transaction_code == None or transaction_code == 409:  # rare conflict case
            transactionID = "Trans" + str(uuid.uuid4())[:7]

            transaction_data = {
                "transactionID": transactionID,
                "type": "purchase",
                "userID": userID,
                "ticketID": ticketID,
                "paymentID": paymentID,
                "amount": price
            }

            transaction_result = invoke_http(f"{transaction_URL}", method="POST", json=transaction_data)
            transaction_code = transaction_result["code"]

        # Step 10: Email buyer asynchronously
        print('\n-----Invoking email service through AMQP-----')
        payload = {
            "user_id": userID,
            "user_name": userName,
            "user_email": userEmail,
            "ticket_id": ticketID,
            "event_id": eventID,
            "event_name": eventName,
            "event_date": eventDateTime,
            "seat_no": seatNo,
            "seat_category": seatCategory,
            "price": price
        }

        channel.basic_publish(
            exchange="ticketing",
            routing_key="ticket.purchased",
            body=json.dumps(payload)
        )

        return {
            "code": 201,
            "data": {
                "ticketID": ticketID,
                "transactionID": transactionID
            },
            "message": "Ticket purchase successful."
        }
    except Exception as e:
        return {
            "code": 500,
            "message": f"Error processing ticket: {str(e)}"
        }

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5100, debug=True)
    