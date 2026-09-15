"""
Generate voice PER SCENE from a structured master.md (Script+Prompt written
together per scene -- see memory step2-script-prompt-authoring / repo
docs/master-format) instead of blindly splitting the whole script by
max_chars like generate_script_to_voice does.

Why: max_chars-splitting has no relationship to the scene boundaries used
for the per-scene image prompts, so there's no way to know afterwards which
part of the merged voice file corresponds to which image -- that's what
forced a fragile Whisper-alignment step downstream. Generating one TTS call
per scene means each scene's exact [start, end] in the merged file is known
directly from generation (summing each clip's real duration as we go), so
the later CapCut-assembly step becomes a plain lookup, no alignment needed.
"""
import os
import re
import csv
import time
import zipfile
import tempfile

import torch
import torchaudio

from .model_manager import model_manager
from .voice_manager import resolve_voice_path
from .generation_functions import format_time

_SCENE_BLOCK_RE = re.compile(
    r'\[Scene\s+(\d+)(?:\s*[—-]\s*(\w+))?\]\s*\nScript:\s*(.+?)\n(?=Prompt:)',
    re.DOTALL,
)


def parse_master_scenes(master_text):
    """[{"scene": int, "tag": "INTRO"/"OUTRO"/"", "script": str}, ...], sorted
    by scene number. Matches the [Scene N] / Script: / Prompt: block format."""
    scenes = []
    for m in _SCENE_BLOCK_RE.finditer(master_text):
        scenes.append({
            "scene": int(m.group(1)),
            "tag": (m.group(2) or "").strip().upper(),
            "script": m.group(3).strip(),
        })
    scenes.sort(key=lambda s: s["scene"])
    return scenes


def generate_scene_voice(master_text, master_file, voice_name, pause_ms, apply_mastering):
    """Generator: yields (progress_0_100, status_text, audio_or_None,
    timing_csv_path_or_None, clips_zip_path_or_None). zip/csv only set on
    the final yield."""
    try:
        start_time = time.time()

        if master_file:
            path = master_file.name if hasattr(master_file, "name") else master_file
            with open(path, encoding="utf-8") as f:
                master_text = f.read()

        if not master_text or not master_text.strip():
            yield 0, "❌ Error: No master.md text/file found.", None, None, None
            return

        scenes = parse_master_scenes(master_text)
        if not scenes:
            yield 0, ("❌ Error: Couldn't find any '[Scene N] / Script: ...' blocks. "
                       "Check the master.md format."), None, None, None
            return

        if not voice_name or voice_name == "None":
            yield 0, "❌ Error: Please select a voice.", None, None, None
            return
        audio_prompt_path = resolve_voice_path(voice_name, "en")
        if not audio_prompt_path:
            yield 0, f"❌ Error: Voice '{voice_name}' not found.", None, None, None
            return

        yield 3, f"Loading Turbo model... ({len(scenes)} scenes found)", None, None, None
        model = model_manager.get_turbo_model()
        if model is None:
            yield 0, "❌ Error: Failed to load Turbo model.", None, None, None
            return

        pause_sec = max(0, pause_ms) / 1000.0
        silence = torch.zeros(1, int(model.sr * pause_sec))

        clips_dir = tempfile.mkdtemp(prefix="scene_clips_")
        pieces, timing = [], []
        cursor_samples = 0
        total = len(scenes)
        for i, sc in enumerate(scenes):
            progress = 3 + int((i / total) * 80)
            preview = sc["script"] if len(sc["script"]) <= 60 else sc["script"][:57] + "..."
            label = f"Scene {sc['scene']}" + (f" ({sc['tag']})" if sc["tag"] else "")
            yield progress, f"{label} ({i + 1}/{total}): {preview}", None, None, None

            wav = model.generate(sc["script"], audio_prompt_path=audio_prompt_path)
            n_samples = wav.shape[-1]
            start_s = cursor_samples / model.sr
            end_s = (cursor_samples + n_samples) / model.sr
            timing.append({
                "scene": sc["scene"], "tag": sc["tag"], "label": label,
                "start": round(start_s, 3), "end": round(end_s, 3),
                "duration": round(end_s - start_s, 3),
            })

            torchaudio.save(os.path.join(clips_dir, f"scene_{sc['scene']:03d}.wav"), wav, model.sr)

            pieces.append(wav)
            cursor_samples += n_samples
            if i < total - 1:
                pieces.append(silence)
                cursor_samples += silence.shape[-1]

        yield 85, "Merging scenes...", None, None, None
        full_wav = torch.cat(pieces, dim=-1)
        sr = model.sr

        if apply_mastering:
            yield 90, "Mastering (Compressor → Normalize → EQ)...", None, None, None
            from . import audio_mastering
            try:
                full_wav_np = audio_mastering.apply_master_chain(full_wav.squeeze(0).numpy(), sr)
            except Exception as e:
                full_wav_np = full_wav.squeeze(0).numpy()
                yield 92, f"⚠️ Mastering failed, dùng bản chưa master: {e}", None, None, None
        else:
            full_wav_np = full_wav.squeeze(0).numpy()

        timing_dir = tempfile.mkdtemp(prefix="scene_timing_")
        timing_path = os.path.join(timing_dir, "scene_timing.csv")
        with open(timing_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["scene", "tag", "label", "start", "end", "duration"])
            w.writeheader()
            w.writerows(timing)

        zip_path = os.path.join(timing_dir, "scene_clips.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            for fn in sorted(os.listdir(clips_dir)):
                zf.write(os.path.join(clips_dir, fn), arcname=fn)

        total_time = time.time() - start_time
        status = (
            f"✅ Done! {total} scenes | {format_time(total_time)}\n"
            f"Total duration: {format_time(timing[-1]['end'])}\n"
            f"Timing manifest + individual clips ready to download below."
        )
        yield 100, status, (sr, full_wav_np), timing_path, zip_path

    except Exception as e:
        yield 0, f"❌ Error: {str(e)}", None, None, None
