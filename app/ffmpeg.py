from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
from pathlib import Path, PurePosixPath
import shlex
import shutil
import subprocess
from urllib.parse import urlsplit, urlunsplit

from app.config import Settings

logger = logging.getLogger(__name__)


def redact_url(url: str) -> str:
    if not url:
        return ""

    parts = urlsplit(url)
    if not parts.username and not parts.password:
        return url

    host = parts.hostname or ""
    if parts.port:
        host = f"{host}:{parts.port}"

    return urlunsplit((parts.scheme, f"***:***@{host}", parts.path, parts.query, parts.fragment))


def build_ffmpeg_command(settings: Settings) -> list[str]:
    playlist_path = str(PurePosixPath(settings.hls_dir) / settings.playlist_name)
    segment_path = str(PurePosixPath(settings.hls_dir) / settings.segment_pattern)

    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "warning",
        "-rtsp_transport",
        "tcp",
    ]

    if settings.rtsp_user_agent:
        command.extend(["-user_agent", settings.rtsp_user_agent])

    command.extend(["-i", settings.camera_rtsp_url])

    if settings.ffmpeg_transcode:
        command.extend(
            [
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-tune",
                "zerolatency",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
            ]
        )
    else:
        command.extend(["-c", "copy"])

    command.extend(
        [
            "-f",
            "hls",
            "-hls_time",
            str(settings.hls_segment_seconds),
            "-hls_list_size",
            str(settings.hls_list_size),
            "-hls_flags",
            "delete_segments+append_list+omit_endlist",
        ]
    )

    if settings.hls_segment_type == "fmp4":
        command.extend(["-hls_segment_type", "fmp4", "-hls_fmp4_init_filename", "init.mp4"])

    command.extend(
        [
            "-hls_segment_filename",
            segment_path,
            playlist_path,
        ]
    )

    return command


def build_gstreamer_command(settings: Settings) -> list[str]:
    playlist_path = str(PurePosixPath(settings.hls_dir) / settings.playlist_name)
    segment_path = str(PurePosixPath(settings.hls_dir) / settings.segment_pattern)

    gst_command = [
        "gst-launch-1.0",
        "-q",
        "rtspsrc",
        f"location={settings.camera_rtsp_location or settings.camera_rtsp_url}",
        "protocols=tcp",
        "latency=200",
        "name=src",
    ]

    if settings.camera_rtsp_username:
        gst_command.append(f"user-id={settings.camera_rtsp_username}")
    if settings.camera_rtsp_password:
        gst_command.append(f"user-pw={settings.camera_rtsp_password}")
    if settings.rtsp_user_agent:
        gst_command.append(f"user-agent={settings.rtsp_user_agent}")

    gst_command.extend(["src.", "!", "application/x-rtp,media=video", "!", "rtph264depay", "!", "h264parse"])

    if settings.gstreamer_transcode:
        raw_caps = (
            "video/x-raw,"
            "format=I420,"
            f"width={settings.gstreamer_video_width},"
            f"height={settings.gstreamer_video_height},"
            f"framerate={settings.gstreamer_video_fps}/1"
        )
        gst_command.extend(
            [
                "!",
                "avdec_h264",
                "!",
                "videoconvert",
                "!",
                "videoscale",
                "!",
                "videorate",
                "!",
                raw_caps,
            ]
        )
    else:
        gst_command.extend(
            [
                "config-interval=-1",
                "!",
                "video/x-h264,stream-format=byte-stream,alignment=au",
            ]
        )

    gst_command.extend(["!", "fdsink", "fd=1"])

    if settings.gstreamer_transcode:
        keyframe_interval = max(settings.hls_segment_seconds * settings.gstreamer_video_fps, settings.gstreamer_video_fps)
        ffmpeg_input = [
            "-f",
            "rawvideo",
            "-pix_fmt",
            "yuv420p",
            "-s:v",
            f"{settings.gstreamer_video_width}x{settings.gstreamer_video_height}",
            "-r",
            str(settings.gstreamer_video_fps),
            "-i",
            "pipe:0",
        ]
        ffmpeg_codec = [
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-tune",
            "zerolatency",
            "-profile:v",
            "baseline",
            "-pix_fmt",
            "yuv420p",
            "-bf",
            "0",
            "-g",
            str(keyframe_interval),
            "-keyint_min",
            str(keyframe_interval),
            "-sc_threshold",
            "0",
            "-b:v",
            f"{settings.gstreamer_video_bitrate}k",
        ]
    else:
        ffmpeg_input = ["-fflags", "+genpts", "-f", "h264", "-r", str(settings.gstreamer_video_fps), "-i", "pipe:0"]
        ffmpeg_codec = ["-c", "copy"]

    ffmpeg_command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "warning",
        *ffmpeg_input,
        *ffmpeg_codec,
        "-f",
        "hls",
        "-hls_time",
        str(settings.hls_segment_seconds),
        "-hls_list_size",
        str(settings.hls_list_size),
        "-hls_flags",
        "delete_segments+omit_endlist+independent_segments",
    ]

    if settings.hls_segment_type == "fmp4":
        ffmpeg_command.extend(["-hls_segment_type", "fmp4", "-hls_fmp4_init_filename", "init.mp4"])

    ffmpeg_command.extend(["-hls_segment_filename", segment_path, playlist_path])

    pipeline = " ".join(shlex.quote(part) for part in gst_command)
    pipeline += " | "
    pipeline += " ".join(shlex.quote(part) for part in ffmpeg_command)
    script = f"trap 'kill 0' TERM INT; {pipeline} & wait $!"

    return ["sh", "-c", script]


def build_stream_command(settings: Settings) -> list[str]:
    if settings.stream_backend == "ffmpeg":
        return build_ffmpeg_command(settings)
    if settings.stream_backend == "gstreamer":
        return build_gstreamer_command(settings)
    raise ValueError(f"Unsupported STREAM_BACKEND: {settings.stream_backend}")


def redact_command(command: list[str], settings: Settings) -> list[str]:
    redacted: list[str] = []
    for part in command:
        value = part
        if settings.camera_rtsp_url:
            value = value.replace(settings.camera_rtsp_url, redact_url(settings.camera_rtsp_url))
        if settings.camera_rtsp_password:
            value = value.replace(settings.camera_rtsp_password, "***")
        if settings.camera_rtsp_username:
            value = value.replace(settings.camera_rtsp_username, "***")
        redacted.append(value)
    return redacted


@dataclass(frozen=True)
class StreamHealth:
    configured: bool
    running: bool
    playlist_exists: bool
    restart_count: int
    last_exit_code: int | None


class FFmpegSupervisor:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.hls_path = Path(settings.hls_dir)
        self.playlist_path = self.hls_path / settings.playlist_name
        self.restart_count = 0
        self.last_exit_code: int | None = None
        self._process: asyncio.subprocess.Process | None = None
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()

    async def start(self) -> None:
        self._prepare_hls_dir()

        if not self.settings.camera_rtsp_url:
            logger.warning("CAMERA_RTSP_URL is not set. Web server is running, but restreaming is disabled.")
            return

        self._stop_event.clear()
        self._task = asyncio.create_task(self._run_loop(), name="ffmpeg-supervisor")

    async def stop(self) -> None:
        self._stop_event.set()

        if self._process and self._process.returncode is None:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=10)
            except asyncio.TimeoutError:
                self._process.kill()
                await self._process.wait()

        if self._task:
            await self._task

    def health(self) -> StreamHealth:
        return StreamHealth(
            configured=bool(self.settings.camera_rtsp_url),
            running=bool(self._process and self._process.returncode is None),
            playlist_exists=self.playlist_path.exists(),
            restart_count=self.restart_count,
            last_exit_code=self.last_exit_code,
        )

    def _prepare_hls_dir(self) -> None:
        if self.hls_path.exists():
            shutil.rmtree(self.hls_path)
        self.hls_path.mkdir(parents=True, exist_ok=True)

    async def _run_loop(self) -> None:
        command = build_stream_command(self.settings)
        redacted_command = redact_command(command, self.settings)

        while not self._stop_event.is_set():
            logger.info("Starting %s: %s", self.settings.stream_backend, " ".join(redacted_command))
            self._process = await asyncio.create_subprocess_exec(
                *command,
                stdout=subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
            stderr_task = asyncio.create_task(
                self._log_process_stderr(self._process)
            )
            self.last_exit_code = await self._process.wait()
            await stderr_task

            if self._stop_event.is_set():
                break

            self.restart_count += 1
            logger.warning(
                "%s exited with code %s. Restarting in %s seconds.",
                self.settings.stream_backend,
                self.last_exit_code,
                self.settings.ffmpeg_restart_seconds,
            )

            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self.settings.ffmpeg_restart_seconds)
            except asyncio.TimeoutError:
                pass

    async def _log_process_stderr(self, process: asyncio.subprocess.Process) -> None:
        if not process.stderr:
            return

        while line := await process.stderr.readline():
            message = line.decode("utf-8", errors="replace").rstrip()
            for raw in (
                self.settings.camera_rtsp_url,
                self.settings.camera_rtsp_location,
                self.settings.camera_rtsp_password,
                self.settings.camera_rtsp_username,
            ):
                if raw:
                    replacement = redact_url(raw) if raw.startswith("rtsp://") else "***"
                    message = message.replace(raw, replacement)
            logger.warning("%s: %s", self.settings.stream_backend, message)
