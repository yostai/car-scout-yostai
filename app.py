"""
Car Scout - Flask API server.
Serves listing data to the frontend and handles config updates.

Run: python3 app.py
Default port: 5000
"""

import json
import os
import logging
from flask import Flask, jsonify, request, abort
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

app = Flask(__name__)
CORS(app)  # Allow requests from yost.ai

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, 'config.json')


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


def save_config(data):
    with open(CONFIG_PATH, 'w') as f:
        json.dump(data, f, indent=2)


def check_admin(req):
    password = req.headers.get('X-Admin-Password') or req.json.get('admin_password', '') if req.is_json else ''
    admin_pw = os.getenv('ADMIN_PASSWORD', '')
    if not admin_pw or password != admin_pw:
        abort(401, 'Unauthorized')


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/health')
def health():
    return jsonify({'status': 'ok'})


@app.route('/api/listings')
def get_listings():
    from database import init_db, get_all_listings
    init_db()
    days = int(request.args.get('days', 30))
    listings = get_all_listings(days=days)
    return jsonify({'listings': listings, 'count': len(listings)})


@app.route('/api/config', methods=['GET'])
def get_config():
    config = load_config()
    # Don't expose the email address publicly
    safe = {k: v for k, v in config.items() if k != 'notification_email'}
    return jsonify(safe)


@app.route('/api/config', methods=['POST'])
def update_config():
    check_admin(request)
    data = request.json
    config = load_config()

    # Only allow updating safe fields
    allowed = ['year_min', 'mileage_min', 'mileage_max', 'zip', 'radius_miles',
               'one_owner', 'no_accidents', 'notification_email', 'send_empty_summary']
    for key in allowed:
        if key in data:
            config[key] = data[key]

    save_config(config)
    logging.info(f"Config updated: {data}")
    return jsonify({'status': 'saved'})


@app.route('/api/run', methods=['POST'])
def trigger_run():
    """Manually trigger a scrape run (for testing)."""
    check_admin(request)
    import threading

    def run():
        import subprocess
        subprocess.run(['python3', os.path.join(BASE_DIR, 'scheduler.py')])

    threading.Thread(target=run, daemon=True).start()
    return jsonify({'status': 'started'})


if __name__ == '__main__':
    from database import init_db
    init_db()
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
