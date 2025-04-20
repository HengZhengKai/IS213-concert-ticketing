from flask import Flask, request, jsonify
from flask_cors import CORS
import pika
import json
import os
import smtplib
import logging
import threading
import requests
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from logging.handlers import RotatingFileHandler

# Load environment variables
load_dotenv()

# Configure logging
def setup_logging():
    """Set up comprehensive logging configuration"""
    # Create logs directory if it doesn't exist
    os.makedirs('logs', exist_ok=True)
    
    # Configure root logger
    logging.basicConfig(
        level=logging.INFO, 
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create a logger for the email service
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # File handler with log rotation
    file_handler = RotatingFileHandler(
        'logs/email_service.log', 
        maxBytes=10*1024*1024,  # 10 MB
        backupCount=5
    )
    file_handler.setLevel(logging.INFO)
    
    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)
    
    # Add handlers to logger
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    # Reduce noise from certain libraries
    logging.getLogger('pika').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    
    return logger

# Initialize logger
logger = setup_logging()

# Flask app setup
app = Flask(__name__)
CORS(app)

# Email configuration
SMTP_SERVER = os.getenv('SMTP_SERVER')
SMTP_PORT = int(os.getenv('SMTP_PORT'))
EMAIL_USERNAME = os.getenv('EMAIL_USERNAME')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
SENDER_EMAIL = os.getenv('SENDER_EMAIL', EMAIL_USERNAME)

# RabbitMQ configuration
RABBITMQ_HOST = os.getenv('RABBITMQ_HOST')
RABBITMQ_PORT = int(os.getenv('RABBITMQ_PORT'))
RABBITMQ_USER = os.getenv('RABBITMQ_USER')
RABBITMQ_PASS = os.getenv('RABBITMQ_PASS')

# Global variables
rabbitmq_connection = None
rabbitmq_channel = None
consumer_thread = None
is_consuming = False
processed_messages = set()  # Track processed message IDs

def get_user_email(user_id):
    """
    Fetch user email from user service with improved error handling and logging
    
    Args:
        user_id (str): User ID to fetch email for
    
    Returns:
        str or None: User email if found, None otherwise
    """
    try:
        url = f"http://kong:8000/user/{user_id}"
        logger.info(f"Fetching user email for ID: {user_id} from URL: {url}")
        
        response = requests.get(url, timeout=5)
        logger.info(f"User service response status: {response.status_code}")
        logger.info(f"User service response body: {response.text}")
        
        if response.status_code == 200:
            user_data = response.json()
            logger.info(f"Parsed user data: {user_data}")
            
            # Check if we have the expected data structure
            if not isinstance(user_data, dict):
                logger.error(f"Invalid response format from user service: {user_data}")
                return None
                
            if 'data' not in user_data:
                logger.error(f"Missing 'data' field in user service response: {user_data}")
                return None
                
            # Get email from the user data
            email = user_data['data'].get('email')
            
            if email:
                logger.info(f"Successfully retrieved email for user {user_id}: {email}")
                return email
            
            logger.warning(f"No email found in user data for user {user_id}")
            return None
        
        logger.warning(f"Failed to get email for user {user_id}. Status code: {response.status_code}")
        return None
    except requests.RequestException as e:
        logger.error(f"Network error fetching user email for {user_id}: {e}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON response when fetching email for user {user_id}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in get_user_email for user {user_id}: {e}")
        return None

def connect_to_rabbitmq():
    """
    Establish connection to RabbitMQ with improved error handling and logging
    
    Returns:
        bool: True if connection successful, False otherwise
    """
    global rabbitmq_connection, rabbitmq_channel
    
    try:
        logger.info(f"Attempting to connect to RabbitMQ at {RABBITMQ_HOST}:{RABBITMQ_PORT}")
        
        # Create connection parameters
        credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
        parameters = pika.ConnectionParameters(
            host=RABBITMQ_HOST,
            port=RABBITMQ_PORT,
            credentials=credentials,
            connection_attempts=3,
            retry_delay=5,
            heartbeat=600,
            blocked_connection_timeout=300
        )
        
        # Implement exponential backoff
        for attempt in range(1, 4):
            try:
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
            except (pika.exceptions.AMQPConnectionError, ConnectionRefusedError) as e:
                wait_time = 2 ** attempt  # Exponential backoff
                logger.warning(f"Connection attempt {attempt} failed: {e}. Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
        
        logger.error("Failed to connect to RabbitMQ after multiple attempts")
        return False
    except Exception as e:
        logger.error(f"Unexpected error connecting to RabbitMQ: {e}", exc_info=True)
        return False

def declare_queues():
    """Declare queues and bind them to the exchange with appropriate routing keys"""
    global rabbitmq_channel
    
    queue_bindings = {
        'email.ticket.purchase': ['ticket.purchased'],  # Only ticket purchase events
        'email.ticket.resale': ['ticket.resold'],
        'email.ticket.checkin': ['ticket.checkedin'],
        'email.payment.confirmation': ['payment.successful'],  # Only payment confirmation events
        'email.waitlist.notification': ['waitlist.available'],
    }
    
    for queue_name, routing_keys in queue_bindings.items():
        try:
            rabbitmq_channel.queue_declare(queue=queue_name, durable=True)
            for routing_key in routing_keys:
                rabbitmq_channel.queue_bind(
                    exchange='ticketing',
                    queue=queue_name,
                    routing_key=routing_key
                )
            logger.info(f"Declared and bound queue: {queue_name}")
        except Exception as e:
            logger.error(f"Error declaring queue {queue_name}: {e}")

def send_email(recipient, subject, html_content):
    """
    Send email using SMTP with improved error handling and logging
    
    Args:
        recipient (str): Email recipient
        subject (str): Email subject
        html_content (str): HTML content of the email
    
    Returns:
        bool: True if email sent successfully, False otherwise
    """
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
    except smtplib.SMTPException as e:
        logger.error(f"SMTP error sending email to {recipient}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error sending email to {recipient}: {e}", exc_info=True)
        return False

# Message handling functions remain largely the same, 
# but with added logging and error tracking
def handle_ticket_purchase(ch, method, properties, body):
    """Handle ticket purchase email"""
    try:
        # Generate a unique message ID from the body
        message_id = hash(body)
        
        # Check if we've already processed this message
        if message_id in processed_messages:
            logger.info("Duplicate message detected, acknowledging and skipping")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return
            
        data = json.loads(body)
        logger.info(f"Processing ticket purchase for user {data.get('user_id', 'Unknown')}")
        
        # Get required data
        user_id = data.get('user_id')
        user_name = data.get('user_name', 'Customer')
        ticket_id = data.get('ticket_id')
        event_id = data.get('event_id')
        event_name = data.get('event_name')
        event_date = data.get('event_date')
        seat_no = data.get('seat_no')
        seat_category = data.get('seat_category')
        price = data.get('price', 0)
        
        # Get user email
        user_email = data.get('user_email')
        if not user_email and user_id:
            user_email = get_user_email(user_id)
            
        if not user_email:
            logger.error(f"No email address found for ticket purchase notification for user {user_id}")
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
        success = send_email(user_email, subject, html_content)
        
        # Acknowledge or negative acknowledge based on email send result
        if success:
            processed_messages.add(message_id)  # Mark message as processed
            ch.basic_ack(delivery_tag=method.delivery_tag)
        else:
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
        
    except Exception as e:
        logger.error(f"Error processing ticket purchase: {e}", exc_info=True)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

def handle_ticket_resale(ch, method, properties, body):
    """Handle ticket resale email"""
    try:        
        # Generate a unique message ID from the body
        message_id = hash(body)
        
        # Check if we've already processed this message
        if message_id in processed_messages:
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return
            
        data = json.loads(body)
        
        # Get required data
        buyer_id = data.get('buyer_id')
        buyer_name = data.get('buyer_name', 'Customer')
        buyer_email = data.get('buyer_email')
        seller_id = data.get('seller_id')
        seller_name = data.get('seller_name', 'Seller')
        seller_email = data.get('seller_email')
        ticket_id = data.get('ticket_id')
        event_id = data.get('event_id')
        event_name = data.get('event_name')
        event_date = data.get('event_date')
        seat_no = data.get('seat_no')
        seat_category = data.get('seat_category')
        price = data.get('price', 0)
        refund_amount = data.get('refund_amount', 0)
        
        logger.info(f"Buyer email: {buyer_email}, Seller email: {seller_email}")
        
        # Verify we have all required data
        if not all([buyer_email, seller_email, ticket_id, event_name, event_date, seat_no, seat_category, price]):
            missing_fields = [field for field in ['buyer_email', 'seller_email', 'ticket_id', 'event_name', 'event_date', 'seat_no', 'seat_category', 'price'] 
                            if not data.get(field)]
            logger.error(f"Missing required data in ticket resale message: {missing_fields}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            return
        
        # Create email content for buyer
        buyer_subject = f"Your Resale Ticket Purchase for {event_name}"
        buyer_html_content = f"""
        <html>
        <body>
            <h2>Your Resale Ticket Purchase Confirmation</h2>
            <p>Thank you for your purchase, {buyer_name}!</p>
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
        
        # Create email content for seller
        seller_subject = f"Your Ticket Has Been Resold - {event_name}"
        seller_html_content = f"""
        <html>
        <body>
            <h2>Your Ticket Has Been Successfully Resold</h2>
            <p>Hello {seller_name},</p>
            <p>Your ticket for the following event has been successfully resold:</p>
            <p>Event: <strong>{event_name}</strong> (ID: {event_id})</p>
            <p>Date: {event_date}</p>
            <p>Ticket ID: {ticket_id}</p>
            <p>Seat: {seat_no}</p>
            <p>Category: {seat_category}</p>
            <p>Refund Amount: ${refund_amount}</p>
            <p>The refund will be processed to your original payment method.</p>
        </body>
        </html>
        """
        
        buyer_success = send_email(buyer_email, buyer_subject, buyer_html_content)
        seller_success = send_email(seller_email, seller_subject, seller_html_content)
        
        # Acknowledge or negative acknowledge based on email send results
        if buyer_success and seller_success:
            processed_messages.add(message_id)  # Mark message as processed
            ch.basic_ack(delivery_tag=method.delivery_tag)
            logger.info(f"Ticket resale emails processed successfully for buyer {buyer_id} and seller {seller_id}")
        else:
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
            logger.error(f"Failed to send ticket resale emails. Buyer success: {buyer_success}, Seller success: {seller_success}")
        
    except Exception as e:
        logger.error(f"Error processing ticket resale: {e}", exc_info=True)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

def handle_waitlist_notification(ch, method, properties, body):
    """Handle waitlist notification email"""
    try:        
        # Generate a unique message ID from the body
        message_id = hash(body)
        
        # Check if we've already processed this message
        if message_id in processed_messages:
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return
            
        data = json.loads(body)
        
        # Get required data
        user_id = data.get('user_id')
        event_id = data.get('event_id')
        event_name = data.get('event_name')
        event_date = data.get('event_date')
        
        # Get user email
        user_email = get_user_email(user_id)
        if not user_email:
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            return
        
        # Create email content
        subject = f"Ticket Available: {event_name}"
        
        html_content = f"""
        <html>
        <body>
            <h2>Ticket Available!</h2>
            <p>Good news! A ticket has become available for an event you're interested in.</p>
            <p>Event: <strong>{event_name}</strong> (ID: {event_id})</p>
            <p>Date: {event_date}</p>
            <p>Please visit our website to purchase the ticket before it's gone!</p>
        </body>
        </html>
        """
        
        # Send email
        success = send_email(user_email, subject, html_content)
        
        # Acknowledge or negative acknowledge based on email send result
        if success:
            processed_messages.add(message_id)  # Mark message as processed
            ch.basic_ack(delivery_tag=method.delivery_tag)
        else:
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
        
    except Exception as e:
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

def start_consuming():
    """Set up consumers for all email queues and start consuming messages"""
    global rabbitmq_channel, is_consuming
    
    try:
        # Set up consumers for each queue
        rabbitmq_channel.basic_qos(prefetch_count=1)  # Process one message at a time
        
        # Set up consumer for ticket purchase queue
        rabbitmq_channel.basic_consume(
            queue='email.ticket.purchase',
            on_message_callback=handle_ticket_purchase,
            auto_ack=False
        )
        
        # Set up consumer for ticket resale queue
        rabbitmq_channel.basic_consume(
            queue='email.ticket.resale',
            on_message_callback=handle_ticket_resale,
            auto_ack=False
        )
        
        # Set up consumer for waitlist notification queue
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
        logger.error(f"Error starting consumers: {e}", exc_info=True)
        is_consuming = False

def consumer_thread_function():
    """Function to run in a separate thread for consuming messages"""
    try:
        connection_result = connect_to_rabbitmq()
        if connection_result:
            start_consuming()
        else:
            logger.critical("Failed to establish RabbitMQ connection in consumer thread")
    except Exception as e:
        logger.critical(f"Unexpected error in consumer thread: {e}", exc_info=True)

# API Routes remain mostly the same, with added logging

if __name__ == "__main__":
    # Attempt to connect to RabbitMQ
    connection_attempts = 0
    max_attempts = 5
    
    while connection_attempts < max_attempts:
        logger.info(f"Connection attempt {connection_attempts + 1} of {max_attempts}")
        if connect_to_rabbitmq():
            break
        connection_attempts += 1
        wait_time = min(2 ** connection_attempts, 60)  # Exponential backoff, max 60 seconds
        logger.warning(f"Connection failed. Waiting {wait_time} seconds before retry...")
        time.sleep(wait_time)
    
    # Start consumer thread
    if connection_attempts < max_attempts:
        consumer_thread = threading.Thread(target=consumer_thread_function)
        consumer_thread.daemon = True
        consumer_thread.start()
        
        # Start Flask app
        logger.info("Starting Flask application...")
        app.run(host='0.0.0.0', port=5008, debug=False)
    else:
        logger.critical("Failed to connect to RabbitMQ after multiple attempts. Exiting...")
        exit(1)