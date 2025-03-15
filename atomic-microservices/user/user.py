from flask import Flask, request, jsonify
from flask_cors import CORS
import mongoengine as db
from os import environ
import os

app = Flask(__name__)

CORS(app)

db.connect(host=os.getenv('MONGO_URI')) # Set this in your .env file

class User(db.Document): # tell flask what are the fields in your database
    userID = db.StringField(primary_key = True)
    name = db.StringField()
    age = db.IntField()
    gender = db.StringField()
    email = db.StringField()
    phone = db.StringField()

    def to_json(self):
        return {
            "userID": self.userID,
            "name": self.name,
            "age": self.age,
            "gender": self.gender,
            "email": self.email,
            "phone": self.phone
        }

@app.route("/user/<string:userID>")
def get_user(userID):
    user = User.objects(userID=userID).first()  # MongoEngine query

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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)