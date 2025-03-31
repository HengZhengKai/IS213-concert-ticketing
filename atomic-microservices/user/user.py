from flask import Flask, request, jsonify
from flask_cors import CORS
import mongoengine as db
from os import environ
import os
from datetime import datetime
import urllib.parse
from flasgger import Swagger
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
swagger = Swagger(app)

CORS(app)

# MongoDB connection details from environment variables
username = os.getenv("MONGO_USERNAME")
password = urllib.parse.quote_plus(os.getenv("MONGO_PASSWORD"))
cluster = os.getenv("MONGO_CLUSTER")
database = os.getenv("MONGO_DATABASE")

# Construct connection string
MONGO_URI = f"mongodb+srv://{username}:{password}@{cluster}/{database}?retryWrites=true&w=majority&authSource=admin"

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

    meta = {
        'collection': 'User' 
    }

    def to_json(self):
        return {
            "userID": self._id,  # Map _id to userID in output
            "name": self.name,
            "age": self.age,
            "gender": self.gender,
            "email": self.email,
            "phoneNum": self.phoneNum  
        }

@app.route("/user/<string:userID>")
def get_user(userID):
    user = User.objects(_id=userID).first()  # MongoEngine query

    if user:
        return jsonify(
            {
                "code": 200,
                "data": user.to_json()  # Use `to_json()` method of user class
            }
        )
    
    return jsonify(
        {
            "code": 404,
            "message": "User not found."
        }
    ), 404

@app.route("/user/<string:email>")
def get_user_by_email(email):
    user = User.objects(email=email).first()  # MongoEngine query

    if user:
        return jsonify(
            {
                "code": 200,
                "data": user.to_json()  # Use `to_json()` method of user class
            }
        )
    
    return jsonify(
        {
            "code": 404,
            "message": "User not found."
        }
    ), 404

#displays the seats in json 
#link to see json http://localhost:5006/users
@app.route('/users', methods=['GET'])
def get_all_users():
    try:
        users = User.objects()
        logger.info(f"Retrieved {len(users)} users from database")
        return jsonify({
            "code": 200,
            "data": {
                "users": [user.to_json() for user in users]
            }
        })
    except Exception as e:
        logger.error(f"Error retrieving users: {e}")
        return jsonify({
            "code": 500,
            "message": f"Error retrieving users: {str(e)}"
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5006, debug=True)