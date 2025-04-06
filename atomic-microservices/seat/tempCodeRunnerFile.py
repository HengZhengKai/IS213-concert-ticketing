def get_all_seats():
    try:
        seats = Seat.objects()
        return jsonify({
            "code": 200,
            "data": {
                "seats": [seat.to_json() for seat in seats]
            }
        })
    except Exception as e:
        return jsonify({
            "code": 500,
            "message": f"Error retrieving seats: {str(e)}"
        }), 500