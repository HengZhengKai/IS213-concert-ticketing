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
        print(f"[Celery Task] Starting send_message task for user_id: {user_id}")
        
        # Message payload for email
        message = {
            "user_id": user_id,
            "event_id": ticket["event_id"],        
            "event_name": ticket["event_name"],
            "event_date": str(ticket["event_date"]),
        }
        
        print(f"[Celery Task] Message payload: {message}")
        
        # Send message via RabbitMQ
        print(f"[Celery Task] Attempting to connect to RabbitMQ at {RABBITMQ_HOST}:{RABBITMQ_PORT}")
        connection = pika.BlockingConnection(pika.ConnectionParameters(
            host=RABBITMQ_HOST,
            port=RABBITMQ_PORT,
            credentials=pika.PlainCredentials('guest', 'guest')
        ))
        print("[Celery Task] Successfully connected to RabbitMQ")
        
        channel = connection.channel()
        print("[Celery Task] Channel created")
        
        # Declare exchange and queue
        channel.exchange_declare(exchange='ticketing', exchange_type='topic', durable=True)
        print("[Celery Task] Exchange declared")
        
        # Declare and bind the queue
        channel.queue_declare(queue='email.waitlist.notification', durable=True)
        channel.queue_bind(exchange='ticketing', queue='email.waitlist.notification', routing_key='waitlist.available')
        print("[Celery Task] Queue declared and bound")
        
        print("[Celery Task] Publishing message to RabbitMQ...")
        channel.basic_publish(
            exchange="ticketing",
            routing_key="waitlist.available",
            body=json.dumps(message),
            properties=pika.BasicProperties(
                delivery_mode=2,  # make message persistent
            )
        )
        print("[Celery Task] Message published successfully")
        
        connection.close()
        print("[Celery Task] Connection closed")
        return True
    except Exception as e:
        print(f"[Celery Task] Error sending message: {str(e)}")
        return False

# Flask route triggering Celery task
@app.route('/send_waitlist_emails', methods=['POST'])
def send_waitlist_messages():
    try:
        print("[Flask Route] Received POST request to /send_waitlist_emails")
        print(f"[Flask Route] Request headers: {request.headers}")
        
        if not request.is_json:
            print("[Flask Route] Request is not JSON")
            print(f"[Flask Route] Request data: {request.get_data()}")
            return jsonify({
                "code": 400,
                "message": "Invalid JSON input"
            }), 400

        data = request.get_json()
        print(f"[Flask Route] Received data: {data}")
        
        waitlist_users = data.get("waitlist_users", [])
        ticket = data.get("ticket", {})

        print(f"[Flask Route] Processing {len(waitlist_users)} waitlist users")
        print(f"[Flask Route] Ticket details: {ticket}")

        if not waitlist_users or not ticket:
            print("[Flask Route] Missing required fields")
            return jsonify({
                "code": 400,
                "message": "Missing required fields: waitlist_users or ticket"
            }), 400

        if not waitlist_users:
            print("[Flask Route] No waitlist users to process")
            return jsonify({
                "code": 200,
                "message": "No messages to be sent"
            }), 200

        for user in waitlist_users:
            print(f"[Flask Route] Dispatching Celery task for user {user['userID']}")
            task = send_message.delay(user["userID"], ticket)
            print(f"[Flask Route] Task dispatched with ID: {task.id}")
        
        print("[Flask Route] All tasks dispatched successfully")
        return jsonify({
            "code": 200,
            "message": "Messages are being sent"
        }), 200
    except Exception as e:
        print(f"[Flask Route] Error: {str(e)}")
        import traceback
        print(f"[Flask Route] Traceback: {traceback.format_exc()}")
        return jsonify({
            "code": 500,
            "message": f"Internal server error: {str(e)}"
        }), 500

if __name__ == '__main__':
    # Start Flask app
    print("Starting Flask application...")
    app.run(host='0.0.0.0', port=5009, debug=True)