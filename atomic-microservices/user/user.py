from flask import Flask, request, jsonify
from flask_cors import CORS
import mongoengine as db
from os import environ
import os
from datetime import datetime, timedelta
import urllib.parse
import logging
from dotenv import load_dotenv
import jwt

# Load environment variables from .env file
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Add a secret key for JWT (store this securely, e.g., in .env)
app.config['SECRET_KEY'] = os.getenv("JWT_SECRET_KEY", "your_default_super_secret_key")

# Configure CORS to allow requests from specified origins
CORS(app, resources={r"/*": {"origins": ["http://localhost", "http://localhost:8000", "http://localhost:8080"]}})

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

# --- ADD THE LOGIN ROUTE (Plain Text Password Check) --- 
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

@app.route("/user/id/<string:userID>")
def get_user(userID):
    user = User.objects(_id=userID).first() 
    if user:
        # Use the updated to_json which excludes password
        return jsonify({"code": 200, "data": user.to_json()})
    return jsonify({"code": 404, "message": "User not found."}), 404

@app.route("/user/email/<string:email>")
def get_user_by_email(email):
    try:
        logger.info(f"Looking up user by email: {email}")
        user = User.objects(email=email).first()
        if user:
            logger.info(f"Found user: {user.to_json()}")
            # Use the updated to_json which excludes password
            return jsonify({"code": 200, "data": user.to_json()})
        logger.info(f"No user found with email: {email}")
        return jsonify({"code": 404, "message": "User not found."}), 404
    except Exception as e:
        logger.error(f"Error finding user by email: {e}")
        return jsonify({"code": 500, "message": f"Error finding user: {str(e)}"}), 500

@app.route('/users', methods=['GET'])
def get_all_users():
    try:
        users = User.objects()
        logger.info(f"Retrieved {len(users)} users from database")
        return jsonify({
            "code": 200,
            # Use the updated to_json which excludes password
            "data": {"users": [user.to_json() for user in users]}
        })
    except Exception as e:
        logger.error(f"Error retrieving users: {e}")
        return jsonify({"code": 500, "message": f"Error retrieving users: {str(e)}"}), 500

if __name__ == '__main__':
    # Run on port 5006 as specified in docker-compose.yml
    app.run(host='0.0.0.0', port=5006, debug=True)