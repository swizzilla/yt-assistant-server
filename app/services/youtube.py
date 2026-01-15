import pickle
from pathlib import Path

from google_auth_oauthlib.flow import Flow
import googleapiclient.discovery
from google.auth.transport.requests import Request
from googleapiclient.http import MediaFileUpload

from app.config import (
    YOUTUBE_SCOPES,
    GOOGLE_REDIRECT_URI,
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
)


def get_oauth_config() -> dict:
    """Build OAuth config from environment variables"""
    return {
        "web": {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [GOOGLE_REDIRECT_URI],
        }
    }


def get_oauth_flow() -> Flow:
    """Create OAuth flow from env vars"""
    return Flow.from_client_config(
        get_oauth_config(),
        scopes=YOUTUBE_SCOPES,
        redirect_uri=GOOGLE_REDIRECT_URI,
    )


def get_authorization_url(state: str) -> str:
    """Generate Google OAuth authorization URL"""
    flow = get_oauth_flow()
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        state=state,
        prompt="consent",
    )
    return auth_url


def exchange_code_for_credentials(code: str, credentials_path: str):
    """Exchange authorization code for credentials and save them"""
    flow = get_oauth_flow()
    flow.fetch_token(code=code)
    credentials = flow.credentials

    with open(credentials_path, "wb") as f:
        pickle.dump(credentials, f)

    return credentials


def get_youtube_service(credentials_path: str):
    """Get authenticated YouTube API service"""
    credentials = None

    if Path(credentials_path).exists():
        with open(credentials_path, "rb") as f:
            credentials = pickle.load(f)

    if credentials and credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        with open(credentials_path, "wb") as f:
            pickle.dump(credentials, f)

    if not credentials or not credentials.valid:
        raise ValueError("Invalid credentials. Please re-authorize.")

    return googleapiclient.discovery.build("youtube", "v3", credentials=credentials)


def upload_video(
    credentials_path: str,
    video_path: str,
    title: str,
    description: str = "",
    privacy: str = "public",
    category_id: str = "10",
    thumbnail_path: str | None = None,
) -> dict:
    """Upload a video to YouTube"""
    youtube = get_youtube_service(credentials_path)

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "categoryId": category_id,
        },
        "status": {
            "privacyStatus": privacy,
        },
    }

    media = MediaFileUpload(
        video_path,
        chunksize=-1,
        resumable=True,
        mimetype="video/mp4",
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    response = None
    while response is None:
        status, response = request.next_chunk()

    video_id = response["id"]

    if thumbnail_path:
        try:
            youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(thumbnail_path),
            ).execute()
        except Exception:
            pass

    return {
        "video_id": video_id,
        "video_url": f"https://youtube.com/watch?v={video_id}",
    }
