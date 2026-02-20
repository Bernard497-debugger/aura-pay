from flask import Flask, jsonify, request, render_template_string, session
import requests
import uuid
from datetime import datetime

app = Flask(__name__)
app.secret_key = "KHALI_DIGITAL_KEY_2026" # Key for securing the ledger

# --- CONFIGURATION ---
PAYPAL_CLIENT_ID = "YOUR_LIVE_CLIENT_ID"
PAYPAL_SECRET = "YOUR_LIVE_SECRET"
PAYPAL_BASE_URL = 'https://api-m.paypal.com' 

HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AuraPay Terminal | Khali Digital</title>
    <style>
        body { background: #050505; color: #00ff88; font-family: 'Courier New', monospace; margin: 0; padding: 20px; display: flex; justify-content: center; }
        .terminal { border: 2px solid #00ff88; padding: 25px; border-radius: 15px; background: #111; width: 100%; max-width: 450px; box-shadow: 0 0 30px rgba(0,255,136,0.1); }
        .balance-card { background: #000; border: 1px dashed #00ff88; padding: 20px; border-radius: 10px; margin: 20px 0; }
        .balance-amt { font-size: 2.5rem; font-weight: bold; }
        input { background: #000; border: 1px solid #00ff88; color: #00ff88; padding: 12px; width: 80%; margin: 10px 0; font-size: 1.1rem; text-align: center; }
        .history-box { margin-top: 30px; text-align: left; border-top: 1px solid #222; padding-top: 15px; max-height: 200px; overflow-y: auto; }
        .tx-item { font-size: 0.75rem; margin-bottom: 8px; border-left: 3px solid #00ff88; padding-left: 10px; }
        .disclosure { font-size: 0.65rem; color: #555; margin-top: 30px; line-height: 1.4; text-align: justify; }
        .badge { background: #00ff88; color: #000; padding: 2px 6px; font-size: 0.6rem; font-weight: bold; border-radius: 3px; }
    </style>
</head>
<body>
    <div class="terminal">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <h2 style="margin:0;">AURAPAY v1.1</h2>
            <span class="badge">SECURED BY KHALI</span>
        </div>
        
        <div class="balance-card">
            <div style="font-size: 0.8rem; color: #888;">AVAILABLE LIQUIDITY</div>
            <div class="balance-amt">$<span id="bal">{{ "{:.2f}".format(balance) }}</span></div>
        </div>

        <label>DEPOSIT AMOUNT (USD):</label><br>
        <input type="number" id="amount" value="10.00" step="0.01">
        <p style="font-size: 0.7rem; color: #888;">+ 1.0% Institutional Processing Fee</p>
        
        <div id="paypal-button-container"></div>

        <div class="history-box">
            <strong style="font-size: 0.8rem;">TRANSACTION LEDGER:</strong>
            <div id="history-list" style="margin-top: 10px;">
                {% for tx in history %}
                <div class="tx-item">
                    ID: {{ tx.id }}<br>
                    DATE: {{ tx.date }} | AMT: +${{ tx.amt }} | STATUS: <span style="color: #00ff88;">SETTLED</span>
                </div>
                {% endfor %}
                {% if not history %}
                <div style="color: #444; font-size: 0.8rem;">NO RECENT ACTIVITY</div>
                {% endif %}
            </div>
        </div>

        <div class="disclosure">
            <strong>CUSTODY DISCLOSURE:</strong> AuraPay utilizes a 'Pooled Fund' model. 
            When you deposit, your balance is updated in our digital ledger and the fiat liquidity 
            is secured in our Master Business Account to facilitate instant 'Send' features 
            and 24/7 ecosystem accessibility.
        </div>
    </div>

    <script src="https://www.paypal.com/sdk/js?client-id={{ client_id }}&currency=USD"></script>
    <script>
        paypal.Buttons({
            createOrder: async () => {
                const amt = document.getElementById('amount').value;
                const response = await fetch('/create-order?amt=' + amt, { method: 'POST' });
                const order = await response.json();
                return order.id;
            },
            onApprove: async (data) => {
                const response = await fetch('/capture/' + data.orderID, { method: 'POST' });
                const result = await response.json();
                if(result.status === 'COMPLETED') {
                    location.reload(); // Refresh to update balance and history
                }
            }
        }).render('#paypal-button-container');
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    if 'balance' not in session: session['balance'] = 0.00
    if 'history' not in session: session['history'] = []
    return render_template_string(HTML_PAGE, 
                                client_id=PAYPAL_CLIENT_ID, 
                                balance=session['balance'],
                                history=session['history'])

@app.route('/create-order', methods=['POST'])
def create_order():
    user_amt = float(request.args.get('amt', '1.00'))
    total_to_charge = "{:.2f}".format(user_amt * 1.01) # Add the 1% fee

    auth = (PAYPAL_CLIENT_ID, PAYPAL_SECRET)
    token = requests.post(f"{PAYPAL_BASE_URL}/v1/oauth2/token", auth=auth, data={'grant_type': 'client_credentials'}).json().get('access_token')

    res = requests.post(
        f"{PAYPAL_BASE_URL}/v2/checkout/orders",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={
            "intent": "CAPTURE",
            "purchase_units": [{
                "amount": {"currency_code": "USD", "value": total_to_charge},
                "description": "AuraPay Digital Asset Deposit"
            }]
        }
    )
    return jsonify(res.json())

@app.route('/capture/<order_id>', methods=['POST'])
def capture(order_id):
    auth = (PAYPAL_CLIENT_ID, PAYPAL_SECRET)
    token = requests.post(f"{PAYPAL_BASE_URL}/v1/oauth2/token", auth=auth, data={'grant_type': 'client_credentials'}).json().get('access_token')
    
    res = requests.post(
        f"{PAYPAL_BASE_URL}/v2/checkout/orders/{order_id}/capture",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    ).json()

    if res.get('status') == 'COMPLETED':
        amt_paid = float(res['purchase_units'][0]['payments']['captures'][0]['amount']['value'])
        # The balance added is the amount MINUS the 1% fee
        deposited_amt = amt_paid / 1.01
        
        session['balance'] += deposited_amt
        new_tx = {
            "id": "TX-" + str(uuid.uuid4())[:8].upper(),
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "amt": "{:.2f}".format(deposited_amt)
        }
        session['history'].insert(0, new_tx)
        session.modified = True

    return jsonify(res)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
