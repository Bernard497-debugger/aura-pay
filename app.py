import os
import requests
import uuid
from datetime import datetime
from flask import Flask, render_template_string, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# --- DATABASE FIX FOR RENDER ---
db_url = os.environ.get('DATABASE_URL')
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url or 'sqlite:///aurapay.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- LIVE PAYPAL CONFIG ---
PAYPAL_CLIENT_ID = os.environ.get('PAYPAL_CLIENT_ID')
PAYPAL_SECRET = os.environ.get('PAYPAL_SECRET')
PAYPAL_BASE_URL = 'https://api-m.paypal.com' 

# --- SQL MODELS ---
class UserAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    balance = db.Column(db.Float, default=0.0)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tx_id = db.Column(db.String(50), unique=True)
    amount = db.Column(db.Float)
    fee = db.Column(db.Float)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()

# --- AUTH HELPER ---
def get_access_token():
    res = requests.post(f"{PAYPAL_BASE_URL}/v1/oauth2/token",
                        auth=(PAYPAL_CLIENT_ID, PAYPAL_SECRET),
                        data={'grant_type': 'client_credentials'})
    return res.json().get('access_token')

# --- UI TEMPLATE (Includes Live History) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>AuraPay Terminal</title>
    <script src="https://www.paypal.com/sdk/js?client-id={{ client_id }}&currency=USD"></script>
    <style>
        body { background: #050505; color: white; font-family: sans-serif; text-align: center; padding: 20px; }
        .card { background: #111; border: 1px solid #222; padding: 30px; border-radius: 20px; max-width: 400px; margin: 0 auto; }
        .balance { font-size: 2rem; color: #00ff88; margin-bottom: 20px; }
        .history { text-align: left; font-size: 12px; margin-top: 20px; color: #888; border-top: 1px solid #222; padding-top: 10px; }
    </style>
</head>
<body>
    <div class="card">
        <h1>AuraPay</h1>
        <div class="balance">${{ "%.2f"|format(balance) }}</div>
        <div id="paypal-button-container"></div>
        <div class="history">
            <strong>AUDIT LOG:</strong>
            {% for tx in history %}
            <div>{{ tx.timestamp.strftime('%H:%M') }} | {{ tx.tx_id }} | +${{ "%.2f"|format(tx.amount) }}</div>
            {% endfor %}
        </div>
    </div>
    <script>
        paypal.Buttons({
            createOrder: function() {
                return fetch('/create-order?amt=1.00', { method: 'POST' }).then(res => res.json()).then(data => data.id);
            },
            onApprove: function(data) {
                return fetch('/capture/' + data.orderID, { method: 'POST' }).then(() => location.reload());
            }
        }).render('#paypal-button-container');
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    master = UserAccount.query.filter_by(email="master@aurapay").first()
    bal = master.balance if master else 0.0
    history = Transaction.query.order_by(Transaction.timestamp.desc()).limit(5).all()
    return render_template_string(HTML_TEMPLATE, client_id=PAYPAL_CLIENT_ID, balance=bal, history=history)

@app.route('/create-order', methods=['POST'])
def create_order():
    token = get_access_token()
    amt = request.args.get('amt', '1.00')
    total = "{:.2f}".format(float(amt) * 1.01)
    r = requests.post(f"{PAYPAL_BASE_URL}/v2/checkout/orders", 
                     headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                     json={"intent": "CAPTURE", "purchase_units": [{"amount": {"currency_code": "USD", "value": total}}]})
    return jsonify(r.json())

@app.route('/capture/<order_id>', methods=['POST'])
def capture(order_id):
    token = get_access_token()
    r = requests.post(f"{PAYPAL_BASE_URL}/v2/checkout/orders/{order_id}/capture", 
                     headers={"Authorization": f"Bearer {token}"})
    data = r.json()
    if data.get('status') == 'COMPLETED':
        val = float(data['purchase_units'][0]['payments']['captures'][0]['amount']['value'])
        clean = val / 1.01
        
        # SAVE TO RENDER POSTGRES
        new_tx = Transaction(tx_id="AP-"+str(uuid.uuid4())[:8], amount=clean, fee=val-clean)
        master = UserAccount.query.filter_by(email="master@aurapay").first()
        if not master: master = UserAccount(email="master@aurapay", balance=0.0)
        master.balance += clean
        db.session.add_all([new_tx, master])
        db.session.commit()
    return jsonify(data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
