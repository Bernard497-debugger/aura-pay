import os
import requests
from flask import Flask, render_template_string, jsonify, request

app = Flask(__name__)

# CONFIG - Pydroid/Render environment
# If testing locally on Pydroid, you might need to hardcode these 
# but for Render, keep the os.environ.get lines.
PAYPAL_CLIENT_ID = os.environ.get('PAYPAL_CLIENT_ID', 'PASTE_YOUR_ID_HERE_IF_TESTING_ON_PHONE')
PAYPAL_SECRET = os.environ.get('PAYPAL_SECRET', 'PASTE_YOUR_SECRET_HERE_IF_TESTING_ON_PHONE')
PAYPAL_BASE_URL = 'https://api-m.paypal.com' # Use live for real testing

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
    <title>AuraPay Mobile</title>
    <script src="https://www.paypal.com/sdk/js?client-id={{ client_id }}&currency=USD"></script>
    <style>
        body { background: #050505; color: white; font-family: sans-serif; text-align: center; padding-top: 50px; }
        .container { width: 90%; max-width: 400px; margin: auto; padding: 20px; border: 1px solid #333; border-radius: 20px; }
        input { width: 80%; padding: 15px; margin: 20px 0; background: #111; border: 1px solid #4facfe; color: white; border-radius: 10px; font-size: 20px; text-align: center; }
        #paypal-button-container { margin-top: 20px; }
    </style>
</head>
<body>
    <div class="container">
        <h2 style="color:#4facfe">AuraPay</h2>
        <p style="font-size: 12px; opacity: 0.5;">Mobile Terminal</p>
        <input type="number" id="amt" value="10.00">
        <div id="paypal-button-container"></div>
    </div>

    <script>
        paypal.Buttons({
            createOrder: function(data, actions) {
                return fetch('/create-order', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ amount: document.getElementById('amt').value })
                }).then(res => {
                    if (!res.ok) throw new Error('Network response was not ok');
                    return res.json();
                }).then(order => order.id);
            },
            onApprove: function(data, actions) {
                return fetch('/confirm-tx/' + data.orderID, { method: 'POST' })
                    .then(res => res.json()).then(result => {
                        if(result.success) alert("Paid!");
                    });
            },
            onError: function(err) {
                alert("PAYPAL ERROR: Check your Client ID and Secret in Render settings.");
            }
        }).render('#paypal-button-container');
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
    if not token:
        return jsonify({"error": "Auth failed"}), 401
    
    amount = request.json.get('amount', '10.00')
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "intent": "CAPTURE",
        "purchase_units": [{"amount": {"currency_code": "USD", "value": amount}}]
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
