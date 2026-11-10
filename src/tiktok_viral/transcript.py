"""Download one video and transcribe its narration: meta.json and transcript.txt for AI analysis.

Whisper backends: mlx-whisper on Apple Silicon (extra `transcribe-mac`), else faster-whisper (extra `transcribe`).
ffmpeg must be on PATH. Music-only videos produce Whisper hallucinations ("Hãy subscribe cho kênh Ghiền Mì Gõ");
those lines are dropped and such a video is marked as having no narration.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

from tiktok_viral.ytdlp import download_video, video_info

META_KEYS = ["id", "title", "description", "uploader", "upload_date", "duration", "view_count", "like_count",
             "comment_count", "repost_count", "webpage_url"]
MLX_MODEL = "mlx-community/whisper-large-v3-turbo"
FASTER_MODEL = "large-v3-turbo"
MIN_NARRATION_WORDS = 20
NO_NARRATION = "(no narration: music and on-screen text only; analyse the frames instead)"
HALLUCINATIONS = re.compile(
    r"(subscribe cho kênh|ghiền mì gõ|cảm ơn các bạn đã theo dõi|hẹn gặp lại các bạn trong những video tiếp theo|"
    r"đăng ký kênh|la la school|thanks for watching|please subscribe)",
    re.IGNORECASE,
)


class TranscriptError(RuntimeError):
    pass


def clean_text(text: str) -> str:
    lines = [line.strip() for line in text.splitlines()]
    kept = [line for line in lines if line and not HALLUCINATIONS.search(line)]
    joined = "\n".join(kept)
    return joined if len(joined.split()) >= MIN_NARRATION_WORDS else NO_NARRATION


def to_wav(video: Path) -> Path:
    if not shutil.which("ffmpeg"):
        raise TranscriptError("ffmpeg is not on PATH")
    wav = video.with_name("audio.wav")
    proc = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-ac", "1", "-ar", "16000",
                           str(wav)], capture_output=True, text=True)
    if proc.returncode != 0:
        raise TranscriptError(f"ffmpeg failed: {proc.stderr[-200:]}")
    return wav


def whisper(wav: Path, language: str) -> str:
    try:
        import mlx_whisper

        result = mlx_whisper.transcribe(str(wav), path_or_hf_repo=MLX_MODEL, language=language or None,
                                        condition_on_previous_text=False)
        return "\n".join(seg["text"].strip() for seg in result.get("segments", []))
    except ImportError:
        pass
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise TranscriptError("no whisper backend: uv sync --extra transcribe-mac (Apple Silicon) "
                              "or --extra transcribe") from exc
    segments, _ = WhisperModel(FASTER_MODEL).transcribe(str(wav), language=language or None,
                                                        condition_on_previous_text=False)
    return "\n".join(seg.text.strip() for seg in segments)


def fetch_transcript(url: str, out_dir: Path, media_dir: Path, language: str = "") -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    info = video_info(url)
    meta = {k: info.get(k) for k in META_KEYS} | {"source_url": url}
    (out_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    text = clean_text(whisper(to_wav(download_video(url, media_dir)), language))
    source = "none" if text == NO_NARRATION else "whisper"
    (out_dir / "transcript.txt").write_text(f"# source: {url}\n# text from: {source}\n\n{text}\n")
    return {"words": 0 if source == "none" else len(text.split()), "source": source, "views": meta.get("view_count")}
