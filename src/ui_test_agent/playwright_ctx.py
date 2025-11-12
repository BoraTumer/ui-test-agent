from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
from typing import Optional

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

from .config import Settings


@dataclass
class BrowserArtifacts:
    har_path: Optional[Path]
    console_log: Path
    video_dir: Optional[Path]


@dataclass
class BrowserSession:
    playwright: Playwright
    browser: Browser
    context: BrowserContext
    page: Page
    artifacts: BrowserArtifacts

    def close(self) -> None:
        self.context.close()
        self.browser.close()
        self.playwright.stop()


class PlaywrightManager:
    def __init__(self, settings: Settings, headful: bool | None = None, slow_mo: int | None = None):
        self.settings = settings
        self.headful = headful
        self.slow_mo = slow_mo
        self._session: Optional[BrowserSession] = None

    def __enter__(self) -> BrowserSession:
        if self._session:
            return self._session
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(
            headless=self._resolve_headless(),
            slow_mo=self._resolve_slow_mo(),
        )
        context_kwargs = {
            "ignore_https_errors": True,
            "viewport": {"width": 1280, "height": 720},
        }
        artifacts = self._prepare_artifacts()
        if self.settings.record_video and artifacts.video_dir:
            context_kwargs["record_video_dir"] = str(artifacts.video_dir)
        if self.settings.collect_har and artifacts.har_path:
            context_kwargs["record_har_path"] = str(artifacts.har_path)
            context_kwargs["record_har_mode"] = "minimal"
        context = browser.new_context(**context_kwargs)
        page = context.new_page()
        _attach_console_logger(page, artifacts.console_log)
        self._session = BrowserSession(
            playwright=playwright,
            browser=browser,
            context=context,
            page=page,
            artifacts=artifacts,
        )
        return self._session

    def __exit__(self, exc_type, exc, tb) -> None:  # pragma: no cover - cleanup
        if self._session:
            artifacts = self._session.artifacts
            self._session.close()
            self._session = None
            _convert_videos_to_mp4(artifacts.video_dir)

    def _resolve_headless(self) -> bool:
        if self.headful is None:
            return self.settings.headless
        return not self.headful

    def _resolve_slow_mo(self) -> int:
        if self.slow_mo is not None:
            return max(0, self.slow_mo)
        return max(0, self.settings.slow_mo)

    def _prepare_artifacts(self) -> BrowserArtifacts:
        base = Path(self.settings.artifacts_dir)
        base.mkdir(parents=True, exist_ok=True)
        console_log = base / "console.log"
        har_path = (base / "network.har") if self.settings.collect_har else None
        video_dir = (base / "videos") if self.settings.record_video else None
        if video_dir:
            video_dir.mkdir(parents=True, exist_ok=True)
        return BrowserArtifacts(har_path=har_path, console_log=console_log, video_dir=video_dir)


def _attach_console_logger(page: Page, log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("", encoding="utf-8")

    def _log(entry) -> None:
        message = f"[{entry.type}] {entry.text}\n"
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(message)

    page.on("console", _log)


def _convert_videos_to_mp4(video_dir: Optional[Path]) -> None:
    if not video_dir or not video_dir.exists():
        return
    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        return
    for webm_file in video_dir.rglob("*.webm"):
        mp4_file = webm_file.with_suffix(".mp4")
        try:
            subprocess.run(
                [
                    ffmpeg_path,
                    "-y",
                    "-i",
                    str(webm_file),
                    "-c",
                    "copy",
                    str(mp4_file),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            webm_file.unlink(missing_ok=True)
        except Exception:
            continue
