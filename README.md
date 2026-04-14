# RTSP Restreamer

Python service that turns a password-protected RTSP camera stream into HLS for playback through a normal HTML5 `<video>` element.

The RTSP URL stays on the server. Browsers only receive the generated HLS playlist and video segments.

## Quick Start

1. Copy the example environment file:

   ```powershell
   Copy-Item .env.example .env
   ```

2. Edit `.env` and set your camera URL and credentials:

   ```env
   CAMERA_RTSP_URL=rtsp://public-ip-or-domain:554/stream-path
   CAMERA_RTSP_USERNAME=login
   CAMERA_RTSP_PASSWORD=password
   ```

3. Build and run:

   ```powershell
   docker compose up --build
   ```

4. Open:

   ```text
   http://localhost:8000
   ```

Healthcheck:

```text
http://localhost:8000/health
```

## Configuration

| Variable | Default | Description |
| --- | --- | --- |
| `CAMERA_RTSP_URL` | empty | RTSP URL. Prefer setting it without username and password. |
| `CAMERA_RTSP_USERNAME` | empty | RTSP username. |
| `CAMERA_RTSP_PASSWORD` | empty | RTSP password. Special characters are encoded automatically. |
| `RTSP_USER_AGENT` | empty | Optional RTSP User-Agent override, for cameras that reject ffmpeg but accept VLC. |
| `STREAM_BACKEND` | `gstreamer` | `gstreamer` is recommended for cameras with Digest auth issues; `ffmpeg` remains available. |
| `GSTREAMER_TRANSCODE` | `true` | Re-encode video into browser-friendly H.264 HLS segments. |
| `GSTREAMER_VIDEO_BITRATE` | `2500` | Target video bitrate in kbit/s when GStreamer transcodes. |
| `GSTREAMER_VIDEO_WIDTH` | `1920` | Output width used by the raw-video handoff to ffmpeg. |
| `GSTREAMER_VIDEO_HEIGHT` | `1080` | Output height used by the raw-video handoff to ffmpeg. |
| `GSTREAMER_VIDEO_FPS` | `25` | Output frame rate used by the raw-video handoff to ffmpeg. |
| `FFMPEG_TRANSCODE` | `false` | Use `true` if the camera stream is not playable after remuxing. |
| `HLS_SEGMENT_TYPE` | `mpegts` | `mpegts` is recommended with hls.js for broad Chrome/Edge/Firefox compatibility in this pipeline. |
| `HLS_SEGMENT_SECONDS` | `2` | Segment duration in seconds. |
| `HLS_LIST_SIZE` | `6` | Number of live playlist segments. |
| `FFMPEG_RESTART_SECONDS` | `5` | Delay before restarting `ffmpeg` after a failure. |

## Notes

- The default mode uses `-c copy`, which is light on CPU and works well when the camera outputs browser-compatible H.264.
- If the camera returns `401 Unauthorized` in `ffmpeg` and the same credentials work in VLC, keep `STREAM_BACKEND=gstreamer`.
- If the player opens but stays black at `0:00`, keep `GSTREAMER_TRANSCODE=true`; some cameras do not include enough H.264 parameter data in every HLS segment for browsers.
- `HLS_SEGMENT_TYPE=mpegts` is the recommended default for hls.js in Chrome, Edge, and Firefox in this pipeline.
- If it still returns `401 Unauthorized`, try `RTSP_USER_AGENT=LibVLC/3.0.20`.
- If the browser cannot play the stream, set `FFMPEG_TRANSCODE=true` and restart the container.
- For public internet use, put the service behind HTTPS with Caddy, Nginx, Cloudflare Tunnel, or a similar reverse proxy.

## Production Traffic

Do not send thousands of viewers directly to the Python container. Use this service as the origin that creates HLS files, then put a CDN, Nginx, Caddy, or object-storage sync layer in front of `/hls/`.

For live HLS, cache the `.m4s` segments for a short time and avoid caching `stream.m3u8` for long. The playlist changes constantly, while completed media segments can safely be served many times.
