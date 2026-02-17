import os
import requests
from flask import Flask, render_template_string, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# --- LIVE CONFIG ---
PAYPAL_CLIENT_ID = os.environ.get('PAYPAL_CLIENT_ID')
PAYPAL_SECRET = os.environ.get('PAYPAL_SECRET')
PAYPAL_BASE_URL = 'https://api-m.paypal.com' 

def get_access_token():
    try:
        res = requests.post(
            f"{PAYPAL_BASE_URL}/v1/oauth2/token",
            auth=(PAYPAL_CLIENT_ID, PAYPAL_SECRET),
            data={'grant_type': 'client_credentials'},
            timeout=10
        )
        return res.json().get('access_token')
    except Exception as e:
        print(f"Auth Error: {e}")
        return None

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>AuraPay Terminal</title>
    <script src="https://www.paypal.com/sdk/js?client-id={{ client_id }}&currency=USD"></script>
    <style>
        :root { --accent: #00ff88; --bg: #050505; }
        body { background: var(--bg); color: white; font-family: sans-serif; margin: 0; padding: 20px; text-align: center; }
        .card { background: #111; border: 1px solid #222; padding: 30px; border-radius: 30px; max-width: 400px; margin: 0 auto; }
        .amount-input { background: transparent; border: none; color: white; font-size: 3.5rem; width: 100%; text-align: center; outline: none; margin: 10px 0; font-weight: 800; }
        .mode-toggle { display: flex; gap: 10px; margin-bottom: 20px; }
        .mode-btn { flex: 1; padding: 10px; border-radius: 12px; border: 1px solid #333; background: #1a1a1a; color: white; cursor: pointer; transition: 0.2s; }
        .mode-btn.active { background: var(--accent); color: black; border-color: var(--accent); font-weight: bold; }
        .email-field { width: 100%; padding: 15px; border-radius: 12px; border: 1px solid #333; background: #000; color: white; margin-bottom: 20px; display: none; box-sizing: border-box; }
        
        /* The Dynamic Label */
        .action-label { font-weight: bold; color: var(--accent); margin-bottom: 15px; font-size: 1.2rem; display: block; }
        #paypal-button-container { min-height: 150px; }
    </style>
</head>
<body>
    <div class="card">
        <h1 style="color: var(--accent); margin-bottom: 5px;">AuraPay</h1>
        <p style="font-size: 10px; opacity: 0.5; letter-spacing: 2px;">LIVE TERMINAL</p>

        <input type="number" id="amount" class="amount-input" value="0.01" step="0.01" oninput="updateActionText()">

        <div class="mode-toggle">
            <button id="dep-btn" class="mode-btn active" onclick="setMode('deposit')">Deposit</button>
            <button id="snd-btn" class="mode-btn" onclick="setMode('send')">Send</button>
        </div>

        <input type="email" id="recipient-email" class="email-field" placeholder="Recipient PayPal Email">

        <span id="dynamic-action-text" class="action-label">Pay $0.01</span>

        <div id="paypal-button-container"></div>
    </div>

    <script>
        let mode = 'deposit';

        function updateActionText() {
            const amt = document.getElementById('amount').value || "0.00";
            const label = document.getElementById('dynamic-action-text');
            const verb = (mode === 'deposit') ? 'Pay' : 'Send';
            label.innerText = `${verb} $${amt}`;
        }

        function setMode(newMode) {
            mode = newMode;
            document.getElementById('dep-btn').classList.toggle('active', mode === 'deposit');
            document.getElementById('snd-btn').classList.toggle('active', mode === 'send');
            document.getElementById('recipient-email').style.display = (mode === 'send') ? 'block' : 'none';
            updateActionText();
        }

        paypal.Buttons({
            style: { shape: 'pill', color: 'gold', layout: 'vertical', label: 'pay' },
            createOrder: function(data, actions) {
                const amt = document.getElementById('amount').value;
                const email = document.getElementById('recipient-email').value;
                
                let url = '/create-order?amt=' + amt;
                if(mode === 'send' && email) url += '&to=' + encodeURIComponent(email);

                return fetch(url, { method: 'POST' })
                    .then(res => res.json())
                    .then(order => order.id);
            },
            onApprove: function(data, actions) {
                return fetch('/capture/' + data.orderID, { method: 'POST' })
                    .then(res => res.json())
                    .then(() => {
                        alert('AuraPay Success: Transaction Complete');
                        location.reload();
                    });
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
    amount = request.args.get('amt', '0.01')
    payee_email = request.args.get('to')

    payload = {
        "intent": "CAPTURE",
        "purchase_units": [{
            "amount": {"currency_code": "USD", "value": amount}
        }]
    }

    if payee_email:
        payload["purchase_units"][0]["payee"] = {"email_address": payee_email}

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
