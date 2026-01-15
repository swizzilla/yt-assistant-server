import httpx
from fastapi import APIRouter, Request, Depends, Form, BackgroundTasks
from fastapi.responses import Response
from sqlalchemy.orm import Session
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse

from app.config import (
    TWILIO_ACCOUNT_SID,
    TWILIO_AUTH_TOKEN,
    TWILIO_WHATSAPP_NUMBER,
    ALLOWED_PHONE_NUMBER,
    TEMP_DIR,
    CREDENTIALS_DIR,
)
from app.database import get_db, Account
from app.config import GOOGLE_CLIENT_ID
from app.services.conversation import ConversationManager
from app.services.video import process_youtube_video, cleanup_temp_files
from app.services.youtube import upload_video, get_authorization_url

router = APIRouter()


def get_twilio_client() -> Client:
    return Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


def send_whatsapp_message(to: str, message: str):
    client = get_twilio_client()
    client.messages.create(
        body=message,
        from_=TWILIO_WHATSAPP_NUMBER,
        to=to,
    )


async def download_media(media_url: str, auth: tuple) -> str:
    import uuid
    async with httpx.AsyncClient() as client:
        response = await client.get(media_url, auth=auth, follow_redirects=True)
        response.raise_for_status()

        content_type = response.headers.get("content-type", "")
        ext = ".jpg" if "jpeg" in content_type or "jpg" in content_type else ".png" if "png" in content_type else ".jpg"

        filename = f"thumb_{uuid.uuid4().hex[:8]}{ext}"
        filepath = TEMP_DIR / filename

        with open(filepath, "wb") as f:
            f.write(response.content)

        return str(filepath)


def process_and_upload(phone_number: str, db: Session):
    """Background task to process and upload video"""
    try:
        manager = ConversationManager(db, phone_number)
        data = manager.get_upload_data()

        if not data["account"]:
            send_whatsapp_message(phone_number, "Error: No account selected.")
            manager.reset()
            return

        account = data["account"]
        thumbnail_path = data.get("thumbnail_path")

        send_whatsapp_message(phone_number, "Downloading audio...")

        video_path = process_youtube_video(
            data["youtube_url"],
            thumbnail_path if thumbnail_path and not thumbnail_path.startswith("http") else None,
        )

        send_whatsapp_message(phone_number, "Uploading to YouTube...")

        result = upload_video(
            credentials_path=account.credentials_path,
            video_path=video_path,
            title=data["title"],
            description=data["description"],
            privacy=data["privacy"],
            thumbnail_path=thumbnail_path if thumbnail_path and not thumbnail_path.startswith("http") else None,
        )

        send_whatsapp_message(phone_number, f"Done!\n{result['video_url']}")

        cleanup_temp_files(video_path)
        if thumbnail_path and not thumbnail_path.startswith("http"):
            cleanup_temp_files(thumbnail_path)

        manager.mark_complete()

    except Exception as e:
        send_whatsapp_message(phone_number, f"Error: {str(e)}")
        manager = ConversationManager(db, phone_number)
        manager.reset()


def create_account_and_get_auth_url(db: Session, account_name: str, phone_number: str) -> str:
    """Create account in DB and return OAuth URL"""
    credentials_path = CREDENTIALS_DIR / f"{account_name}_credentials.pickle"

    account = Account(
        name=account_name,
        credentials_path=str(credentials_path),
    )
    db.add(account)
    db.commit()
    db.refresh(account)

    # State format: account_id:phone_number (to send confirmation after OAuth)
    state = f"{account.id}:{phone_number}"
    return get_authorization_url(state=state)


@router.post("/webhook")
async def whatsapp_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    From: str = Form(None),
    Body: str = Form(""),
    NumMedia: str = Form("0"),
    MediaUrl0: str = Form(None),
    MediaContentType0: str = Form(None),
):
    response = MessagingResponse()

    # Auth check
    if ALLOWED_PHONE_NUMBER and From != ALLOWED_PHONE_NUMBER:
        response.message("Not authorized.")
        return Response(content=str(response), media_type="application/xml")

    # Check Google OAuth is configured
    if not GOOGLE_CLIENT_ID:
        response.message("Server not configured. Set GOOGLE_CLIENT_ID in .env")
        return Response(content=str(response), media_type="application/xml")

    manager = ConversationManager(db, From)

    # Handle media
    media_path = None
    if int(NumMedia) > 0 and MediaUrl0:
        try:
            media_path = await download_media(
                MediaUrl0,
                auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
            )
        except Exception:
            response.message("Failed to download image. Try again.")
            return Response(content=str(response), media_type="application/xml")

    # Preserve case for title/description
    state = manager.conversation.state
    original_body = Body.strip()

    if state == "awaiting_title":
        manager.set_title(original_body)
    if state == "awaiting_description":
        manager.set_description(original_body)

    # Process message
    reply = manager.process_message(Body, media_path)

    # Handle special actions
    if isinstance(reply, dict):
        if reply.get("action") == "create_account":
            auth_url = create_account_and_get_auth_url(db, reply["account_name"], From)
            manager.reset()
            response.message(f"Click to authorize:\n{auth_url}")
            return Response(content=str(response), media_type="application/xml")

    # Start upload if processing
    if manager.conversation.state == "processing":
        background_tasks.add_task(process_and_upload, From, db)

    response.message(reply)
    return Response(content=str(response), media_type="application/xml")


@router.get("/webhook")
async def whatsapp_webhook_verify():
    return {"status": "ok"}
