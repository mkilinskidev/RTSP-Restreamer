from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_index_does_not_expose_rtsp_credentials(tmp_path: Path) -> None:
    app = create_app(
        Settings(
            camera_rtsp_url="rtsp://user:secret@example.com:554/live",
            camera_rtsp_location="rtsp://example.com:554/live",
            camera_rtsp_username="user",
            camera_rtsp_password="secret",
            rtsp_user_agent="",
            stream_backend="gstreamer",
            gstreamer_transcode=True,
            gstreamer_video_bitrate=2500,
            gstreamer_video_width=1920,
            gstreamer_video_height=1080,
            gstreamer_video_fps=25,
            hls_dir=str(tmp_path),
            hls_segment_type="mpegts",
            hls_segment_seconds=2,
            hls_list_size=6,
            ffmpeg_transcode=False,
            ffmpeg_restart_seconds=5,
        ),
        start_supervisor=False,
    )

    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "<video" in response.text
    assert "rtsp://" not in response.text
    assert "secret" not in response.text


def test_health_without_playlist(tmp_path: Path) -> None:
    app = create_app(
        Settings(
            camera_rtsp_url="",
            camera_rtsp_location="",
            camera_rtsp_username="",
            camera_rtsp_password="",
            rtsp_user_agent="",
            stream_backend="gstreamer",
            gstreamer_transcode=True,
            gstreamer_video_bitrate=2500,
            gstreamer_video_width=1920,
            gstreamer_video_height=1080,
            gstreamer_video_fps=25,
            hls_dir=str(tmp_path),
            hls_segment_type="mpegts",
            hls_segment_seconds=2,
            hls_list_size=6,
            ffmpeg_transcode=False,
            ffmpeg_restart_seconds=5,
        ),
        start_supervisor=False,
    )

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "configured": False,
        "running": False,
        "playlist_exists": False,
        "restart_count": 0,
        "last_exit_code": None,
    }
