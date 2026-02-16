import os
import requests
from flask import Flask, render_template_string, jsonify, request

app = Flask(__name__)

# CONFIG
PAYPAL_CLIENT_ID = os.environ.get('PAYPAL_CLIENT_ID')
PAYPAL_SECRET = os.environ.get('PAYPAL_SECRET')
# Set this to https://api-m.paypal.com for real money
PAYPAL_BASE_URL = 'https://api-m.paypal.com' 

def get_access_token():
    try:
        response = requests.post(
            f"{PAYPAL_BASE_URL}/v1/oauth2/token",
            auth=(PAYPAL_CLIENT_ID, PAYPAL_SECRET),
            data={'grant_type': 'client_credentials'},
            timeout=10
        )
        return response.json().get('access_token')
    except:
        return None

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AuraPay | Secure Terminal</title>
    <script src="https://www.paypal.com/sdk/js?client-id={{ client_id }}&currency=USD"></script>
    <style>
        :root { --accent: #4facfe; --bg: #050505; }
        body { background: var(--bg); color: white; font-family: -apple-system, sans-serif; text-align: center; margin: 0; display: flex; align-items: center; justify-content: center; min-height: 100vh; }
        .container { width: 90%; max-width: 400px; padding: 30px; border: 1px solid rgba(255,255,255,0.1); border-radius: 30px; background: rgba(255,255,255,0.02); backdrop-filter: blur(10px); }
        .logo { font-weight: 900; font-size: 24px; color: var(--accent); margin-bottom: 5px; }
        .recipient-box { background: rgba(79, 172, 254, 0.1); padding: 10px; border-radius: 15px; margin-bottom: 25px; font-size: 13px; color: var(--accent); border: 1px solid rgba(79, 172, 254, 0.2); }
        input { width: 100%; background: transparent; border: none; color: white; font-size: 3rem; font-weight: 800; text-align: center; outline: none; margin-bottom: 20px; border-bottom: 1px solid rgba(255,255,255,0.1); }
        label { font-size: 11px; opacity: 0.5; letter-spacing: 1px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">AuraPay</div>
        
        <div class="recipient-box">
            Recipient: <strong>{{ payee_email }}</strong>
        </div>

        <label>AMOUNT TO SEND (USD)</label>
        <input type="number" id="amt" value="10.00" step="0.01">
        
        <div id="paypal-button-container"></div>
    </div>

    <script>
        paypal.Buttons({
            createOrder: function() {
                // We send the 'to' email from the URL to our backend
                return fetch('/create-order?to={{ payee_email }}', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ amount: document.getElementById('amt').value })
                }).then(res => res.json()).then(order => order.id);
            },
            onApprove: function(data) {
                return fetch('/confirm-tx/' + data.orderID, { method: 'POST' })
                    .then(res => res.json()).then(result => {
                        if(result.success) alert("Payment Sent Successfully to {{ payee_email }}");
                    });
            }
        }).render('#paypal-button-container');
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    # If someone goes to yoursite.com/?to=bob@gmail.com, bob gets paid.
    # If they just go to yoursite.com, it uses YOUR email as fallback.
    payee_email = request.args.get('to', 'YOUR_OWN_PAYPAL_EMAIL@GMAIL.COM')
    return render_template_string(HTML_TEMPLATE, client_id=PAYPAL_CLIENT_ID, payee_email=payee_email)

@app.route('/create-order', methods=['POST'])
def create_order():
    token = get_access_token()
    payee_email = request.args.get('to')
    amount = request.json.get('amount', '10.00')
    
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    # The 'payee' block is what makes it multi-user
    payload = {
        "intent": "CAPTURE",
        "purchase_units": [{
            "amount": {"currency_code": "USD", "value": amount},
            "payee": {"email_address": payee_email}
        }]
    }
    
    r = requests.post(f"{PAYPAL_BASE_URL}/v2/checkout/orders", json=payload, headers=headers)
    return jsonify(r.json())

@app.route('/confirm-tx/<order_id>', methods=['POST'])
def confirm_tx(order_id):
    token = get_access_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    r = requests.post(f"{PAYPAL_BASE_URL}/v2/checkout/orders/{order_id}/capture", headers=headers)
    return jsonify({"success": r.status_code in [200, 201]})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
