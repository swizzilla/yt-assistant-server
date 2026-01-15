from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.config import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_NUMBER
from app.database import get_db, Account
from app.services.youtube import exchange_code_for_credentials
from twilio.rest import Client

router = APIRouter()


def send_whatsapp_message(to: str, message: str):
    """Send WhatsApp confirmation"""
    if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_WHATSAPP_NUMBER:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        client.messages.create(
            body=message,
            from_=TWILIO_WHATSAPP_NUMBER,
            to=to,
        )


@router.get("/callback", response_class=HTMLResponse)
async def oauth_callback(
    request: Request,
    db: Session = Depends(get_db),
    code: str = None,
    state: str = None,
    error: str = None,
):
    """Handle Google OAuth callback"""

    # Simple HTML response
    def html_response(title: str, message: str, success: bool = True):
        color = "#22c55e" if success else "#ef4444"
        return f"""
        <!DOCTYPE html>
        <html>
        <head><title>{title}</title></head>
        <body style="font-family: system-ui; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; background: #111;">
            <div style="text-align: center; color: white;">
                <h1 style="color: {color};">{title}</h1>
                <p>{message}</p>
                <p style="color: #666; margin-top: 2rem;">You can close this window.</p>
            </div>
        </body>
        </html>
        """

    if error:
        return html_response("Authorization Failed", f"Error: {error}", success=False)

    if not code or not state:
        return html_response("Error", "Missing authorization code.", success=False)

    # Parse state: account_id:phone_number
    try:
        parts = state.split(":")
        account_id = int(parts[0])
        phone_number = parts[1] if len(parts) > 1 else None
    except (ValueError, IndexError):
        return html_response("Error", "Invalid state.", success=False)

    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        return html_response("Error", "Account not found.", success=False)

    # Exchange code for credentials
    try:
        exchange_code_for_credentials(code, account.credentials_path)
    except Exception as e:
        return html_response("Authorization Failed", f"Error: {str(e)}", success=False)

    # Send WhatsApp confirmation
    if phone_number:
        try:
            send_whatsapp_message(phone_number, f"Account '{account.name}' authorized! Send 'upload' to start.")
        except Exception:
            pass  # Don't fail if WhatsApp message fails

    return html_response("Success!", f"Account '{account.name}' is now connected.")
