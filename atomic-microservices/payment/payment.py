from flask import Flask, jsonify
from flask_cors import CORS
import stripe
import os

app = Flask(__name__)

CORS(app)

# @michelle write your code in this file