from flask import Flask, request, jsonify
from flask_cors import CORS
import os, sys
import requests
from invokes import invoke_http

app = Flask(__name__)

CORS(app)

waitlist_URL = "http://localhost:5003/waitlist"
ticket_URL = "http://localhost:5004/ticket"
user_URL = "http://localhost:5006/user"

## can work on this first, no need stripe api implementation yet
@app.route("/sellticket/<string:ticketID>", methods=['POST']) # json body: resalePrice
def sell_ticket(ticketID):
    if request.is_json:
        try:
            ticket = request.get_json()
            ticket["ticketID"] = ticketID
            # so now ticket looks like {tickekID: T001, resalePrice: 80}
            print("\nReceived a ticket in JSON:", ticket)

            # do the actual work
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
    # Step 2. Update ticket resalePrice and status
    print('\n-----Invoking ticket microservice-----')
    ticket_result = invoke_http(f"{ticket_URL}/{ticket.ticketID}", method='PUT', json={"resalePrice": ticket.resalePrice, "status": "available"})
