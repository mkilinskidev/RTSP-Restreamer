from app.config import Settings
from app.ffmpeg import build_ffmpeg_command, build_gstreamer_command, redact_url


def settings(transcode: bool = False) -> Settings:
    return Settings(
        camera_rtsp_url="rtsp://user:secret@example.com:554/live",
        camera_rtsp_location="rtsp://example.com:554/live",
        camera_rtsp_username="user",
        camera_rtsp_password="secret",
        rtsp_user_agent="",
        stream_backend="ffmpeg",
        gstreamer_transcode=True,
        gstreamer_video_bitrate=2500,
        gstreamer_video_width=1920,
        gstreamer_video_height=1080,
        gstreamer_video_fps=25,
        hls_dir="/tmp/hls",
        hls_segment_type="mpegts",
        hls_segment_seconds=2,
        hls_list_size=6,
        ffmpeg_transcode=transcode,
        ffmpeg_restart_seconds=5,
    )


def test_build_ffmpeg_command_remux() -> None:
    command = build_ffmpeg_command(settings())

    assert "-rtsp_transport" in command
    assert "tcp" in command
    assert command[command.index("-i") + 1] == "rtsp://user:secret@example.com:554/live"
    assert "-c" in command
    assert command[command.index("-c") + 1] == "copy"
    assert "-hls_time" in command
    assert command[command.index("-hls_time") + 1] == "2"
    assert "-hls_list_size" in command
    assert command[command.index("-hls_list_size") + 1] == "6"


def test_build_ffmpeg_command_transcode() -> None:
    command = build_ffmpeg_command(settings(transcode=True))

    assert "-c:v" in command
    assert command[command.index("-c:v") + 1] == "libx264"
    assert "-c:a" in command
    assert command[command.index("-c:a") + 1] == "aac"
    assert "-c" not in command


def test_build_ffmpeg_command_user_agent() -> None:
    custom_settings = settings()
    custom_settings = Settings(
        camera_rtsp_url=custom_settings.camera_rtsp_url,
        camera_rtsp_location=custom_settings.camera_rtsp_location,
        camera_rtsp_username=custom_settings.camera_rtsp_username,
        camera_rtsp_password=custom_settings.camera_rtsp_password,
        rtsp_user_agent="LibVLC/3.0.20",
        stream_backend=custom_settings.stream_backend,
        gstreamer_transcode=custom_settings.gstreamer_transcode,
        gstreamer_video_bitrate=custom_settings.gstreamer_video_bitrate,
        gstreamer_video_width=custom_settings.gstreamer_video_width,
        gstreamer_video_height=custom_settings.gstreamer_video_height,
        gstreamer_video_fps=custom_settings.gstreamer_video_fps,
        hls_dir=custom_settings.hls_dir,
        hls_segment_type=custom_settings.hls_segment_type,
        hls_segment_seconds=custom_settings.hls_segment_seconds,
        hls_list_size=custom_settings.hls_list_size,
        ffmpeg_transcode=custom_settings.ffmpeg_transcode,
        ffmpeg_restart_seconds=custom_settings.ffmpeg_restart_seconds,
    )

    command = build_ffmpeg_command(custom_settings)

    assert "-user_agent" in command
    assert command[command.index("-user_agent") + 1] == "LibVLC/3.0.20"
    assert command.index("-user_agent") < command.index("-i")


def test_build_gstreamer_command_uses_separate_credentials() -> None:
    command = build_gstreamer_command(settings())
    command_text = " ".join(command)

    assert command[:2] == ["sh", "-c"]
    assert "gst-launch-1.0" in command_text
    assert "location=rtsp://example.com:554/live" in command_text
    assert "user-id=user" in command_text
    assert "user-pw=secret" in command_text
    assert "avdec_h264" in command_text
    assert "video/x-raw,format=I420,width=1920,height=1080,framerate=25/1" in command_text
    assert "fdsink" in command_text
    assert "mpegtsmux" not in command_text
    assert "ffmpeg" in command_text
    assert "-f rawvideo" in command_text
    assert "-s:v 1920x1080" in command_text
    assert "-c:v libx264" in command_text
    assert "-b:v 2500k" in command_text
    assert "independent_segments" in command_text
    assert "-hls_segment_type fmp4" not in command_text
    assert "/tmp/hls/segment_%05d.ts" in command_text
    assert "/tmp/hls/stream.m3u8" in command_text


def test_build_gstreamer_command_can_remux_without_transcode() -> None:
    base = settings()
    remux_settings = Settings(
        camera_rtsp_url=base.camera_rtsp_url,
        camera_rtsp_location=base.camera_rtsp_location,
        camera_rtsp_username=base.camera_rtsp_username,
        camera_rtsp_password=base.camera_rtsp_password,
        rtsp_user_agent=base.rtsp_user_agent,
        stream_backend=base.stream_backend,
        gstreamer_transcode=False,
        gstreamer_video_bitrate=base.gstreamer_video_bitrate,
        gstreamer_video_width=base.gstreamer_video_width,
        gstreamer_video_height=base.gstreamer_video_height,
        gstreamer_video_fps=base.gstreamer_video_fps,
        hls_dir=base.hls_dir,
        hls_segment_type=base.hls_segment_type,
        hls_segment_seconds=base.hls_segment_seconds,
        hls_list_size=base.hls_list_size,
        ffmpeg_transcode=base.ffmpeg_transcode,
        ffmpeg_restart_seconds=base.ffmpeg_restart_seconds,
    )

    command = build_gstreamer_command(remux_settings)
    command_text = " ".join(command)

    assert "avdec_h264" not in command_text
    assert "x264enc" not in command_text
    assert "-f h264" in command_text


def test_redact_url_hides_credentials() -> None:
    redacted = redact_url("rtsp://user:secret@example.com:554/live")

    assert redacted == "rtsp://***:***@example.com:554/live"
    assert "user" not in redacted
    assert "secret" not in redacted
