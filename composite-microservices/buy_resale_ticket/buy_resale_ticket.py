from flask import Flask, request, jsonify
from flask_cors import CORS
import uuid
import os, sys
import requests
import pika
import json
from invokes import invoke_http

app = Flask(__name__)

CORS(app)

connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()

waitlist_URL = "http://localhost:5003/waitlist"
ticket_URL = "http://localhost:5004/ticket"
transaction_URL = "http://localhost:5005/transaction"
user_URL = "http://localhost:5006/user"
payment_URL = "http://localhost:5007/payment"

@app.route("/buyresaleticket/<string:ticketID>", methods=['POST'])
def buy_resale_ticket(ticketID):
    try:
        print(f"\nReceived a request to buy resale ticket with ID: {ticketID}")

        # Step 3. Process ticket using only the ticketID
        result = process_buy_resale_ticket(ticketID)  # Pass only ticketID

        return jsonify(result), result["code"]

    except Exception as e:
        # Unexpected error in code
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        ex_str = f"{str(e)} at {str(exc_type)}: {fname}: line {str(exc_tb.tb_lineno)}"
        print(ex_str)

        return jsonify({
            "code": 500,
            "message": "buy_resale_ticket.py internal error: " + ex_str
        }), 500
    
def process_buy_resale_ticket(ticketID):
    # Step 4-5. Update ticket reserved for user
    print('\n-----Invoking ticket microservice-----')
    ticket_result = invoke_http(f"{ticket_URL}/{ticketID}", method='PUT', json={"status": "reseved"})

    # Step 6-7: Get paymentID for refund
    query = """
    query GetPaymentId($ticketID: String!) {
        paymentId(ticketID: $ticketID)
    }
    """
    variables = {"ticketID": ticketID}
    response = requests.post(f"{ticket_URL}/graphql", json={'query': query, 'variables': variables})
    
    if response.status_code == 200:
        data = response.json()
        if data.get("data") and "paymentId" in data["data"]:
            paymentID = data["data"]["paymentId"]

    # Step 8-9: Invoke payment service to refund charge



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5101, debug=True)