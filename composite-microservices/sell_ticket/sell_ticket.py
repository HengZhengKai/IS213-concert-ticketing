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
ticket_URL = os.environ.get('ticket_service_URL') or "http://localhost:5004" # Use ENV variable
celery_URL = "http://kong:8000/send_waitlist_emails"

@app.route("/sellticket/<string:ticketID>", methods=['POST']) # json body: resalePrice
def sell_ticket(ticketID):
    print(f"--- sell_ticket route entered for ticketID: {ticketID} ---", flush=True) # Keep this initial print
    if request.is_json:
        print("--- Request is JSON ---", flush=True)
        try:
            print("--- Inside try block ---", flush=True)
            ticket = request.get_json()
            print("--- Got JSON data ---", ticket, flush=True)
            ticket["ticketID"] = ticketID
            print("\nReceived a ticket in JSON:", ticket, flush=True)

            # 1. Put ticket up for sale
            print("--- Calling process_sell_ticket ---", flush=True)
            result = process_sell_ticket(ticket)
            print("--- process_sell_ticket returned ---", result, flush=True)
            return jsonify(result), result["code"]

        except Exception as e:
            # Unexpected error in code
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            ex_str = str(e) + " at " + str(exc_type) + ": " + fname + ": line " + str(exc_tb.tb_lineno)
            print("--- Exception caught in sell_ticket ---", flush=True)
            print(ex_str, flush=True)

            return jsonify({
                "code": 500,
                "message": f"sell_ticket.py internal error: {ex_str}"
            }), 500
    else:
        print("--- Request is NOT JSON ---", flush=True)
        print("Request Data:", request.get_data(), flush=True)

    # if reached here, not a JSON request.
    print("--- Returning 400: Invalid JSON input ---", flush=True)
    return jsonify({
        "code": 400,
        "message": "Invalid JSON input: " + str(request.get_data())
    }), 400

def process_sell_ticket(ticket):
    try:
        # === Step 1: Query current ticket status via REST ===
        print('\n----- Checking current ticket status via REST -----', flush=True)
        ticket_details_url = f"{ticket_URL}/ticket/{ticket['ticketID']}"
        print(f"Attempting to GET ticket details from: {ticket_details_url}", flush=True)
        ticket_details_result = invoke_http(ticket_details_url, method='GET')
        print(f"Ticket details response: {ticket_details_result}", flush=True)
        
        if ticket_details_result.get("code") != 200:
             print(f"Failed to get ticket details. Status: {ticket_details_result.get('code')}, Response: {ticket_details_result.get('message')}", flush=True)
             # Use 500 or potentially map the code (e.g., 404 if not found)
             return {"code": ticket_details_result.get("code", 500), "message": f"Failed to query current ticket status: {ticket_details_result.get('message', 'Unknown error')}"} 
        
        current_status = ticket_details_result.get("data", {}).get("status")
        
        if not current_status:
             print("Error: Could not retrieve current ticket status from response.", flush=True)
             return {"code": 500, "message": "Failed to parse current ticket status."} 

        # === Step 1b: Check if already for resale ===
        if current_status == 'available':
             print(f"Ticket {ticket['ticketID']} is already listed for resale (status: {current_status}). Aborting PUT, returning 409 Conflict.", flush=True)
             # Return 409 Conflict as requested
             return {
                 "code": 409,
                 "message": "Ticket is already listed for resale."
             }
        
        # === Step 2-3: Update ticket resalePrice and status ===
        print('\n-----Invoking ticket microservice to update status to available-----', flush=True)
        json_body={"resalePrice": ticket["resalePrice"], "status": "available"}
        update_url = f"{ticket_URL}/ticket/{ticket['ticketID']}" # Corrected URL construction
        print(f"Attempting to PUT to: {update_url}", flush=True)
        ticket_result = invoke_http(update_url, method='PUT', json=json_body)

        # Check the ticket result; if a failure, do error handling.
        code = ticket_result.get("code")
        if code is None or code not in range(200, 300):
            print(f"Ticket update failed. Response: {ticket_result}", flush=True)
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
        graphql_url = f"{ticket_URL}/graphql"
        print(f"Attempting GraphQL query to: {graphql_url}", flush=True)
        response = requests.post(graphql_url, json={'query': query, 'variables': variables})

        # Check if response is valid
        if response.status_code != 200:
            print(f"GraphQL query failed. Status: {response.status_code}", flush=True)
            return {
                "code": 500,
                "message": f"Failed to query event details, status code: {response.status_code}",
            }

        event_data = response.json()
        print(f"GraphQL response data: {event_data}", flush=True)
    
        if "data" in event_data and event_data["data"].get("eventDetails"): # Safer access
            event_details = event_data["data"]["eventDetails"]
            eventID = event_details.get("eventID")
            eventName = event_details.get("eventName")
            eventDateTime = event_details.get("eventDateTime")
            if not all([eventID, eventName, eventDateTime]): # Check if any detail is missing
                 print("Error: Incomplete event details received from GraphQL", flush=True)
                 return {"code": 500, "message": "Incomplete event details received."}
        else:
            print("Error: Could not retrieve event details from GraphQL response", flush=True)
            return {"code": 500, "message": "Event details not found or invalid response from ticket service."}


        # Step 6-7. Get waitlist users
        print('\n-----Invoking waitlist microservice-----', flush=True)
        waitlist_invoke_url = f"{waitlist_URL}/{eventID}/{eventDateTime}"
        print(f"Attempting to GET waitlist from: {waitlist_invoke_url}", flush=True)
        waitlist_users = invoke_http(waitlist_invoke_url)
        print(f"Waitlist response: {waitlist_users}", flush=True)

        # Safer check for waitlist data
        waitlist_data = waitlist_users.get("data", {}).get("waitlist", None)
        if waitlist_data is None:
             print("Error: Invalid waitlist response format.", flush=True)
             # Decide if this is critical; maybe proceed without notification?
             # For now, let's return an error, but indicate the ticket IS listed.
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
        print(f"Found {len(waitlist_data)} users on waitlist. Attempting to notify.", flush=True)
        payload = {
            "waitlist_users": waitlist_data,
            "ticket": {
                "event_id": eventID,
                "event_name": eventName,
                "event_date": eventDateTime,
            }
        }

        print(f"Attempting POST to Celery at: {celery_URL}", flush=True)
        celery_result = invoke_http(celery_URL, method='POST', json=payload)
        print(f"Celery response: {celery_result}", flush=True)
        # Note: We typically don't wait for or check celery_result in fire-and-forget

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
        print(f"--- Exception caught in process_sell_ticket ---: {ex_str}", flush=True)
        return {
            "code": 500,
            "message": f"Error processing ticket sale: {str(e)}"
        }

if __name__ == "__main__":
    print("Starting sell_ticket service...")
    app.run(host="0.0.0.0", port=5101, debug=True)