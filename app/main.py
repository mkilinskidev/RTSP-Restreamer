from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, Response

from app.config import Settings, load_settings
from app.ffmpeg import FFmpegSupervisor


def create_app(settings: Settings | None = None, start_supervisor: bool = True) -> FastAPI:
    app_settings = settings or load_settings()
    supervisor = FFmpegSupervisor(app_settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if start_supervisor:
            await supervisor.start()
        yield
        if start_supervisor:
            await supervisor.stop()

    app = FastAPI(title="RTSP Restreamer", lifespan=lifespan)
    app.state.settings = app_settings
    app.state.supervisor = supervisor

    @app.get("/", response_class=HTMLResponse)
    async def index() -> HTMLResponse:
        index_path = Path(__file__).parent / "static" / "index.html"
        return HTMLResponse(
            index_path.read_text(encoding="utf-8"),
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/health")
    async def health() -> dict[str, bool | int | None]:
        stream_health = supervisor.health()
        return {
            "configured": stream_health.configured,
            "running": stream_health.running,
            "playlist_exists": stream_health.playlist_exists,
            "restart_count": stream_health.restart_count,
            "last_exit_code": stream_health.last_exit_code,
        }

    @app.get("/hls/{filename}")
    async def hls_file(filename: str) -> FileResponse:
        if "/" in filename or "\\" in filename or filename.startswith("."):
            raise HTTPException(status_code=404)

        file_path = Path(app_settings.hls_dir) / filename
        if not file_path.is_file():
            raise HTTPException(status_code=404)

        if filename.endswith(".m3u8"):
            return Response(
                file_path.read_text(encoding="utf-8"),
                media_type="application/vnd.apple.mpegurl",
                headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
            )

        if filename.endswith(".ts"):
            media_type = "video/mp2t"
        elif filename.endswith(".m4s"):
            media_type = "video/iso.segment"
        elif filename.endswith(".mp4"):
            media_type = "video/mp4"
        else:
            media_type = "application/octet-stream"

        return FileResponse(
            file_path,
            media_type=media_type,
            headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
        )

    return app


app = create_app()
