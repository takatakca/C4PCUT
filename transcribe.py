"""Optional offline Faster Whisper adapter; no automatic model downloads."""
import json
import sys
from pathlib import Path

def transcribe(source, model_path):
    from faster_whisper import WhisperModel
    path = Path(model_path)
    if not path.is_dir():
        raise ValueError("A local CTranslate2 Whisper model directory is required")
    model = WhisperModel(str(path.resolve()), device="cpu", compute_type="int8", cpu_threads=2, num_workers=1, local_files_only=True)
    segments, _ = model.transcribe(str(source), beam_size=1, vad_filter=True)
    return [{"start": s.start, "end": s.end, "text": s.text.strip()} for s in segments if s.text.strip()]

if __name__ == "__main__":
    print(json.dumps(transcribe(sys.argv[1], sys.argv[2]), ensure_ascii=False))
