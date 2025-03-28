from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_graphql import GraphQLView
import graphene
import mongoengine as db
from os import environ
import os
from datetime import datetime
import urllib.parse
from flasgger import Swagger
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
swagger = Swagger(app)

CORS(app)

# MongoDB connection details from environment variables
username = os.getenv("MONGO_USERNAME")
password = urllib.parse.quote_plus(os.getenv("MONGO_PASSWORD"))
cluster = os.getenv("MONGO_CLUSTER")
database = os.getenv("MONGO_DATABASE")

# Construct connection string
MONGO_URI = f"mongodb+srv://{username}:{password}@{cluster}/{database}?retryWrites=true&w=majority&authSource=admin"

try:
    # Connect to MongoDB Atlas
    logger.info(f"Connecting to MongoDB at: {cluster}")
    db.connect(host=MONGO_URI, alias='default')
    logger.info("Connected to MongoDB successfully")
except Exception as e:
    logger.error(f"Failed to connect to MongoDB: {e}")

class Ticket(db.Document): # tell flask what are the fields in your database
    ticketID = db.StringField(primary_key = True)
    ownerID = db.StringField()
    eventID = db.StringField()
    eventDateTime = db.DateTimeField(required=True)
    seatNo = db.IntField()
    seatCategory = db.StringField()
    price = db.FloatField()
    resalePrice = db.FloatField(null=True) #resalePrice is None when first created
    status = db.StringField()
    chargeID = db.StringField() # can be "" for mock tickets
    isCheckedIn = db.BooleanField()

    def to_json(self):
        return {
            "ticketID": self.ticketID,
            "ownerID": self.ownerID,
            "eventID": self.eventID,
            "eventDateTime": self.eventDateTime,
            "seatNo": self.seatNo,
            "seatCategory": self.seatCategory,
            "price": self.price,
            "resalePrice": self.resalePrice,
            "status": self.status,
            "chargeID": self.chargeID,
            "isCheckedIn": self.isCheckedIn
        }

# Define GraphQL Queries
class EventDetails(graphene.ObjectType):
    eventID = graphene.String()
    eventDateTime = graphene.DateTime()

class Query(graphene.ObjectType):
    """
    GraphQL Query class to fetch ticket details.

    Available Queries:
    1. charge_id(ticketID: <string>): Returns the chargeID associated with a given ticket.
    2. is_checked_in(ticketID: <string>): Returns the check-in status (Boolean) of a given ticket.
    3. event_details(ticketID: <string>): Returns eventID and eventDateTime of a given ticket

    Example Queries:
    ```
    query {
        chargeId(ticketID: "12345")
    }

    query {
        isCheckedIn(ticketID: "12345")
    }
    ```
    """
    charge_id = graphene.String(ticketID=graphene.String(required=True))
    is_checked_in = graphene.Boolean(ticketID=graphene.String(required=True))
    event_details = graphene.Field(EventDetails, ticketID=graphene.String(required=True))

    # Query for chargeID
    def resolve_charge_id(self, info, ticketID):
        ticket = Ticket.objects(ticketID=ticketID).first()
        if ticket:
            return ticket.chargeID
        return None  # If no ticket found, return None

    # Query for isCheckedIn
    def resolve_is_checked_in(self, info, ticketID):
        ticket = Ticket.objects(ticketID=ticketID).first()
        if ticket:
            return ticket.isCheckedIn
        return None  # If no ticket found, return None

    # Query for eventDetails
    def resolve_event_details(self, info, ticketID):
        """Resolves event details (event name and event date) for the given ticketID."""
        ticket = Ticket.objects(ticketID=ticketID).first()
        if ticket:
            return EventDetails(eventID=ticket.eventID, eventDateTime=ticket.eventDateTime)
        return None 
    
# Define the schema
schema = graphene.Schema(query=Query)

# Add the GraphQL view with the schema
app.add_url_rule(
    '/graphql', 
    view_func=GraphQLView.as_view('graphql', schema=schema, graphiql=True)
)

@app.route('/ticket/<string:eventID>/<string:eventDateTime>')
def get_available_tickets(eventID, eventDateTime):
    '''get tickets with available status'''
    available_tickets = Ticket.objects(eventID=eventID, eventDateTime=eventDateTime, status="available")

    if not available_tickets:
        return jsonify({"code": 404, "message": "No available tickets for this event on this date."}), 404

    # Return the available tickets in the response
    tickets_data = [ticket.to_json() for ticket in available_tickets]

    return jsonify({"code": 200, "data": tickets_data}), 200

@app.route('/ticket/<string:userID>')
def get_tickets_by_user(userID):
    '''get tickets under selected user'''
    tickets = Ticket.objects(userID=userID)

    if not tickets:
        return jsonify({"code": 404, "message": "User has no tickets."}), 404

    # Return the available tickets in the response
    tickets_data = [ticket.to_json() for ticket in tickets]

    return jsonify({"code": 200, "data": tickets_data}), 200

@app.route('/ticket/<string:ticketID>', methods=['PUT'])
def update_ticket(ticketID):
    # Find the ticket by ticketID
    ticket = Ticket.objects(ticketID=ticketID).first()

    if not ticket:
        return jsonify({"code": 404, "message": "Ticket not found."}), 404

    # Check if the ticket is already checked in
    if ticket.isCheckedIn:
        return jsonify({
            "code": 409,
            "data": {"ticketID": ticketID},
            "message": "Ticket is already checked in and cannot be modified."
        }), 409

    # Get the request data to update
    data = request.get_json()

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
        if data['status'] == ticket.status:
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
            "eventID": updated_ticket.eventID,
            "eventDateTime": updated_ticket.eventDateTime,
            "seatNo": updated_ticket.seatNo,
            "seatCategory": updated_ticket.seatCategory,
            "price": updated_ticket.price,
            "resalePrice": updated_ticket.resalePrice,
            "status": updated_ticket.status,
            "chargeID": updated_ticket.chargeID,
            "isCheckedIn": updated_ticket.isCheckedIn
        }
    }), 200


# POST /ticket/<ticketID> - Create new ticket
@app.route("/ticket/<string:ticketID>", methods=["POST"])
def create_ticket(ticketID):
    try:
        # Check if ticket already exists
        if Ticket.objects(ticketID=ticketID).first():
            return jsonify({
                "code": 409,
                "data": {"ticketID": ticketID},
                "message": "Ticket already exists."
            }), 409

        # Get request data
        data = request.get_json()

        # Validate input
        required_fields = ["ownerID", "eventID", "eventDateTime", "seatNo", "seatCategory", "price", "status", "chargeID", "isCheckedIn"]
        if any(field not in data for field in required_fields):
            return jsonify({
                "code": 400,
                "message": "Missing required fields."
            }), 400

        if not isinstance(data["seatNo"], int):
            return jsonify({
                "code": 400,
                "message": "Seat number must be an integer."
            }), 400
    
        if data["seatNo"] <= 0:
            return jsonify({
                "code": 400,
                "message": "Seat number must be positive."
            }), 400

        if not isinstance(data["price"], (int, float)) or data["price"] < 0:
            return jsonify({
                "code": 400,
                "message": "Price must be a non-negative number."
            }), 400
        
        # Create and save the new ticket
        ticket = Ticket(
            ticketID=ticketID,
            ownerID=data["ownerID"],
            eventID=data["eventID"],
            seatNo=data["seatNo"],
            seatCategory=data["seatCategory"],
            price=data["price"],
            resalePrice=data["resalePrice"],
            status=data["status"],
            chargeID=data["chargeID"],
            isCheckedIn=data["isCheckedIn"]
        )
        ticket.save()

        # Return successful response
        return jsonify({
            "code": 201,
            "data": ticket.to_json()
        }), 201

    except Exception as e:
        return jsonify({
            "code": 500,
            "data": {"ticketID": ticketID},
            "message": "An error occurred creating the ticket."
        }), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5004, debug=True)