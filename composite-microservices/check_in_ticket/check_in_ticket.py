from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import os, sys
import qrcode
import uuid
import requests
from io import BytesIO
from invokes import invoke_http

import socket

hostname = socket.gethostname()
local_ip = socket.gethostbyname(hostname)

app = Flask(__name__)

CORS(app)

ticket_URL = "http://localhost:5004/ticket"

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

@app.route("/generateqr/<string:ticketID>", methods=['POST'])
def generate_qr(ticketID):
    if is_ticket_checked_in(ticketID) == True:
        return jsonify({"error": "Ticket already checked in"}), 400
    
    # Use current local IP to construct full scan URL
    scan_url = f"http://{local_ip}:5103/scanqr/{ticketID}"

    # Generate QR code
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(scan_url)
    qr.make(fit=True)

    img = qr.make_image(fill="black", back_color="white")

    # Save QR code to an in-memory file
    img_io = BytesIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)

    return send_file(img_io, mimetype='image/png')

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