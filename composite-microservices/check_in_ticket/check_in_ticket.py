from flask import Flask, request, jsonify, send_file, make_response
from flask_cors import CORS
import os, sys
import segno
import uuid
import requests
from io import BytesIO
from invokes import invoke_http

import socket

hostname = socket.gethostname()
local_ip = socket.gethostbyname(hostname)

app = Flask(__name__)
CORS(app)  # Simple CORS configuration allowing all origins

ticket_URL = "http://kong:8000/ticket"

# Function to check if the ticket is checked in using GraphQL
def is_ticket_checked_in(ticketID):
    query = """
    query GetTicketStatus($ticketID: String!) {
        isCheckedIn(ticketID: $ticketID)
    }
    """
    variables = {"ticketID": ticketID}
    response = requests.post(f"{ticket_URL}/graphql", json={'query': query, 'variables': variables})
    
    if response.status_code == 200:
        data = response.json()
        if data.get("data") and "isCheckedIn" in data["data"]:
            return data["data"]["isCheckedIn"]
    return False  # Return False if ticket is not found or response is invalid

@app.route('/generateqr/<string:ticketID>', methods=['POST', 'OPTIONS'])
def generate_qr_code(ticketID):
    try:
        if request.method == 'OPTIONS':
            response = make_response()
            response.headers.add('Access-Control-Allow-Origin', '*')
            response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
            return response

        # Use current local IP to construct full scan URL
        scan_url = f"http://{local_ip}:5103/scanqr/{ticketID}"

        # Generate QR code using segno
        qr = segno.make(scan_url)
        
        # Create a BytesIO object to store the PNG data
        img_io = BytesIO()
        qr.save(img_io, kind='png', scale=10)  # Scale up for better visibility
        img_io.seek(0)

        response = make_response(send_file(img_io, mimetype='image/png'))
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response
        
    except Exception as e:
        print(f"Error generating QR code: {str(e)}")
        response = jsonify({"error": str(e)})
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response, 500

@app.route("/scanqr/<string:ticketID>", methods=['GET', 'POST'])
def on_qr_scanned(ticketID):
    if is_ticket_checked_in(ticketID):
        return jsonify({"error": "Ticket already checked in"}), 400

    print('\n-----Invoking ticket microservice-----')
    response = invoke_http(f"{ticket_URL}/{ticketID}", method='PUT', json={"isCheckedIn": True})

    if isinstance(response, dict) and response.get("code") == 200:
        return True  # Success
    return False  # Failed to update

@app.route("/checkstatus/<string:ticketID>", methods=['GET'])
def check_status(ticketID):
    if is_ticket_checked_in(ticketID):
        return jsonify({"status": "checked_in"})
    else:
        return jsonify({"status": "not_yet"})

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5103, debug=True)