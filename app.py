import os
import requests
from flask import Flask, render_template_string, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# --- CONFIGURATION ---
# These should be your "Live" credentials from the auto-created PayPal app
PAYPAL_CLIENT_ID = os.environ.get('PAYPAL_CLIENT_ID')
PAYPAL_SECRET = os.environ.get('PAYPAL_SECRET')
PAYPAL_BASE_URL = 'https://api-m.paypal.com' 

def get_access_token():
    try:
        res = requests.post(
            f"{PAYPAL_BASE_URL}/v1/oauth2/token",
            auth=(PAYPAL_CLIENT_ID, PAYPAL_SECRET),
            data={'grant_type': 'client_credentials'},
            timeout=15
        )
        return res.json().get('access_token') if res.status_code == 200 else None
    except: return None

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>AuraPay | Public Platform</title>
    <script src="https://www.paypal.com/sdk/js?client-id={{ client_id }}&currency=USD"></script>
    <style>
        :root { --accent: #00ff88; --bg: #050505; }
        body { background: var(--bg); color: white; font-family: -apple-system, sans-serif; text-align: center; margin: 0; display: flex; align-items: center; justify-content: center; min-height: 100vh; }
        .container { width: 92%; max-width: 400px; padding: 40px 25px; border-radius: 40px; background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.1); backdrop-filter: blur(15px); }
        .main-input { width: 100%; background: transparent; border: none; color: white; font-size: 4rem; font-weight: 800; text-align: center; outline: none; margin-bottom: 20px; }
        .email-input { width: 85%; background: #111; border: 1px solid #333; padding: 18px; border-radius: 20px; color: white; text-align: center; font-size: 16px; margin-bottom: 15px; }
        .btn { background: var(--accent); color: #000; border: none; padding: 18px; border-radius: 20px; font-weight: 800; width: 100%; cursor: pointer; }
        #setup-ui, #terminal-ui, #success-screen { display: none; }
    </style>
</head>
<body>
    <div class="container">
        <div id="setup-ui">
            <h2>Setup Receiver</h2>
            <input type="email" id="merchant-email" class="email-input" placeholder="PayPal Email">
            <button onclick="saveEmail()" class="btn">Launch Terminal</button>
        </div>

        <div id="terminal-ui">
            <input type="number" id="sale-amt" class="main-input" value="1.00" step="0.01">
            <p id="display-email" style="opacity: 0.5; font-size: 12px; margin-bottom: 20px;"></p>
            <div id="paypal-button-container"></div>
            <button onclick="clearStorage()" style="background:none; border:none; color:grey; margin-top:20px;">Switch Account</button>
        </div>

        <div id="success-screen">
            <h1 style="color:var(--accent)">✓ PAID</h1>
            <button onclick="location.reload()" class="btn">New Sale</button>
        </div>
    </div>

    <script>
        const savedEmail = localStorage.getItem('aurapay_email');
        
        if (savedEmail) {
            document.getElementById('terminal-ui').style.display = 'block';
            document.getElementById('display-email').innerText = "Receiver: " + savedEmail;
            initPaypal(savedEmail);
        } else {
            document.getElementById('setup-ui').style.display = 'block';
        }

        function saveEmail() {
            const email = document.getElementById('merchant-email').value;
            if (email.includes('@')) {
                localStorage.setItem('aurapay_email', email);
                location.reload();
            }
        }

        function clearStorage() {
            localStorage.removeItem('aurapay_email');
            location.reload();
        }

        function initPaypal(email) {
            paypal.Buttons({
                createOrder: function() {
                    return fetch('/create-order?to=' + encodeURIComponent(email), {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({ amount: document.getElementById('sale-amt').value })
                    }).then(res => res.json()).then(data => data.id);
                },
                onApprove: function(data) {
                    return fetch('/capture/' + data.orderID, { method: 'POST' })
                    .then(() => {
                        document.getElementById('terminal-ui').style.display = 'none';
                        document.getElementById('success-screen').style.display = 'block';
                    });
                }
            }).render('#paypal-button-container');
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE, client_id=PAYPAL_CLIENT_ID)

@app.route('/create-order', methods=['POST'])
def create_order():
    token = get_access_token()
    payee_email = request.args.get('to')
    amount = request.json.get('amount', '1.00')
    
    # Logic: The 'payee' field directs the money to the User's email
    payload = {
        "intent": "CAPTURE",
        "purchase_units": [{
            "amount": {"currency_code": "USD", "value": "{:.2f}".format(float(amount))},
            "payee": {"email_address": payee_email}
        }]
    }
    r = requests.post(f"{PAYPAL_BASE_URL}/v2/checkout/orders", json=payload, 
                     headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    return jsonify(r.json())

@app.route('/capture/<order_id>', methods=['POST'])
def capture(order_id):
    token = get_access_token()
    r = requests.post(f"{PAYPAL_BASE_URL}/v2/checkout/orders/{order_id}/capture", 
                     headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    return jsonify(r.json())

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
