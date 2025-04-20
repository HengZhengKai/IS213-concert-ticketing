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
from pika.exceptions import AMQPConnectionError, AMQPChannelError

app = Flask(__name__)
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
app.debug = True

CORS(app)

rabbitmq_host = os.getenv("RABBITMQ_HOST", "rabbitmq")
credentials = pika.PlainCredentials('guest', 'guest')

waitlist_URL = "http://kong:8000/waitlist"
ticket_URL = "http://kong:8000/ticket"
transaction_URL = "http://kong:8000/transaction"
user_URL = "http://kong:8000/user"
payment_URL = "http://kong:8000"

def get_rabbitmq_connection():
    """Get a RabbitMQ connection with retry logic"""
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
    raise Exception("Could not connect to RabbitMQ after multiple attempts.")

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
    except Exception as e:
        logger.error(f"Error publishing to RabbitMQ: {e}")
        raise

def invoke_http_with_retry(url, method='GET', json=None, max_retries=3, retry_delay=1):
    for attempt in range(max_retries):
        try:
            result = invoke_http(url, method=method, json=json)
            if isinstance(result, dict) and result.get('code') in [500, 502, 503, 504]:
                raise Exception(f"Service returned error code: {result.get('code')}")
            return result
        except Exception as e:
            if attempt == max_retries - 1:
                logger.error(f"Request failed after {max_retries} attempts: {e}")
                raise
            logger.warning(f"Request failed (attempt {attempt + 1}/{max_retries}): {e}")
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
        logger.info(f"\n=== Starting process_buy_resale_ticket ===")
        logger.info(f"Parameters: userID={userID}, ticketID={ticketID}, paymentID={paymentID}")
        
        # Step 2-3: Get user name and email from userID
        logger.info(f'\n-----Invoking user microservice for user {userID}-----')
        try:
            user = invoke_http_with_retry(f"{user_URL}/{userID}")
        except Exception as e:
            logger.error(f"Error calling user service: {e}")
            return {"code": 500, "message": f"Error retrieving user details: {str(e)}"}
            
        userName = user["data"]["name"]
        userEmail = user["data"]["email"]
        logger.info(f"Retrieved user details: name={userName}, email={userEmail}")
        
        # Step 4-5: Get ticket details
        logger.info(f'\n-----Invoking ticket microservice for ticket {ticketID}-----')
        ticket_url = f"{ticket_URL}/{ticketID}"
        try:
            ticket = invoke_http_with_retry(ticket_url)
                
            # Check if ticket is already paid
            if ticket["data"].get("status") == "paid":
                return {
                    "code": 409,
                    "message": "Ticket is already paid and cannot be updated."
                }
        except Exception as e:
            logger.error(f"Error calling ticket service: {e}")
            return {"code": 500, "message": f"Error retrieving ticket details: {str(e)}"}
        
        try:
            # Get ticket details and ensure price is available
            sellerID = ticket["data"]["ownerID"]
            sellerName = ticket["data"]["ownerName"]
            eventID = ticket["data"]["eventID"]
            eventName = ticket["data"]["eventName"]
            eventDateTime = ticket["data"]["eventDateTime"]
            seatNo = ticket["data"]["seatNo"]
            seatCategory = ticket["data"]["seatCategory"]
            price = float(ticket["data"]["price"])  # Original price
            resalePrice = ticket["data"]["resalePrice"]
            if resalePrice is not None:
                resalePrice = float(resalePrice)
            else:
                resalePrice = price
            original_paymentID = ticket["data"]["paymentID"]
            logger.info(f"Ticket details: sellerID={sellerID}, eventID={eventID}, price={price}, resalePrice={resalePrice}")

            # Get seller's email
            logger.info(f'\n-----Invoking user microservice for seller {sellerID}-----')
            try:
                seller = invoke_http_with_retry(f"{user_URL}/{sellerID}")
                sellerEmail = seller["data"]["email"]
                logger.info(f"Retrieved seller details: name={sellerName}, email={sellerEmail}")
            except Exception as e:
                logger.error(f"Error getting seller details: {e}")
                return {"code": 500, "message": f"Error retrieving seller details: {str(e)}"}

        except KeyError as e:
            logger.error(f"Failed to extract ticket details. Missing key: {e}")
            logger.error(f"Full ticket response: {ticket}")
            return {"code": 500, "message": f"Invalid ticket data structure: missing {e}"}
        
        # Step 6-7. Update ticket for user
        logger.info(f'\n-----Updating ticket {ticketID} for user {userID}-----')
        
        # Check ticket conditions before update
        if ticket['data']['isCheckedIn']:
            return {
                "code": 409,
                "message": "Ticket is already checked in and cannot be modified."
            }
            
        if ticket['data']['status'] != 'available':
            return {
                "code": 409,
                "message": f"Ticket cannot be updated. Current status: {ticket['data']['status']}"
            }
            
        update_data = {
            "status": "paid",
            "ownerID": userID,
            "ownerName": userName,
            "paymentID": paymentID,
            "isCheckedIn": False
        }
        logger.info(f"Update data being sent: {json.dumps(update_data, indent=2)}")
        
        try:
            reserve_data = {"status": "paid"}
            reserve_result = invoke_http_with_retry(f"{ticket_URL}/{ticketID}", method='PUT', json=reserve_data)
            
            if not isinstance(reserve_result, dict) or reserve_result.get("code") != 200:
                return {
                    "code": 500,
                    "message": f"Failed to reserve ticket: {reserve_result.get('message', 'Unknown error')}"
                }
            
            # Then, update with the full data
            ticket_result = invoke_http_with_retry(f"{ticket_URL}/{ticketID}", method='PUT', json=update_data)
            
            if not isinstance(ticket_result, dict):
                return {
                    "code": 500,
                    "message": f"Invalid response type from ticket update: {type(ticket_result)}"
                }
                
            if ticket_result.get("code") != 200:
                return {
                    "code": ticket_result.get("code", 500),
                    "message": f"Unexpected response code: {ticket_result.get('code')}"
                }
        except Exception as e:
            logger.error(f"Error updating ticket: {e}")
            # Try to revert the ticket status back to available if the update failed
            try:
                revert_data = {"status": "available"}
                invoke_http_with_retry(f"{ticket_URL}/{ticketID}", method='PUT', json=revert_data)
            except Exception as revert_error:
                logger.error(f"Failed to revert ticket status: {revert_error}")
            return {"code": 500, "message": f"Error updating ticket: {str(e)}"}

        # Step 8-9: Invoke payment service to refund charge
        logger.info(f'\n-----Invoking payment microservice for refund {original_paymentID}-----')
        try:
            refund_result = invoke_http_with_retry(
                f"{payment_URL}/makerefund", 
                method='POST', 
                json={"payment_intent": original_paymentID}
            )
        except Exception as e:
            logger.error(f"Error processing refund: {e}")
            return {"code": 500, "message": f"Error processing refund: {str(e)}"}

        # Step 10-11: Log purchase and refund transactions
        try:
            # Create purchase transaction
            purchase_transactionID = "Trans" + str(uuid.uuid4())[:7]
            transaction_data = {
                "transactionID": purchase_transactionID,
                "type": "purchase",
                "userID": userID,
                "ticketID": ticketID,
                "paymentID": paymentID,
                "amount": resalePrice
            }
            invoke_http_with_retry(f"{transaction_URL}", method="POST", json=transaction_data)

            # Create refund transaction
            refund_transactionID = "Ref" + str(uuid.uuid4())[:7]
            transaction_data = {
                "transactionID": refund_transactionID,
                "type": "refund",
                "userID": sellerID,
                "ticketID": ticketID,
                "paymentID": original_paymentID,
                "amount": resalePrice
            }
            invoke_http_with_retry(f"{transaction_URL}", method="POST", json=transaction_data)
        except Exception as e:
            logger.error(f"Error creating transactions: {e}")
            return {"code": 500, "message": f"Error creating transactions: {str(e)}"}

        # Step 12-13: Email buyers and sellers asynchronously
        logger.info('\n-----Invoking email service through AMQP-----')

        # Publish the message
        try:
            publish_to_rabbitmq(
                exchange='ticketing',
                routing_key='ticket.resold',
                body={
                    "buyer_id": userID,
                    "buyer_name": userName,
                    "buyer_email": userEmail,
                    "seller_id": sellerID,
                    "seller_name": sellerName,
                    "seller_email": sellerEmail,
                    "ticket_id": ticketID,
                    "event_id": eventID,
                    "event_name": eventName,
                    "event_date": eventDateTime,
                    "seat_no": seatNo,
                    "seat_category": seatCategory,
                    "price": resalePrice,  
                    "refund_amount": resalePrice 
                },
            )
        except Exception as e:
            logger.error(f"Error sending email notification: {e}")
            logger.error(f"Full error details: {str(e)}", exc_info=True)
            # Don't fail the whole transaction if email fails
            pass

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
        logger.error(f"Internal error occurred during ticket purchase: {e}")
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