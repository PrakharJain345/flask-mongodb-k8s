import os
from datetime import datetime
from flask import Flask, request, jsonify
from pymongo import MongoClient
from pymongo.errors import PyMongoError

app = Flask(__name__)

# Configure MongoDB connection from environment variables
MONGO_HOST = os.environ.get("MONGO_HOST", "localhost")
MONGO_PORT = int(os.environ.get("MONGO_PORT", 27017))
MONGO_USERNAME = os.environ.get("MONGO_USERNAME")
MONGO_PASSWORD = os.environ.get("MONGO_PASSWORD")
MONGO_AUTH_DB = os.environ.get("MONGO_AUTH_DB", "admin")
MONGODB_URI = os.environ.get("MONGODB_URI")

def get_mongo_client():
    if MONGODB_URI:
        return MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    
    client_kwargs = {
        "host": MONGO_HOST,
        "port": MONGO_PORT,
        "serverSelectionTimeoutMS": 5000
    }
    if MONGO_USERNAME and MONGO_PASSWORD:
        client_kwargs["username"] = MONGO_USERNAME
        client_kwargs["password"] = MONGO_PASSWORD
        client_kwargs["authSource"] = MONGO_AUTH_DB
        
    return MongoClient(**client_kwargs)

_client = None

def get_collection():
    global _client
    if _client is None:
        _client = get_mongo_client()
    return _client["flask_db"]["data"]

@app.route("/", methods=["GET"])
def index():
    return f"Welcome to the Flask app! The current time is: {datetime.now()}"

@app.route("/health", methods=["GET"])
def health():
    # Health endpoint does not touch MongoDB, used for Kubernetes liveness & readiness probes
    return jsonify({"status": "ok"}), 200

@app.route("/cpu", methods=["GET"])
def cpu_load():
    # Compute loop to generate CPU load for HPA autoscaling testing
    val = 0
    for i in range(500000):
        val += (i % 7) * (i % 11)
    return jsonify({"status": "computed", "result": val}), 200

@app.route("/data", methods=["POST"])
def insert_data():
    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 400
    
    payload = request.get_json(silent=True)
    if payload is None or not isinstance(payload, dict) or len(payload) == 0:
        return jsonify({"error": "Request body must be a non-empty JSON object"}), 400

    try:
        # Avoid mutating the original payload with _id when inserting
        insert_doc = payload.copy()
        get_collection().insert_one(insert_doc)
        return jsonify({"status": "Data inserted"}), 201
    except PyMongoError as err:
        return jsonify({"error": f"Database error: {str(err)}"}), 500
    except Exception as err:
        return jsonify({"error": f"Unexpected error: {str(err)}"}), 500

@app.route("/data", methods=["GET"])
def get_data():
    try:
        # Exclude _id from returned documents
        docs = list(get_collection().find({}, {"_id": 0}))
        return jsonify(docs), 200
    except PyMongoError as err:
        return jsonify({"error": f"Database error: {str(err)}"}), 500
    except Exception as err:
        return jsonify({"error": f"Unexpected error: {str(err)}"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

