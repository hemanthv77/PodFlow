"""
Filesystem abstractions for podcast audio files.

Encapsulates naming conventions, directory structure, and file-existence
checks so the downloader does not need to know about these details.
"""

import re
from pathlib import Path

from podflow.domain.episode import Episode
from podflow.exceptions.exceptions import FilesystemError
from podflow.logging.logger import get_logger

logger = get_logger(__name__)

# Characters to strip / replace when building safe filenames
_UNSAFE_CHARS = re.compile(r'[<>:"/\\|?*\'’]')


class FileManager:
    """Manages podcast audio files on the local filesystem.

    Responsibilities:
        - Generate safe, deterministic filenames from episode metadata.
        - Check whether an episode has already been downloaded.
        - Ensure the download directory exists.
    """

    def __init__(self, download_dir: Path) -> None:
        """
        Args:
            download_dir: Root directory for downloaded audio files.
        """
        self._root = download_dir
        self._ensure_directory()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def episode_path(self, episode: Episode) -> Path:
        """Return the full filesystem path where this episode's audio *should* be stored.

        The filename is derived from the episode title (sanitised) with
        the audio file extension preserved from the URL.

        Args:
            episode: The episode domain object.

        Returns:
            Resolved :class:`Path` to the audio file.
        """
        extension = self._guess_extension(episode.audio_url)
        filename = self._safe_filename(episode.title, extension)
        return self._root / filename

    def exists(self, episode: Episode) -> bool:
        """Check whether the audio file for *episode* already exists on disk.

        Only checks the path returned by :meth:`episode_path` — does not
        scan the entire directory.

        Args:
            episode: The episode to check.

        Returns:
            ``True`` if the file exists and is a regular file.
        """
        return self.episode_path(episode).is_file()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _ensure_directory(self) -> None:
        try:
            self._root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise FilesystemError(
                f"Cannot create download directory {self._root}: {exc}"
            ) from exc

    @staticmethod
    def _safe_filename(title: str, extension: str) -> str:
        """Build a sanitised filename from an episode title.

        Replaces unsafe characters with underscores, collapses whitespace,
        and truncates to a reasonable length.

        Args:
            title: Raw episode title.
            extension: File extension including leading dot (e.g. ``.mp3``).

        Returns:
            A safe filename string.
        """
        sanitised = _UNSAFE_CHARS.sub("_", title)
        sanitised = re.sub(r"\s+", " ", sanitised).strip()
        # Truncate to avoid filesystem limits (leave room for extension)
        max_len = 200 - len(extension)
        sanitised = sanitised[:max_len].rstrip()
        return f"{sanitised}{extension}"

    @staticmethod
    def _guess_extension(audio_url: str | None) -> str:
        """Extract the file extension from an audio URL.

        Falls back to ``.mp3`` if the URL is absent or has no recognisable extension.
        """
        if not audio_url:
            return ".mp3"
        # Strip query params / fragments before extracting suffix
        path = audio_url.split("?")[0].split("#")[0]
        suffix = Path(path).suffix.lower()
        if suffix in (".mp3", ".m4a", ".ogg", ".wav", ".opus", ".aac"):
            return suffix
        return ".mp3"
