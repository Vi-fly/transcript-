import whisper
import tempfile
import yt_dlp
import os
import random
import time
import gc
import torch
from urllib.parse import urlparse


class TranscriptionService:
    def __init__(self):
        self.model = None
        self.model_size = "tiny"  # Use tiny model for faster processing
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self._model_loaded = False

    def load_model(self):
        """Load the Whisper model."""
        if not self._model_loaded:
            # Clear CUDA cache if using GPU
            if self.device == "cuda":
                torch.cuda.empty_cache()

            # Clear memory
            gc.collect()

            # Load model
            self.model = whisper.load_model(self.model_size, device=self.device)
            self._model_loaded = True

            # Another memory cleanup after loading
            gc.collect()

        return self.model

    def _get_ydl_opts(self, temp_file, format_option="bestaudio/best"):
        """Get yt-dlp options with specified format."""
        return {
            "format": format_option,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "128",
            }],
            "outtmpl": temp_file[:-4],
            "quiet": True,
            "no_warnings": True,
            "nocheckcertificate": True,
            "ignoreerrors": False,
            "logtostderr": False,
            "extractor_retries": 3,
            "retries": 3,
            "fragment_retries": 3,
            "skip_unavailable_fragments": False,
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1"
            },
        }

    def _try_download(self, url, temp_file, format_option):
        """Attempt to download with specific format option."""
        try:
            ydl_opts = self._get_ydl_opts(temp_file, format_option)
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            return True
        except Exception as e:
            print(f"Download attempt failed with format {format_option}: {str(e)}")
            return False

    def download_audio(self, url):
        """Download audio from YouTube video."""
        temp_file = None
        try:
            temp_dir = tempfile.gettempdir()
            timestamp = int(time.time())
            temp_file = os.path.join(temp_dir, f"audio_{timestamp}.mp3")

            # Try different format options
            format_options = [
                "bestaudio/best",
                "worstaudio/worst",  # Fallback to lower quality
                "bestaudio[ext=m4a]",
                "bestaudio[ext=mp3]",
                "140"  # Common audio-only format
            ]

            for format_option in format_options:
                if self._try_download(url, temp_file, format_option):
                    break
            else:
                raise ValueError("All download attempts failed")

            if not os.path.exists(temp_file):
                raise FileNotFoundError("Downloaded audio file not found")

            return temp_file

        except Exception as e:
            if temp_file:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                if os.path.exists(temp_file[:-4]):
                    os.remove(temp_file[:-4])
            raise ValueError(f"Error downloading audio: {str(e)}")

    def transcribe_audio(self, audio_path):
        """Transcribe audio using Whisper model."""
        try:
            if not os.path.exists(audio_path):
                raise FileNotFoundError(f"Audio file not found at {audio_path}")

            if os.path.getsize(audio_path) == 0:
                raise ValueError("Audio file is empty")

            # Load model
            model = self.load_model()

            # Transcribe with optimized settings
            result = model.transcribe(
                audio_path,
                fp16=False,  # Disable half-precision for better compatibility
                language="en",  # Specify English for faster processing
                task="transcribe",  # Specific task for optimization
            )

            # Clean up
            try:
                os.remove(audio_path)
            except Exception:
                pass  # Ignore cleanup errors

            # Memory cleanup
            gc.collect()
            if self.device == "cuda":
                torch.cuda.empty_cache()

            return result["text"]
        except Exception as e:
            try:
                if os.path.exists(audio_path):
                    os.remove(audio_path)
            except Exception:
                pass  # Ignore cleanup errors
            raise ValueError(f"Error transcribing audio: {str(e)}")

    def process_video(self, url):
        """Process video URL and return transcription."""
        audio_path = None
        try:
            audio_path = self.download_audio(url)
            if not audio_path:
                raise ValueError("Failed to download audio")

            transcript = self.transcribe_audio(audio_path)
            return transcript
        except Exception as e:
            # Ensure cleanup
            if audio_path and os.path.exists(audio_path):
                try:
                    os.remove(audio_path)
                except Exception:
                    pass
            raise ValueError(f"Error processing video: {str(e)}")
