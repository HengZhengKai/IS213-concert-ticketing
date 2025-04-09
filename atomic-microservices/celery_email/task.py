from flask import Flask, request, jsonify
from flask_cors import CORS
from celery import Celery
import pika
import json

# Initialize the Flask app context here if needed, otherwise just define Celery directly
app = Flask(__name__)
CORS(app)

app.config['broker_url'] = 'pyamqp://guest@localhost//'
app.config['result_backend'] = 'rpc://'


def create_celery_app(app):
    # Use new-style config keys

    celery = Celery(
        app.import_name,
        broker=app.config['broker_url'],
        backend=app.config['result_backend']
    )

    # Update Celery config from Flask
    celery.conf.update(app.config)

    celery.conf.task_always_eager = False

    return celery

# Create Celery app and Flask app
celery = create_celery_app(app)

# Celery task for sending email and publishing RabbitMQ messages
@celery.task
def send_message(user_id, ticket):
    # Message payload for email
    message = {
        "user_id": user_id,
        "event_id": ticket["event_id"],        
        "event_name": ticket["event_name"],
        "event_date": str(ticket["event_date"]),
    }
    
    # Send message via RabbitMQ or other necessary channels
    connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
    channel = connection.channel()
    channel.exchange_declare(exchange='ticketing', exchange_type='topic', durable=True)
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
            # waitlist_users": [{
            #     "userID": "U366",
            #     "waitlistDate": "2025-04-08T06:46:08.648000"
            # }]
            #     "ticket": {
            #     "event_id": eventID,
            #     "event_name": eventName,
            #     "event_date": eventDateTime,
            # }
    
    if waitlist_users == []:
        return jsonify({
            "code": 200,
            "message": "No messages to be sent"}),200

    for user in waitlist_users:
        send_message.delay(user["userID"], ticket)  # Send task to Celery workers
    
    return jsonify({
        "code": 200,
        "message": "Messages are being sent"}),200

# To call the task:
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5009, debug=True)