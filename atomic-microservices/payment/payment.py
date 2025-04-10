from flask import Flask, jsonify, request, redirect
from flask_cors import CORS
import os
import logging
import urllib.parse
import mongoengine as db
from dotenv import load_dotenv
load_dotenv()
import requests
import stripe

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

CORS(app)

@app.route("/start-checkout", methods=["POST"])
def start_checkout():
    try:
          
        stripe_key = os.getenv("STRIPE_SECRET_KEY")
        
        data = request.get_json()

        # Extract values safely
        mode = data.get("mode")
        success_url = data.get("success_url")
        cancel_url = data.get("cancel_url")
        currency = data.get("currency")
        product_name = data.get("product_name")
        unit_amount = data.get("unit_amount")
        quantity = data.get("quantity")

        # ✅ Stripe key
        stripe_key = os.getenv("STRIPE_SECRET_KEY")

        # External endpoint for your custom Stripe handler
        outsystems_url = "https://personal-5nnqipga.outsystemscloud.com/Stripe/rest/payments/checkout"

        payload = {
            "mode": mode,
            "success_url": success_url,
            "cancel_url": cancel_url,
            "currency": currency,
            "product_name": product_name,
            "unit_amount": unit_amount,
            "quantity": quantity
        }

        headers = {
             "Content-Type": "application/json",
             "Authorization": f"Bearer {stripe_key}"}
        

        response = requests.post(outsystems_url, json=payload, headers=headers)
        response.raise_for_status()

        data = response.json()
        checkout_url = data.get("url") or data.get("checkout_url")
        if not checkout_url:
            return jsonify({"error": "No checkout URL in response"}), 500
        return jsonify({"checkout_url": checkout_url})

    except Exception as e:
      import traceback
      traceback.print_exc()
      return jsonify({"error": str(e)}), 500

@app.route('/makerefund', methods=['POST'])
def make_refund():
        try:
            # Get Stripe secret key from environment variable
            stripe_key = os.getenv("STRIPE_SECRET_KEY")

            # Get refund request data
            req_data = request.get_json()
            payment_intent = req_data.get("payment_intent")
            reason = req_data.get("reason", "")  # Optional

            if not payment_intent:
                return jsonify({"error": "Missing required field: payment_intent"}), 400

            refund_url = "https://personal-5nnqipga.outsystemscloud.com/Stripe/rest/payments/refund"
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {stripe_key}"
            }

            payload = {
                "payment_intent": payment_intent,
                "reason": reason
            }

            response = requests.post(refund_url, json=payload, headers=headers)

            if response.status_code == 200:
                return jsonify({"success": True, "refund": response.json()}), 200
            else:
                return jsonify({"error": "Refund failed", "details": response.text}), response.status_code

        except Exception as e:
            return jsonify({"error": str(e)}), 500
        


@app.route('/verify-payment')
def verify_payment():
    session_id = request.args.get("session_id")
    stripe.api_key = os.getenv("STRIPE_SECRET_KEY")  

    try:
        session = stripe.checkout.Session.retrieve(session_id)

        payment_intent_id = session.payment_intent
        payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)

        return jsonify({
            # "amount_total": session.amount_total,
             "payment_intent_id": payment_intent_id
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5007, debug=True)
