import os
import requests
from flask import Flask, render_template_string, jsonify, request

app = Flask(__name__)

# --- CONFIGURATION ---
# These must be set in your Render Environment Variables
PAYPAL_CLIENT_ID = os.environ.get('PAYPAL_CLIENT_ID')
PAYPAL_SECRET = os.environ.get('PAYPAL_SECRET')
# Set to 'live' for real money, 'sandbox' for testing
ENV = os.environ.get('PAYPAL_ENV', 'live') 
PAYPAL_BASE_URL = 'https://api-m.paypal.com' if ENV == 'live' else 'https://api-m.sandbox.paypal.com'

def get_access_token():
    try:
        response = requests.post(
            f"{PAYPAL_BASE_URL}/v1/oauth2/token",
            auth=(PAYPAL_CLIENT_ID, PAYPAL_SECRET),
            data={'grant_type': 'client_credentials'},
            timeout=10
        )
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
    <title>AuraPay | Global Terminal</title>
    <script src="https://www.paypal.com/sdk/js?client-id={{ client_id }}&currency=USD"></script>
    <style>
        :root { --accent: #4facfe; --bg: #050505; }
        body { margin: 0; background: var(--bg); font-family: -apple-system, sans-serif; color: white; display: flex; justify-content: center; align-items: center; min-height: 100vh; overflow: hidden; }
        
        .app-container { 
            width: 92%; max-width: 400px; padding: 40px 30px; 
            border-radius: 40px; background: rgba(255,255,255,0.03); 
            backdrop-filter: blur(50px); border: 1px solid rgba(255,255,255,0.1); 
            text-align: center; box-shadow: 0 20px 50px rgba(0,0,0,0.5);
        }

        .logo { font-weight: 900; font-size: 28px; color: var(--accent); margin-bottom: 5px; letter-spacing: -1px; }
        .tagline { font-size: 12px; opacity: 0.4; margin-bottom: 30px; display: block; }
        
        /* Onboarding UI */
        .onboard-form { display: flex; flex-direction: column; gap: 15px; }
        .input-field { 
            background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); 
            padding: 18px; border-radius: 20px; color: white; text-align: center; font-size: 16px; outline: none;
        }
        .primary-btn { 
            background: var(--accent); color: white; border: none; padding: 18px; 
            border-radius: 20px; font-weight: 800; cursor: pointer; transition: 0.3s;
        }
        .primary-btn:hover { opacity: 0.8; transform: scale(0.98); }

        /* Terminal UI */
        .payee-info { font-size: 12px; background: rgba(79, 172, 254, 0.1); color: var(--accent); padding: 8px 15px; border-radius: 20px; display: inline-block; margin-bottom: 25px; }
        .amount-display { width: 100%; background: transparent; border: none; color: white; font-size: 4rem; font-weight: 800; text-align: center; outline: none; margin-bottom: 5px; }
        .fee-text { font-size: 11px; opacity: 0.3; margin-bottom: 30px; }

        #success-screen { 
            display: none; position: absolute; inset: 0; background: #000; 
            border-radius: 40px; z-index: 100; flex-direction: column; 
            justify-content: center; align-items: center; 
        }
    </style>
</head>
<body>
    <div class="app-container">
        <div id="success-screen">
            <h1 style="color: #00ff88; font-size: 60px; margin: 0;">✓</h1>
            <h2>Payment Sent</h2>
            <p style="opacity:0.5;">Verified by AuraPay</p>
            <button onclick="location.reload()" class="primary-btn" style="margin-top:20px; padding: 10px 30px;">New Transaction</button>
        </div>

        <div class="logo">AuraPay</div>
        <span class="tagline">INSTANT PAYMENT TERMINAL</span>

        {% if not payee_email %}
        <div class="onboard-form">
            <input type="email" id="email-setup" class="input-field" placeholder="Enter your PayPal Email">
            <button onclick="createTerminal()" class="primary-btn">Generate My Terminal</button>
            <p style="font-size: 10px; opacity: 0.3;">By using this service, you agree to our 1% platform fee.</p>
        </div>
        {% else %}
        <div id="terminal">
            <div class="payee-info">To: {{ payee_email }}</div>
            <input type="number" id="pay-amount" class="amount-display" value="20.00" oninput="calcFee(this.value)">
            <div class="fee-text" id="fee-notice">Includes $0.20 platform fee</div>
            
            <div id="paypal-button-container"></div>
            
            <button onclick="copyLink()" style="background:none; border:none; color:white; opacity:0.3; margin-top:25px; cursor:pointer; font-size:12px;">🔗 Copy Payment Link</button>
        </div>
        {% endif %}
    </div>

    <script>
        function createTerminal() {
            const email = document.getElementById('email-setup').value;
            if(email.includes('@')) {
                window.location.href = '/?to=' + encodeURIComponent(email);
            } else {
                alert("Please enter a valid email.");
            }
        }

        function calcFee(val) {
            const fee = (val * 0.01).toFixed(2);
            document.getElementById('fee-notice').innerText = `Includes $${fee} platform fee`;
        }

        function copyLink() {
            navigator.clipboard.writeText(window.location.href);
            alert("Link copied! Share this with your customers.");
        }

        // Only load buttons if we have a recipient
        if ("{{ payee_email }}") {
            paypal.Buttons({
                style: { shape: 'pill', color: 'blue', layout: 'vertical', label: 'pay' },
                createOrder: function(data, actions) {
                    return fetch('/create-order?to={{ payee_email }}', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({ amount: document.getElementById('pay-amount').value })
                    }).then(res => res.json()).then(order => order.id);
                },
                onApprove: function(data, actions) {
                    return fetch('/confirm-tx/' + data.orderID, { method: 'POST' })
                        .then(res => res.json()).then(result => {
                            if(result.success) document.getElementById('success-screen').style.display = 'flex';
                        });
                },
                onError: function(err) {
                    console.error("PayPal Error:", err);
                    alert("The payment form couldn't load. Please check your internet or try a different recipient email.");
                }
            }).render('#paypal-button-container');
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    # Detect recipient from URL (?to=email@example.com)
    payee_email = request.args.get('to')
    return render_template_string(HTML_TEMPLATE, client_id=PAYPAL_CLIENT_ID, payee_email=payee_email)

@app.route('/create-order', methods=['POST'])
def create_order():
    token = get_access_token()
    payee_email = request.args.get('to')
    amount = request.json.get('amount', '0.00')
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # Simple order creation. 
    # NOTE: To collect the 1% fee automatically, you must be a PayPal Partner.
    # For now, this routes 100% of the money to the 'payee_email'.
    payload = {
        "intent": "CAPTURE",
        "purchase_units": [{
            "amount": {
                "currency_code": "USD",
                "value": "{:.2f}".format(float(amount))
            },
            "payee": {
                "email_address": payee_email
            }
        }]
    }
    
    response = requests.post(f"{PAYPAL_BASE_URL}/v2/checkout/orders", json=payload, headers=headers)
    return jsonify(response.json())

@app.route('/confirm-tx/<order_id>', methods=['POST'])
def confirm_tx(order_id):
    token = get_access_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    response = requests.post(f"{PAYPAL_BASE_URL}/v2/checkout/orders/{order_id}/capture", headers=headers)
    return jsonify({"success": response.status_code in [200, 201]})

if __name__ == '__main__':
    # Render uses the PORT environment variable
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
