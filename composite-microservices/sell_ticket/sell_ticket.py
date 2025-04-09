from flask import Flask, request, jsonify
from flask_cors import CORS
import os, sys
import requests
import pika
import json
from invokes import invoke_http

app = Flask(__name__)

CORS(app)

waitlist_URL = "http://kong:8000/waitlist"
ticket_URL = "http://kong:8000"
user_URL = "http://localhost:5006/user"
email_URL = "http://localhost:5008/email"
celery_URL = "http://localhost:5009/send_waitlist_emails"

@app.route("/sellticket/<string:ticketID>", methods=['POST']) # json body: resalePrice
def sell_ticket(ticketID):
    if request.is_json:
        try:
            ticket = request.get_json()
            ticket["ticketID"] = ticketID  # ticket looks like {ticketID: T001, resalePrice: 80}
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
                "message": f"sell_ticket.py internal error: {ex_str}"
            }), 500

    # if reached here, not a JSON request.
    return jsonify({
        "code": 400,
        "message": "Invalid JSON input: " + str(request.get_data())
    }), 400

def process_sell_ticket(ticket):
    try:
        # Step 2-3. Update ticket resalePrice and status
        print('\n-----Invoking ticket microservice-----')
        json_body={"resalePrice": ticket["resalePrice"], "status": "available"}
        ticket_result = invoke_http(f"{ticket_URL}/ticket/{ticket['ticketID']}", method='PUT', json=json_body)

        # Check the ticket result; if a failure, do error handling.
        code = ticket_result["code"]
        if code not in range(200, 300):
            if code == 400:
                return {
                    "code": 400,
                    "message": "Resale price cannot be higher than the original price or the previous resale price."
                }
            else:
                return {
                    "code": 500,
                    "message": f"Ticket update failure, {ticket["ticketID"]} status code: {code} \n PUT URL: {ticket_URL}/ticket/{ticket['ticketID']} \n body: {json_body}",
                    "ticket_message": ticket_result["message"]
                }

        # Step 4-5. Query eventID and eventDateTime
        print('\n-----Querying ticket microservice-----')
        query = """
        query($ticketID: String!) {
            eventDetails(ticketID: $ticketID) {
                eventID
                eventName
                eventDateTime
            }
        }
        """
        variables = {"ticketID": ticket["ticketID"]}
        response = requests.post(f"{ticket_URL}/graphql", json={'query': query, 'variables': variables})

        # Check if response is valid
        if response.status_code != 200:
            return {
                "code": 500,
                "message": f"Failed to query event details, status code: {response.status_code}",
            }

        event_data = response.json()
    
        if "data" in event_data and event_data["data"]["eventDetails"]:
            eventID = event_data["data"]["eventDetails"]["eventID"]
            eventName = event_data["data"]["eventDetails"]["eventName"]
            eventDateTime = event_data["data"]["eventDetails"]["eventDateTime"]
        else:
            print("Error: Could not retrieve event details")
            return {"code": 500, "message": "Event details not found or invalid response from ticket service."}


        # Step 6-7. Get waitlist users
        print('\n-----Invoking waitlist microservice-----')
        waitlist_users = invoke_http(f"{waitlist_URL}/{eventID}/{eventDateTime}")

    
        if waitlist_users["data"]["waitlist"] == []:
            return{'code': 201,
                    "data": {
                    "ticketID": ticket["ticketID"],
                    "resalePrice": ticket["resalePrice"]
                },
                "message": "Ticket up for resale. No users on waitlist at the moment."
            }

        # Step 8: Email all waitlist users
        payload = {
            "waitlist_users": waitlist_users["data"]["waitlist"],
            "ticket": {
                "event_id": eventID,
                "event_name": eventName,
                "event_date": eventDateTime,
            }
        }

        celery_result = invoke_http(f"{celery_URL}", method='POST', json=payload)

        if celery_result["code"] not in range(200, 300):
            return {
                "code": 500,
                "message": f"Celery task failure, status code: {celery_result['code']}",
            }

        # Step 9: Return Ticket up for Resale
        return {
            "code": 201,
            "data": {
                "ticketID": ticket["ticketID"],
                "resalePrice": ticket["resalePrice"]
            },
            "message": "Ticket up for resale. Users on waitlist have been notified."
        }

    except Exception as e:
        return {
            "code": 500,
            "message": f"Error processing ticket sale: {str(e)}"
        }

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5101, debug=True)