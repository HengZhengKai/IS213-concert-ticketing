from flask import Flask, request, jsonify
from flask_cors import CORS
import os, sys
import qrcode
import uuid
import requests
from invokes import invoke_http

app = Flask(__name__)

CORS(app)

ticket_URL = "http://localhost:5004/ticket"

ticket_microservice_url = "http://localhost:5004/graphql"  # Ticket microservice runs on localhost:5004

# Function to check if the ticket is checked in using GraphQL
def is_ticket_checked_in(ticketID):
    query = """
    query GetTicketStatus($ticketID: String!) {
        isCheckedIn(ticketID: $ticketID)
    }
    """
    variables = {"ticketID": ticketID}
    response = requests.post(ticket_microservice_url, json={'query': query, 'variables': variables})
    
    if response.status_code == 200:
        data = response.json()
        if data.get("data") and "isCheckedIn" in data["data"]:
            return data["data"]["isCheckedIn"]
    return False  # Return False if ticket is not found or response is invalid

@app.route("/generateqr/<string:ticketID>", methods=['POST'])
def generate_qr(ticketID):
    pass

@app.route("/scanqr/<string:ticketID>", methods=['POST'])
def on_qr_scanned(ticketID):
    pass
