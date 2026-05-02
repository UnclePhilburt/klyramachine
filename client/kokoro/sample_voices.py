"""Synthesize a Klyra-style line in several Kokoro voices for vibe-check."""
import wave, time
from pathlib import Path
from kokoro_onnx import Kokoro

HERE = Path(__file__).parent
k = Kokoro(str(HERE / "kokoro-v1.0.onnx"), str(HERE / "voices-v1.0.bin"))

LINE = (
    "Oh look who's turned into a sailor overnight. "
    "Better watch out for seagulls in here. "
    "And next time, maybe rinse the spaghetti stain off your shirt before going outside."
)

# All English voices. Skipping am_santa (Christmas), ef_dora / em_alex (Spanish).
VOICES = [
    # American male
    "am_adam", "am_echo", "am_eric", "am_fenrir", "am_liam",
    "am_michael", "am_onyx", "am_puck",
    # American female
    "af_alloy", "af_aoede", "af_bella", "af_heart", "af_jessica",
    "af_kore", "af_nicole", "af_nova", "af_river", "af_sarah", "af_sky",
    # British male
    "bm_daniel", "bm_fable", "bm_george", "bm_lewis",
    # British female
    "bf_alice", "bf_emma", "bf_isabella", "bf_lily",
]

for v in VOICES:
    t0 = time.time()
    samples, sr = k.create(LINE, voice=v, speed=1.0, lang="en-us")
    dt = time.time() - t0

    out = HERE / f"sample_{v}.wav"
    # Convert to int16 PCM
    import numpy as np
    pcm = (samples * 32767).clip(-32768, 32767).astype(np.int16)
    with wave.open(str(out), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())

    audio_dur = len(samples) / sr
    print(f"{v:15} | gen {dt:.2f}s | audio {audio_dur:.2f}s | RTF {dt/audio_dur:.2f}x | {out.name}")
