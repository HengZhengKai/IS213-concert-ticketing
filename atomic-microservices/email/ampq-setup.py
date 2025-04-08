"""
A standalone script to create exchanges and queues on RabbitMQ for the Ticketing system.
"""

import pika

amqp_host = "localhost"
amqp_port = 5672
exchange_name = "ticketing"
exchange_type = "topic"


def create_exchange(hostname, port, exchange_name, exchange_type):
    print(f"Connecting to AMQP broker {hostname}:{port}...")
    # connect to the broker
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(
            host=hostname,
            port=port,
            heartbeat=300,
            blocked_connection_timeout=300,
        )
    )
    print("Connected")

    print("Open channel")
    channel = connection.channel()

    # Set up the exchange if the exchange doesn't exist
    print(f"Declare exchange: {exchange_name}")
    channel.exchange_declare(
        exchange=exchange_name, exchange_type=exchange_type, durable=True
    )
    # 'durable' makes the exchange survive broker restarts

    return channel


def create_queue(channel, exchange_name, queue_name, routing_keys):
    print(f"Declare queue: {queue_name}")
    channel.queue_declare(queue=queue_name, durable=True)
    # 'durable' makes the queue survive broker restarts

    # bind the queue to the exchange via the routing_key
    for routing_key in routing_keys:
        print(f"Bind {queue_name} to {exchange_name} with routing key {routing_key}")
        channel.queue_bind(
            exchange=exchange_name, queue=queue_name, routing_key=routing_key
        )


print("Setting up RabbitMQ exchanges and queues for Ticketing System...")
channel = create_exchange(
    hostname=amqp_host,
    port=amqp_port,
    exchange_name=exchange_name,
    exchange_type=exchange_type,
)

# Create email service queues
create_queue(
    channel=channel,
    exchange_name=exchange_name,
    queue_name="email.ticket.purchase",
    routing_keys=["ticket.purchased", "payment.successful"]
)

create_queue(
    channel=channel,
    exchange_name=exchange_name,
    queue_name="email.ticket.resale",
    routing_keys=["ticket.resold"]
)

create_queue(
    channel=channel,
    exchange_name=exchange_name,
    queue_name="email.ticket.checkin",
    routing_keys=["ticket.checkedin"]
)

create_queue(
    channel=channel,
    exchange_name=exchange_name,
    queue_name="email.payment.confirmation",
    routing_keys=["payment.successful"]
)

create_queue(
    channel=channel,
    exchange_name=exchange_name,
    queue_name="email.waitlist.notification",
    routing_keys=["waitlist.available"]
)

# Create error and logging queues
create_queue(
    channel=channel,
    exchange_name=exchange_name,
    queue_name="Error",
    routing_keys=["*.error"]
)

create_queue(
    channel=channel,
    exchange_name=exchange_name,
    queue_name="Activity_Log",
    routing_keys=["#"]
)

print("RabbitMQ setup completed!")