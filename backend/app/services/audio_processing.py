from __future__ import annotations

import shutil
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path

from app.core.config import settings


@dataclass
class AudioChunk:
    path: Path
    start_ms: int
    end_ms: int


class AudioChunkingError(RuntimeError):
    pass


class AudioChunkingService:
    def __init__(self, chunk_seconds: int | None = None) -> None:
        self.chunk_seconds = chunk_seconds or settings.audio_chunk_seconds

    def split(self, audio_path: Path) -> list[AudioChunk]:
        if shutil.which("ffmpeg") is None:
            raise AudioChunkingError("缺少 ffmpeg，无法处理多格式长音频。请安装 ffmpeg 后重试。")
        try:
            from pydub import AudioSegment
        except ImportError as exc:
            raise AudioChunkingError("缺少 pydub，请先安装后端依赖。") from exc

        try:
            audio = AudioSegment.from_file(audio_path)
        except Exception as exc:  # pragma: no cover - pydub raises backend-specific errors
            raise AudioChunkingError(f"音频解码失败：{exc}") from exc

        audio = audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)
        chunk_ms = self.chunk_seconds * 1000
        output_dir = Path(tempfile.mkdtemp(prefix="audio_chunks_"))
        chunks: list[AudioChunk] = []
        for start_ms in range(0, len(audio), chunk_ms):
            end_ms = min(start_ms + chunk_ms, len(audio))
            chunk_path = output_dir / f"chunk_{start_ms}_{end_ms}.wav"
            audio[start_ms:end_ms].export(chunk_path, format="wav")
            chunks.append(AudioChunk(path=chunk_path, start_ms=start_ms, end_ms=end_ms))
        return chunks

    def split_wav_without_ffmpeg(self, audio_path: Path) -> list[AudioChunk]:
        """Testing fallback for simple PCM wav fixtures."""
        with wave.open(str(audio_path), "rb") as reader:
            frame_rate = reader.getframerate()
            channels = reader.getnchannels()
            sample_width = reader.getsampwidth()
            total_frames = reader.getnframes()
            chunk_frames = frame_rate * self.chunk_seconds
            output_dir = Path(tempfile.mkdtemp(prefix="audio_chunks_"))
            chunks: list[AudioChunk] = []
            start_frame = 0
            while start_frame < total_frames:
                frames = reader.readframes(chunk_frames)
                end_frame = min(start_frame + chunk_frames, total_frames)
                chunk_path = output_dir / f"chunk_{start_frame}_{end_frame}.wav"
                with wave.open(str(chunk_path), "wb") as writer:
                    writer.setnchannels(channels)
                    writer.setsampwidth(sample_width)
                    writer.setframerate(frame_rate)
                    writer.writeframes(frames)
                chunks.append(
                    AudioChunk(
                        path=chunk_path,
                        start_ms=round(start_frame / frame_rate * 1000),
                        end_ms=round(end_frame / frame_rate * 1000),
                    )
                )
                start_frame = end_frame
        return chunks
