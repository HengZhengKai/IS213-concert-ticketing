from flask import Flask, request, jsonify
from flask_cors import CORS
from celery import Celery
import pika
import json

# Initialize the Flask app context here if needed, otherwise just define Celery directly
def create_celery_app():
    # Celery instance tied to a Flask app context
    app = Flask(__name__)
    CORS(app)

    # Celery configuration
    app.config['CELERY_BROKER_URL'] = 'pyamqp://guest@localhost//'
    app.config['CELERY_RESULT_BACKEND'] = 'rpc://'

    celery = Celery(
        app.import_name,
        backend=app.config['CELERY_RESULT_BACKEND'],
        broker=app.config['CELERY_BROKER_URL']
    )
    celery.conf.update(app.config)

    return celery, app

# Create Celery app and Flask app
celery, app = create_celery_app()

# Celery task for sending email and publishing RabbitMQ messages
@celery.task
def send_message(user, ticket):
    # Message payload for email
    message = {
        "user_id": user["user_id"],
        "user_name": user["user_name"],
        "event_id": ticket["event_id"],        
        "event_name": ticket["event_name"],
        "event_date": str(ticket["event_date"]),
        "expiration_time": str(ticket["expiration_time"])
    }
    
    # Send message via RabbitMQ or other necessary channels
    connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
    channel = connection.channel()
    channel.basic_publish(
        exchange="ticketing",
        routing_key="waitlist.available",
        body=json.dumps(message)
    )
    connection.close()

# Flask route triggering Celery task
@app.route('/send_waitlist_emails', methods=['POST'])
def send_waitlist_messages():
    waitlist_users = request.json["waitlist_users"]
    ticket = request.json["ticket"]
    
    if waitlist_users == []:
        return jsonify({
            "code": 200,
            "message": "No messages to be sent"}),200

    for user in waitlist_users:
        send_message.delay(user["userID"], ticket)  # Send task to Celery workers
    
    return jsonify({
        "code": 200,
        "message": "Messages are being sent"}),200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5009, debug=True)