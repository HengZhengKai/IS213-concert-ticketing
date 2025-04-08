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


waitlist_URL = "http://localhost:5003/waitlist"
ticket_URL = "http://localhost:5004/ticket"
transaction_URL = "http://localhost:5005/transaction"
user_URL = "http://localhost:5006/user"
payment_URL = "http://localhost:5007/payment"

@app.route("/buyresaleticket/<string:ticketID>", methods=['POST'])
def buy_resale_ticket(ticketID):
    if request.is_json:
        try:
            data = request.get_json()
            required_fields = ["userID", "paymentID"]

            if not all(field in data for field in required_fields):
                return jsonify({"code": 400, "message": "Missing required fields."}), 400
    
            print(f"\nReceived a request to buy resale ticket with ID: {ticketID}")

            # Step 1. Process ticket
            userID = data["userID"]
            paymentID = data["paymentID"]            

            result = process_buy_resale_ticket(userID, ticketID, paymentID)  # Pass only ticketID

            return jsonify(result), result["code"]

        except Exception as e:
            # Unexpected error in code
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            ex_str = f"{str(e)} at {str(exc_type)}: {fname}: line {str(exc_tb.tb_lineno)}"
            print(ex_str)

            return jsonify({
                "code": 500,
                "message": "buy_resale_ticket.py internal error: " + ex_str
            }), 500
        
    # if reached here, not a JSON request.
    return jsonify({
        "code": 400,
        "message": "Invalid JSON input: " + str(request.get_data())
    }), 400

def process_buy_resale_ticket(userID, ticketID, paymentID):
    # Step 2-3: Get user name and email from userID
    print('\n-----Invoking user microservice-----')
    user = invoke_http(f"{user_URL}/{userID}")
    if user["code"] != 200:
        return {"code": user["code"], "message": "User not found."}
    
    userName = user["data"]["name"]
    userEmail = user["data"]["email"]
    
    # Step 4-5: Get ticket details
    print('\n-----Invoking ticket microservice-----')
    ticket = invoke_http(f"{ticket_URL}/ticket/{ticketID}")
    sellerID = ticket["data"]["ownerId"]
    sellerName = ticket["data"]["ownerName"]
    eventID = ticket["data"]["eventID"]
    eventName = ticket["data"]["eventName"]
    eventDateTime = ticket["data"]["eventDateTime"]
    seatNo = ticket["data"]["seatNo"]
    seatCategory = ticket["data"]["seatCategory"]
    price = ticket["data"]["price"]
    resalePrice = ticket["data"]["resalePrice"]
    original_paymentID = ticket["data"]["paymentID"]
    
    # Step 6-7. Update ticket for user
    ticket_result = invoke_http(f"{ticket_URL}/{ticketID}", method='PUT', json={"status": "paid",
                                                                                "ownerID": userID,
                                                                                "ownerName": userName,
                                                                                "paymentID": paymentID})

    # Step 8-9: Invoke payment service to refund charge
    print('\n-----Invoking payment microservice-----')

    # check if using paymentID or payment intent
    refund_result = invoke_http(f"{payment_URL}/makerefund", method='POST', json={"payment_id": original_paymentID})

    # Step 10-11: Log purchase and refund transactions
    # purchase transaction
    transaction_code = None
    while transaction_code == None or transaction_code == 409: # ticketid already exists (rare chance)
        print('\n-----Creating new transaction-----')

        purchase_transactionID = "Trans" + str(uuid.uuid4())[:7]

        transaction_data = {
            "transactionID": purchase_transactionID,
            "type": "purchase",
            "userID": userID,
            "ticketID": ticketID,
            "paymentID": paymentID,
            "amount": resalePrice
        }

        transaction_result = invoke_http(f"{transaction_URL}", method="POST", json=transaction_data)
        transaction_code = transaction_result["code"]

    # refund transaction
    transaction_code = None
    while transaction_code == None or transaction_code == 409: # ticketid already exists (rare chance)
        print('\n-----Creating new transaction-----')

        refund_transactionID = "Ref" + str(uuid.uuid4())[:7]

        transaction_data = {
            "transactionID": refund_transactionID,
            "type": "refund",
            "userID": sellerID,
            "ticketID": ticketID,
            "paymentID": original_paymentID, #check whether new payment intent is created from transaction
            "amount": resalePrice
        }

        transaction_result = invoke_http(f"{transaction_URL}", method="POST", json=transaction_data)
        transaction_code = transaction_result["code"]

    # Step 12-13: Email buyers and sellers asynchronously
    print('\n-----Invoking email service through AMQP-----')
    
    payload = {
        "buyer_id": userID,
        "buyer_name": userName,
        "seller_id": sellerID,
        "seller_name": sellerName,
        "ticket_id": ticketID,
        "event_id": eventID,
        "event_name": eventName,
        "event_date": eventDateTime,
        "seat_no": seatNo,
        "seat_category": seatCategory,
        "price": resalePrice,       
        "charge_id": paymentID,         # check paymentID vs chargeID
        "refund_amount": resalePrice    # check what is the diff between price and refiund_amount
    }

    channel.basic_publish(
        exchange="ticketing",
        routing_key="ticket.resold",
        body=json.dumps(payload)
    )

    # Step 14: Return
    return {
        "code": 201,
        "data": {
            "ticketID": ticketID,
            "transactionID": purchase_transactionID,
        },
        "message": "Ticket bought successfully."
    }

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5101, debug=True)