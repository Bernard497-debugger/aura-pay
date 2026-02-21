import os, requests, uuid
from datetime import datetime
from flask import Flask, render_template_string, jsonify, request, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = os.environ.get('SESSION_KEY', 'AURA_ULTRA_HIDDEN_777')

# --- DATABASE ---
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///aurapay.db').replace("postgres://", "postgresql://", 1)
db = SQLAlchemy(app)

# --- MODELS ---
class UserAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    balance = db.Column(db.Float, default=0.0)
    is_admin = db.Column(db.Boolean, default=False) # 🛡️ This identifies YOU

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user_account.id'))
    tx_id = db.Column(db.String(50), unique=True)
    amount = db.Column(db.Float)
    type = db.Column(db.String(20)) # DEPOSIT, WITHDRAW
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()

# --- PAYPAL CONFIG ---
PAYPAL_CLIENT_ID = os.environ.get('PAYPAL_CLIENT_ID')
PAYPAL_SECRET = os.environ.get('PAYPAL_SECRET')

def get_access_token():
    res = requests.post("https://api-m.paypal.com/v1/oauth2/token",
                         auth=(PAYPAL_CLIENT_ID, PAYPAL_SECRET),
                         data={'grant_type': 'client_credentials'})
    return res.json().get('access_token')

# --- THE HIDDEN LEDGER LOGIC ---
@app.route('/')
def index():
    if 'user_id' not in session: return redirect(url_for('login'))
    
    user = UserAccount.query.get(session['user_id'])
    
    # SECURITY: Fetch ONLY this user's transactions
    history = Transaction.query.filter_by(user_id=user.id).order_by(Transaction.timestamp.desc()).limit(5).all()
    
    # If the user is an Admin, we show them a special "Admin Dashboard" link
    return render_template_string(HTML_TEMPLATE, 
                                balance=user.balance, 
                                email=user.email, 
                                history=history, 
                                is_admin=user.is_admin,
                                client_id=PAYPAL_CLIENT_ID)

# --- DEPOSIT (CREDITS INDIVIDUAL USER) ---
@app.route('/capture/<order_id>', methods=['POST'])
def capture(order_id):
    if 'user_id' not in session: return jsonify({"status": "error"}), 401
    token = get_access_token()
    res = requests.post(f"https://api-m.paypal.com/v2/checkout/orders/{order_id}/capture", 
                         headers={"Authorization": f"Bearer {token}"})
    
    if res.json().get('status') == 'COMPLETED':
        user = UserAccount.query.get(session['user_id'])
        full_val = float(res.json()['purchase_units'][0]['payments']['captures'][0]['amount']['value'])
        clean_amt = full_val / 1.01 # Subtract your 1% fee
        
        user.balance += clean_amt
        db.session.add(Transaction(user_id=user.id, tx_id="AP-"+str(uuid.uuid4())[:8].upper(), amount=clean_amt, type="DEPOSIT"))
        db.session.commit()
    return jsonify(res.json())

# --- UI (SHOWS ONLY PERSONAL BALANCE) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AuraPay | My Wallet</title>
    <script src="https://www.paypal.com/sdk/js?client-id={{ client_id }}&currency=USD"></script>
    <style>
        body { background:#0a0a0a; color:white; font-family:sans-serif; text-align:center; padding:20px; }
        .card { background:#111; padding:30px; border-radius:25px; max-width:400px; margin:auto; border:1px solid #222; }
        .bal { font-size: 3rem; color:#00ff88; margin: 10px 0; font-weight:bold; }
        .history { text-align:left; font-size:11px; color:#666; margin-top:20px; }
    </style>
</head>
<body>
    <div class="card">
        <h2 style="margin:0;">AuraPay Wallet</h2>
        <p style="font-size:12px; color:#444;">{{ email }}</p>
        
        <div class="bal">${{ "%.2f"|format(balance) }}</div>
        <p style="font-size:10px; opacity:0.5;">Available Personal Funds</p>

        <div id="paypal-button-container"></div>
        
        <div class="history">
            <strong>MY RECENT ACTIVITY</strong>
            {% for tx in history %}
                <div style="border-bottom:1px solid #222; padding:5px 0;">
                    {{ tx.type }}: +${{ "%.2f"|format(tx.amount) }} <span style="float:right;">{{ tx.timestamp.strftime('%d %b') }}</span>
                </div>
            {% endfor %}
        </div>
    </div>
</body>
</html>
"""

# Simple Login Logic
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        user = UserAccount.query.filter_by(email=email).first()
        if not user:
            user = UserAccount(email=email)
            db.session.add(user)
            db.session.commit()
        session['user_id'] = user.id
        return redirect(url_for('index'))
    return '<body style="background:#000;color:white;text-align:center;"><form method="post"><h1>AuraPay</h1><input name="email" placeholder="Email"><button>Enter</button></form></body>'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
