from flask import Flask, request, jsonify
from flask_cors import CORS
from celery import Celery
import pika
import json
import os

# Initialize the Flask app context here if needed, otherwise just define Celery directly
app = Flask(__name__)
CORS(app)

# Get RabbitMQ host from environment variable or use default
RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'rabbitmq')
RABBITMQ_PORT = os.getenv('RABBITMQ_PORT', '5672')

app.config['broker_url'] = f'amqp://guest:guest@{RABBITMQ_HOST}:{RABBITMQ_PORT}//'
app.config['result_backend'] = 'rpc://'

# Add Celery configuration
app.config['broker_connection_retry_on_startup'] = True
app.config['broker_connection_max_retries'] = 100
app.config['broker_connection_retry_delay'] = 2

def create_celery_app(app):
    # Use new-style config keys
    celery = Celery(
        'task',  # Use module name instead of app.import_name
        broker=app.config['broker_url'],
        backend=app.config['result_backend']
    )

    # Update Celery config from Flask
    celery.conf.update(app.config)
    celery.conf.task_default_queue = 'email.waitlist.notification'
    celery.conf.task_always_eager = False

    return celery

# Create Celery app and Flask app
celery = create_celery_app(app)

# Celery task for sending email and publishing RabbitMQ messages
@celery.task(name='task.send_message')
def send_message(user_id, ticket):
    try:        
        # Message payload for email
        message = {
            "user_id": user_id,
            "event_id": ticket["event_id"],        
            "event_name": ticket["event_name"],
            "event_date": str(ticket["event_date"]),
        }
        
        # Send message via RabbitMQ
        connection = pika.BlockingConnection(pika.ConnectionParameters(
            host=RABBITMQ_HOST,
            port=RABBITMQ_PORT,
            credentials=pika.PlainCredentials('guest', 'guest')
        ))
        
        channel = connection.channel()
        
        # Declare exchange and queue
        channel.exchange_declare(exchange='ticketing', exchange_type='topic', durable=True)
        
        # Declare and bind the queue
        channel.queue_declare(queue='email.waitlist.notification', durable=True)
        channel.queue_bind(exchange='ticketing', queue='email.waitlist.notification', routing_key='waitlist.available')
        channel.basic_publish(
            exchange="ticketing",
            routing_key="waitlist.available",
            body=json.dumps(message),
            properties=pika.BasicProperties(
                delivery_mode=2,  # make message persistent
            )
        )
        
        connection.close()
        return True
    except Exception as e:
        return False

# Flask route triggering Celery task
@app.route('/send_waitlist_emails', methods=['POST'])
def send_waitlist_messages():
    try:
        if not request.is_json:

            return jsonify({
                "code": 400,
                "message": "Invalid JSON input"
            }), 400

        data = request.get_json()
        
        waitlist_users = data.get("waitlist_users", [])
        ticket = data.get("ticket", {})

        if not waitlist_users or not ticket:
            return jsonify({
                "code": 400,
                "message": "Missing required fields: waitlist_users or ticket"
            }), 400

        if not waitlist_users:
            return jsonify({
                "code": 200,
                "message": "No messages to be sent"
            }), 200

        for user in waitlist_users:
            task = send_message.delay(user["userID"], ticket)
        
        return jsonify({
            "code": 200,
            "message": "Messages are being sent"
        }), 200
    except Exception as e:
        return jsonify({
            "code": 500,
            "message": f"Internal server error: {str(e)}"
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5009, debug=True)