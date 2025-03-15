from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import requests
from invokes import invoke_http

app = Flask(__name__)

CORS(app)

waitlist_URL = "http://localhost:5003/waitlist"
ticket_URL = "http://localhost:5004/ticket"
user_URL = "http://localhost:5006/user"

## can work on this first, no need stripe api implementation yet