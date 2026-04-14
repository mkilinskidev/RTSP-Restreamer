from dataclasses import dataclass
import os
from urllib.parse import quote, unquote, urlsplit, urlunsplit


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return int(value)


@dataclass(frozen=True)
class Settings:
    camera_rtsp_url: str
    camera_rtsp_location: str
    camera_rtsp_username: str
    camera_rtsp_password: str
    rtsp_user_agent: str
    stream_backend: str
    gstreamer_transcode: bool
    gstreamer_video_bitrate: int
    gstreamer_video_width: int
    gstreamer_video_height: int
    gstreamer_video_fps: int
    hls_dir: str
    hls_segment_type: str
    hls_segment_seconds: int
    hls_list_size: int
    ffmpeg_transcode: bool
    ffmpeg_restart_seconds: int

    @property
    def playlist_name(self) -> str:
        return "stream.m3u8"

    @property
    def segment_pattern(self) -> str:
        extension = "m4s" if self.hls_segment_type == "fmp4" else "ts"
        return f"segment_%05d.{extension}"


def build_camera_rtsp_url() -> str:
    location, username, password = load_camera_rtsp_parts()

    if not location or not username:
        return location

    parts = urlsplit(location)
    host = _host_with_port(parts)
    if not host:
        return location

    credentials = quote(username, safe="")
    if password:
        credentials = f"{credentials}:{quote(password, safe='')}"

    return urlunsplit((parts.scheme, f"{credentials}@{host}", parts.path, parts.query, parts.fragment))


def load_camera_rtsp_parts() -> tuple[str, str, str]:
    url = os.getenv("CAMERA_RTSP_URL", "").strip()
    username = os.getenv("CAMERA_RTSP_USERNAME", "").strip()
    password = os.getenv("CAMERA_RTSP_PASSWORD", "")

    if not url:
        return "", username, password

    parts = urlsplit(url)
    host = parts.hostname or ""
    if not host:
        return url, username, password

    if not username and parts.username:
        username = unquote(parts.username)
        password = unquote(parts.password or "")

    location = urlunsplit((parts.scheme, _host_with_port(parts), parts.path, parts.query, parts.fragment))
    return location, username, password


def _host_with_port(parts) -> str:
    host = parts.hostname or ""
    if parts.port:
        host = f"{host}:{parts.port}"
    return host


def load_settings() -> Settings:
    location, username, password = load_camera_rtsp_parts()
    return Settings(
        camera_rtsp_url=build_camera_rtsp_url(),
        camera_rtsp_location=location,
        camera_rtsp_username=username,
        camera_rtsp_password=password,
        rtsp_user_agent=os.getenv("RTSP_USER_AGENT", "").strip(),
        stream_backend=os.getenv("STREAM_BACKEND", "gstreamer").strip().lower(),
        gstreamer_transcode=_env_bool("GSTREAMER_TRANSCODE", True),
        gstreamer_video_bitrate=_env_int("GSTREAMER_VIDEO_BITRATE", 2500),
        gstreamer_video_width=_env_int("GSTREAMER_VIDEO_WIDTH", 1920),
        gstreamer_video_height=_env_int("GSTREAMER_VIDEO_HEIGHT", 1080),
        gstreamer_video_fps=_env_int("GSTREAMER_VIDEO_FPS", 25),
        hls_dir=os.getenv("HLS_DIR", "/tmp/restreamer-hls"),
        hls_segment_type=os.getenv("HLS_SEGMENT_TYPE", "fmp4").strip().lower(),
        hls_segment_seconds=_env_int("HLS_SEGMENT_SECONDS", 2),
        hls_list_size=_env_int("HLS_LIST_SIZE", 6),
        ffmpeg_transcode=_env_bool("FFMPEG_TRANSCODE", False),
        ffmpeg_restart_seconds=_env_int("FFMPEG_RESTART_SECONDS", 5),
    )
