from app.config import build_camera_rtsp_url


def test_build_camera_rtsp_url_encodes_separate_credentials(monkeypatch) -> None:
    monkeypatch.setenv("CAMERA_RTSP_URL", "rtsp://example.com:554/Streaming/Channels/101")
    monkeypatch.setenv("CAMERA_RTSP_USERNAME", "camera user")
    monkeypatch.setenv("CAMERA_RTSP_PASSWORD", "pa:ss@word#1")

    assert (
        build_camera_rtsp_url()
        == "rtsp://camera%20user:pa%3Ass%40word%231@example.com:554/Streaming/Channels/101"
    )


def test_build_camera_rtsp_url_keeps_legacy_full_url(monkeypatch) -> None:
    monkeypatch.setenv("CAMERA_RTSP_URL", "rtsp://user:password@example.com/live")
    monkeypatch.delenv("CAMERA_RTSP_USERNAME", raising=False)
    monkeypatch.delenv("CAMERA_RTSP_PASSWORD", raising=False)

    assert build_camera_rtsp_url() == "rtsp://user:password@example.com/live"


def test_build_camera_rtsp_url_normalizes_legacy_credentials(monkeypatch) -> None:
    monkeypatch.setenv("CAMERA_RTSP_URL", "rtsp://user:pa:ss@word@example.com/live")
    monkeypatch.delenv("CAMERA_RTSP_USERNAME", raising=False)
    monkeypatch.delenv("CAMERA_RTSP_PASSWORD", raising=False)

    assert build_camera_rtsp_url() == "rtsp://user:pa%3Ass%40word@example.com/live"
