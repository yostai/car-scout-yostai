"""
Car Scout - Daily job runner.
Run this via cron at 6am:
  0 6 * * * cd /opt/car-scout && python3 scheduler.py >> /var/log/car-scout.log 2>&1
"""

import json
import logging
import os
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)
log = logging.getLogger(__name__)


def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(base_dir, 'config.json')

    with open(config_path) as f:
        config = json.load(f)

    from database import init_db, get_new_listings, save_listings, mark_seen
    from scraper import run_all
    from emailer import send_summary

    init_db()

    log.info("Starting Car Scout daily run...")
    all_scraped = run_all(config)

    new_listings = get_new_listings(all_scraped)
    log.info(f"Found {len(all_scraped)} total, {len(new_listings)} new")

    recipient = config.get('notification_email', '')
    send_empty = config.get('send_empty_summary', False)

    if new_listings or send_empty:
        from database import get_all_listings
        all_listings = get_all_listings()
        send_summary(new_listings, all_listings, recipient, config)
    else:
        log.info("No new listings and send_empty_summary=false — skipping email")

    save_listings(all_scraped)
    mark_seen([l['id'] for l in all_scraped])

    log.info("Run complete.")


if __name__ == '__main__':
    main()
