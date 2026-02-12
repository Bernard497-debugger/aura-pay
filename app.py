import os
import uuid
import requests
from flask import Flask, render_template_string, jsonify, request

app = Flask(__name__)

# 🛡️ PRODUCTION CONFIGURATION
# These are pulled from Render's "Environment" tab
PAYPAL_CLIENT_ID = os.environ.get('PAYPAL_CLIENT_ID')
PAYPAL_SECRET = os.environ.get('PAYPAL_SECRET')

# Auto-switch URL based on environment (Defaults to Sandbox if not specified)
ENV = os.environ.get('PAYPAL_ENV', 'sandbox') 
PAYPAL_BASE_URL = 'https://api-m.paypal.com' if ENV == 'live' else 'https://api-m.sandbox.paypal.com'

# Mock Database (In production, replace this with a real DB like PostgreSQL)
user_account = {
    "name": "Alex",
    "balance": 1000.00,
    "history": []
}

def get_access_token():
    """Authenticates with PayPal."""
    try:
        response = requests.post(
            f"{PAYPAL_BASE_URL}/v1/oauth2/token",
            auth=(PAYPAL_CLIENT_ID, PAYPAL_SECRET),
            data={'grant_type': 'client_credentials'},
            timeout=10
        )
        response.raise_for_status()
        return response.json().get('access_token')
    except Exception as e:
        print(f"Auth Error: {e}")
        return None

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GlassBank Pro</title>
    <script src="https://www.paypal.com/sdk/js?client-id={{ client_id }}&currency=USD"></script>
    <style>
        body { margin: 0; background: #0a0a0a; font-family: 'Inter', sans-serif; color: white; display: flex; justify-content: center; align-items: center; min-height: 100vh; }
        .app-container { width: 90%; max-width: 400px; padding: 30px; border-radius: 40px; background: rgba(255, 255, 255, 0.03); backdrop-filter: blur(20px); border: 1px solid rgba(255, 255, 255, 0.1); box-shadow: 0 25px 50px rgba(0,0,0,0.5); }
        .balance-amount { font-size: 3rem; font-weight: 800; margin: 10px 0 30px 0; color: #00d2ff; }
        .tabs { display: flex; gap: 10px; margin-bottom: 25px; }
        .tab-btn { flex: 1; padding: 12px; border-radius: 15px; border: 1px solid rgba(255,255,255,0.1); background: rgba(255,255,255,0.05); color: white; cursor: pointer; transition: 0.3s; }
        .tab-btn.active { background: white; color: black; font-weight: bold; }
        .action-card { background: rgba(255, 255, 255, 0.05); padding: 20px; border-radius: 25px; display: none; }
        .action-card.active { display: block; }
        input { width: 100%; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); border-radius: 12px; color: white; font-size: 16px; padding: 12px; margin-bottom: 15px; box-sizing: border-box; }
        .send-btn { width: 100%; padding: 16px; border-radius: 15px; border: none; background: #00d2ff; color: white; font-weight: bold; cursor: pointer; }
        .history-item { display: flex; justify-content: space-between; padding: 12px 0; border-bottom: 1px solid rgba(255,255,255,0.05); }
    </style>
</head>
<body>
    <div class="app-container">
        <p style="opacity:0.5; margin:0; letter-spacing:1px;">TOTAL BALANCE</p>
        <div class="balance-amount">${{ "%.2f"|format(user.balance) }}</div>

        <div class="tabs">
            <button class="tab-btn active" onclick="showTab('deposit')">Deposit</button>
            <button class="tab-btn" onclick="showTab('send')">Send</button>
        </div>

        <div id="deposit-tab" class="action-card active">
            <input type="number" id="dep-amt" value="85" placeholder="Deposit Amount">
            <div id="paypal-button-container"></div>
