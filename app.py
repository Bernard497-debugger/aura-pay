import os
import requests
from flask import Flask, render_template_string, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# --- CONFIGURATION ---
# Use the 'Live' Client ID and Secret from your PayPal Activation App
PAYPAL_CLIENT_ID = os.environ.get('PAYPAL_CLIENT_ID')
PAYPAL_SECRET = os.environ.get('PAYPAL_SECRET')
PAYPAL_BASE_URL = 'https://api-m.paypal.com' # Verified Live URL

def get_access_token():
    try:
        res = requests.post(
            f"{PAYPAL_BASE_URL}/v1/oauth2/token",
            auth=(PAYPAL_CLIENT_ID, PAYPAL_SECRET),
            data={'grant_type': 'client_credentials'},
            timeout=15
        )
        return res.json().get('access_token') if res.status_code == 200 else None
    except Exception as e:
        print(f"Auth Error: {e}")
        return None

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>AuraPay | Retail Engine</title>
    <script src="https://www.paypal.com/sdk/js?client-id={{ client_id }}&currency=USD"></script>
    <style>
        :root { --accent: #00ff88; --bg: #050505; --card: #121212; }
        body { background: var(--bg); color: white; font-family: -apple-system, sans-serif; margin: 0; padding: 20px; text-align: center; }
        .logo { font-weight: 900; font-size: 28px; color: var(--accent); letter-spacing: -1px; margin-bottom: 5px; }
        .badge { font-size: 10px; background: rgba(0, 255, 136, 0.1); color: var(--accent); padding: 4px 10px; border-radius: 20px; text-transform: uppercase; font-weight: bold; }
        
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-top: 30px; }
        .product-card { background: var(--card); border: 1px solid #222; border-radius: 25px; padding: 20px; transition: 0.3s; }
        .product-card:active { transform: scale(0.95); }
        .icon { font-size: 40px; margin-bottom: 10px; display: block; }
        .price { color: var(--accent); font-weight: 800; display: block; margin: 10px 0; font-size: 1.2rem; }
        
        .buy-btn { background: var(--accent); color: black; border: none; padding: 12px; width: 100%; border-radius: 15px; font-weight: 800; cursor: pointer; }

        #setup-screen { display: none; padding: 40px 20px; }
        .email-input { width: 90%; background: #111; border: 1px solid #333; padding: 18px; border-radius: 20px; color: white; text-align: center; margin-bottom: 15px; font-size: 16px; }

        #payment-modal { display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.95); z-index:1000; align-items:center; justify-content:center; backdrop-filter: blur(10px); }
        .modal-content { background: #111; padding: 30px; border-radius: 35px; width: 85%; max-width: 400px; border: 1px solid #333; }
    </style>
</head>
<body>

    <div id="setup-screen">
        <div class="logo">AuraPay</div>
        <p>Enter the receiver's PayPal email to start.</p>
        <input type="email" id="merchant-email" class="email-input" placeholder="email@example.com">
        <button onclick="saveMerchant()" class="buy-btn">Launch Terminal</button>
    </div>

    <div id="storefront" style="display:none;">
        <div class="logo">AuraPay</div>
        <span class="badge">Live Terminal Verified</span>
        
        <div class="grid">
            <div class="product-card">
                <span class="icon">👕</span>
                <span>Premium Tee</span>
                <span class="price">$25.00</span>
                <button class="buy-btn" onclick="openCheckout('25.00', 'Premium Tee')">BUY</button>
            </div>
            <div class="product-card">
                <span class="icon">👟</span>
                <span>Urban Kicks</span>
                <span class="price">$85.00</span>
                <button class="buy-btn" onclick="openCheckout('85.00', 'Urban Kicks')">BUY</button>
            </div>
        </div>
        <button onclick="logout()" style="margin-top:40px; background:none; border:none; color:grey; font-size:12px;">Reset Terminal</button>
    </div>

    <div id="payment-modal">
        <div class="modal-content">
            <h2 id="item-name">Checkout</h2>
            <p id="item-price" style="font-size: 2rem; color: var(--accent); font-weight: 800;"></p>
            <div id="paypal-button-container"></div>
            <button onclick="closeModal()" style="margin-top:20px; background:none; border:none; color:white; opacity:0.5;">Go Back</button>
        </div>
    </div>

    <script>
        let currentAmt = "0.00";
        const setup = document.getElementById('setup-screen');
        const store = document.getElementById('storefront');

        window.onload = () => {
            if(localStorage.getItem('aura_mail')) {
                store.style.display = 'block';
            } else {
                setup.style.display = 'block';
            }
        };

        function saveMerchant() {
            const m = document.getElementById('merchant-email').value;
            if(m.includes('@')) {
                localStorage.setItem('aura_mail', m);
                location.reload();
            }
        }

        function logout() {
            localStorage.removeItem('aura_mail');
            location.reload();
        }

        function openCheckout(price, name) {
            currentAmt = price;
            document.getElementById('item-name').innerText = name;
            document.getElementById('item-price').innerText = "$" + price;
            document.getElementById('payment-modal').style.display = 'flex';
            renderPaypal();
        }

        function closeModal() {
            document.getElementById('payment-modal').style.display = 'none';
        }

        function renderPaypal() {
            document.getElementById('paypal-button-container').innerHTML = '';
            paypal.Buttons({
                style: { layout: 'vertical', color: 'gold', shape: 'pill', label: 'pay' },
                createOrder: function() {
                    const m = localStorage.getItem('aura_mail');
                    return fetch(`/create-order?to=${encodeURIComponent(m)}`, {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({ amount: currentAmt })
                    }).then(res => res.json()).then(data => data.id);
                },
                onApprove: function(data) {
                    return fetch(`/capture/${data.orderID}`, { method: 'POST' })
                    .then(res => res.json())
                    .then(res => {
                        if(res.id) {
                            alert("Payment Successful!");
                            closeModal();
                        }
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
    payee = request.args.get('to')
    amount = request.json.get('amount')
    
    payload = {
        "intent": "CAPTURE",
        "purchase_units": [{
            "amount": {"currency_code": "USD", "value": amount},
            "payee": {"email_address": payee}
        }]
    }
    r = requests.post(f"{PAYPAL_BASE_URL}/v2/checkout/orders", json=payload, 
                     headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    return jsonify(r.json()), r.status_code

@app.route('/capture/<order_id>', methods=['POST'])
def capture(order_id):
    token = get_access_token()
    r = requests.post(f"{PAYPAL_BASE_URL}/v2/checkout/orders/{order_id}/capture", 
                     headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    return jsonify(r.json()), r.status_code

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
