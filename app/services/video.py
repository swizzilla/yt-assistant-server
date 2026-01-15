import os
import uuid
import yt_dlp
from pathlib import Path
from moviepy import AudioFileClip, ImageClip

from app.config import TEMP_DIR


def download_audio(youtube_url: str) -> str:
    """
    Download audio from YouTube video as MP3.
    Returns path to the downloaded audio file.
    """
    audio_id = str(uuid.uuid4())[:8]
    output_path = TEMP_DIR / f"audio_{audio_id}"

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": str(output_path),
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
        "keepvideo": False,
        "quiet": True,
        "no_warnings": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([youtube_url])

    return str(output_path) + ".mp3"


def get_video_thumbnail(youtube_url: str) -> str:
    """
    Extract thumbnail URL from YouTube video.
    Returns the thumbnail URL.
    """
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(youtube_url, download=False)
        # Get the best quality thumbnail
        thumbnail_url = info.get("thumbnail", "")
        return thumbnail_url


def download_thumbnail(thumbnail_url: str) -> str:
    """
    Download thumbnail image from URL.
    Returns path to downloaded image.
    """
    import httpx

    thumb_id = str(uuid.uuid4())[:8]
    thumb_path = TEMP_DIR / f"thumb_{thumb_id}.jpg"

    response = httpx.get(thumbnail_url, follow_redirects=True)
    response.raise_for_status()

    with open(thumb_path, "wb") as f:
        f.write(response.content)

    return str(thumb_path)


def create_video(audio_path: str, thumbnail_path: str) -> str:
    """
    Create a 1080p video from audio and thumbnail image.
    The thumbnail becomes a static background for the entire audio duration.
    Returns path to the created video file.
    """
    video_id = str(uuid.uuid4())[:8]
    output_path = TEMP_DIR / f"video_{video_id}.mp4"

    # Load audio
    audio = AudioFileClip(audio_path)

    # Create image clip with audio duration
    img_clip = ImageClip(thumbnail_path, duration=audio.duration)
    img_clip = img_clip.resized(height=1080, width=1920)

    # Combine image and audio
    final_clip = img_clip.with_audio(audio)

    # Write video file (optimized settings)
    final_clip.write_videofile(
        str(output_path),
        fps=1,  # Static image only needs 1 fps
        codec="libx264",
        audio_codec="aac",
        audio_bitrate="192k",
        preset="ultrafast",  # Faster encoding
        threads=4,
        logger=None,  # Suppress moviepy logging
    )

    # Cleanup
    audio.close()
    final_clip.close()

    return str(output_path)


def process_youtube_video(youtube_url: str, thumbnail_path: str | None = None) -> str:
    """
    Full pipeline: download audio, get/use thumbnail, create video.

    Args:
        youtube_url: YouTube video URL to download audio from
        thumbnail_path: Optional custom thumbnail. If None, uses YouTube video thumbnail.

    Returns:
        Path to the created video file.
    """
    # Download audio
    audio_path = download_audio(youtube_url)

    # Get thumbnail (use custom or extract from video)
    if thumbnail_path is None:
        thumb_url = get_video_thumbnail(youtube_url)
        thumbnail_path = download_thumbnail(thumb_url)

    # Create video
    video_path = create_video(audio_path, thumbnail_path)

    # Cleanup audio file (video is final output)
    try:
        os.remove(audio_path)
    except Exception:
        pass

    return video_path


def cleanup_temp_files(*file_paths: str):
    """Remove temporary files after upload"""
    for path in file_paths:
        try:
            if path and os.path.exists(path):
                os.remove(path)
        except Exception:
            pass
