import pika
import json
import argparse
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# RabbitMQ configuration
RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'localhost')
RABBITMQ_PORT = int(os.getenv('RABBITMQ_PORT', 5672))
RABBITMQ_USER = os.getenv('RABBITMQ_USER', 'guest')
RABBITMQ_PASS = os.getenv('RABBITMQ_PASS', 'guest')

def connect_to_rabbitmq():
    """Establish connection to RabbitMQ"""
    # Create connection parameters
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
    parameters = pika.ConnectionParameters(
        host=RABBITMQ_HOST,
        port=RABBITMQ_PORT,
        credentials=credentials
    )
    
    # Connect to RabbitMQ
    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()
    
    return connection, channel

def publish_ticket_purchase(channel, recipient_email):
    """Publish a sample ticket purchase message"""
    message = {
        "user_id": "user123",
        "user_name": "Test User",
        "user_email": recipient_email,  # Use provided email for testing
        "ticket_id": "ticket456",
        "event_id": "event789",
        "event_name": "Test Concert",
        "event_date": "2025-05-15",
        "seat_no": "A12",
        "seat_category": "VIP",
        "price": 149.99,
        "payment_id": "payment123"
    }
    
    channel.basic_publish(
        exchange='ticketing',
        routing_key='ticket.purchased',
        body=json.dumps(message)
    )
    
    print(f"Published ticket purchase message for {recipient_email}")

def publish_ticket_resale(channel, buyer_email, seller_email):
    """Publish a sample ticket resale message"""
    message = {
        "buyer_id": "buyer123",
        "buyer_name": "Buyer User",
        "buyer_email": buyer_email,
        "seller_id": "seller456",
        "seller_name": "Seller User",
        "seller_email": seller_email,
        "ticket_id": "ticket789",
        "event_id": "event789",
        "event_name": "Test Concert",
        "seat_no": "B15",
        "seat_category": "Premium",
        "price": 199.99,
        "charge_id": "charge123",
        "refund_amount": 189.99
    }
    
    channel.basic_publish(
        exchange='ticketing',
        routing_key='ticket.resold',
        body=json.dumps(message)
    )
    
    print(f"Published ticket resale message for buyer {buyer_email} and seller {seller_email}")

def publish_waitlist_notification(channel, recipient_email):
    """Publish a sample waitlist notification message"""
    message = {
        "user_id": "user789",
        "user_name": "Waitlist User",
        "user_email": recipient_email,
        "event_id": "event789",
        "event_name": "Test Concert",
        "event_date": "2025-05-15",
        "expiration_time": "6 hours"
    }
    
    channel.basic_publish(
        exchange='ticketing',
        routing_key='waitlist.available',
        body=json.dumps(message)
    )
    
    print(f"Published waitlist notification message for {recipient_email}")

def main():
    parser = argparse.ArgumentParser(description='Test RabbitMQ message publishing for email service')
    parser.add_argument('--type', choices=['purchase', 'resale', 'waitlist'], required=True,
                        help='Type of message to publish')
    parser.add_argument('--email', required=True, help='Recipient email address')
    parser.add_argument('--seller-email', help='Seller email address (for resale only)')
    
    args = parser.parse_args()
    
    # Connect to RabbitMQ
    connection, channel = connect_to_rabbitmq()
    
    try:
        # Publish message based on type
        if args.type == 'purchase':
            publish_ticket_purchase(channel, args.email)
        elif args.type == 'resale':
            if not args.seller_email:
                print("Error: --seller-email is required for resale messages")
                return
            publish_ticket_resale(channel, args.email, args.seller_email)
        elif args.type == 'waitlist':
            publish_waitlist_notification(channel, args.email)
    finally:
        # Close connection
        connection.close()

if __name__ == "__main__":
    main()