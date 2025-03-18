from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_graphql import GraphQLView
import graphene
import mongoengine as db
from os import environ
import os

app = Flask(__name__)

CORS(app)

db.connect(host=os.getenv('MONGO_URI')) # Set this in your .env file

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
class Query(graphene.ObjectType):
    charge_id = graphene.String(ticketID=graphene.String(required=True))
    is_checked_in = graphene.Boolean(ticketID=graphene.String(required=True))

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