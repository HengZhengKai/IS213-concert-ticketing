from flask import Flask, request, jsonify
from flask_cors import CORS
from mongoengine import *

app = Flask(__name__)

CORS(app)