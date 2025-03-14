from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_mongoengine import MongoEngine
from os import environ
import os

app = Flask(__name__)

CORS(app)

app.config['MONGODB_SETTINGS'] = {
    'host': os.getenv('MONGO_URI')  # Set this in your .env file
}

db = MongoEngine(app)