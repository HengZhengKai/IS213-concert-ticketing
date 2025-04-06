from flask import Flask, request, jsonify
from flask_cors import CORS
import os, sys
import requests
import pika
import json
from invokes import invoke_http

app = Flask(__name__)

CORS(app)

waitlist_URL = "http://localhost:5003/waitlist"
ticket_URL = "http://localhost:5004"
user_URL = "http://localhost:5006/user"
email_URL = "http://localhost:5008/email"
celery_URL = "http://localhost:5009/send_waitlist_emails"

@app.route("/sellticket/<string:ticketID>", methods=['POST']) # json body: resalePrice
def sell_ticket(ticketID):
    if request.is_json:
        try:
            ticket = request.get_json()
            ticket["ticketID"] = ticketID # ticket looks like {ticketID: T001, resalePrice: 80}
            print("\nReceived a ticket in JSON:", ticket)

            # 1. Put ticket up for sale
            result = process_sell_ticket(ticket)
            return jsonify(result), result["code"]

        except Exception as e:
            # Unexpected error in code
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            ex_str = str(e) + " at " + str(exc_type) + ": " + fname + ": line " + str(exc_tb.tb_lineno)
            print(ex_str)

            return jsonify({
                "code": 500,
                "message": "sell_ticket.py internal error: " + ex_str
            }), 500


    # if reached here, not a JSON request.
    return jsonify({
        "code": 400,
        "message": "Invalid JSON input: " + str(request.get_data())
    }), 400

def process_sell_ticket(ticket):
    # Step 2-3. Update ticket resalePrice and status
    print('\n-----Invoking ticket microservice-----')
    ticket_result = invoke_http(f"{ticket_URL}/ticket/{ticket.ticketID}", method='PUT', json={"resalePrice": ticket.resalePrice, "status": "available"})

    # Check the ticket result; if a failure, do error handling.
    code = ticket_result["code"]
    if code not in range(200, 300):
        pass
        # # Inform the error microservice
        # print('\n\n-----Invoking error microservice as order fails-----')
        # invoke_http(error_URL, method="POST", json=ticket_result)
        # # - reply from the invocation is not used; 
        # # continue even if this invocation fails
        # print("Order status ({:d}) sent to the error microservice:".format(
        #     code), order_result)

        return {
            "code": 500,
            "data": {"ticket_result": ticket_result},
            "message": "Ticket update failure, sent for error handling."
        }

    # Step 4-5. Query eventID and eventDateTime
    print('\n-----Querying ticket microservice-----')
    query = """
    query {
        eventDetails(ticketID: $ticketID) {
            eventID
            eventDateTime
        }
    }
    """
    variables = {"ticketID": ticket.ticketID}
    response = requests.post(f"{ticket_URL}/graphql", json={'query': query, 'variables': variables})
    
    # Step 5: Process event details to call the right waitlist route
    event_data = response.json()
    
    if "data" in event_data and event_data["data"]["eventDetails"]:
        eventID = event_data["data"]["eventDetails"]["eventID"]
        eventDateTime = event_data["data"]["eventDetails"]["eventDateTime"]
    else:
        print("Error: Could not retrieve event details")
        return {"error": "Event details not found"}

    print(f"Event ID: {eventID}, Event DateTime: {eventDateTime}")

    # Step 6-7. Get waitlist users
    print('\n-----Invoking waitlist microservice-----')
    waitlist_users = invoke_http(f"{waitlist_URL}/waitlist/{eventID}/{eventDateTime}")
    
    if not waitlist_users:
        print("No users on waitlist.")
        return {'status': 404, 'message': 'No users on waitlist.'}
    
    # Step 8: Email all waitlist users
    payload = {
        "waitlist_users": waitlist_users["data"],
        "ticket": {
            "event_name": ticket["event_name"],
            "event_date": eventDateTime,
            "expiration_time": "15 minutes"
        }
    }

    celery_result = invoke_http(f"{celery_URL}", method='POST', json=payload)

    if celery_result["code"] not in range(200, 300):
        return {
            "code": 500,
            "data": {"celery_result": celery_result},
            "message": "Error, sent for error handling."
        }

    # Step 9: Return Ticket up for Resale
    return {
        "code": 201,
        "data": {
            "ticketID": ticket.ticketID,
            "resalePrice": ticket.resalePrice
        },
        "message": "Ticket up for resale."
    }

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5101, debug=True)