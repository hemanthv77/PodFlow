"""
Filesystem abstraction for podcast assets.

Encapsulates directory structure, safe filename generation, and
file-existence checks.  The rest of the application should never
hardcode paths — all path logic flows through this module.

Directory layout::

    {download_root}/
    ├── audio/          ← .mp3, .m4a
    ├── transcripts/    ← .txt, .vtt, .srt
    ├── summaries/      ← .json
    ├── images/         ← .jpg, .png
    └── metadata/       ← .json
"""

from __future__ import annotations

import re
from pathlib import Path

from podflow.domain.episode import Episode
from podflow.exceptions.exceptions import FilesystemError
from podflow.logging.logger import get_logger

logger = get_logger(__name__)

# Characters to replace when building safe filenames
_UNSAFE_CHARS = re.compile(r'[<>:"/\\|?*\'’]')

# Subdirectories under the download root
_SUBDIR_AUDIO = "audio"
_SUBDIR_TRANSCRIPTS = "transcripts"
_SUBDIR_SUMMARIES = "summaries"
_SUBDIR_IMAGES = "images"
_SUBDIR_METADATA = "metadata"

_ALL_SUBDIRS = (
    _SUBDIR_AUDIO,
    _SUBDIR_TRANSCRIPTS,
    _SUBDIR_SUMMARIES,
    _SUBDIR_IMAGES,
    _SUBDIR_METADATA,
)


class FileManager:
    """Manages filesystem paths for podcast assets.

    Responsibilities:
        - Generate safe, deterministic filenames from episode metadata.
        - Route files into type-specific subdirectories (audio, transcripts, ...).
        - Provide atomic-write temporary paths.
        - Check file existence.

    Usage::

        fm = FileManager(Path("downloads"))
        fm.ensure_directories()

        path = fm.audio_path(episode)
        tmp  = fm.temporary_path(episode)
        done = fm.exists(path)
    """

    def __init__(self, download_root: Path) -> None:
        """
        Args:
            download_root: Root directory for all downloaded assets.
        """
        self._root = download_root

    # ------------------------------------------------------------------
    # Directories
    # ------------------------------------------------------------------

    def ensure_directories(self) -> None:
        """Create the root directory and all asset subdirectories.

        Idempotent — safe to call multiple times.
        """
        try:
            self._root.mkdir(parents=True, exist_ok=True)
            for sub in _ALL_SUBDIRS:
                (self._root / sub).mkdir(exist_ok=True)
        except OSError as exc:
            raise FilesystemError(
                f"Cannot create download directories under {self._root}: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Paths
    # ------------------------------------------------------------------

    def audio_path(self, episode: Episode) -> Path:
        """Return the path where this episode's audio file should be stored.

        Lives under ``downloads/audio/``.
        """
        return self._build_path(episode, _SUBDIR_AUDIO)

    def temporary_path(self, episode: Episode) -> Path:
        """Return a temporary path for atomic writes.

        The caller writes to this path, then renames it to
        :meth:`audio_path` on success.  Prevents partial files from being
        treated as complete.
        """
        return Path(str(self.audio_path(episode)) + ".part")

    def transcript_path(self, episode: Episode) -> Path:
        """Return the path for a transcript file (future use)."""
        return self._build_path(episode, _SUBDIR_TRANSCRIPTS, extension=".txt")

    def summary_path(self, episode: Episode) -> Path:
        """Return the path for a summary file (future use)."""
        return self._build_path(episode, _SUBDIR_SUMMARIES, extension=".json")

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @staticmethod
    def exists(path: Path) -> bool:
        """Return ``True`` if *path* points to an existing regular file."""
        return path.is_file()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_path(
        self,
        episode: Episode,
        subdir: str,
        *,
        extension: str | None = None,
    ) -> Path:
        """Build a full path: ``root/subdir/safe_filename.ext``."""
        if subdir == _SUBDIR_AUDIO:
            ext = extension or self._guess_audio_extension(episode.audio_url)
        else:
            ext = extension or ""

        filename = self._safe_filename(episode.title, ext)
        return self._root / subdir / filename

    @staticmethod
    def _safe_filename(title: str, extension: str) -> str:
        """Build a sanitised filename from an episode title.

        Replaces unsafe characters, collapses whitespace, and truncates
        to stay within filesystem limits.
        """
        sanitised = _UNSAFE_CHARS.sub("_", title)
        sanitised = re.sub(r"\s+", " ", sanitised).strip()
        max_len = 200 - len(extension)
        sanitised = sanitised[:max_len].rstrip()
        return f"{sanitised}{extension}"

    @staticmethod
    def _guess_audio_extension(audio_url: str | None) -> str:
        """Extract the file extension from an audio URL.

        Falls back to ``.mp3`` if the URL is absent or has no recognisable
        audio extension.
        """
        if not audio_url:
            return ".mp3"

        path = audio_url.split("?")[0].split("#")[0]
        suffix = Path(path).suffix.lower()
        if suffix in (".mp3", ".m4a", ".ogg", ".wav", ".opus", ".aac"):
            return suffix
        return ".mp3"
