from flask import Flask, request, jsonify
from flask_cors import CORS
import pika
import json
import os
import smtplib
import logging
import threading
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import time  # Add this to the top of your imports

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Flask app setup
app = Flask(__name__)
CORS(app)

# Email configuration
SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
EMAIL_USERNAME = os.getenv('EMAIL_USERNAME')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
SENDER_EMAIL = os.getenv('SENDER_EMAIL', EMAIL_USERNAME)

# RabbitMQ configuration
RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'localhost')
RABBITMQ_PORT = int(os.getenv('RABBITMQ_PORT', 5672))
RABBITMQ_USER = os.getenv('RABBITMQ_USER', 'guest')
RABBITMQ_PASS = os.getenv('RABBITMQ_PASS', 'guest')

# User Service configuration
USER_SERVICE_URL = os.getenv('USER_SERVICE_URL', 'http://user-service:5006')

# Global variables
rabbitmq_connection = None
rabbitmq_channel = None
consumer_thread = None
is_consuming = False

def get_user_email(user_id):
    """
    Get user email from User Service
    
    Args:
        user_id (str): User ID
            
    Returns:
        str: User email address or None if not found
    """
    try:
        response = requests.get(f"{USER_SERVICE_URL}/user/{user_id}")
        
        if response.status_code == 200:
            user_data = response.json()
            if 'data' in user_data and 'email' in user_data['data']:
                return user_data['data']['email']
        
        logger.warning(f"Failed to get email for user {user_id}. Status code: {response.status_code}")
        return None
    except Exception as e:
        logger.error(f"Error fetching user email: {e}")
        return None

def get_user_tickets(user_id):
    """
    Get all tickets for a specific user from Ticket Service
    
    Args:
        user_id (str): User ID
            
    Returns:
        list: List of ticket details or empty list if none found
    """
    try:
        TICKET_SERVICE_URL = os.getenv('TICKET_SERVICE_URL', 'http://ticket-service:5004')
        
        response = requests.get(f"{TICKET_SERVICE_URL}/ticket/{user_id}")
        
        if response.status_code == 200:
            return response.json().get('data', [])
        
        logger.warning(f"Failed to get tickets for user {user_id}. Status code: {response.status_code}")
        return []
    except Exception as e:
        logger.error(f"Error fetching user tickets: {e}")
        return []
    
def connect_to_rabbitmq():
    """Establish connection to RabbitMQ"""
    global rabbitmq_connection, rabbitmq_channel
    
    try:
        # Create connection parameters
        credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
        parameters = pika.ConnectionParameters(
            host=RABBITMQ_HOST,
            port=RABBITMQ_PORT,
            credentials=credentials,
            connection_attempts=3,  # Retry connection 3 times
            retry_delay=5,          # Wait 5 seconds between retries
            heartbeat=600,
            blocked_connection_timeout=300
        )
        
        # Connect to RabbitMQ
        rabbitmq_connection = pika.BlockingConnection(parameters)
        rabbitmq_channel = rabbitmq_connection.channel()
        
        # Declare exchange
        rabbitmq_channel.exchange_declare(
            exchange='ticketing',
            exchange_type='topic',
            durable=True
        )
        
        # Declare queues and bind them
        declare_queues()
        
        logger.info("Successfully connected to RabbitMQ")
        return True
    except Exception as e:
        logger.error(f"Failed to connect to RabbitMQ: {e}")
        return False

def declare_queues():
    """Declare queues and bind them to the exchange with appropriate routing keys"""
    global rabbitmq_channel
    
    queue_bindings = {
        'email.ticket.purchase': ['ticket.purchased', 'payment.successful'],
        'email.ticket.resale': ['ticket.resold'],
        'email.ticket.checkin': ['ticket.checkedin'],
        'email.payment.confirmation': ['payment.successful'],
        'email.waitlist.notification': ['waitlist.available'],
    }
    
    for queue_name, routing_keys in queue_bindings.items():
        rabbitmq_channel.queue_declare(queue=queue_name, durable=True)
        for routing_key in routing_keys:
            rabbitmq_channel.queue_bind(
                exchange='ticketing',
                queue=queue_name,
                routing_key=routing_key
            )

def send_email(recipient, subject, html_content):
    """Send email using SMTP"""
    try:
        # Create message container
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = SENDER_EMAIL
        msg['To'] = recipient
        
        # Attach HTML content
        html_part = MIMEText(html_content, 'html')
        msg.attach(html_part)
        
        # Connect to SMTP server
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()  # Secure the connection
            server.login(EMAIL_USERNAME, EMAIL_PASSWORD)
            server.sendmail(SENDER_EMAIL, recipient, msg.as_string())
            
        logger.info(f"Email sent to {recipient}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False

def handle_ticket_purchase(ch, method, properties, body):
    """Handle ticket purchase email"""
    try:
        data = json.loads(body)
        logger.info(f"Received ticket purchase notification: {data}")
        
        # Get required data
        user_id = data.get('user_id')
        user_name = data.get('user_name', 'Customer')
        ticket_id = data.get('ticket_id')
        event_id = data.get('event_id')
        event_name = data.get('event_name')
        event_date = data.get('event_date')
        seat_no = data.get('seat_no')
        seat_category = data.get('seat_category')
        seat_info = data.get('seat_info') or f"{seat_category}, Seat {seat_no}"
        price = data.get('price', 0)
        
        # Get user email
        user_email = data.get('user_email')
        if not user_email and user_id:
            user_email = get_user_email(user_id)
            
        if not user_email:
            logger.error("No email address found for ticket purchase notification")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            return
        
        # Create email content
        subject = f"Your Ticket for {event_name}"
        
        html_content = f"""
        <html>
        <body>
            <h2>Your Ticket Purchase Confirmation</h2>
            <p>Thank you for your purchase, {user_name}!</p>
            <p>Event: <strong>{event_name}</strong> (ID: {event_id})</p>
            <p>Date: {event_date}</p>
            <p>Ticket ID: {ticket_id}</p>
            <p>Seat: {seat_no}</p>
            <p>Category: {seat_category}</p>
            <p>Price: ${price}</p>
            <p>Please show this email or your ticket ID when checking in.</p>
        </body>
        </html>
        """
        
        # Send email
        send_email(user_email, subject, html_content)
        
        # Acknowledge message
        ch.basic_ack(delivery_tag=method.delivery_tag)
        logger.info(f"Ticket purchase email sent to {user_email}")
        
    except Exception as e:
        logger.error(f"Error processing ticket purchase: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

def handle_ticket_resale(ch, method, properties, body):
    """Handle ticket resale email"""
    try:
        data = json.loads(body)
        logger.info(f"Received ticket resale notification: {data}")
        
        # Get required data
        buyer_id = data.get('buyer_id')
        buyer_name = data.get('buyer_name', 'Customer')
        seller_id = data.get('seller_id')
        seller_name = data.get('seller_name', 'Customer')
        ticket_id = data.get('ticket_id')
        event_id = data.get('event_id')
        event_name = data.get('event_name')
        seat_no = data.get('seat_no')
        seat_category = data.get('seat_category')
        price = data.get('price', 0)
        charge_id = data.get('charge_id', 'N/A')
        refund_amount = data.get('refund_amount', price)
        
        # Get emails
        buyer_email = data.get('buyer_email')
        seller_email = data.get('seller_email')
        
        if not buyer_email and buyer_id:
            buyer_email = get_user_email(buyer_id)
            
        if not seller_email and seller_id:
            seller_email = get_user_email(seller_id)
        
        # Email to buyer
        if buyer_email:
            subject = f"Your Resale Ticket Purchase for {event_name}"
            html_content = f"""
            <html>
            <body>
                <h2>Resale Ticket Purchase Confirmation</h2>
                <p>Hello {buyer_name},</p>
                <p>You have successfully purchased a resale ticket!</p>
                <p>Event: <strong>{event_name}</strong> (ID: {event_id})</p>
                <p>Ticket ID: {ticket_id}</p>
                <p>Seat: {seat_no}</p>
                <p>Category: {seat_category}</p>
                <p>Price: ${price}</p>
            </body>
            </html>
            """
            send_email(buyer_email, subject, html_content)
            
        # Email to seller
        if seller_email:
            subject = f"Your Ticket for {event_name} Has Been Resold"
            html_content = f"""
            <html>
            <body>
                <h2>Ticket Resale Confirmation</h2>
                <p>Hello {seller_name},</p>
                <p>Your ticket has been successfully resold!</p>
                <p>Event: <strong>{event_name}</strong> (ID: {event_id})</p>
                <p>Ticket ID: {ticket_id}</p>
                <p>Seat: {seat_no}</p>
                <p>Category: {seat_category}</p>
                <p>Resale Price: ${price}</p>
                <p>You have been refunded ${refund_amount}</p>
                <p>Charge ID: {charge_id}</p>
            </body>
            </html>
            """
            send_email(seller_email, subject, html_content)
            
        # Acknowledge message
        ch.basic_ack(delivery_tag=method.delivery_tag)
        logger.info(f"Ticket resale emails sent")
        
    except Exception as e:
        logger.error(f"Error processing ticket resale: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

def handle_waitlist_notification(ch, method, properties, body):
    """Handle waitlist notification email"""
    try:
        data = json.loads(body)
        logger.info(f"Received waitlist notification: {data}")
        
        # Get required data
        user_id = data.get('user_id')
        user_name = data.get('user_name', 'Customer')
        event_id = data.get('event_id')
        event_name = data.get('event_name')
        event_date = data.get('event_date')
        expiration_time = data.get('expiration_time', '24 hours')
        
        # Get user email
        user_email = data.get('user_email')
        if not user_email and user_id:
            user_email = get_user_email(user_id)
            
        if not user_email:
            logger.error(f"No email address found for waitlist notification")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            return
        
        # Create email content
        subject = f"Tickets Now Available for {event_name}"
        
        html_content = f"""
        <html>
        <body>
            <h2>Waitlist Notification</h2>
            <p>Hello {user_name},</p>
            <p>Good news! Tickets are now available for resale for event:</p>
            <p><strong>{event_name}</strong> (ID: {event_id}) on {event_date}</p>
            <p>As you were on our waitlist, you now have priority access to purchase tickets.</p>
            <p><strong>This offer expires in: {expiration_time}</strong></p>
            <p>Please log in to your account to complete your purchase.</p>
        </body>
        </html>
        """
        
        # Send email
        send_email(user_email, subject, html_content)
        
        # Acknowledge message
        ch.basic_ack(delivery_tag=method.delivery_tag)
        logger.info(f"Waitlist notification email sent to {user_email}")
        
    except Exception as e:
        logger.error(f"Error processing waitlist notification: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

def handle_ticket_checkin(ch, method, properties, body):
    """Handle ticket check-in email"""
    try:
        data = json.loads(body)
        logger.info(f"Received ticket check-in notification: {data}")
        
        # Get required data
        user_id = data.get('user_id')
        ticket_id = data.get('ticket_id')
        event_name = data.get('event_name')
        check_in_time = data.get('check_in_time')
        
        # Get user email
        user_email = data.get('user_email')
        if not user_email and user_id:
            user_email = get_user_email(user_id)
            
        if not user_email:
            logger.error(f"No email address found for check-in notification")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            return
        
        # Create email content
        subject = f"Check-in Confirmation for {event_name}"
        
        html_content = f"""
        <html>
        <body>
            <h2>Event Check-in Confirmation</h2>
            <p>You have successfully checked in to {event_name}!</p>
            <p>Ticket ID: {ticket_id}</p>
            <p>Check-in Time: {check_in_time}</p>
            <p>Enjoy the event!</p>
        </body>
        </html>
        """
        
        # Send email
        send_email(user_email, subject, html_content)
        
        # Acknowledge message
        ch.basic_ack(delivery_tag=method.delivery_tag)
        logger.info(f"Ticket check-in email sent to {user_email}")
        
    except Exception as e:
        logger.error(f"Error processing ticket check-in: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

def handle_payment_confirmation(ch, method, properties, body):
    """Handle payment confirmation email"""
    try:
        data = json.loads(body)
        logger.info(f"Received payment confirmation: {data}")
        
        # Get required data
        user_id = data.get('user_id')
        amount = data.get('amount')
        payment_id = data.get('payment_id')
        transaction_id = data.get('transaction_id')
        payment_method = data.get('payment_method', 'Credit Card')
        
        # Get user email
        user_email = data.get('user_email')
        if not user_email and user_id:
            user_email = get_user_email(user_id)
            
        if not user_email:
            logger.error(f"No email address found for payment confirmation")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            return
        
        # Create email content
        subject = "Payment Confirmation"
        
        html_content = f"""
        <html>
        <body>
            <h2>Payment Confirmation</h2>
            <p>Your payment has been successfully processed.</p>
            <p>Amount: ${amount}</p>
            <p>Payment ID: {payment_id}</p>
            <p>Transaction ID: {transaction_id}</p>
            <p>Payment Method: {payment_method}</p>
            <p>Thank you for your purchase!</p>
        </body>
        </html>
        """
        
        # Send email
        send_email(user_email, subject, html_content)
        
        # Acknowledge message
        ch.basic_ack(delivery_tag=method.delivery_tag)
        logger.info(f"Payment confirmation email sent to {user_email}")
        
    except Exception as e:
        logger.error(f"Error processing payment confirmation: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

def handle_waitlist_notification(ch, method, properties, body):
    """Handle waitlist notification email"""
    try:
        data = json.loads(body)
        logger.info(f"Received waitlist notification: {data}")
        
        # Get required data
        user_id = data.get('user_id')
        event_name = data.get('event_name')
        event_date = data.get('event_date')
        expiration_time = data.get('expiration_time')  # Time until this offer expires
        
        # Get user email
        user_email = data.get('user_email')
        if not user_email and user_id:
            user_email = get_user_email(user_id)
            
        if not user_email:
            logger.error(f"No email address found for waitlist notification")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            return
        
        # Create email content
        subject = f"Tickets Now Available for {event_name}"
        
        html_content = f"""
        <html>
        <body>
            <h2>Waitlist Notification</h2>
            <p>Good news! Tickets are now available for {event_name} on {event_date}.</p>
            <p>As you were on our waitlist, you now have priority access to purchase tickets.</p>
            <p><strong>This offer expires in: {expiration_time}</strong></p>
            <p>Please log in to your account to complete your purchase.</p>
        </body>
        </html>
        """
        
        # Send email
        send_email(user_email, subject, html_content)
        
        # Acknowledge message
        ch.basic_ack(delivery_tag=method.delivery_tag)
        logger.info(f"Waitlist notification email sent to {user_email}")
        
    except Exception as e:
        logger.error(f"Error processing waitlist notification: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

def start_consuming():
    """Set up consumers for all email queues and start consuming messages"""
    global rabbitmq_channel, is_consuming
    
    try:
        # Set up consumers for each queue
        rabbitmq_channel.basic_consume(
            queue='email.ticket.purchase',
            on_message_callback=handle_ticket_purchase,
            auto_ack=False
        )
        
        rabbitmq_channel.basic_consume(
            queue='email.ticket.resale',
            on_message_callback=handle_ticket_resale,
            auto_ack=False
        )
        
        rabbitmq_channel.basic_consume(
            queue='email.ticket.checkin',
            on_message_callback=handle_ticket_checkin,
            auto_ack=False
        )
        
        rabbitmq_channel.basic_consume(
            queue='email.payment.confirmation',
            on_message_callback=handle_payment_confirmation,
            auto_ack=False
        )
        
        rabbitmq_channel.basic_consume(
            queue='email.waitlist.notification',
            on_message_callback=handle_waitlist_notification,
            auto_ack=False
        )
        
        logger.info("Email service started consuming messages")
        is_consuming = True
        
        # Start consuming messages
        rabbitmq_channel.start_consuming()
    except Exception as e:
        logger.error(f"Error starting consumers: {e}")
        is_consuming = False

def consumer_thread_function():
    """Function to run in a separate thread for consuming messages"""
    connect_to_rabbitmq()
    start_consuming()

# API Routes
@app.route("/health", methods=["GET"])
def health_check():
    """
    Health check endpoint
    ---
    responses:
        200:
            description: Service is healthy
    """
    global is_consuming
    
    return jsonify({
        "status": "healthy",
        "service": "email",
        "rabbitmq_connected": rabbitmq_connection is not None and rabbitmq_connection.is_open,
        "consuming_messages": is_consuming
    })

@app.route("/status", methods=["GET"])
def status():
    """
    Get detailed status of the email service
    ---
    responses:
        200:
            description: Detailed service status
    """
    global is_consuming
    
    # Get RabbitMQ queue info if connected
    queue_info = {}
    if rabbitmq_connection is not None and rabbitmq_connection.is_open:
        try:
            for queue in ['email.ticket.purchase', 'email.ticket.resale', 'email.ticket.checkin', 
                        'email.payment.confirmation', 'email.waitlist.notification']:
                queue_data = rabbitmq_channel.queue_declare(queue=queue, passive=True)
                queue_info[queue] = {
                    "message_count": queue_data.method.message_count,
                    "consumer_count": queue_data.method.consumer_count
                }
        except Exception as e:
            logger.error(f"Error getting queue info: {e}")
            queue_info = {"error": str(e)}
    
    return jsonify({
        "service": "email",
        "version": "1.0.0",
        "rabbitmq": {
            "connected": rabbitmq_connection is not None and rabbitmq_connection.is_open,
            "host": RABBITMQ_HOST,
            "port": RABBITMQ_PORT,
            "queues": queue_info
        },
        "smtp": {
            "server": SMTP_SERVER,
            "port": SMTP_PORT,
            "username": EMAIL_USERNAME is not None
        },
        "consumer_active": is_consuming,
        "user_service_url": USER_SERVICE_URL
    })

@app.route("/send", methods=["POST"])
def send_test_email():
    """
    Send a test email
    ---
    parameters:
        - name: body
            in: body
            required: true
        schema:
            type: object
            properties:
            recipient:
                type: string
                description: Email recipient
            subject:
                type: string
                description: Email subject
            content:
                type: string
                description: Email content (HTML)
    responses:
        200:
            description: Email sent successfully
        400:
            description: Bad request
        500:
            description: Internal server error
    """
    try:
        data = request.get_json()
        
        # Validate input
        if not all(k in data for k in ["recipient", "subject", "content"]):
            return jsonify({
                "code": 400,
                "message": "Missing required fields: recipient, subject, and content are required"
            }), 400
        
        # Send email
        success = send_email(
            recipient=data["recipient"],
            subject=data["subject"],
            html_content=data["content"]
        )
        
        if success:
            return jsonify({
                "code": 200,
                "message": f"Test email sent to {data['recipient']}"
            })
        else:
            return jsonify({
                "code": 500,
                "message": "Failed to send email"
            }), 500
            
    except Exception as e:
        logger.error(f"Error in send_test_email: {e}")
        return jsonify({
            "code": 500,
            "message": f"Internal server error: {str(e)}"
        }), 500

@app.route("/start", methods=["POST"])
def start_consumer():
    """
    Start the RabbitMQ consumer if it's not already running
    ---
    responses:
        200:
            description: Consumer started or already running
        500:
            description: Failed to start consumer
    """
    global consumer_thread, is_consuming
    
    try:
        if is_consuming:
            return jsonify({
                "code": 200,
                "message": "Consumer is already running"
            })
        
        # Start consumer in a new thread
        consumer_thread = threading.Thread(target=consumer_thread_function)
        consumer_thread.daemon = True
        consumer_thread.start()
        
        return jsonify({
            "code": 200,
            "message": "Consumer started successfully"
        })
    except Exception as e:
        logger.error(f"Error starting consumer: {e}")
        return jsonify({
            "code": 500,
            "message": f"Failed to start consumer: {str(e)}"
        }), 500

@app.route("/stop", methods=["POST"])
def stop_consumer():
    """
    Stop the RabbitMQ consumer
    ---
    responses:
        200:
            description: Consumer stopped or not running
        500:
            description: Failed to stop consumer
    """
    global rabbitmq_connection, is_consuming
    
    try:
        if not is_consuming:
            return jsonify({
                "code": 200,
                "message": "Consumer is not running"
            })
            
        # Stop consuming and close connection
        if rabbitmq_connection and rabbitmq_connection.is_open:
            rabbitmq_connection.close()
            rabbitmq_connection = None
            is_consuming = False
            
        return jsonify({
            "code": 200,
            "message": "Consumer stopped successfully"
        })
    except Exception as e:
        logger.error(f"Error stopping consumer: {e}")
        return jsonify({
            "code": 500,
            "message": f"Failed to stop consumer: {str(e)}"
        }), 500


if __name__ == "__main__":
    # Attempt to connect to RabbitMQ
    connection_attempts = 0
    while connection_attempts < 3:
        if connect_to_rabbitmq():
            break
        connection_attempts += 1
        logger.warning(f"Connection attempt {connection_attempts} failed. Retrying...")
        time.sleep(5)
    
    # Start consumer thread
    consumer_thread = threading.Thread(target=consumer_thread_function)
    consumer_thread.daemon = True
    consumer_thread.start()
    
    # Start Flask app
    app.run(host='0.0.0.0', port=5008, debug=True)