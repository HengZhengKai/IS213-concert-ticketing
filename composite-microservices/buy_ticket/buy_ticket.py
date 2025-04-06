from flask import Flask, request, jsonify
from flask_cors import CORS
import uuid
import os, sys
import requests
import pika
import json
from invokes import invoke_http

app = Flask(__name__)

CORS(app)

connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()

event_URL = "http://localhost:5001/event"
seat_URL = "http://localhost:5002/seat"
ticket_URL = "http://localhost:5004/ticket"
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
                               "eventDate",
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
            eventDate = data["eventDate"]
            seatNo = data["seatNo"]
            seatCategory = data["seatCategory"]
            price = data["price"]
            paymentID = data["paymentID"]            

            result = process_buy_ticket(userID, eventName, eventID, eventDate, seatNo, seatCategory, price, paymentID)
            return jsonify(result), result["code"]

        except Exception as e:
            # Unexpected error in code
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            ex_str = str(e) + " at " + str(exc_type) + ": " + fname + ": line " + str(exc_tb.tb_lineno)
            print(ex_str)

            return jsonify({
                "code": 500,
                "message": "buy_ticket.py internal error: " + ex_str
            }), 500


    # if reached here, not a JSON request.
    return jsonify({
        "code": 400,
        "message": "Invalid JSON input: " + str(request.get_data())
    }), 400

def process_buy_ticket(userID, eventName, eventID, eventDate, seatNo, seatCategory, price, paymentID):
    # Step 2-3. Update event availableSeats
    print('\n-----Invoking event microservice-----')
    event = invoke_http(f"{event_URL}/{eventID}/{eventDate}")
    availableSeats = event["data"]["availableSeats"]
    newSeats = availableSeats - 1
    event_result = invoke_http(f"{event_URL}/{eventID}/{eventDate}",method="PUT",
                               json={"availableSeats":newSeats})
    
    # Check the event result; if a failure, do error handling.
    code = event_result["code"]
    if code not in range(200, 300):
        # # Inform the error microservice
        # print('\n\n-----Invoking error microservice as order fails-----')
        # invoke_http(error_URL, method="POST", json=ticket_result)
        # # - reply from the invocation is not used; 
        # # continue even if this invocation fails
        # print("Order status ({:d}) sent to the error microservice:".format(
        #     code), order_result)

        return {
            "code": 500,
            "data": {"event_result": event_result},
            "message": "Event update failure, sent for error handling."
        }
    
    # Step 4-5: Get user name and email from userID
    print('\n-----Invoking user microservice-----')
    user = invoke_http(f"{user_URL}/{userID}")
    userName = user["data"]["name"]
    userEmail = user["data"]["email"]

    # Step 6-7: Create new ticket
    print('\n-----Invoking ticket microservice-----')
    ticketID = None
    for i in range(5): # max 5 attempts to create new ticket
        temp_ticketID = "T" + str(uuid.uuid4())[:4]
        ticket_data = {
            "ownerID": userID,
            "ownerName": userName,
            "eventID": eventID,
            "eventName": eventName,
            "eventDateTime": eventDate,
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
            "message": "Failed to create ticket after multiple attempts. Try again later."
        }

    # Step 8-9: Create new transaction
    print('\n-----Invoking transaction microservice-----')
    transaction_code = None
    while transaction_code == None or transaction_code == 409: # ticketid already exists (rare chance)
        print('\n-----Creating new transaction-----')

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
        "event_date": eventDate,
        "seat_no": seatNo,
        "seat_category": seatCategory,
        "price": price
    }

    channel.basic_publish(
        exchange="ticketing",
        routing_key="ticket.purchased",
        body=json.dumps(payload)
    )

    # Step 11: Return
    return {
        "code": 201,
        "data": {
            "ticketID": ticketID,
            "transactionID": transactionID
        },
        "message": "Ticket purchase successful."
    }

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5100, debug=True)


    # # Step 4-5. Update seat status
    # print('\n-----Invoking seat microservice-----')
    # seat_result = invoke_http(f"{seat_URL}", method="PUT",json = {"eventID":eventID,
    #                                                               "eventDate":eventDate,
    #                                                               "seatNo":seatNo,
    #                                                               "status":"booked"})
    
    # # Check the ticket result; if a failure, do error handling.
    # code = seat_result["code"]
    # if code not in range(200, 300):
    #     pass
    #     # # Inform the error microservice
    #     # print('\n\n-----Invoking error microservice as order fails-----')
    #     # invoke_http(error_URL, method="POST", json=ticket_result)
    #     # # - reply from the invocation is not used; 
    #     # # continue even if this invocation fails
    #     # print("Order status ({:d}) sent to the error microservice:".format(
    #     #     code), order_result)

    #     return {
    #         "code": 500,
    #         "data": {"seat_result": seat_result},
    #         "message": "Seat update failure, sent for error handling."
    #     }
    