from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_graphql import GraphQLView
import graphene
import mongoengine as db
from datetime import datetime
from os import environ
import os
import re
from datetime import datetime
import urllib.parse
import logging
from dotenv import load_dotenv
import requests
#For Rabbitmq message publishing
import pika
import json

# Imports for QR Code generation
import qrcode
import base64
from io import BytesIO
import jwt # For decoding token

# Load environment variables from .env file
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# --- JWT Secret Key --- 
app.config['SECRET_KEY'] = os.getenv("JWT_SECRET_KEY", "your_default_super_secret_key")

# --- Configure CORS --- 
# Allow requests from WAMP, Python HTTP server, and potentially other local ports
cors_origins = ["http://localhost", "http://localhost:8000", "http://localhost:8080"]
CORS(app, 
        resources={r"/*": {"origins": cors_origins}}, 
        methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"], # Allow common methods
        allow_headers=["Authorization", "Content-Type", "Accept"], # Allow necessary headers
        supports_credentials=True # If you need cookies/session later
)
# --- End CORS Configuration ---

# --- Event Service URL --- 
EVENT_SERVICE_URL = os.getenv("EVENT_SERVICE_URL", "http://event_service:5001")

# MongoDB connection details from environment variables
username = os.getenv("MONGO_USERNAME")
password = urllib.parse.quote_plus(os.getenv("MONGO_PASSWORD"))
cluster = os.getenv("MONGO_CLUSTER")
database = os.getenv("MONGO_DATABASE")

# Use the MONGO_URI directly from environment if available, otherwise construct it
MONGO_URI = os.getenv("MONGO_URI") or f"mongodb+srv://{username}:{password}@{cluster}/{database}?retryWrites=true&w=majority"

try:
    # Connect to MongoDB Atlas
    logger.info(f"Connecting to MongoDB at: {cluster}")
    db.connect(host=MONGO_URI, alias='default')
    logger.info("Connected to MongoDB successfully")
except Exception as e:
    logger.error(f"Failed to connect to MongoDB: {e}")
    raise  # Re-raise the exception to prevent the service from starting with a bad connection

# Get RabbitMQ host and URI
# Get RabbitMQ host and URI
RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'rabbitmq')
RABBITMQ_URI = os.getenv('RABBITMQ_PORT', 'tcp://rabbitmq:5672')

# Extract the port number from the URI
match = re.search(r'tcp://.*:(\d+)', RABBITMQ_URI)
if match:
    RABBITMQ_PORT = int(match.group(1))  # Extracted port
else:
    RABBITMQ_PORT = 5672  # Default fallback port
    
RABBITMQ_USER = os.getenv('RABBITMQ_USER', 'guest')
RABBITMQ_PASS = os.getenv('RABBITMQ_PASS', 'guest')

def publish_to_rabbitmq(routing_key, message):
    try:
        # Create connection parameters
        credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
        parameters = pika.ConnectionParameters(
            host=RABBITMQ_HOST,
            port=RABBITMQ_PORT,
            credentials=credentials
        )
        
        # Connect to RabbitMQ
        connection = pika.BlockingConnection(parameters)
        channel = connection.channel()
        
        # Publish message
        channel.basic_publish(
            exchange='ticketing',
            routing_key=routing_key,
            body=json.dumps(message)
        )
        
        # Close connection
        connection.close()
        logger.info(f"Published message with routing key: {routing_key}")
        return True
    except Exception as e:
        logger.error(f"Failed to publish to RabbitMQ: {e}")
        return False

# Define MongoDB models
class Ticket(db.Document): # tell flask what are the fields in your database
    ticketID = db.StringField(primary_key = True)
    ownerID = db.StringField()
    ownerName = db.StringField()
    eventID = db.StringField()
    eventName = db.StringField()
    eventDateTime = db.DateTimeField(required=True)
    seatNo = db.IntField()
    seatCategory = db.StringField()
    price = db.FloatField()
    resalePrice = db.FloatField(null=True) #resalePrice is None when first created
    status = db.StringField()
    paymentID = db.StringField() # can be "" for mock tickets
    isCheckedIn = db.BooleanField()

    meta = {'collection': 'Ticket'} 

    def to_json(self):
        return {
            "ticketID": self.ticketID,
            "ownerID": self.ownerID,
            "ownerName": self.ownerName,
            "eventID": self.eventID,
            "eventName": self.eventName,
            "eventDateTime": self.eventDateTime,
            "seatNo": self.seatNo,
            "seatCategory": self.seatCategory,
            "price": self.price,
            "resalePrice": self.resalePrice,
            "status": self.status,
            "paymentID": self.paymentID,
            "isCheckedIn": self.isCheckedIn
        }
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

# Define GraphQL Queries
class EventDetails(graphene.ObjectType):
    eventID = graphene.String()
    eventName = graphene.String()
    eventDateTime = graphene.DateTime()

class OwnerDetails(graphene.ObjectType):
    ownerID = graphene.String()
    ownerName = graphene.String()

class Query(graphene.ObjectType):
    """
    GraphQL Query class to fetch ticket details.

    Available Queries:
    1. payment_id(ticketID: <string>): Returns the paymentID associated with a given ticket.
    2. is_checked_in(ticketID: <string>): Returns the check-in status (Boolean) of a given ticket.
    3. event_details(ticketID: <string>): Returns eventID and eventDateTime of a given ticket

    Example Queries:
    ```
    query {
        paymentId(ticketID: "T001")
    }

    query {
        isCheckedIn(ticketID: "T001")
    }

    query {
        eventDetails(ticketID: "T001") {
            eventID
            eventName
            eventDateTime
        }
    }

    query {
        ownerDetails(ticketID: "T001") {
            ownerID
            ownerName
        }
    }
    ```
    """
    payment_id = graphene.String(ticketID=graphene.String(required=True))
    is_checked_in = graphene.Boolean(ticketID=graphene.String(required=True))
    event_details = graphene.Field(EventDetails, ticketID=graphene.String(required=True))
    owner_details = graphene.Field(EventDetails, ticketID=graphene.String(required=True))

    # Query for paymentID
    def resolve_payment_id(self, info, ticketID):
        ticket = Ticket.objects(ticketID=ticketID).first()
        if ticket:
            return ticket.paymentID
        return None  # If no ticket found, return None

    # Query for isCheckedIn
    def resolve_is_checked_in(self, info, ticketID):
        ticket = Ticket.objects(ticketID=ticketID).first()
        if ticket:
            return ticket.isCheckedIn
        return None  # If no ticket found, return None

    # Query for eventDetails
    def resolve_event_details(self, info, ticketID):
        """Resolves event details (event id, event name and event date) for the given ticketID."""
        ticket = Ticket.objects(ticketID=ticketID).first()
        if ticket:
            return EventDetails(eventID=ticket.eventID, eventName=ticket.eventName, eventDateTime=ticket.eventDateTime)
        return None 
    
    # Query for ownerDetails
    def resolve_owner_details(self, info, ticketID):
        """Resolves owner details (ownerID and owner name) for the given ticketID."""
        ticket = Ticket.objects(ticketID=ticketID).first()
        if ticket:
            return OwnerDetails(ownerID=ticket.ownerID, ownerName=ticket.ownerName)
        return None 
    
# Define the schema
schema = graphene.Schema(query=Query)

# Add the GraphQL view with the schema
app.add_url_rule(
    '/graphql', 
    view_func=GraphQLView.as_view('graphql', schema=schema, graphiql=True)
)

@app.route('/tickets/<string:eventID>/<string:eventDateTime>')
def get_available_tickets(eventID, eventDateTime):
    '''get tickets with available status'''
    available_tickets = Ticket.objects(eventID=eventID, eventDateTime=eventDateTime, status="available")

    if not available_tickets:
        return jsonify({"code": 404, "message": "No available tickets for this event on this date."}), 404

    # Return the available tickets in the response
    tickets_data = [ticket.to_json() for ticket in available_tickets]

    return jsonify({"code": 200,
                    "data": {
                        "tickets": tickets_data
                    }}), 200

@app.route('/ticket/<string:ticketID>', methods=['GET'])
def get_ticket_by_id(ticketID):
    '''Get ticket by ticketID'''
    ticket = Ticket.objects(ticketID=ticketID).first()

    if not ticket:
        return jsonify({"code": 404, "message": "Ticket not found."}), 404

    # Return the ticket data in the response
    return jsonify({
        "code": 200,
        "data": ticket.to_json()
    }), 200

@app.route('/tickets/<string:ownerID>')
def get_tickets_by_user(ownerID):
    '''get tickets under selected user'''
    tickets = Ticket.objects(ownerID=ownerID)

    if not tickets:
        return jsonify({"code": 404, "message": "User has no tickets."}), 404

    # Return the available tickets in the response
    tickets_data = [ticket.to_json() for ticket in tickets]

    return jsonify({"code": 200,
                    "data": {
                        "tickets":tickets_data
                    }}), 200

@app.route('/ticket/<string:ticketID>', methods=['PUT'])
def update_ticket(ticketID):
    # Find the ticket by ticketID
    ticket = Ticket.objects(ticketID=ticketID).first()

    if not ticket:
        return jsonify({"code": 404, "message": "Ticket not found."}), 404

    # Get the request data to update
    data = request.get_json()


    # Check if the ticket is already checked in
    if ticket.isCheckedIn and 'isCheckedIn' not in data:
        return jsonify({
            "code": 409,
            "data": {"ticketID": ticketID},
            "message": "Ticket is already checked in and cannot be modified."
        }), 409

    # Validate resalePrice if present in the request
    if 'resalePrice' in data:
        new_resale_price = data['resalePrice']
        if new_resale_price > ticket.price or (ticket.resalePrice is not None and new_resale_price > ticket.resalePrice):
            return jsonify({
                "code": 400,
                "data": {"ticketID": ticketID},
                "message": "Resale price cannot be higher than the original price or the previous resale price."
            }), 400

    # If the status is being updated, check for conflicts
    if 'status' in data:
        if data['status'] == ticket.status and ticket.status == "paid":
            return jsonify({
                "code": 409,
                "data": {"ticketID": ticketID},
                "message": f"Ticket is already {ticket.status}."
            }), 409

    # Update the ticket with new values from the request
    ticket.update(**data)

    # Return the updated ticket data
    updated_ticket = Ticket.objects(ticketID=ticketID).first()

    return jsonify({
        "code": 200,
        "data": {
            "ticketID": updated_ticket.ticketID,
            "ownerID": updated_ticket.ownerID,
            "ownerName": updated_ticket.ownerName,
            "eventID": updated_ticket.eventID,
            "eventName": updated_ticket.eventName,
            "eventDateTime": updated_ticket.eventDateTime,
            "seatNo": updated_ticket.seatNo,
            "seatCategory": updated_ticket.seatCategory,
            "price": updated_ticket.price,
            "resalePrice": updated_ticket.resalePrice,
            "status": updated_ticket.status,
            "paymentID": updated_ticket.paymentID,
            "isCheckedIn": updated_ticket.isCheckedIn
        }
    }), 200


# POST /ticket/<ticketID> - Create new ticket
@app.route("/ticket/<string:ticketID>", methods=["POST"])
def create_ticket(ticketID):
    try:
        logger.info(f"Attempting to create ticket with ID: {ticketID}")
        
        # Check if ticket already exists
        if Ticket.objects(ticketID=ticketID).first():
            logger.warning(f"Ticket {ticketID} already exists")
            return jsonify({
                "code": 409,
                "data": {"ticketID": ticketID},
                "message": "Ticket already exists."
            }), 409

        # Get request data
        data = request.get_json()
        logger.info(f"Received ticket data: {data}")

        # Validate input
        required_fields = ["ownerID",
                           "ownerName",
                           "eventID",
                           "eventName",
                           "eventDateTime",
                           "seatNo",
                           "seatCategory",
                           "price",
                           "resalePrice",
                           "status",
                           "paymentID",
                           "isCheckedIn"] #ticketID in url
        
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            logger.error(f"Missing required fields: {missing_fields}")
            return jsonify({
                "code": 400,
                "message": f"Missing required fields: {', '.join(missing_fields)}"
            }), 400

        if not isinstance(data["seatNo"], int):
            logger.error(f"Invalid seatNo type: {type(data['seatNo'])}")
            return jsonify({
                "code": 400,
                "message": "Seat number must be an integer."
            }), 400
    
        if data["seatNo"] <= 0:
            logger.error(f"Invalid seatNo value: {data['seatNo']}")
            return jsonify({
                "code": 400,
                "message": "Seat number must be positive."
            }), 400

        if not isinstance(data["price"], (int, float)) or data["price"] < 0:
            logger.error(f"Invalid price value: {data['price']}")
            return jsonify({
                "code": 400,
                "message": "Price must be a non-negative number."
            }), 400
        
        try:
            event_datetime = datetime.fromisoformat(data["eventDateTime"].replace("Z", "+00:00"))
            logger.info(f"Parsed event datetime: {event_datetime}")
        except ValueError as e:
            logger.error(f"Error parsing datetime: {e}")
            return jsonify({
                "code": 400,
                "message": f"Invalid datetime format: {data['eventDateTime']}"
            }), 400

        # Create and save the new ticket
        try:
            ticket = Ticket(
                ticketID=ticketID,
                ownerID=data["ownerID"],
                ownerName=data["ownerName"],
                eventID=data["eventID"],
                eventName=data["eventName"],
                eventDateTime=event_datetime,
                seatNo=data["seatNo"],
                seatCategory=data["seatCategory"],
                price=data["price"],
                resalePrice=data["resalePrice"],
                status=data["status"],
                paymentID=data["paymentID"],
                isCheckedIn=data["isCheckedIn"]
            )
            logger.info("Attempting to save ticket to database")
            ticket.save()
            logger.info("Successfully saved ticket to database")
        except Exception as e:
            logger.error(f"Error saving ticket: {str(e)}")
            raise

        # Prepare message for email service
        message = {
            "ownerID": data["ownerID"],
            "user_name": data["ownerName"],
            "_id": ticketID,
            "event_id": data["eventID"],
            "event_name": data["eventName"],
            "eventDateTime": data["eventDateTime"],
            "seatNo": data["seatNo"],
            "seatCategory": data["seatCategory"],
            "price": data["price"]
        }

        # Publish to RabbitMQ
        logger.info("Attempting to publish to RabbitMQ")
        if publish_to_rabbitmq('ticket.purchased', message):
            logger.info("Successfully published to RabbitMQ")
        else:
            logger.warning("Failed to publish to RabbitMQ")

        # Return successful response
        return jsonify({
            "code": 201,
            "data": ticket.to_json()
        }), 201

    except Exception as e:
        logger.error(f"Error in create_ticket: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({
            "code": 500,
            "data": {"ticketID": ticketID},
            "message": f"An error occurred creating the ticket: {str(e)}"
        }), 500

@app.route('/ticket', methods=['GET'])
def get_all_tickets():
    try:
        tickets = Ticket.objects()
        return jsonify({
            "code": 200,
            "data": {
                "tickets": [ticket.to_json() for ticket in tickets]
            }
        })
    except Exception as e:
        return jsonify({
            "code": 500,
            "message": f"Error retrieving tickets: {str(e)}"
        }), 500

# # === QR Code Generation Endpoint (Simplified for Debugging) ===
# @app.route('/generateQR/<string:ticketID>', methods=['POST'])
# def generate_qr_code(ticketID):
#     logger.info(f"[DEBUG] Accessed simplified /generateQR route for ticketID: {ticketID}")
#     # Just return a simple success message to test route registration
#     return jsonify({"message": "QR Route OK"}), 200
# # === End Simplified Route ===

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5004, debug=True)