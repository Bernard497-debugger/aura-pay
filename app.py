import os
import requests
from flask import Flask, render_template_string, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# --- CONFIG ---
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
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AuraStore | Retail Terminal</title>
    <script src="https://www.paypal.com/sdk/js?client-id={{ client_id }}&currency=USD"></script>
    <style>
        :root { --accent: #00ff88; --bg: #0a0a0a; --card: #1a1a1a; }
        body { background: var(--bg); color: white; font-family: sans-serif; margin: 0; padding: 20px; }
        .header { text-align: center; margin-bottom: 30px; }
        .logo { font-weight: 900; font-size: 24px; color: var(--accent); }
        
        /* Product Grid */
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; max-width: 600px; margin: 0 auto; }
        .product-card { background: var(--card); border-radius: 20px; padding: 15px; text-align: center; border: 1px solid #333; }
        .product-card img { width: 100%; border-radius: 10px; margin-bottom: 10px; }
        .price { color: var(--accent); font-weight: bold; font-size: 1.2rem; display: block; margin: 5px 0; }
        
        .buy-btn { background: var(--accent); color: black; border: none; padding: 10px; width: 100%; border-radius: 10px; font-weight: bold; cursor: pointer; }
        
        /* Overlay for Payment */
        #payment-modal { display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.9); z-index:100; align-items:center; justify-content:center; }
        .modal-content { background: #111; padding: 30px; border-radius: 30px; width: 80%; max-width: 400px; text-align: center; }
    </style>
</head>
<body>

    <div class="header">
        <div class="logo">AuraStore</div>
        <p style="font-size: 12px; opacity: 0.5;">RETAIL MODE</p>
    </div>

    <div class="grid">
        <div class="product-card">
            <div style="font-size: 40px;">👕</div>
            <span class="name">Premium Tee</span>
            <span class="price">$25.00</span>
            <button class="buy-btn" onclick="openPayment('25.00', 'Premium Tee')">BUY</button>
        </div>

        <div class="product-card">
            <div style="font-size: 40px;">🧢</div>
            <span class="name">Aura Cap</span>
            <span class="price">$15.00</span>
            <button class="buy-btn" onclick="openPayment('15.00', 'Aura Cap')">BUY</button>
        </div>

        <div class="product-card">
            <div style="font-size: 40px;">👟</div>
            <span class="name">Urban Kicks</span>
            <span class="price">$85.00</span>
            <button class="buy-btn" onclick="openPayment('85.00', 'Urban Kicks')">BUY</button>
        </div>

        <div class="product-card">
            <div style="font-size: 40px;">🕶️</div>
            <span class="name">Sunnies</span>
            <span class="price">$12.00</span>
            <button class="buy-btn" onclick="openPayment('12.00', 'Sunnies')">BUY</button>
        </div>
    </div>

    <div id="payment-modal">
        <div class="modal-content">
            <h2 id="item-name">Checkout</h2>
            <p id="item-price" style="color:var(--accent); font-size: 1.5rem;"></p>
            <div id="paypal-button-container"></div>
            <button onclick="closeModal()" style="background:none; border:none; color:white; margin-top:20px; opacity:0.5;">Cancel</button>
        </div>
    </div>

    <script>
        let currentPrice = "0.00";
        const merchantEmail = localStorage.getItem('aurapay_email') || "your-email@example.com";

        function openPayment(price, name) {
            currentPrice = price;
            document.getElementById('item-name').innerText = name;
            document.getElementById('item-price').innerText = "$" + price;
            document.getElementById('payment-modal').style.display = 'flex';
            renderButtons();
        }

        function closeModal() {
            document.getElementById('payment-modal').style.display = 'none';
        }

        function renderButtons() {
            document.getElementById('paypal-button-container').innerHTML = "";
            paypal.Buttons({
                createOrder: function() {
                    return fetch('/create-order?to=' + encodeURIComponent(merchantEmail), {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({ amount: currentPrice })
                    }).then(res => res.json()).then(data => data.id);
                },
                onApprove: function(data) {
                    return fetch('/capture/' + data.orderID, { method: 'POST' })
                    .then(() => {
                        alert("Purchase Successful!");
                        closeModal();
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
    amount = request.json.get('amount', '10.00')
    
    payload = {
        "intent": "CAPTURE",
        "purchase_units": [{
            "amount": {"currency_code": "USD", "value": amount},
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
