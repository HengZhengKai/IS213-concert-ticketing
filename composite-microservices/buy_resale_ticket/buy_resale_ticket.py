from flask import Flask, request, jsonify
from flask_cors import CORS
import os, sys
import requests
from invokes import invoke_http

app = Flask(__name__)

CORS(app)

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
    # Step 4. Update ticket reserved for user
    print('\n-----Invoking ticket microservice-----')
    ticket_result = invoke_http(f"{ticket_URL}/{ticketID}", method='PUT', json={"status": "reseved"})
    
    # Step 5. Return ticket reserved
    print('ticket_result:', ticket_result)

    # Step 6-8: Invoke payment service

# Execute this program if it is run as a main script (not by 'import')
if __name__ == "__main__":
    print("This is flask " + os.path.basename(__file__) +
          " for placing an order...")
    app.run(host="0.0.0.0", port=5101, debug=True)
    # Notes for the parameters:
    # - debug=True will reload the program automatically if a change is detected;
    #   -- it in fact starts two instances of the same flask program,
    #       and uses one of the instances to monitor the program changes;
    # - host="0.0.0.0" allows the flask program to accept requests sent from any IP/host (in addition to localhost),
    #   -- i.e., it gives permissions to hosts with any IP to access the flask program,
    #   -- as long as the hosts can already reach the machine running the flask program along the network;
    #   -- it doesn't mean to use http://0.0.0.0 to access the flask program.