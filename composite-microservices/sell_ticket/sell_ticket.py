from flask import Flask, request, jsonify
from flask_cors import CORS
import os, sys
import requests
import pika
import json
from invokes import invoke_http

app = Flask(__name__)

CORS(app) # Restore CORS

waitlist_URL = "http://kong:8000/waitlist"
ticket_URL = "http://kong:8000/ticket"
graphql_URL = "http://kong:8000/graphql"
celery_URL = "http://kong:8000/send_waitlist_emails"

@app.route("/sellticket/<string:ticketID>", methods=['POST']) # json body: resalePrice
def sell_ticket(ticketID):
    if request.is_json:
        try:
            ticket = request.get_json()
            ticket["ticketID"] = ticketID

            # 1. Put ticket up for sale
            result = process_sell_ticket(ticket)
            return jsonify(result), result["code"]

        except Exception as e:
            # Unexpected error in code
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            ex_str = str(e) + " at " + str(exc_type) + ": " + fname + ": line " + str(exc_tb.tb_lineno)
            print(ex_str, flush=True)

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
        # === Step 1: Query current ticket status via REST ===
        print('\n----- Checking current ticket status via REST -----', flush=True)
        ticket_details_url = f"{ticket_URL}/{ticket['ticketID']}"
        ticket_details_result = invoke_http(ticket_details_url, method='GET')
        
        if ticket_details_result.get("code") != 200:
             return {"code": ticket_details_result.get("code", 500), "message": f"Failed to query current ticket status: {ticket_details_result.get('message', 'Unknown error')}"} 
        
        current_status = ticket_details_result.get("data", {}).get("status")
        
        if not current_status:
             return {"code": 500, "message": "Failed to parse current ticket status."} 

        # === Step 1b: Check if already for resale ===
        if current_status == 'available':
             print(f"Ticket {ticket['ticketID']} is already listed for resale (status: {current_status}). Aborting PUT, returning 409 Conflict.", flush=True)
             return {
                 "code": 409,
                 "message": "Ticket is already listed for resale."
             }
        
        # === Step 2-3: Update ticket resalePrice and status ===
        print('\n-----Invoking ticket microservice to update status to available-----', flush=True)
        json_body={"resalePrice": ticket["resalePrice"], "status": "available"}
        update_url = f"{ticket_URL}/{ticket['ticketID']}"
        ticket_result = invoke_http(update_url, method='PUT', json=json_body)

        # Check the ticket result; if a failure, do error handling.
        code = ticket_result.get("code")
        if code is None or code not in range(200, 300):
            if code == 400:
                return {
                    "code": 400,
                    "message": ticket_result.get("message", "Resale price cannot be higher than the original price or the previous resale price.")
                }
            else:
                return {
                    "code": 500,
                    "message": f"Ticket update failure, {ticket['ticketID']} status code: {code} \n PUT URL: {update_url} \n body: {json_body}",
                    "ticket_message": ticket_result.get("message", "Unknown error from ticket service")
                }

        # Step 4-5. Query eventID and eventDateTime
        print('\n-----Querying ticket microservice-----', flush=True)
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
        response = requests.post(graphql_URL, json={'query': query, 'variables': variables})

        # Check if response is valid
        if response.status_code != 200:
            return {
                "code": 500,
                "message": f"Failed to query event details, status code: {response.status_code}",
            }

        event_data = response.json()
    
        if "data" in event_data and event_data["data"].get("eventDetails"): # Safer access
            event_details = event_data["data"]["eventDetails"]
            eventID = event_details.get("eventID")
            eventName = event_details.get("eventName")
            eventDateTime = event_details.get("eventDateTime")
            if not all([eventID, eventName, eventDateTime]): # Check if any detail is missing
                 return {"code": 500, "message": "Incomplete event details received."}
        else:
            return {"code": 500, "message": "Event details not found or invalid response from ticket service."}


        # Step 6-7. Get waitlist users
        print('\n-----Invoking waitlist microservice-----', flush=True)
        waitlist_invoke_url = f"{waitlist_URL}/{eventID}/{eventDateTime}"
        waitlist_users = invoke_http(waitlist_invoke_url)

        # Safer check for waitlist data
        waitlist_data = waitlist_users.get("data", {}).get("waitlist", None)
        if waitlist_data is None:
             return{'code': 500, 
                    "message": "Ticket listed, but failed to retrieve waitlist. Cannot notify users."}

        if not waitlist_data: # Empty list is okay
            print("No users on waitlist.", flush=True)
            return{'code': 201,
                    "data": {
                    "ticketID": ticket["ticketID"],
                    "resalePrice": ticket["resalePrice"]
                },
                "message": "Ticket up for resale. No users on waitlist at the moment."
            }

        # Step 8: Email all waitlist users through fire and forget
        payload = {
            "waitlist_users": waitlist_data,
            "ticket": {
                "event_id": eventID,
                "event_name": eventName,
                "event_date": eventDateTime,
            }
        }

        celery_result = invoke_http(celery_URL, method='POST', json=payload)

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
        # Log the exception from process_sell_ticket
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        ex_str = str(e) + " at " + str(exc_type) + ": " + fname + ": line " + str(exc_tb.tb_lineno)
        return {
            "code": 500,
            "message": f"Error processing ticket sale: {str(e)}"
        }

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5101, debug=True)