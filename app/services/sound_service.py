from __future__ import annotations

import platform
from pathlib import Path

from PySide6.QtWidgets import QApplication

try:
    from PySide6.QtCore import QUrl
    from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
    HAS_MULTIMEDIA = True
except ImportError:
    HAS_MULTIMEDIA = False

from app.core.logger import get_logger


class SoundService:
    """Service for playing reminder notification sounds.
    
    Supports:
    - System sounds (macOS built-in sounds)
    - Custom sound files (WAV, MP3, etc.)
    """
    
    # macOS system sounds
    SYSTEM_SOUNDS = {
        "Default": None,  # Use QApplication.beep()
        "Basso": "Basso",
        "Blow": "Blow",
        "Bottle": "Bottle",
        "Frog": "Frog",
        "Funk": "Funk",
        "Glass": "Glass",
        "Hero": "Hero",
        "Morse": "Morse",
        "Ping": "Ping",
        "Pop": "Pop",
        "Purr": "Purr",
        "Sosumi": "Sosumi",
        "Submarine": "Submarine",
        "Tink": "Tink",
    }
    
    def __init__(self) -> None:
        self._logger = get_logger(__name__)
        self._is_macos = platform.system() == "Darwin"
        self._player = None
        self._audio_output = None
        
    def play_sound(self, sound_name: str = "Default", custom_file: str | None = None, repeat: int = 3) -> bool:
        """Play a notification sound, repeating multiple times.
        
        Args:
            sound_name: Name of system sound (from SYSTEM_SOUNDS) or "Default" for beep
            custom_file: Path to custom sound file (WAV, MP3, etc.)
            repeat: Number of times to play the sound (default: 3, minimum: 3)
        
        Returns:
            True if sound played successfully, False otherwise
        """
        try:
            # Ensure at least 3 repetitions
            repeat = max(3, repeat)
            
            # If custom file is provided, use it
            if custom_file and Path(custom_file).exists():
                return self._play_custom_file(custom_file, repeat)
            
            # Check for custom sounds in the sounds folder (try exact match first, then without emoji)
            clean_name = sound_name.replace("🎵 ", "").strip()
            self._logger.info(f"Looking for custom sound: '{clean_name}'")
            custom_sound_path = self._find_custom_sound(clean_name)
            if custom_sound_path:
                self._logger.info(f"Playing custom sound file: {custom_sound_path}")
                return self._play_custom_file(custom_sound_path, repeat)
            
            # If "Default", use system beep
            if sound_name == "Default" or not sound_name:
                self._play_beep_repeat(repeat)
                self._logger.info(f"Played system beep {repeat} times")
                return True
            
            # Try macOS system sound
            if self._is_macos and sound_name in self.SYSTEM_SOUNDS:
                return self._play_macos_sound(sound_name, repeat)
            
            # Fallback to beep
            self._play_beep_repeat(repeat)
            self._logger.warning(f"Sound '{sound_name}' not found, using beep")
            return True
            
        except Exception as e:
            self._logger.error(f"Error playing sound: {e}", exc_info=True)
            # Fallback to beep
            try:
                self._play_beep_repeat(3)
                return True
            except:
                return False
    
    def _play_macos_sound(self, sound_name: str, repeat: int = 3) -> bool:
        """Play a macOS system sound using afplay, repeating multiple times."""
        try:
            import subprocess
            import time
            # macOS system sounds are in /System/Library/Sounds/
            sound_path = f"/System/Library/Sounds/{sound_name}.aiff"
            if Path(sound_path).exists():
                # Play the sound multiple times with a small delay between
                for i in range(repeat):
                    subprocess.Popen(
                        ["afplay", sound_path],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    if i < repeat - 1:  # Don't wait after the last play
                        time.sleep(0.4)  # Small delay between plays
                self._logger.info(f"Played macOS system sound: {sound_name} ({repeat} times)")
                return True
            else:
                self._logger.warning(f"System sound file not found: {sound_path}")
                self._play_beep_repeat(repeat)
                return True
        except Exception as e:
            self._logger.error(f"Error playing macOS sound: {e}")
            self._play_beep_repeat(repeat)
            return True
    
    def _play_beep_repeat(self, repeat: int = 3) -> None:
        """Play system beep multiple times."""
        import time
        for i in range(repeat):
            QApplication.beep()
            if i < repeat - 1:
                time.sleep(0.3)  # Small delay between beeps
    
    def _play_custom_file(self, file_path: str, repeat: int = 3) -> bool:
        """Play a custom sound file using QMediaPlayer or system command, repeating multiple times."""
        try:
            import time
            if HAS_MULTIMEDIA:
                # Use Qt Multimedia if available - play multiple times
                for i in range(repeat):
                    if not self._player:
                        self._audio_output = QAudioOutput()
                        self._player = QMediaPlayer()
                        self._player.setAudioOutput(self._audio_output)
                    
                    url = QUrl.fromLocalFile(file_path)
                    self._player.setSource(url)
                    self._audio_output.setVolume(0.8)  # 80% volume
                    self._player.play()
                    
                    # Wait for sound to finish (approximate) before next play
                    if i < repeat - 1:
                        # Get duration if possible, otherwise use default delay
                        time.sleep(1.0)  # Default 1 second between plays
                
                self._logger.info(f"Playing custom sound file: {file_path} ({repeat} times)")
                return True
            else:
                # Fallback: Use system command (macOS: afplay, Linux: aplay, Windows: start)
                import subprocess
                for i in range(repeat):
                    if self._is_macos:
                        subprocess.Popen(["afplay", file_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    elif platform.system() == "Linux":
                        subprocess.Popen(["aplay", file_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    elif platform.system() == "Windows":
                        # Windows: Use PowerShell to play sound synchronously
                        subprocess.Popen(
                            ["powershell", "-Command", f"(New-Object Media.SoundPlayer '{file_path}').PlaySync()"],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
                    else:
                        self._play_beep_repeat(repeat)
                        return True
                    
                    if i < repeat - 1:
                        time.sleep(0.5)  # Small delay between plays
                
                self._logger.info(f"Playing custom sound file via system command: {file_path} ({repeat} times)")
                return True
                
        except Exception as e:
            self._logger.error(f"Error playing custom sound file: {e}", exc_info=True)
            # Fallback to beep
            self._play_beep_repeat(repeat)
            return True
    
    def _find_custom_sound(self, sound_name: str) -> str | None:
        """Find a custom sound file in the sounds folder.
        
        Returns the path to the sound file if found, None otherwise.
        """
        try:
            sounds_dir = Path(__file__).resolve().parents[1] / "resources" / "sounds"
            if not sounds_dir.exists():
                self._logger.debug(f"Sounds directory does not exist: {sounds_dir}")
                return None
            
            # Clean the sound name (remove any spaces, special chars that might be in file names)
            clean_name = sound_name.strip().lower()
            self._logger.info(f"Searching for custom sound: '{sound_name}' (cleaned: '{clean_name}') in {sounds_dir}")
            
            # Look for files matching the sound name (case-insensitive, with or without extension)
            for ext in [".wav", ".mp3", ".aiff", ".m4a", ".aac"]:
                # Try exact match
                sound_file = sounds_dir / f"{sound_name}{ext}"
                if sound_file.exists():
                    self._logger.info(f"Found custom sound (exact match): {sound_file}")
                    return str(sound_file)
                
                # Try case-insensitive match
                for existing_file in sounds_dir.glob(f"*{ext}"):
                    if existing_file.stem.lower() == clean_name:
                        self._logger.info(f"Found custom sound (case-insensitive): {existing_file}")
                        return str(existing_file)
            
            # If no exact match, try partial match (e.g., "alert-tone" matches "alert -tone.wav")
            for ext in [".wav", ".mp3", ".aiff", ".m4a", ".aac"]:
                for existing_file in sounds_dir.glob(f"*{ext}"):
                    file_stem = existing_file.stem.lower().replace(" ", "").replace("-", "")
                    search_name = clean_name.replace(" ", "").replace("-", "")
                    if search_name in file_stem or file_stem in search_name:
                        self._logger.info(f"Found custom sound (partial match): {existing_file}")
                        return str(existing_file)
            
            # List all available sounds for debugging
            all_sounds = list(sounds_dir.glob("*.wav")) + list(sounds_dir.glob("*.mp3")) + \
                        list(sounds_dir.glob("*.aiff")) + list(sounds_dir.glob("*.m4a"))
            self._logger.warning(
                f"Custom sound '{sound_name}' not found. Available sounds: {[f.stem for f in all_sounds]}"
            )
            return None
        except Exception as e:
            self._logger.error(f"Error finding custom sound: {e}", exc_info=True)
            return None
    
    def get_custom_sounds(self) -> list[str]:
        """Get list of custom sound files in the sounds folder."""
        try:
            sounds_dir = Path(__file__).resolve().parents[1] / "resources" / "sounds"
            if not sounds_dir.exists():
                return []
            
            sound_files = []
            for ext in [".wav", ".mp3", ".aiff", ".m4a", ".aac"]:
                sound_files.extend(sounds_dir.glob(f"*{ext}"))
            
            return [f.name for f in sound_files]
        except Exception as e:
            self._logger.error(f"Error getting custom sounds: {e}")
            return []
    
    def get_available_sounds(self) -> list[str]:
        """Get list of available system sounds."""
        return list(self.SYSTEM_SOUNDS.keys())
    
    def stop(self) -> None:
        """Stop any currently playing sound."""
        if self._player:
            self._player.stop()
