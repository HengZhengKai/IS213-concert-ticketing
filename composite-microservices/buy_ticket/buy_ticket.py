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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

CORS(app)

# Determine if we're running in Docker or locally
is_docker = os.getenv("DOCKER_ENV", "false").lower() == "true"
base_url = "http://kong:8000" if is_docker else "http://localhost:8000" 
rabbitmq_host = "rabbitmq" if is_docker else "localhost"

credentials = pika.PlainCredentials('guest', 'guest')

event_URL = f"{base_url}/event"
seat_URL = f"{base_url}/seat"
ticket_URL = f"{base_url}/ticket"
transaction_URL = f"{base_url}/transaction"
user_URL = f"{base_url}/user"
payment_URL = f"{base_url}/payment"
email_URL = f"{base_url}/email"

def get_rabbitmq_connection():
    """Get a RabbitMQ connection with retry logic"""
    try:
        for attempt in range(5):
            try:
                logger.info(f"Connecting to RabbitMQ at {rabbitmq_host} (Attempt {attempt + 1})...")
                parameters = pika.ConnectionParameters(
                    host=rabbitmq_host,
                    credentials=credentials,
                    connection_attempts=3,
                    retry_delay=5,
                    heartbeat=600,
                    blocked_connection_timeout=300
                )
                connection = pika.BlockingConnection(parameters)
                channel = connection.channel()
                logger.info("Successfully connected to RabbitMQ.")
                return connection, channel
            except pika.exceptions.AMQPConnectionError as e:
                logger.error(f"Connection failed: {e}")
                if attempt < 4:  # Don't sleep on the last attempt
                    time.sleep(5)
        logger.warning("Could not connect to RabbitMQ after multiple attempts, continuing without it...")
        return None, None
    except Exception as e:
        logger.warning(f"Error connecting to RabbitMQ: {e}, continuing without it...")
        return None, None

# Initialize RabbitMQ connection
connection, channel = get_rabbitmq_connection()

def ensure_rabbitmq_connection():
    """Ensure RabbitMQ connection is active, reconnect if necessary"""
    global connection, channel
    try:
        if not connection or connection.is_closed:
            logger.warning("RabbitMQ connection lost, attempting to reconnect...")
            connection, channel = get_rabbitmq_connection()
    except Exception as e:
        logger.error(f"Error checking RabbitMQ connection: {e}")
        connection, channel = get_rabbitmq_connection()

def publish_to_rabbitmq(exchange, routing_key, body):
    """Publish message to RabbitMQ with connection handling"""
    if connection is None or channel is None:
        logger.warning("RabbitMQ not available, skipping message publishing")
        return
        
    try:
        ensure_rabbitmq_connection()
        channel.basic_publish(
            exchange=exchange,
            routing_key=routing_key,
            body=json.dumps(body),
            properties=pika.BasicProperties(
                delivery_mode=2,  # make message persistent
            )
        )
        logger.info(f"Successfully published message to {exchange} with routing key {routing_key}")
    except Exception as e:
        logger.error(f"Error publishing to RabbitMQ: {e}")

#app route: http://localhost:5100/buyticket
@app.route("/buyticket", methods=['POST'])
def buy_ticket():
    if request.is_json:
        try:
            data = request.get_json()
            required_fields = ["userID", "eventName", "eventID", "eventDateTime", "seats"]

            if not all(field in data for field in required_fields):
                return jsonify({"code": 400, "message": "Missing required fields."}), 400

            userID = data["userID"]
            eventName = data["eventName"]
            eventID = data["eventID"]
            eventDateTime = data["eventDateTime"]
            seats = data["seats"]

            # Step 1: Initialize an empty list to store results
            results = []

            # Step 2: Iterate through each seat and call process_buy_ticket for each one
            for seat in seats:
                seatNo = seat["seatNo"]
                seatCategory = seat["seatCategory"]
                price = seat["price"]
                paymentID = seat["paymentID"]

                # Step 3: Call process_buy_ticket for each seat
                result = process_buy_ticket(userID, eventName, eventID, eventDateTime, seatNo, seatCategory, price, paymentID)

                # Collect the result of each ticket purchase
                results.append(result)

            # Step 4: Return the results of all ticket purchases
            return jsonify({
                "code": 200,
                "data": results,
                "message": "Ticket purchase successful for all seats."
            }), 200

        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            ex_str = str(e) + " at " + str(exc_type) + ": " + fname + ": line " + str(exc_tb.tb_lineno)
            print(ex_str)

            return jsonify({
                "code": 500,
                "message": f"Unexpected error: {str(e)}"
            }), 500

    return jsonify({
        "code": 400,
        "message": "Invalid JSON input: " + str(request.get_data())
    }), 400



def process_buy_ticket(userID, eventName, eventID, eventDateTime, seatNo, seatCategory, price, paymentID):
    try:
        # Step 2-3: Update event availableSeats
        print('\n-----Invoking event microservice-----')
        event = invoke_http(f"{event_URL}/{eventID}/{eventDateTime}")
        
        if not isinstance(event, dict):
            return {
                "code": 500,
                "message": "Invalid response from event microservice."
            }
        
        if event.get("code") not in range(200, 300):
            return {
                "code": 500,
                "message": f"Failed to get event: {event.get('message', 'Unknown error')}"
            }

        if "data" not in event or "availableSeats" not in event["data"]:
            return {
                "code": 500,
                "message": "Event data not found or unavailable."
            }

        availableSeats = event["data"]["availableSeats"]
        newSeats = availableSeats - 1
        event_result = invoke_http(f"{event_URL}/{eventID}/{eventDateTime}", method="PUT", json={"availableSeats": newSeats})

        if not isinstance(event_result, dict):
            return {
                "code": 500,
                "message": "Invalid response from event update."
            }

        if event_result.get("code") not in range(200, 300):
            return {
                "code": 500,
                "message": f"Failed to update event: {event_result.get('message', 'Unknown error')}"
            }

        # Step 4-5: Get user name and email from userID
        print('\n-----Invoking user microservice-----')
        user = invoke_http(f"{user_URL}/{userID}")
        
        if not isinstance(user, dict):
            return {
                "code": 500,
                "message": "Invalid response from user microservice."
            }

        if user.get("code") not in range(200, 300):
            return {
                "code": 500,
                "message": f"Failed to get user: {user.get('message', 'Unknown error')}"
            }
        
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
                "resalePrice": None,  # Set to None for new tickets
                "status": "paid",
                "paymentID": paymentID,
                "isCheckedIn": False  # Set to False for new tickets
            }

            try:
                logger.info(f"Making request to ticket service: {ticket_URL}/{temp_ticketID}")
                ticket_result = invoke_http(f"{ticket_URL}/{temp_ticketID}", method="POST", json=ticket_data)
                
                if not isinstance(ticket_result, dict):
                    continue  # Try again with new ticketID
                
                if ticket_result.get("code") == 201:
                    ticketID = temp_ticketID
                    logger.info(f"Successfully created ticket with ID: {ticketID}")
                    break
                else:
                    logger.error(f"Failed to create ticket: {ticket_result.get('message', 'Unknown error')}")
                    continue  # Try again with new ticketID
            except Exception as e:
                logger.error(f"Exception during ticket creation: {str(e)}")
                continue  # Try again with new ticketID

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
            
            if not isinstance(transaction_result, dict):
                continue  # Try again with new transactionID
                
            transaction_code = transaction_result.get("code")

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

        try:
            publish_to_rabbitmq(
                exchange="ticketing",
                routing_key="ticket.purchased",
                body=payload
            )
        except Exception as e:
            logger.error(f"Failed to publish email notification: {e}")
            # Don't fail the whole transaction if email fails
            pass

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



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5100, debug=True)
    