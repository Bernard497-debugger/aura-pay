import os
import requests
from flask import Flask, render_template_string, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app) # This prevents "Cross-Origin" blocks on mobile browsers

# CONFIG
PAYPAL_CLIENT_ID = os.environ.get('PAYPAL_CLIENT_ID')
PAYPAL_SECRET = os.environ.get('PAYPAL_SECRET')
PAYPAL_BASE_URL = 'https://api-m.paypal.com' 

def get_access_token():
    try:
        response = requests.post(
            f"{PAYPAL_BASE_URL}/v1/oauth2/token",
            auth=(PAYPAL_CLIENT_ID, PAYPAL_SECRET),
            data={'grant_type': 'client_credentials'},
            timeout=15
        )
        return response.json().get('access_token')
    except Exception as e:
        print(f"Auth Error: {e}")
        return None

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AuraPay | QR Terminal</title>
    <script src="https://www.paypal.com/sdk/js?client-id={{ client_id }}&currency=USD"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script>
    <style>
        :root { --accent: #4facfe; --bg: #050505; }
        body { background: var(--bg); color: white; font-family: sans-serif; text-align: center; margin: 0; display: flex; align-items: center; justify-content: center; min-height: 100vh; }
        .container { width: 90%; max-width: 400px; padding: 35px; border: 1px solid rgba(255,255,255,0.1); border-radius: 40px; background: rgba(255,255,255,0.02); backdrop-filter: blur(15px); }
        .logo { font-weight: 900; font-size: 26px; color: var(--accent); margin-bottom: 25px; }
        .btn { background: var(--accent); color: white; border: none; padding: 18px; border-radius: 20px; font-weight: 800; width: 100%; cursor: pointer; }
        input { background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); padding: 15px; border-radius: 15px; color: white; text-align: center; width: 80%; margin-bottom: 20px; }
        #loading { display: none; color: var(--accent); font-size: 12px; margin-top: 10px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">AuraPay</div>

        {% if not payee_email %}
        <div class="setup-box">
            <input type="email" id="user-email" placeholder="Recipient PayPal Email">
            <button onclick="window.location.href='/?to='+document.getElementById('user-email').value" class="btn">Launch Terminal</button>
        </div>
        {% else %}
        <div id="terminal">
            <p style="font-size:12px; color:var(--accent);">Recipient: {{ payee_email }}</p>
            <input type="number" id="amt" value="10.00" style="font-size: 2rem; border:none; background:none;">
            <div id="loading">Connecting to Secure Server...</div>
            <div id="paypal-button-container"></div>
        </div>
        {% endif %}
    </div>

    <script>
        if("{{ payee_email }}") {
            paypal.Buttons({
                createOrder: async function(data, actions) {
                    document.getElementById('loading').style.display = 'block';
                    try {
                        const response = await fetch('/create-order?to={{ payee_email }}', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({ amount: document.getElementById('amt').value })
                        });
                        
                        const orderData = await response.json();
                        
                        if (!orderData.id) {
                            throw new Error('Order creation failed');
                        }
                        
                        document.getElementById('loading').style.display = 'none';
                        return orderData.id;
                    } catch (err) {
                        document.getElementById('loading').style.display = 'none';
                        alert("Error: Server is sleeping or credentials invalid.");
                        console.error(err);
                    }
                },
                onApprove: async function(data, actions) {
                    const response = await fetch('/confirm-tx/' + data.orderID, { method: 'POST' });
                    const result = await response.json();
                    if(result.success) alert("Payment Complete!");
                }
            }).render('#paypal-button-container');
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    payee_email = request.args.get('to')
    return render_template_string(HTML_TEMPLATE, client_id=PAYPAL_CLIENT_ID, payee_email=payee_email)

@app.route('/create-order', methods=['POST'])
def create_order():
    token = get_access_token()
    if not token: return jsonify({"error": "No Token"}), 500
    
    payee_email = request.args.get('to')
    amount = request.json.get('amount', '10.00')
    
    payload = {
        "intent": "CAPTURE",
        "purchase_units": [{
            "amount": {"currency_code": "USD", "value": amount},
            "payee": {"email_address": payee_email}
        }]
    }
    
    r = requests.post(f"{PAYPAL_BASE_URL}/v2/checkout/orders", 
                     json=payload, 
                     headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    return jsonify(r.json())

@app.route('/confirm-tx/<order_id>', methods=['POST'])
def confirm_tx(order_id):
    token = get_access_token()
    r = requests.post(f"{PAYPAL_BASE_URL}/v2/checkout/orders/{order_id}/capture", 
                     headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    return jsonify({"success": r.status_code in [200, 201]})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
