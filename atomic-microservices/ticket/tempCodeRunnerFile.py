

    # Get the request data to update
    data = request.get_json()

    # Validate resalePrice if present in the request
    if 'resalePrice' in data:
        new_resale_price = data['resalePrice']
        if new_resale_price > ticket.price or (ticket.resalePrice is not None and new_resale_price > ticket.resalePrice):
            return jsonify({
                "code": 400,
                "data": {"ticketID": ticketID},
                "message": "Resale price cannot be higher than the original price or the previous resale price."
            }), 400

    # If the status is being updated, check for conflicts