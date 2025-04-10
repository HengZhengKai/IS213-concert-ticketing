from flask import Flask, request, jsonify, send_file, make_response, render_template
from flask_cors import CORS
import os, sys
import segno
import uuid
import requests
from io import BytesIO
from invokes import invoke_http
import base64

import socket

# Prioritize HOST_IP from environment variable, fallback to local IP detection
HOST_IP = os.environ.get('HOST_IP')
if not HOST_IP:
    try:
        hostname = socket.gethostname()
        HOST_IP = socket.gethostbyname(hostname)
    except socket.gaierror:
        HOST_IP = "127.0.0.1" # Final fallback
        print("Warning: Could not determine local IP, falling back to 127.0.0.1. External access might fail.")

print(f"Check-in service running with HOST_IP: {HOST_IP}")

app = Flask(__name__, template_folder='templates')
CORS(app)

# Assuming Kong gateway is running and configured
# Adjust these if your service discovery or naming is different
kong_base_url = "http://kong:8000"
ticket_URL = f"{kong_base_url}/ticket"
graphql_URL = f"{kong_base_url}/graphql"

# Function to check if the ticket is checked in using GraphQL
def is_ticket_checked_in(ticketID):
    query = """
    query GetTicketStatus($ticketID: String!) {
        isCheckedIn(ticketID: $ticketID)
    }
    """
    variables = {"ticketID": ticketID}
    print(f'\n-----Invoking GraphQL endpoint for status check: {graphql_URL}-----\n')
    try:
        response = requests.post(f"{graphql_URL}", json={'query': query, 'variables': variables})
        response.raise_for_status() # Raise an exception for bad status codes

        data = response.json()
        print("GraphQL Response Data:", data) # Debugging output

        # Check response structure carefully
        if data.get("data") and "isCheckedIn" in data["data"]:
             # Check if isCheckedIn is None, handle potential errors upstream
            if data["data"]["isCheckedIn"] is None:
                print(f"Warning: GraphQL returned null for isCheckedIn for ticket {ticketID}")
                return False # Treat null as not checked in or error
            return data["data"]["isCheckedIn"]
        elif data.get("errors"):
             print(f"GraphQL Errors: {data['errors']}")
             return False # Treat GraphQL errors as not checked in
        else:
            print(f"Unexpected GraphQL response structure for ticket {ticketID}")
            return False # Unexpected structure

    except requests.exceptions.RequestException as e:
        print(f"Error invoking GraphQL: {e}")
        # Consider the implications: if GraphQL is down, should we assume not checked in?
        return False # Treat connection errors etc. as not checked in for safety
    except json.JSONDecodeError:
        print("Error decoding GraphQL JSON response")
        return False

@app.route('/generateqr/<string:ticketID>', methods=['GET'])
def generate_qr_code_route(ticketID):
    try:
        # Use HOST_IP (env var or detected) to construct full scan URL
        # This URL is what the phone will open
        scan_url = f"http://{HOST_IP}:5103/scanqr/{ticketID}"
        print(f"Generating QR code for URL: {scan_url}")

        # Generate QR code using segno
        qr = segno.make(scan_url)

        # Create a BytesIO object to store the PNG data
        img_io = BytesIO()
        qr.save(img_io, kind='png', scale=10)  # Scale up for better visibility
        img_io.seek(0)

        # Send the image file directly
        response = make_response(send_file(img_io, mimetype='image/png'))
        # Allow browser caching for a short time if needed, but maybe not for unique tickets
        # response.headers['Cache-Control'] = 'public, max-age=60'
        return response

    except Exception as e:
        print(f"Error generating QR code: {str(e)}")
        return jsonify({"error": "Failed to generate QR code", "details": str(e)}), 500

@app.route('/displayqr/<string:ticketID>', methods=['GET'])
def display_qr(ticketID):
    # Optional: check if already checked in before displaying
    if is_ticket_checked_in(ticketID):
         return render_template('already_checked_in.html', ticketID=ticketID) # Or redirect to success

    # Pass ticketID to the template for use in JS and image source
    return render_template('display_qr.html', ticketID=ticketID)

@app.route("/scanqr/<string:ticketID>", methods=['GET'])
def on_qr_scanned(ticketID):
    print(f'\n-----Received QR scan for ticket: {ticketID}-----')
    
    # Check initial status
    initially_checked_in = is_ticket_checked_in(ticketID)

    if initially_checked_in:
        print(f'Ticket {ticketID} was already checked in.')
        return render_template('scan_result.html', message=f"Ticket {ticketID} was already checked in.")
    else:
        print(f'Ticket {ticketID} is not checked in yet. Attempting update...')
        print(f'\n-----Invoking ticket microservice to check-in: {ticket_URL}/{ticketID}-----')
        try:
            # Using the PUT request as per the original file's logic
            update_payload = {"isCheckedIn": True}
            response_data = invoke_http(f"{ticket_URL}/{ticketID}", method='PUT', json=update_payload)
            print(f"Ticket service update response: {response_data}")

            # Check if the update call was successful
            if isinstance(response_data, dict) and response_data.get("code") in range(200, 300):
                 print(f"Ticket {ticketID} successfully checked in via API.")
                 # Confirm check-in status *after* successful update if needed, 
                 # but for now, assume success means checked in.
                 return render_template('scan_result.html', message=f"Ticket {ticketID} checked in successfully!")
            else:
                print(f"Failed to update ticket {ticketID} status via API.")
                error_detail = response_data.get("message", "Update failed.") if isinstance(response_data, dict) else "Invalid response."
                return render_template('scan_result.html', message=f"Failed to check in ticket {ticketID}. Error: {error_detail}"), 500

        except Exception as e:
            print(f"Error during ticket update invocation: {e}")
            return render_template('scan_result.html', message=f"A server error occurred while checking in ticket {ticketID}."), 500

@app.route("/checkstatus/<string:ticketID>", methods=['GET'])
def check_status(ticketID):
    print(f"Polling status for ticket: {ticketID}") # Add log for polling
    if is_ticket_checked_in(ticketID):
        return jsonify({"status": "checked_in"})
    else:
        return jsonify({"status": "not_yet"})

@app.route("/success")
def success_page():
    return render_template('success.html')

if __name__ == "__main__":
    print("Starting Flask app...")
    # Make sure host is '0.0.0.0' to be accessible externally
    app.run(host='0.0.0.0', port=5103, debug=True) # Debug=True helps development