import os
import sqlite3
import uuid
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string, session
from flask_cors import CORS

app = Flask(__name__)
# The secret key keeps user sessions secure
app.secret_key = os.environ.get('SESSION_KEY', 'AURA_ULTIMATE_SECRET_99')
CORS(app)

# --- BANKING PRECISION UTILS ---
def to_cents(amount):
    return int(Decimal(str(amount)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) * 100)

def from_cents(cents):
    return "{:.2f}".format(Decimal(cents) / 100)

def get_db():
    conn = sqlite3.connect('bank.db')
    conn.row_factory = sqlite3.Row
    return conn

# --- DATABASE INITIALIZATION ---
def init_db():
    conn = get_db()
    conn.execute('''CREATE TABLE IF NOT EXISTS accounts 
                    (user_id TEXT PRIMARY KEY, balance_cents INTEGER DEFAULT 0)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS ledger 
                    (txn_id TEXT, sender TEXT, receiver TEXT, amount_cents INTEGER, timestamp TEXT, type TEXT)''')
    conn.commit()
    conn.close()

init_db()

# --- UI TEMPLATE (AURA NEON DESIGN) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AuraPay Terminal | Private API</title>
    <style>
        :root { --accent: #00ff88; --bg: #050505; }
        body { background: var(--bg); color: white; font-family: sans-serif; margin: 0; padding: 10px; text-align: center; }
        .card { background: #111; border: 1px solid #222; padding: 25px; border-radius: 30px; max-width: 400px; margin: 20px auto; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }
        .balance-display { background: #000; padding: 15px; border-radius: 15px; border: 1px dashed #333; margin-bottom: 20px; }
        .amount-input { background: transparent; border: none; color: white; font-size: 3rem; width: 100%; text-align: center; outline: none; font-weight: 800; }
        input[type="text"] { width: 100%; padding: 12px; border-radius: 12px; border: 1px solid #333; background: #000; color: white; margin-bottom: 10px; box-sizing: border-box; }
        .mode-btn { width: 100%; padding: 15px; border-radius: 12px; border: none; background: var(--accent); color: black; font-weight: bold; cursor: pointer; font-size: 1.1rem; margin-top: 10px; }
        .history-section { text-align: left; margin-top: 20px; border-top: 1px solid #222; padding-top: 15px; font-family: monospace; font-size: 10px; color: #666; }
    </style>
</head>
<body>
    <div class="card">
        <h1 style="color: var(--accent);">AuraPay</h1>
        <div class="balance-display">
            <span style="font-size: 10px; color: #666;">AVAILABLE BALANCE (ID: {{ user_id }})</span><br>
            <span style="font-size: 1.8rem; font-weight: bold;">${{ balance }}</span>
        </div>

        <div id="login-section" style="display: {{ 'none' if user_id != 'Guest' else 'block' }}">
            <input type="text" id="my_id" placeholder="Enter Your User ID">
            <button class="mode-btn" onclick="login()">Enter Terminal</button>
        </div>

        <div id="action-section" style="display: {{ 'block' if user_id != 'Guest' else 'none' }}">
            <input type="number" id="main_amount" class="amount-input" value="10.00" step="0.01">
            <input type="text" id="target_id" placeholder="Recipient ID">
            <button class="mode-btn" onclick="handleAction('/api/send')">Send Funds</button>
            <button class="mode-btn" style="background: #222; color: var(--accent); margin-top: 5px;" onclick="handleAction('/api/deposit')">Self-Deposit (Test)</button>
        </div>

        <div class="history-section">
            <strong>RECENT ACTIVITY</strong><br>
            <div id="history-list">
                {% for tx in history %}
                <div>[{{ tx.timestamp[11:16] }}] {{ tx.type }}: ${{ tx.amt }}</div>
                {% endfor %}
            </div>
        </div>
    </div>

    <script>
        function login() {
            const id = document.getElementById('my_id').value;
            if(id) {
                fetch('/set_session?user_id=' + id).then(() => location.reload());
            }
        }

        async function handleAction(url) {
            const data = {
                user_id: "{{ user_id }}",
                sender: "{{ user_id }}",
                receiver: document.getElementById('target_id').value,
                amount: document.getElementById('main_amount').value
            };

            const res = await fetch(url, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(data)
            });
            const result = await res.json();
            if(result.status === 'success') location.reload();
            else alert("Error: " + result.message);
        }
    </script>
</body>
</html>
"""

# --- API ROUTES WITH CENTS LOGIC ---

@app.route('/')
def index():
    user_id = session.get('user_id', 'Guest')
    balance = "0.00"
    history = []
    
    if user_id != 'Guest':
        conn = get_db()
        acc = conn.execute("SELECT balance_cents FROM accounts WHERE user_id = ?", (user_id,)).fetchone()
        if acc:
            balance = from_cents(acc['balance_cents'])
        
        txs = conn.execute("SELECT * FROM ledger WHERE sender = ? OR receiver = ? ORDER BY timestamp DESC LIMIT 5", (user_id, user_id)).fetchall()
        for tx in txs:
            history.append({"timestamp": tx['timestamp'], "type": tx['type'], "amt": from_cents(tx['amount_cents'])})
        conn.close()

    return render_template_string(HTML_TEMPLATE, user_id=user_id, balance=balance, history=history)

@app.route('/set_session')
def set_session():
    user_id = request.args.get('user_id')
    session['user_id'] = user_id
    # Auto-create account if new
    conn = get_db()
    conn.execute("INSERT OR IGNORE INTO accounts (user_id, balance_cents) VALUES (?, 0)", (user_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})

@app.route('/api/deposit', methods=['POST'])
def deposit():
    data = request.json
    user_id = data.get('user_id')
    amount = data.get('amount')
    conn = get_db()
    try:
        amt_cents = to_cents(amount)
        conn.execute("UPDATE accounts SET balance_cents = balance_cents + ? WHERE user_id = ?", (amt_cents, user_id))
        conn.execute("INSERT INTO ledger VALUES (?, ?, ?, ?, ?, ?)", 
                     (str(uuid.uuid4()), 'SYSTEM', user_id, amt_cents, datetime.now().isoformat(), 'DEPOSIT'))
        conn.commit()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    finally:
        conn.close()

@app.route('/api/send', methods=['POST'])
def send():
    data = request.json
    sender, receiver, amount = data.get('sender'), data.get('receiver'), data.get('amount')
    amt_cents = to_cents(amount)
    
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("BEGIN TRANSACTION")
        cursor.execute("SELECT balance_cents FROM accounts WHERE user_id = ?", (sender,))
        row = cursor.fetchone()
        if not row or row['balance_cents'] < amt_cents:
            raise Exception("Insufficient funds")
        
        cursor.execute("UPDATE accounts SET balance_cents = balance_cents - ? WHERE user_id = ?", (amt_cents, sender))
        cursor.execute("UPDATE accounts SET balance_cents = balance_cents + ? WHERE user_id = ?", (amt_cents, receiver))
        cursor.execute("INSERT INTO ledger VALUES (?, ?, ?, ?, ?, ?)", 
                       (str(uuid.uuid4()), sender, receiver, amt_cents, datetime.now().isoformat(), 'TRANSFER'))
        conn.commit()
        return jsonify({"status": "success"})
    except Exception as e:
        conn.rollback()
        return jsonify({"status": "error", "message": str(e)}), 400
    finally:
        conn.close()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
