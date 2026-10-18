from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Callable
from datetime import datetime, timezone

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
Progress = Callable[[int], None]


def _token_file() -> Path:
    return Path.home() / ".animatube" / "youtube_token.json"


def authenticate(credentials_file: str | Path):
    credentials_path = Path(credentials_file).expanduser()
    if not credentials_path.is_file():
        raise FileNotFoundError(
            f"OAuth client file not found: {credentials_path}. "
            "Download a Desktop app OAuth client JSON from Google Cloud Console."
        )
    token_path = _token_file()
    token_path.parent.mkdir(parents=True, exist_ok=True)
    credentials = None
    if token_path.is_file():
        try:
            credentials = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        except (ValueError, OSError) as exc:
            raise RuntimeError(f"Saved YouTube authorization is invalid: {exc}") from exc
    if credentials and credentials.expired and credentials.refresh_token:
        try:
            credentials.refresh(Request())
        except Exception as exc:
            raise RuntimeError(f"Could not refresh YouTube authorization: {exc}") from exc
    if not credentials or not credentials.valid:
        try:
            flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
            credentials = flow.run_local_server(port=0, open_browser=True)
        except Exception as exc:
            raise RuntimeError(f"Google sign-in failed: {exc}") from exc
    token_path.write_text(credentials.to_json(), encoding="utf-8")
    return build("youtube", "v3", credentials=credentials, cache_discovery=False)


def upload_video(
    service,
    video_path: str | Path,
    *,
    title: str,
    description: str = "",
    tags: list[str] | None = None,
    category_id: str = "22",
    privacy: str = "private",
    thumbnail_path: str | Path | None = None,
    publish_at: str | None = None,
    progress: Progress | None = None,
) -> str:
    source = Path(video_path)
    if not source.is_file():
        raise FileNotFoundError(f"Rendered video not found: {source}")
    if not title.strip():
        raise ValueError("A video title is required.")
    if privacy not in ("public", "unlisted", "private"):
        raise ValueError("Privacy must be public, unlisted, or private.")
    if publish_at and privacy != "private":
        raise ValueError("Scheduled uploads must use private visibility until the scheduled time.")
    if publish_at:
        try:
            scheduled_time = datetime.fromisoformat(publish_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("Scheduled publish time must be a valid RFC 3339 timestamp.") from exc
        if scheduled_time.tzinfo is None or scheduled_time <= datetime.now(timezone.utc):
            raise ValueError("Scheduled publish time must be in the future and include a time zone.")

    status: dict[str, str] = {"privacyStatus": privacy}
    if publish_at:
        status["privacyStatus"] = "private"
        status["publishAt"] = publish_at
    body = {
        "snippet": {
            "title": title.strip(),
            "description": description,
            "tags": [tag.strip() for tag in (tags or []) if tag.strip()],
            "categoryId": category_id,
        },
        "status": status,
    }
    media = MediaFileUpload(str(source), mimetype="video/mp4", chunksize=8 * 1024 * 1024, resumable=True)
    try:
        request = service.videos().insert(part="snippet,status", body=body, media_body=media)
        response = None
        while response is None:
            upload_status, response = request.next_chunk(num_retries=5)
            if upload_status and progress:
                progress(round(upload_status.progress() * 100))
    except HttpError as exc:
        raise RuntimeError(f"YouTube rejected the upload: {exc}") from exc
    except Exception as exc:
        raise RuntimeError(f"YouTube upload failed: {exc}") from exc

    video_id = response.get("id") if response else None
    if not video_id:
        raise RuntimeError("YouTube reported an upload complete but returned no video ID.")
    if thumbnail_path:
        thumbnail = Path(thumbnail_path)
        if not thumbnail.is_file():
            raise FileNotFoundError(f"Thumbnail not found: {thumbnail}")
        thumbnail_mime, _ = mimetypes.guess_type(str(thumbnail))
        if thumbnail_mime not in ("image/jpeg", "image/png"):
            raise ValueError("YouTube thumbnails must be JPEG or PNG images.")
        try:
            service.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(str(thumbnail), mimetype=thumbnail_mime, resumable=False),
            ).execute()
        except HttpError as exc:
            raise RuntimeError(
                f"Video uploaded to https://www.youtube.com/watch?v={video_id}, "
                f"but YouTube rejected the thumbnail: {exc}"
            ) from exc
    if progress:
        progress(100)
    return f"https://www.youtube.com/watch?v={video_id}"
