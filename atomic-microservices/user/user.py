from flask import Flask, request, jsonify
from flask_cors import CORS
import mongoengine as db
from os import environ
import os
import re
from datetime import datetime, timedelta
import urllib.parse
import logging
from dotenv import load_dotenv
import jwt
import pika
import json

# Load environment variables from .env file
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Add a secret key for JWT (store this securely, e.g., in .env)
app.config['SECRET_KEY'] = os.getenv("JWT_SECRET_KEY", "your_default_super_secret_key")

CORS(app)

# MongoDB connection details from environment variables
username = os.getenv("MONGO_USERNAME")
password_db_connect = urllib.parse.quote_plus(os.getenv("MONGO_PASSWORD"))
cluster = os.getenv("MONGO_CLUSTER")
database = os.getenv("MONGO_DATABASE")

# Construct connection string
MONGO_URI = f"mongodb+srv://{username}:{password_db_connect}@{cluster}/{database}?retryWrites=true&w=majority&authSource=admin"

try:
    # Connect to MongoDB Atlas
    logger.info(f"Connecting to MongoDB at: {cluster}")
    db.connect(host=MONGO_URI, alias='default')
    logger.info("Connected to MongoDB successfully")
except Exception as e:
    logger.error(f"Failed to connect to MongoDB: {e}")

# Get RabbitMQ host and URI
RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'localhost')
RABBITMQ_URI = os.getenv('RABBITMQ_PORT', 'tcp://localhost:5672')

# Extract the port number from the URI
match = re.search(r'tcp://.*:(\d+)', RABBITMQ_URI)
if match:
    RABBITMQ_PORT = int(match.group(1))  # Extracted port
else:
    RABBITMQ_PORT = 5672  # Default fallback port
    
RABBITMQ_USER = os.getenv('RABBITMQ_USER', 'guest')
RABBITMQ_PASS = os.getenv('RABBITMQ_PASS', 'guest')

def publish_to_rabbitmq(routing_key, message):
    try:
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
        
        # Publish message
        channel.basic_publish(
            exchange='ticketing',
            routing_key=routing_key,
            body=json.dumps(message)
        )
        
        # Close connection
        connection.close()
        logger.info(f"Published message with routing key: {routing_key}")
        return True
    except Exception as e:
        logger.error(f"Failed to publish to RabbitMQ: {e}")
        return False
    
class User(db.Document): # tell flask what are the fields in your database
    _id = db.StringField(primary_key=True) 
    name = db.StringField()
    age = db.IntField()
    gender = db.StringField()
    email = db.StringField()
    phoneNum = db.StringField()
    password = db.StringField()  # Assuming plain text password storage

    meta = {
        'collection': 'User' 
    }

    def to_json(self):
        # Exclude password from default JSON representation
        return {
            "userID": self._id, 
            "name": self.name,
            "age": self.age,
            "gender": self.gender,
            "email": self.email,
            "phoneNum": self.phoneNum
        }

# --- LOGIN ROUTE (Plain Text Password Check) --- 
@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        email = data.get('email')
        password_input = data.get('password') # Renamed variable

        if not email or not password_input:
            return jsonify({"message": "Email and password are required"}), 400

        logger.info(f"Login attempt for email: {email}")
        user = User.objects(email=email).first()

        if not user:
            logger.warning(f"Login failed: User not found for email {email}")
            return jsonify({"message": "Invalid credentials"}), 401

        # Direct plain-text password comparison (INSECURE!)
        if user.password == password_input:
            logger.info(f"Login successful for user: {email} (Plain text check)")
            # Generate JWT token
            token = jwt.encode({
                'userID': user._id,
                'email': user.email,
                'exp': datetime.utcnow() + timedelta(hours=24) # Token expires in 24 hours
            }, app.config['SECRET_KEY'], algorithm="HS256")

            # Prepare user data for response (password already excluded in to_json)
            user_data = user.to_json()

            return jsonify({
                "message": "Login successful",
                "token": token,
                "user": user_data
            }), 200
        else:
            logger.warning(f"Login failed: Invalid password for email {email} (Plain text check)")
            return jsonify({"message": "Invalid credentials"}), 401

    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({"message": f"An error occurred during login: {str(e)}"}), 500
# --- END OF LOGIN ROUTE ---

# Route 1
@app.route('/users', methods=['GET'])
def get_all_users():
    try:
        users = User.objects()
        return jsonify({
            "code": 200,
            # Use the updated to_json which excludes password
            "data": {"users": [user.to_json() for user in users]}
        })
    except Exception as e:
        logger.error(f"Error retrieving users: {e}")
        return jsonify({"code": 500, "message": f"Error retrieving users: {str(e)}"}), 500

# Route 2
@app.route("/user/<string:userID>")
def get_user(userID):
    user = User.objects(_id=userID).first() 
    if user:
        # Use the updated to_json which excludes password
        return jsonify({"code": 200, "data": user.to_json()})
    return jsonify({"code": 404, "message": "User not found."}), 404

# Route 3
@app.route("/user/email/<string:email>")
def get_user_by_email(email):
    try:
        user = User.objects(email=email).first()
        if user:
            return jsonify({"code": 200, "data": user.to_json()})
        return jsonify({"code": 404, "message": "User not found."}), 404
    except Exception as e:
        return jsonify({"code": 500, "message": f"Error finding user: {str(e)}"}), 500

if __name__ == '__main__':
    # Run on port 5006 as specified in docker-compose.yml
    app.run(host='0.0.0.0', port=5006, debug=True)