import os
import requests
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)

# 1. THE SECURITY KEY: This allows your GitHub site to talk to Render
# Make sure 'flask-cors' is in your requirements.txt
CORS(app)

# 2. CONFIGURATION: These pull from your Render Environment Variables
PAYPAL_CLIENT_ID = os.environ.get('PAYPAL_CLIENT_ID')
PAYPAL_SECRET = os.environ.get('PAYPAL_SECRET')

# Use 'https://api-m.sandbox.paypal.com' for testing
# Use 'https://api-m.paypal.com' for real money
PAYPAL_BASE_URL = 'https://api-m.paypal.com' 

def get_access_token():
    """Internal helper to get the PayPal Authorization token."""
    try:
        res = requests.post(
            f"{PAYPAL_BASE_URL}/v1/oauth2/token",
            auth=(PAYPAL_CLIENT_ID, PAYPAL_SECRET),
            data={'grant_type': 'client_credentials'},
            timeout=10
        )
        return res.json().get('access_token')
    except Exception as e:
        print(f"Token Error: {e}")
        return None

@app.route('/')
def home():
    """Simple check to see if the server is awake."""
    return "AuraPay Backend is Live! 🚀"

@app.route('/get-config', methods=['GET'])
def get_config():
    """Sends the Public Client ID to your GitHub frontend."""
    if not PAYPAL_CLIENT_ID:
        return jsonify({"error": "Client ID not set on server"}), 500
    return jsonify({"client_id": PAYPAL_CLIENT_ID})

@app.route('/create-order', methods=['POST'])
def create_order():
    """Creates a PayPal order when someone clicks a button."""
    token = get_access_token()
    amount = request.args.get('amt', '0.01')
    payee_email = request.args.get('to') # For the 'Send' mode
    
    payload = {
        "intent": "CAPTURE",
        "purchase_units": [{
            "amount": {
                "currency_code": "USD", 
                "value": amount
            }
        }]
    }
    
    # If the user is sending money to someone else's email
    if payee_email:
        payload["purchase_units"][0]["payee"] = {"email_address": payee_email}
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    r = requests.post(f"{PAYPAL_BASE_URL}/v2/checkout/orders", json=payload, headers=headers)
    return jsonify(r.json())

@app.route('/capture/<order_id>', methods=['POST'])
def capture(order_id):
    """Finalizes the payment after the user enters their card info."""
    token = get_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    r = requests.post(f"{PAYPAL_BASE_URL}/v2/checkout/orders/{order_id}/capture", headers=headers)
    return jsonify(r.json())

if __name__ == '__main__':
    # Render provides the PORT variable automatically
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
