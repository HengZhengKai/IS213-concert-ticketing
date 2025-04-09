from flask import Flask, request, jsonify
from flask_cors import CORS
import uuid
import os, sys
import requests
import pika
import json
from invokes import invoke_http
import time
import logging
from requests.exceptions import ConnectionError, RequestException

app = Flask(__name__)
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
app.debug = True

CORS(app)

rabbitmq_host = os.getenv("RABBITMQ_HOST", "rabbitmq")
credentials = pika.PlainCredentials('guest', 'guest')

# Determine if we're running in Docker or locally
is_docker = os.getenv("DOCKER_ENV", "false").lower() == "true"
base_url = "http://kong:8000" if is_docker else "http://localhost:8000"

waitlist_URL = f"{base_url}/waitlist"
ticket_URL = f"{base_url}/ticket"
transaction_URL = f"{base_url}/transaction"
user_URL = f"{base_url}/user"
payment_URL = f"{base_url}"

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

def make_request_with_retry(url, method='GET', json=None, max_retries=3, retry_delay=1):
    for attempt in range(max_retries):
        try:
            response = requests.request(method, url, json=json, timeout=10)
            return response.json()
        except ConnectionError as e:
            if attempt == max_retries - 1:
                raise
            print(f"Connection error (attempt {attempt + 1}/{max_retries}): {str(e)}")
            time.sleep(retry_delay)
        except RequestException as e:
            if attempt == max_retries - 1:
                raise
            print(f"Request error (attempt {attempt + 1}/{max_retries}): {str(e)}")
            time.sleep(retry_delay)

@app.route("/buyresaleticket/<string:ticketID>", methods=['POST'])
def buy_resale_ticket(ticketID):
    if request.is_json:
        try:
            # Parse the incoming JSON request
            data = request.get_json()
            required_fields = ["userID", "paymentID"]

            # Check if all required fields are in the request data
            if not all(field in data for field in required_fields):
                return jsonify({"code": 400, "message": "Missing required fields."}), 400
            
            print(f"\nReceived a request to buy resale ticket with ID: {ticketID}")

            # Extract userID and paymentID from request data
            userID = data["userID"]
            paymentID = data["paymentID"]

            # Call the process function to handle the ticket purchase logic
            result = process_buy_resale_ticket(userID, ticketID, paymentID)

            # Return the result from the ticket purchase processing
            return jsonify(result), result["code"]

        except KeyError as e:
            # Catch KeyErrors if expected keys are missing
            return jsonify({
                "code": 400,
                "message": f"Missing or invalid key in the request: {str(e)}"
            }), 400

        except ValueError as e:
            # Catch ValueErrors for invalid data types or values
            return jsonify({
                "code": 400,
                "message": f"Invalid value provided: {str(e)}"
            }), 400

        except Exception as e:
            # Catch any other unexpected exceptions
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            ex_str = f"{str(e)} at {str(exc_type)}: {fname}: line {str(exc_tb.tb_lineno)}"

            return jsonify({
                "code": 500,
                "message": f"Internal error in buy_resale_ticket.py: {ex_str}"
            }), 500

    # If the request is not JSON
    return jsonify({
        "code": 400,
        "message": f"Invalid JSON input: {str(request.get_data())}"
    }), 400

def process_buy_resale_ticket(userID, ticketID, paymentID):
    try:
        print(f"\n=== Starting process_buy_resale_ticket ===")
        print(f"Parameters: userID={userID}, ticketID={ticketID}, paymentID={paymentID}")
        
        # Step 2-3: Get user name and email from userID
        print(f'\n-----Invoking user microservice for user {userID}-----')
        try:
            user = invoke_http(f"{user_URL}/{userID}")
        except Exception as e:
            return {"code": 500, "message": f"DEBUGGING: Error calling user service: {str(e)}"}
            
        userName = user["data"]["name"]
        userEmail = user["data"]["email"]
        print(f"Retrieved user details: name={userName}, email={userEmail}")
        
        # Step 4-5: Get ticket details
        print(f'\n-----Invoking ticket microservice for ticket {ticketID}-----')
        ticket_url = f"{ticket_URL}/{ticketID}"
        print(f"Calling ticket URL: {ticket_url}")
        try:
            ticket = invoke_http(ticket_url)
                
            # Check if ticket is already paid
            if ticket["data"].get("status") == "paid":
                return {
                    "code": 409,
                    "message": "Ticket is already paid and cannot be updated."
                }
        except Exception as e:
            return {"code": 500, "message": f"DEBUGGING: Error calling ticket service: {str(e)}"}
        
        try:
            sellerID = ticket["data"]["ownerID"]
            sellerName = ticket["data"]["ownerName"]
            eventID = ticket["data"]["eventID"]
            eventName = ticket["data"]["eventName"]
            eventDateTime = ticket["data"]["eventDateTime"]
            seatNo = ticket["data"]["seatNo"]
            seatCategory = ticket["data"]["seatCategory"]
            price = ticket["data"]["price"]
            resalePrice = ticket["data"]["resalePrice"]
            original_paymentID = ticket["data"]["paymentID"]
            print(f"Ticket details: sellerID={sellerID}, eventID={eventID}, resalePrice={resalePrice}")
        except KeyError as e:
            print(f"Failed to extract ticket details. Missing key: {e}")
            print(f"Full ticket response: {ticket}")
            return {"code": 500, "message": f"DEBUGGING: Invalid ticket data structure: missing {e}"}
        
        # Step 6-7. Update ticket for user
        print(f'\n-----Updating ticket {ticketID} for user {userID}-----')
        
        # Check ticket conditions before update
        if ticket['data']['isCheckedIn']:
            return {
                "code": 409,
                "message": "DEBUGGING: Ticket is already checked in and cannot be modified."
            }
            
        if ticket['data']['status'] != 'available':
            return {
                "code": 409,
                "message": f"DEBUGGING: Ticket cannot be updated. Current status: {ticket['data']['status']}"
            }
            
        update_data = {
            "status": "paid",
            "ownerID": userID,
            "ownerName": userName,
            "paymentID": paymentID,
            "isCheckedIn": False
        }
        print(f"Update data being sent: {json.dumps(update_data, indent=2)}")
        ticket_result = invoke_http(f"{ticket_URL}/{ticketID}", method='PUT', json=update_data)
        print(f"Raw ticket update response: {json.dumps(ticket_result, indent=2)}")
        
        if not isinstance(ticket_result, dict):
            return {
                "code": 500,
                "message": f"DEBUGGING: Invalid response type from ticket update: {type(ticket_result)}"
            }
            
        if ticket_result.get("code") != 200:
            return {
                "code": ticket_result.get("code", 500),
                "message": f"DEBUGGING: Unexpected response code: {ticket_result.get('code')}"
            }

        # Step 8-9: Invoke payment service to refund charge
        print(f'\n-----Invoking payment microservice for refund {original_paymentID}-----')
        refund_result = invoke_http(f"{payment_URL}/makerefund", method='POST', json={"payment_intent": original_paymentID})

        # Step 10-11: Log purchase and refund transactions
        transaction_code = None
        while transaction_code == None or transaction_code == 409:
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
        while transaction_code == None or transaction_code == 409:
            print('\n-----Creating new transaction-----')
            refund_transactionID = "Ref" + str(uuid.uuid4())[:7]
            transaction_data = {
                "transactionID": refund_transactionID,
                "type": "refund",
                "userID": sellerID,
                "ticketID": ticketID,
                "paymentID": original_paymentID,
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
            "charge_id": paymentID,
            "refund_amount": resalePrice
        }

        channel.basic_publish(
            exchange="ticketing",
            routing_key="ticket.resold",
            body=json.dumps(payload)
        )

        # Step 14: Return success response
        return {
            "code": 201,
            "data": {
                "ticketID": ticketID,
                "transactionID": purchase_transactionID,
            },
            "message": "Ticket bought successfully."
        }

    except Exception as e:
        # Catch any unhandled exceptions
        return {
            "code": 500,
            "message": f"Internal error occurred during ticket purchase: {str(e)}"
        }
if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    app.logger.setLevel(logging.DEBUG)
    
    # Enable debug mode
    app.debug = True
    app.run(host="0.0.0.0", port=5102, debug=True)