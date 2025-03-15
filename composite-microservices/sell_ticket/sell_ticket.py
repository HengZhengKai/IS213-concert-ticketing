from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import requests
from invokes import invoke_http

app = Flask(__name__)

CORS(app)