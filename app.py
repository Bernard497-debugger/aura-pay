import os
import requests
from flask import Flask, render_template_string, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# --- CONFIGURATION ---
PAYPAL_CLIENT_ID = os.environ.get('PAYPAL_CLIENT_ID')
PAYPAL_SECRET = os.environ.get('PAYPAL_SECRET')
# Change to 'https://api-m.sandbox.paypal.com' if using Sandbox keys
PAYPAL_BASE_URL = 'https://api-m.paypal.com' 
FALLBACK_EMAIL = "YOUR_PAYPAL_EMAIL@GMAIL.COM" 

def get_access_token():
    try:
        res = requests.post(
            f"{PAYPAL_BASE_URL}/v1/oauth2/token",
            auth=(PAYPAL_CLIENT_ID, PAYPAL_SECRET),
            data={'grant_type': 'client_credentials'},
            timeout=15
        )
        if res.status_code != 200:
            print(f"Auth Error: {res.text}")
            return None
        return res.json().get('access_token')
    except Exception as e:
        print(f"Connection Error: {e}")
        return None

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AuraPay | QR Terminal</title>
    <script src="https://www.paypal.com/sdk/js?client-id={{ client_id }}&currency=USD"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script>
    <style>
        :root { --accent: #4facfe; --bg: #050505; }
        body { background: var(--bg); color: white; font-family: sans-serif; text-align: center; margin: 0; display: flex; align-items: center; justify-content: center; min-height: 100vh; }
        .container { width: 90%; max-width: 400px; padding: 35px; border: 1px solid rgba(255,255,255,0.1); border-radius: 40px; background: rgba(255,255,255,0.02); backdrop-filter: blur(15px); }
        .logo { font-weight: 900; font-size: 28px; color: var(--accent); margin-bottom: 20px; }
        input { background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); padding: 15px; border-radius: 15px; color: white; text-align: center; width: 85%; margin-bottom: 20px; outline: none; }
        .btn { background: var(--accent); color: white; border: none; padding: 18px; border-radius: 20px; font-weight: 800; width: 100%; cursor: pointer; }
        #qr-box { display: none; background: white; padding: 15px; border-radius: 20px; margin: 20px auto; width: fit-content; }
        #loading { display: none; color: var(--accent); margin-bottom: 10px; font-size: 14px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">AuraPay</div>

        {% if not payee_email %}
        <div class="setup">
            <p style="opacity:0.6;">Enter recipient's PayPal email:</p>
            <input type="email" id="email-in" placeholder="name@example.com">
            <button onclick="location.href='/?to='+document.getElementById('email-in').value" class="btn">Open Terminal</button>
        </div>
        {% else %}
        <div class="terminal">
            <p style="color:var(--accent); font-size:12px;">Recipient: {{ payee_email }}</p>
            <input type="number" id="amt" value="10.00" style="font-size:3rem; background:none; border:none; margin-bottom:0;">
            <p style="font-size:10px; opacity:0.4; margin-bottom:20px;">AMOUNT IN USD</p>
            
            <div id="loading">Connecting to PayPal...</div>
            <div id="paypal-button-container"></div>
            
            <button onclick="showQR()" style="background:none; border:none; color:white; opacity:0.4; margin-top:20px; cursor:pointer;">Show QR Code</button>
            <div id="qr-box"><div id="qrcode"></div></div>
        </div>
        {% endif %}
    </div>

    <script>
        function showQR() {
            const box = document.getElementById('qr-box');
            box.style.display = 'block';
            document.getElementById('qrcode').innerHTML = "";
            new QRCode(document.getElementById("qrcode"), { text: window.location.href, width: 160, height: 160 });
        }

        if("{{ payee_email }}") {
            paypal.Buttons({
                createOrder: async function() {
                    document.getElementById('loading').style.display = 'block';
                    const res = await fetch('/create-order?to={{ payee_email }}', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({ amount: document.getElementById('amt').value })
                    });
                    const data = await res.json();
                    document.getElementById('loading').style.display = 'none';
                    if(!data.id) { alert("Error: Check Render logs for details."); return; }
                    return data.id;
                },
                onApprove: async function(data) {
                    const res = await fetch('/confirm-tx/' + data.orderID, { method: 'POST' });
                    const result = await res.json();
                    if(result.success) alert("Paid successfully!");
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
    if not token: return jsonify({"error": "Auth Failed"}), 401
    
    payee_email = request.args.get('to') or FALLBACK_EMAIL
    amount = request.json.get('amount', '10.00')
    
    payload = {
        "intent": "CAPTURE",
        "purchase_units": [{
            "amount": {"currency_code": "USD", "value": "{:.2f}".format(float(amount))},
            "payee": {"email_address": payee_email}
        }]
    }
    
    r = requests.post(f"{PAYPAL_BASE_URL}/v2/checkout/orders", 
                     json=payload, 
                     headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    return jsonify(r.json()), r.status_code

@app.route('/confirm-tx/<order_id>', methods=['POST'])
def confirm_tx(order_id):
    token = get_access_token()
    r = requests.post(f"{PAYPAL_BASE_URL}/v2/checkout/orders/{order_id}/capture", 
                     headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    return jsonify({"success": r.status_code in [200, 201]})

if __name__ == '__main__':
    # CRITICAL RENDER FIX:
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
