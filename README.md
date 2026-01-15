# YouTube WhatsApp Uploader

Download audio from YouTube → merge with thumbnail → upload to your YouTube channel. All via WhatsApp.

## Setup

### 1. Install

```bash
cd yt-assistant
uv venv && source .venv/bin/activate
uv pip install -r requirements.txt
brew install ffmpeg
```

### 2. Google OAuth

1. [console.cloud.google.com](https://console.cloud.google.com) → Create project
2. Enable **YouTube Data API v3**
3. **OAuth consent screen** → External → Add your email as test user
4. **Credentials** → OAuth client ID → Web app
5. Add redirect: `http://localhost:8000/oauth/callback`
6. Copy **Client ID** and **Client Secret**

### 3. Twilio

1. [twilio.com](https://www.twilio.com) → Sign up
2. **Messaging** → **WhatsApp sandbox** → Follow setup
3. Copy **Account SID**, **Auth Token**, **WhatsApp number**

### 4. Configure

```bash
cp .env.example .env
```

```env
GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_client_secret
GOOGLE_REDIRECT_URI=http://localhost:8000/oauth/callback

TWILIO_ACCOUNT_SID=your_sid
TWILIO_AUTH_TOKEN=your_token
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886

ALLOWED_PHONE_NUMBER=whatsapp:+your_number
```

### 5. Run

```bash
uvicorn app.main:app --reload
ngrok http 8000  # in another terminal
```

Set Twilio webhook: `https://your-ngrok.ngrok.io/whatsapp/webhook`

## Usage (All via WhatsApp)

```
You: add
Bot: Enter account name:
You: MyChannel
Bot: Click to authorize: https://...
[Click link, login to Google]
Bot: Account 'MyChannel' authorized!

You: upload
Bot: Send YouTube link:
You: https://youtube.com/watch?v=xxx
Bot: Enter title:
You: My Cool Video
Bot: Description? (or 'skip'):
You: skip
Bot: Send thumbnail or 'auto':
You: auto
Bot: Privacy? (public/unlisted/private):
You: public
Bot: Processing...
Bot: Done! https://youtube.com/watch?v=NEW_ID
```

## Commands

| Command | Description |
|---------|-------------|
| `add` | Add YouTube account |
| `remove` | Remove account |
| `accounts` | List accounts |
| `upload` | Start upload |
| `cancel` | Cancel |
| `help` | Help |
# yt-assistant-server
