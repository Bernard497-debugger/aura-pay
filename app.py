import os
import requests
from datetime import datetime, timedelta
from flask import Flask, render_template_string, jsonify, request

app = Flask(__name__)

# 🛡️ LIVE CREDENTIALS
PAYPAL_CLIENT_ID = os.environ.get('PAYPAL_CLIENT_ID')
PAYPAL_SECRET = os.environ.get('PAYPAL_SECRET')
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
    except Exception:
        return None

def get_app_data():
    token = get_access_token()
    if not token: return "0.00", [], 0.0
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    balance = "0.00"
    total_revenue = 0.0
    history = []
    
    try:
        # Fetch Balance
        b_res = requests.get(f"{PAYPAL_BASE_URL}/v1/reporting/balances?currency_code=USD", headers=headers, timeout=10)
        balance = b_res.json()['balances'][0]['total_balance']['value']
        
        # Fetch Transactions (30 Days)
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%dT%H:%M:%SZ')
        t_res = requests.get(
            f"{PAYPAL_BASE_URL}/v1/reporting/transactions?start_date={start_date}&end_date={datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')}&fields=transaction_info", 
            headers=headers, timeout=10
        )
        for tx in t_res.json().get('transaction_details', []):
            info = tx.get('transaction_info', {})
            val = float(info.get('transaction_amount', {}).get('value', 0))
            if val > 0:
                total_revenue += val
                history.append({
                    "type": "Incoming",
                    "amount": val,
                    "date": info.get('transaction_initiation_date', '')[:10]
                })
    except: pass
    return balance, history, total_revenue

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AuraPay | Personal Terminal</title>
    <script src="https://www.paypal.com/sdk/js?client-id={{ client_id }}&currency=USD&components=buttons,card-fields"></script>
    <style>
        :root { --accent: #4facfe; --bg: #050505; --glass: rgba(255, 255, 255, 0.03); }
        body { margin: 0; background: var(--bg); font-family: 'Inter', sans-serif; color: white; display: flex; justify-content: center; align-items: center; min-height: 100vh; overflow-x: hidden; }
        .app-container { width: 92%; max-width: 420px; padding: 30px; border-radius: 40px; background: var(--glass); backdrop-filter: blur(50px); border: 1px solid rgba(255, 255, 255, 0.1); position: relative; }
        
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px; }
        .logo { font-weight: 900; font-size: 20px; background: linear-gradient(45deg, #fff, var(--accent)); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .share-btn { background: var(--glass); border: 1px solid rgba(255,255,255,0.1); color: white; padding: 8px 15px; border-radius: 12px; font-size: 12px; cursor: pointer; }
        
        .balance-card { text-align: center; margin-bottom: 30px; }
        .balance-amount { font-size: 3.8rem; font-weight: 800; margin: 0; letter-spacing: -2px; }
        .revenue-badge { display: inline-block; padding: 4px 12px; background: rgba(0, 255, 136, 0.1); color: #00ff88; border-radius: 20px; font-size: 11px; font-weight: 700; margin-top: 10px; }

        .tabs { display: flex; gap: 5px; background: rgba(255,255,255,0.05); padding: 5px; border-radius: 20px; margin-bottom: 25px; }
        .tab-btn { flex: 1; padding: 12px; border-radius: 16px; border: none; background: transparent; color: white; opacity: 0.5; cursor: pointer; transition: 0.3s; }
        .tab-btn.active { background: rgba(255,255,255,0.1); opacity: 1; font-weight: 700; }

        input { width: 100%; background: transparent; border: none; color: white; font-size: 2.5rem; font-weight: 800; text-align: center; margin-bottom: 20px; outline: none; }
        .card-field { height: 55px; padding: 15px; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); border-radius: 16px; margin-bottom: 10px; box-sizing: border-box; }
        .action-sec { display: none; }
        .action-sec.active { display: block; animation: scaleUp 0.3s ease; }

        .submit-btn { width: 100%; padding: 20px; border-radius: 18px; border: none; background: white; color: black; font-weight: 800; cursor: pointer; font-size: 16px; margin-top: 15px; }
        
        .history { margin-top: 30px; border-top: 1px solid rgba(255,255,255,0.1); padding-top: 20px; }
        .history-item { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; font-size: 14px; }

        /* Success Overlay */
        #success-overlay { display: none; position: absolute; inset: 0; background: #000; border-radius: 40px; z-index: 100; flex-direction: column; justify-content: center; align-items: center; text-align: center; padding: 20px; }
        .check-icon { width: 80px; height: 80px; background: #00ff88; color: black; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 40px; margin-bottom: 20px; }

        @keyframes scaleUp { from { opacity: 0; transform: scale(0.95); } to { opacity: 1; transform: scale(1); } }
    </style>
</head>
<body>
    <div class="app-container">
        <div id="success-overlay">
            <div class="check-icon">✓</div>
            <h2>Payment Received</h2>
            <p style="opacity: 0.6;">The funds have been settled into your account.</p>
            <button class="submit-btn" onclick="location.reload()">Done</button>
        </div>

        <div class="header">
            <div class="logo">AuraPay</div>
            <button class="share-btn" onclick="copyLink()">Share Link</button>
        </div>

        <div class="balance-card">
            <div style="opacity: 0.4; font-size: 11px; letter-spacing: 1px;">AVAILABLE BALANCE</div>
            <div class="balance-amount">${{ balance }}</div>
            <div class="revenue-badge">Total Revenue: ${{ "%.2f"|format(total_revenue) }}</div>
        </div>

        <div class="tabs">
            <button class="tab-btn active" onclick="switchTab('dep', this)">Wallet</button>
            <button class="tab-btn" onclick="switchTab('rec', this)">Terminal</button>
        </div>

        <div style="text-align: center; opacity: 0.4; font-size: 12px; margin-bottom: 5px;">Amount (USD)</div>
        <input type="number" id="main-amt" value="20.00" step="0.01">

        <div id="dep-sec" class="action-sec active">
            <div id="paypal-button-container"></div>
        </div>

        <div id="rec-sec" class="action-sec">
            <div id="card-number-field" class="card-field"></div>
            <div style="display: flex; gap: 10px;">
                <div id="card-expiry-field" class="card-field" style="flex: 2;"></div>
                <div id="card-cvv-field" class="card-field" style="flex: 1;"></div>
            </div>
            <button id="card-btn" class="submit-btn">Complete Payment</button>
        </div>

        <div class="history">
            <div style="font-size: 11px; opacity: 0.3; margin-bottom: 15px;">RECENT LOGS</div>
            {% for item in history[:5] %}
            <div class="history-item">
                <span>{{ item.type }}<br><small style="opacity:0.4">{{ item.date }}</small></span>
                <span style="font-weight: 800; color: #00ff88;">+${{ "%.2f"|format(item.amount) }}</span>
            </div>
            {% endfor %}
        </div>
    </div>

    <script>
        function switchTab(t, b) {
            document.querySelectorAll('.action-sec, .tab-btn').forEach(el => el.classList.remove('active'));
            document.getElementById(t + '-sec').classList.add('active');
            b.classList.add('active');
        }

        function copyLink() {
            navigator.clipboard.writeText(window.location.href);
            alert("Link copied! Send it to anyone who needs to pay you.");
        }

        const createOrder = () => {
            return fetch('/create-order', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ amount: document.getElementById('main-amt').value })
            }).then(res => res.json()).then(data => data.id);
        };

        const onApprove = (data) => {
            return fetch('/confirm-tx/' + data.orderID, { method: 'POST' })
                .then(res => res.json())
                .then(d => { if(d.success) document.getElementById('success-overlay').style.display = 'flex'; });
        };

        // Initialize PayPal
        paypal.Buttons({ createOrder, onApprove }).render('#paypal-button-container');
        
        const cardFields = paypal.CardFields({ createOrder, onApprove });
        if (cardFields.isEligible()) {
            const style = { input: { color: 'white', 'font-size': '16px' } };
            cardFields.NumberField({style}).render('#card-number-field');
            cardFields.ExpiryField({style}).render('#card-expiry-field');
            cardFields.CVVField({style}).render('#card-cvv-field');
            document.getElementById('card-btn').addEventListener('click', () => cardFields.submit());
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    balance, history, total_revenue = get_app_data()
    return render_template_string(HTML_TEMPLATE, client_id=PAYPAL_CLIENT_ID, balance=balance, history=history, total_revenue=total_revenue)

@app.route('/create-order', methods=['POST'])
def create_order():
    token = get_access_token()
    amt = "{:.2f}".format(float(request.json.get('amount', 0)))
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {"intent": "CAPTURE", "purchase_units": [{"amount": {"currency_code": "USD", "value": amt}}]}
    r = requests.post(f"{PAYPAL_BASE_URL}/v2/checkout/orders", json=payload, headers=headers)
    return jsonify(r.json())

@app.route('/confirm-tx/<order_id>', methods=['POST'])
def confirm_tx(order_id):
    token = get_access_token()
    r = requests.post(f"{PAYPAL_BASE_URL}/v2/checkout/orders/{order_id}/capture", headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    return jsonify({"success": r.status_code in [200, 201]})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
