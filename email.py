import asyncio
import httpx
from flask import current_app


# ─────────────────────────────────────────────────────────────────────────────
# Constants (read from Flask config at runtime)
# ─────────────────────────────────────────────────────────────────────────────
APP_NAME           = "indiaShop"
OTP_EXPIRE_MINUTES = 15


def _cfg(key: str):
    return current_app.config[key]


# ─────────────────────────────────────────────────────────────────────────────
# Brevo send helper
# ─────────────────────────────────────────────────────────────────────────────
def _send_via_brevo(to_email: str, subject: str, html: str) -> None:
    url = "https://api.brevo.com/v3/smtp/email"
    payload = {
        "sender":      {"name": _cfg("SENDER_NAME"), "email": _cfg("SENDER_EMAIL")},
        "to":          [{"email": to_email}],
        "subject":     subject,
        "htmlContent": html,
    }
    headers = {
        "accept":       "application/json",
        "content-type": "application/json",
        "api-key":      _cfg("BREVO_API_KEY"),
    }
    with httpx.Client(timeout=15) as client:
        resp = client.post(url, json=payload, headers=headers)
        if resp.status_code not in (200, 201, 202):
            raise RuntimeError(f"Brevo error {resp.status_code}: {resp.text}")


# ─────────────────────────────────────────────────────────────────────────────
# HTML: OTP (register / verify email)
# ─────────────────────────────────────────────────────────────────────────────
def _otp_html(otp: str, purpose: str) -> str:
    digits = list(otp)
    digit_cells = "".join(
        f'''<td style="padding:0 5px;">
          <div style="
            width:52px;height:64px;
            background:linear-gradient(145deg,#0d1f0f,#0a1a0c);
            border:1.5px solid rgba(52,211,153,0.5);
            border-radius:12px;
            display:inline-block;
            text-align:center;
            line-height:64px;
            font-size:28px;
            font-weight:900;
            color:#34D399;
            font-family:'Courier New',monospace;
            box-shadow:0 0 18px rgba(52,211,153,0.15),inset 0 1px 0 rgba(52,211,153,0.1);
          ">{d}</div>
        </td>'''
        for d in digits
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>{APP_NAME} — Verification Code</title>
</head>
<body style="margin:0;padding:0;background:#060D08;font-family:Georgia,serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#060D08;min-height:100vh;">
<tr><td align="center" style="padding:48px 16px;">
  <table width="520" cellpadding="0" cellspacing="0" style="
    background:#080F09;border-radius:24px;
    border:1px solid rgba(52,211,153,0.18);overflow:hidden;
    box-shadow:0 32px 80px rgba(0,0,0,0.6),0 0 60px rgba(52,211,153,0.04);
  ">
    <tr><td style="padding:0;">
      <div style="background:linear-gradient(135deg,#052210 0%,#083318 40%,#0a4020 100%);
        padding:44px 40px 36px;text-align:center;position:relative;">
        <div style="width:80px;height:80px;border-radius:50%;border:2px solid rgba(52,211,153,0.35);
          margin:0 auto 20px;background:rgba(52,211,153,0.06);font-size:34px;line-height:80px;text-align:center;">🛍️</div>
        <p style="margin:0;font-size:28px;font-weight:700;color:#ECFDF5;letter-spacing:6px;
          font-family:Georgia,serif;text-transform:uppercase;">{APP_NAME}</p>
        <p style="margin:10px 0 0;font-size:11px;color:rgba(52,211,153,0.6);letter-spacing:4px;
          font-family:Arial,sans-serif;text-transform:uppercase;">Verification Code</p>
        <div style="position:absolute;bottom:0;left:0;right:0;height:1px;
          background:linear-gradient(90deg,transparent,rgba(52,211,153,0.4),transparent);"></div>
      </div>
    </td></tr>
    <tr><td style="padding:44px 40px 36px;">
      <p style="margin:0 0 6px;font-size:20px;font-weight:700;color:#F0FDF4;font-family:Georgia,serif;">
        Your one-time code</p>
      <p style="margin:0 0 36px;font-size:14px;color:rgba(255,255,255,0.38);font-family:Arial,sans-serif;line-height:1.6;">
        Use this code to <span style="color:rgba(52,211,153,0.75);">{purpose}</span>.<br/>Do not share it with anyone.
      </p>
      <div style="background:linear-gradient(145deg,#040a05,#070e08);border:1.5px solid rgba(52,211,153,0.22);
        border-radius:18px;padding:32px 16px 24px;text-align:center;margin-bottom:28px;">
        <p style="margin:0 0 22px;font-size:11px;color:rgba(52,211,153,0.4);letter-spacing:3px;
          font-family:Arial,sans-serif;text-transform:uppercase;">Enter this code</p>
        <table style="margin:0 auto;"><tr>{digit_cells}</tr></table>
        <p style="margin:22px 0 0;font-size:12px;color:rgba(255,255,255,0.22);font-family:Arial,sans-serif;">
          ⏰&nbsp;Expires in <span style="color:rgba(52,211,153,0.5);">{OTP_EXPIRE_MINUTES} minutes</span>
        </p>
      </div>
      <table width="100%" cellpadding="0" cellspacing="0"><tr>
        <td style="background:rgba(251,191,36,0.05);border:1px solid rgba(251,191,36,0.2);
          border-left:3px solid rgba(251,191,36,0.6);border-radius:10px;padding:14px 18px;">
          <p style="margin:0;font-size:12.5px;color:rgba(251,191,36,0.75);font-family:Arial,sans-serif;line-height:1.55;">
            ⚠️&nbsp;<strong style="color:rgba(251,191,36,0.9);">{APP_NAME}</strong>
            will never ask for your OTP over phone or email.
          </p>
        </td>
      </tr></table>
    </td></tr>
    <tr><td style="padding:20px 40px 28px;border-top:1px solid rgba(255,255,255,0.05);text-align:center;">
      <p style="margin:0;font-size:11px;color:rgba(255,255,255,0.15);font-family:Arial,sans-serif;letter-spacing:1px;">
        © {APP_NAME} &nbsp;·&nbsp; Automated message — do not reply
      </p>
    </td></tr>
  </table>
</td></tr>
</table>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
# HTML: Password Reset OTP
# ─────────────────────────────────────────────────────────────────────────────
def _reset_html(otp: str, email: str) -> str:
    digits = list(otp)
    digit_cells = "".join(
        f'''<td style="padding:0 5px;">
          <div style="
            width:52px;height:64px;
            background:linear-gradient(145deg,#1a0d06,#130a04);
            border:1.5px solid rgba(251,113,61,0.5);
            border-radius:12px;
            display:inline-block;
            text-align:center;
            line-height:64px;
            font-size:28px;
            font-weight:900;
            color:#FB713D;
            font-family:'Courier New',monospace;
            box-shadow:0 0 18px rgba(251,113,61,0.15),inset 0 1px 0 rgba(251,113,61,0.1);
          ">{d}</div>
        </td>'''
        for d in digits
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>{APP_NAME} — Password Reset</title>
</head>
<body style="margin:0;padding:0;background:#0D0806;font-family:Georgia,serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#0D0806;min-height:100vh;">
<tr><td align="center" style="padding:48px 16px;">
  <table width="520" cellpadding="0" cellspacing="0" style="
    background:#0A0705;border-radius:24px;
    border:1px solid rgba(251,113,61,0.18);overflow:hidden;
    box-shadow:0 32px 80px rgba(0,0,0,0.6),0 0 60px rgba(251,113,61,0.04);
  ">
    <tr><td style="padding:0;">
      <div style="background:linear-gradient(135deg,#1f0a02 0%,#2e1005 40%,#3d1508 100%);
        padding:44px 40px 36px;text-align:center;position:relative;">
        <div style="width:80px;height:80px;border-radius:50%;border:2px solid rgba(251,113,61,0.35);
          margin:0 auto 20px;background:rgba(251,113,61,0.07);font-size:34px;line-height:80px;text-align:center;">🔐</div>
        <p style="margin:0;font-size:28px;font-weight:700;color:#FFF7F5;letter-spacing:6px;
          font-family:Georgia,serif;text-transform:uppercase;">{APP_NAME}</p>
        <p style="margin:10px 0 0;font-size:11px;color:rgba(251,113,61,0.6);letter-spacing:4px;
          font-family:Arial,sans-serif;text-transform:uppercase;">Password Reset</p>
        <div style="position:absolute;bottom:0;left:0;right:0;height:1px;
          background:linear-gradient(90deg,transparent,rgba(251,113,61,0.4),transparent);"></div>
      </div>
    </td></tr>
    <tr><td style="padding:44px 40px 36px;">
      <p style="margin:0 0 6px;font-size:20px;font-weight:700;color:#FFF7F5;font-family:Georgia,serif;">
        Reset your password</p>
      <p style="margin:0 0 36px;font-size:14px;color:rgba(255,255,255,0.38);font-family:Arial,sans-serif;line-height:1.6;">
        Enter this code to reset your password for<br/>
        <span style="color:rgba(251,113,61,0.8);font-family:'Courier New',monospace;font-size:13px;">{email}</span>
      </p>
      <div style="background:linear-gradient(145deg,#080403,#0a0604);border:1.5px solid rgba(251,113,61,0.22);
        border-radius:18px;padding:32px 16px 24px;text-align:center;margin-bottom:28px;">
        <p style="margin:0 0 22px;font-size:11px;color:rgba(251,113,61,0.4);letter-spacing:3px;
          font-family:Arial,sans-serif;text-transform:uppercase;">Reset Code</p>
        <table style="margin:0 auto;"><tr>{digit_cells}</tr></table>
        <p style="margin:22px 0 0;font-size:12px;color:rgba(255,255,255,0.22);font-family:Arial,sans-serif;">
          ⏰&nbsp;Expires in <span style="color:rgba(251,113,61,0.5);">15 minutes</span>
        </p>
      </div>
      <table width="100%" cellpadding="0" cellspacing="0"><tr>
        <td style="background:rgba(239,68,68,0.05);border:1px solid rgba(239,68,68,0.2);
          border-left:3px solid rgba(239,68,68,0.6);border-radius:10px;padding:14px 18px;">
          <p style="margin:0;font-size:12.5px;color:rgba(252,165,165,0.75);font-family:Arial,sans-serif;line-height:1.55;">
            🔒&nbsp;If you did not request a password reset, your account may be at risk.
          </p>
        </td>
      </tr></table>
    </td></tr>
    <tr><td style="padding:20px 40px 28px;border-top:1px solid rgba(255,255,255,0.05);text-align:center;">
      <p style="margin:0;font-size:11px;color:rgba(255,255,255,0.15);font-family:Arial,sans-serif;letter-spacing:1px;">
        © {APP_NAME} &nbsp;·&nbsp; Automated message — do not reply
      </p>
    </td></tr>
  </table>
</td></tr>
</table>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
# HTML: Order Confirmation
# ─────────────────────────────────────────────────────────────────────────────
def _order_confirm_html(order) -> str:
    rows = "".join(
        f"""<tr>
          <td style="padding:10px 12px;border-bottom:1px solid #2a2a2a;color:#e0e0e0;font-size:13px;">
            {item.product.name}</td>
          <td style="padding:10px 12px;border-bottom:1px solid #2a2a2a;color:#aaa;font-size:13px;text-align:center;">
            {item.quantity}</td>
          <td style="padding:10px 12px;border-bottom:1px solid #2a2a2a;color:#34D399;font-size:13px;text-align:right;font-weight:700;">
            ₹{item.subtotal:,.2f}</td>
        </tr>"""
        for item in order.items
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>{APP_NAME} — Order Confirmed</title>
</head>
<body style="margin:0;padding:0;background:#0a0a0a;font-family:Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#0a0a0a;min-height:100vh;">
<tr><td align="center" style="padding:48px 16px;">
  <table width="540" cellpadding="0" cellspacing="0" style="
    background:#111;border-radius:20px;
    border:1px solid rgba(52,211,153,0.2);overflow:hidden;">
    <tr><td style="background:linear-gradient(135deg,#052210,#083318);padding:36px 40px;text-align:center;">
      <p style="margin:0 0 8px;font-size:32px;">🛍️</p>
      <p style="margin:0;font-size:24px;font-weight:800;color:#ECFDF5;letter-spacing:4px;text-transform:uppercase;">{APP_NAME}</p>
      <p style="margin:8px 0 0;font-size:13px;color:rgba(52,211,153,0.7);letter-spacing:2px;text-transform:uppercase;">Order Confirmed</p>
    </td></tr>
    <tr><td style="padding:36px 40px;">
      <p style="font-size:18px;font-weight:700;color:#f0fdf4;margin:0 0 8px;">
        🎉 Thank you for your order!</p>
      <p style="font-size:13px;color:#999;margin:0 0 28px;line-height:1.6;">
        Order <strong style="color:#34D399;">#{order.id}</strong> has been placed successfully.
        Payment method: <strong style="color:#e0e0e0;">{order.payment_method.upper()}</strong>
      </p>

      <table width="100%" cellpadding="0" cellspacing="0" style="border-radius:12px;overflow:hidden;border:1px solid #2a2a2a;">
        <tr style="background:#1a1a1a;">
          <th style="padding:10px 12px;text-align:left;color:#888;font-size:12px;font-weight:600;text-transform:uppercase;">Product</th>
          <th style="padding:10px 12px;text-align:center;color:#888;font-size:12px;font-weight:600;text-transform:uppercase;">Qty</th>
          <th style="padding:10px 12px;text-align:right;color:#888;font-size:12px;font-weight:600;text-transform:uppercase;">Amount</th>
        </tr>
        {rows}
        <tr style="background:#1a1a1a;">
          <td colspan="2" style="padding:14px 12px;color:#ccc;font-weight:700;font-size:14px;">Total</td>
          <td style="padding:14px 12px;text-align:right;color:#34D399;font-weight:800;font-size:18px;">
            ₹{float(order.total_amount):,.2f}</td>
        </tr>
      </table>

      <div style="margin-top:24px;background:#161f17;border:1px solid rgba(52,211,153,0.15);
        border-radius:12px;padding:18px 20px;">
        <p style="margin:0 0 6px;font-size:12px;color:#34D399;text-transform:uppercase;letter-spacing:2px;font-weight:600;">
          Delivery Address</p>
        <p style="margin:0;font-size:13px;color:#ccc;line-height:1.7;">
          {order.address.full_name}<br/>
          {order.address.line1}{', ' + order.address.line2 if order.address.line2 else ''}<br/>
          {order.address.city}, {order.address.state} — {order.address.pincode}<br/>
          📞 {order.address.phone}
        </p>
      </div>
    </td></tr>
    <tr><td style="padding:20px 40px;border-top:1px solid #222;text-align:center;">
      <p style="margin:0;font-size:11px;color:#555;letter-spacing:1px;">
        © {APP_NAME} &nbsp;·&nbsp; Questions? Email support@indiashop.in
      </p>
    </td></tr>
  </table>
</td></tr>
</table>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
# HTML: Order Status Update
# ─────────────────────────────────────────────────────────────────────────────
def _order_status_html(order_id: int, status: str, customer_name: str) -> str:
    status_info = {
        "confirmed": ("✅", "#34D399", "Your order has been confirmed and is being processed."),
        "shipped":   ("🚚", "#60a5fa", "Your order is on its way! Track it with your courier."),
        "delivered": ("🎁", "#a78bfa", "Your order has been delivered. Enjoy your purchase!"),
        "cancelled": ("❌", "#f87171", "Your order has been cancelled. Refund will be processed shortly."),
    }
    icon, color, msg = status_info.get(status, ("📦", "#e0e0e0", f"Order status updated to {status}."))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>{APP_NAME} — Order Update</title>
</head>
<body style="margin:0;padding:0;background:#0a0a0a;font-family:Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#0a0a0a;min-height:100vh;">
<tr><td align="center" style="padding:48px 16px;">
  <table width="520" cellpadding="0" cellspacing="0" style="
    background:#111;border-radius:20px;border:1px solid #222;overflow:hidden;">
    <tr><td style="background:linear-gradient(135deg,#052210,#083318);padding:36px 40px;text-align:center;">
      <p style="margin:0;font-size:24px;font-weight:800;color:#ECFDF5;letter-spacing:4px;text-transform:uppercase;">{APP_NAME}</p>
      <p style="margin:8px 0 0;font-size:12px;color:rgba(52,211,153,0.6);letter-spacing:3px;text-transform:uppercase;">Order Update</p>
    </td></tr>
    <tr><td style="padding:44px 40px;text-align:center;">
      <div style="font-size:56px;margin-bottom:16px;">{icon}</div>
      <p style="font-size:22px;font-weight:800;color:{color};margin:0 0 12px;">
        {status.replace('_',' ').title()}</p>
      <p style="font-size:14px;color:#888;margin:0 0 8px;">Hi {customer_name},</p>
      <p style="font-size:14px;color:#ccc;line-height:1.7;margin:0 0 24px;">{msg}</p>
      <p style="font-size:13px;color:#666;">Order ID: <strong style="color:#e0e0e0;">#{order_id}</strong></p>
    </td></tr>
    <tr><td style="padding:20px 40px;border-top:1px solid #222;text-align:center;">
      <p style="margin:0;font-size:11px;color:#555;">© {APP_NAME} &nbsp;·&nbsp; Automated message — do not reply</p>
    </td></tr>
  </table>
</td></tr>
</table>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
# Public async API
# ─────────────────────────────────────────────────────────────────────────────
async def send_otp_email(email: str, otp: str, purpose: str = "complete your registration"):
    subject = f"{otp} — your {APP_NAME} verification code"
    html    = _otp_html(otp, purpose)
    loop    = asyncio.get_event_loop()
    await loop.run_in_executor(None, _send_via_brevo, email, subject, html)


async def send_reset_email(email: str, otp: str):
    subject = f"Reset your {APP_NAME} password"
    html    = _reset_html(otp, email)
    loop    = asyncio.get_event_loop()
    await loop.run_in_executor(None, _send_via_brevo, email, subject, html)


async def send_order_confirmation(email: str, order):
    subject = f"Order #{order.id} Confirmed — {APP_NAME}"
    html    = _order_confirm_html(order)
    loop    = asyncio.get_event_loop()
    await loop.run_in_executor(None, _send_via_brevo, email, subject, html)


async def send_order_status_update(email: str, order_id: int, status: str, customer_name: str):
    subject = f"Order #{order_id} Update — {status.title()} | {APP_NAME}"
    html    = _order_status_html(order_id, status, customer_name)
    loop    = asyncio.get_event_loop()
    await loop.run_in_executor(None, _send_via_brevo, email, subject, html)


# ─────────────────────────────────────────────────────────────────────────────
# Sync wrappers (for use inside Flask route handlers)
# ─────────────────────────────────────────────────────────────────────────────
def send_otp_email_sync(email: str, otp: str, purpose: str = "complete your registration"):
    asyncio.run(send_otp_email(email, otp, purpose))


def send_reset_email_sync(email: str, otp: str):
    asyncio.run(send_reset_email(email, otp))


def send_order_confirmation_sync(email: str, order):
    asyncio.run(send_order_confirmation(email, order))


def send_order_status_update_sync(email: str, order_id: int, status: str, customer_name: str):
    asyncio.run(send_order_status_update(email, order_id, status, customer_name))
