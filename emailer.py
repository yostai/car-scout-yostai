"""
Car Scout - Email sender.
Sends a daily summary of new listings via Gmail SMTP.
"""

import os
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

log = logging.getLogger(__name__)


def build_listing_card(l):
    image_html = (
        f'<img src="{l["image_url"]}" style="width:100%;max-width:400px;border-radius:6px;margin-bottom:8px;" />'
        if l.get("image_url") else
        '<div style="width:100%;height:160px;background:#f0f0f0;border-radius:6px;margin-bottom:8px;display:flex;align-items:center;justify-content:center;color:#999;">No image</div>'
    )

    price_str = f"${l['price']}" if l.get('price') else "Price not listed"
    mileage_str = f"{l['mileage']:,} mi." if l.get('mileage') else "Mileage unknown"
    location_str = l.get('location') or "Location unknown"
    source_str = l.get('source', '')
    vehicle_str = l.get('vehicle', '')

    return f"""
    <div style="background:#fff;border:1px solid #e0e0e0;border-radius:8px;padding:16px;
                margin-bottom:16px;max-width:480px;font-family:Arial,sans-serif;">
      {image_html}
      <div style="font-size:11px;color:#888;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:4px;">
        {source_str} &bull; {vehicle_str}
      </div>
      <div style="font-size:15px;font-weight:bold;color:#222;margin-bottom:8px;line-height:1.3;">
        {l['title']}
      </div>
      <div style="display:flex;gap:16px;margin-bottom:12px;font-size:14px;">
        <span style="color:#1a7a2e;font-weight:bold;">{price_str}</span>
        <span style="color:#555;">{mileage_str}</span>
        <span style="color:#555;">{location_str}</span>
      </div>
      <div style="font-size:12px;color:#888;margin-bottom:12px;font-style:italic;">
        ⚠️ Verify manually: non-smoking, garage kept, area of listing
      </div>
      <a href="{l['url']}"
         style="display:inline-block;background:#1a7a2e;color:#fff;padding:8px 18px;
                border-radius:5px;text-decoration:none;font-size:13px;font-weight:bold;">
        View Listing →
      </a>
    </div>
    """


def build_email_html(new_listings, all_listings):
    today = datetime.now().strftime("%A, %B %d, %Y")
    count = len(new_listings)
    header_msg = f"{count} new match{'es' if count != 1 else ''} found today" if count else "No new matches today"

    cards_html = "".join(build_listing_card(l) for l in new_listings)

    if not new_listings:
        cards_html = """
        <p style="color:#666;font-size:14px;padding:20px 0;">
            No new listings matching your criteria were found today.
            Check back tomorrow — or <a href="YOUR_SITE_URL">view all current matches</a>.
        </p>
        """

    total_str = f"{len(all_listings)} total listings in the last 30 days"

    return f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"></head>
    <body style="background:#f5f5f5;margin:0;padding:20px;font-family:Arial,sans-serif;">
      <div style="max-width:520px;margin:0 auto;">

        <!-- Header -->
        <div style="background:#1a7a2e;color:#fff;padding:20px 24px;border-radius:8px 8px 0 0;">
          <div style="font-size:20px;font-weight:bold;">🚗 Car Scout</div>
          <div style="font-size:13px;opacity:0.85;margin-top:4px;">{today}</div>
        </div>

        <!-- Summary bar -->
        <div style="background:#fff;border-left:4px solid #1a7a2e;padding:14px 20px;
                    border-bottom:1px solid #e0e0e0;font-size:15px;font-weight:bold;color:#222;">
          {header_msg}
        </div>

        <!-- Listings -->
        <div style="background:#f5f5f5;padding:16px;">
          {cards_html}
        </div>

        <!-- Footer -->
        <div style="background:#fff;padding:14px 20px;border-radius:0 0 8px 8px;
                    border-top:1px solid #e0e0e0;font-size:12px;color:#999;text-align:center;">
          {total_str} &bull; Honda Pilot &amp; Toyota 4Runner &bull; 50mi of Hackettstown, NJ
        </div>

      </div>
    </body>
    </html>
    """


def send_summary(new_listings, all_listings, recipient_email, config):
    if not recipient_email:
        log.warning("No recipient email configured — skipping send")
        return

    smtp_host = os.getenv('SMTP_HOST', 'smtp.gmail.com')
    smtp_port = int(os.getenv('SMTP_PORT', '587'))
    smtp_user = os.getenv('SMTP_USER', '')
    smtp_password = os.getenv('SMTP_PASSWORD', '')

    if not smtp_user or not smtp_password:
        log.error("SMTP_USER or SMTP_PASSWORD not set — cannot send email")
        return

    count = len(new_listings)
    subject = (
        f"🚗 Car Scout: {count} new match{'es' if count != 1 else ''} today"
        if count else
        "🚗 Car Scout: No new matches today"
    )

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = smtp_user
    msg['To'] = recipient_email

    html = build_email_html(new_listings, all_listings)
    msg.attach(MIMEText(html, 'html'))

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_user, recipient_email, msg.as_string())
        log.info(f"Email sent to {recipient_email}: {subject}")
    except Exception as e:
        log.error(f"Failed to send email: {e}")
        raise
