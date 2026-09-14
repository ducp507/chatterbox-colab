"""
Speech generation, conversion, and utility functions for Chatterbox TTS Enhanced
"""
import os
import random
import numpy as np
import torch
import time
import re
from .config import DEVICE, LANGUAGE_CONFIG, SUPPORTED_LANGUAGES
from .model_manager import model_manager
from .voice_manager import resolve_voice_path


def set_seed(seed: int):
    """Set random seed for reproducibility."""
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
    random.seed(seed)
    np.random.seed(seed)


def estimate_generation_time(text_length):
    """Estimate generation time based on text length."""
    return (text_length / 50) * 2 + 1


def format_time(seconds):
    """Format seconds into readable time string."""
    if seconds < 60:
        return f"{seconds:.1f} seconds"
    minutes = int(seconds // 60)
    seconds = seconds % 60
    return f"{minutes} minute{'s' if minutes != 1 else ''} {seconds:.1f} seconds"


def smart_chunk_text(text, max_words=40):
    """
    Intelligently chunk text based on sentence boundaries and word count.
    Accumulates sentences to maximize chunk size up to max_words.
    Supports all languages including CJK (Chinese, Japanese, Korean).
    """
    # Detect if text contains CJK characters (Chinese, Japanese, Korean)
    def has_cjk(text):
        return bool(re.search(r'[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af]', text))
    
    is_cjk = has_cjk(text)
    
    # Enhanced sentence pattern supporting multiple languages
    # Includes: . ! ? (Western), 。！？ (CJK), । (Hindi), ؟ (Arabic)
    sentence_pattern = r'(?<=[.!?。！？।؟])\s*|\n+'
    sentences = re.split(sentence_pattern, text)
    
    chunks = []
    current_chunk = []
    current_count = 0
    
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        
        # Count words (space-separated) or characters (CJK)
        if is_cjk:
            sentence_count = len(re.sub(r'\s+', '', sentence))
        else:
            sentence_count = len(sentence.split())
        
        # Check if adding this sentence exceeds the limit
        if current_count + sentence_count > max_words:
            # If current chunk is not empty, save it
            if current_chunk:
                chunks.append(' '.join(current_chunk) if not is_cjk else ''.join(current_chunk))
                current_chunk = []
                current_count = 0
            
            # If the single sentence itself is longer than max_words, we must split it
            if sentence_count > max_words:
                # Split at commas/semicolons: , ; (Western), ，、； (CJK), ، (Arabic)
                sub_parts = re.split(r'[,;،、；،]\s*', sentence)
                for part in sub_parts:
                    part = part.strip()
                    if not part:
                        continue
                    
                    if is_cjk:
                        part_count = len(re.sub(r'\s+', '', part))
                    else:
                        part_count = len(part.split())
                    
                    if current_count + part_count > max_words and current_chunk:
                        chunks.append(' '.join(current_chunk) if not is_cjk else ''.join(current_chunk))
                        current_chunk = [part]
                        current_count = part_count
                    else:
                        current_chunk.append(part)
                        current_count += part_count
            else:
                # Sentence fits in a new chunk
                current_chunk.append(sentence)
                current_count += sentence_count
        else:
            # Sentence fits in current chunk
            current_chunk.append(sentence)
            current_count += sentence_count
    
    # Add remaining chunk
    if current_chunk:
        chunks.append(' '.join(current_chunk) if not is_cjk else ''.join(current_chunk))
    
    return chunks if chunks else [text]


def generate_speech(text, voice_name, exaggeration, temperature, seed_num, cfgw, min_p, top_p, repetition_penalty):
    """Generate speech with progress tracking and validation."""
    try:
        start_time = time.time()
        
        # Input validations
        if not text or not text.strip():
            yield 0, None, "❌ Error: Input text cannot be empty."
            return
        
        if len(text) > 250:
            print(f"ℹ️ Text length: {len(text)} chars - Using smart chunking")
        
        if not voice_name or voice_name == "None":
            audio_prompt_path = None
            yield 10, None, "⚠️ No voice selected - using default voice..."
        else:
            audio_prompt_path = resolve_voice_path(voice_name, "en")
            if not audio_prompt_path:
                yield 0, None, f"❌ Error: Voice '{voice_name}' not found."
                return
            yield 10, None, f"Loading voice: {voice_name}..."
        
        # Load model via manager (handles unloading others)
        yield 20, None, "Loading TTS model..."
        model = model_manager.get_tts_model()
        if model is None:
             yield 0, None, "❌ Error: Failed to load TTS model."
             return
        
        # Set seed if specified
        if seed_num != 0:
            set_seed(int(seed_num))
            yield 30, None, f"Seed set to {seed_num}"
        
        # Chunk text
        text_chunks = smart_chunk_text(text)
        total_chunks = len(text_chunks)
        generated_wavs = []
        
        # Estimate time
        estimated_time = estimate_generation_time(len(text))
        yield 40, None, f"Generating speech (English)...\nChunks: {total_chunks}\nEstimated time: {format_time(estimated_time)}"
        
        # Generate audio for each chunk
        for i, chunk in enumerate(text_chunks):
            progress = 40 + int((i / total_chunks) * 50)
            yield progress, None, f"Generating chunk {i+1}/{total_chunks}..."
            
            chunk_wav = model.generate(
                chunk,
                audio_prompt_path=audio_prompt_path,
                exaggeration=exaggeration,
                temperature=temperature,
                cfg_weight=cfgw,
                min_p=min_p,
                top_p=top_p,
                repetition_penalty=repetition_penalty,
            )
            generated_wavs.append(chunk_wav)
        
        if not generated_wavs:
             yield 0, None, "❌ Error: No audio generated."
             return

        yield 90, None, "Finalizing audio..."
        
        # Concatenate audio chunks
        if len(generated_wavs) > 1:
            full_wav = torch.cat(generated_wavs, dim=-1)
        else:
            full_wav = generated_wavs[0]
        
        # Calculate actual time taken
        total_time = time.time() - start_time
        final_status = f"✅ Generation complete!\nTime taken: {format_time(total_time)}\nText length: {len(text)} chars\nChunks: {total_chunks}"
        
        yield 100, (model.sr, full_wav.squeeze(0).numpy()), final_status
        
    except Exception as e:
        error_status = f"❌ Error generating speech: {str(e)}"
        yield 0, None, error_status


def generate_multilingual_speech(text, voice_name, language_code, exaggeration, temperature, seed_num, cfgw):
    """Generate multilingual speech with progress tracking."""
    try:
        start_time = time.time()
        
        # Input validations
        if not text or not text.strip():
            yield 0, None, "❌ Error: Input text cannot be empty."
            return
        
        if len(text) > 250:
            print(f"ℹ️ Text length: {len(text)} chars - Using smart chunking")
        
        if not language_code:
            yield 0, None, "❌ Error: Please select a language for multilingual TTS."
            return
        
        # Resolve voice path based on language
        if not voice_name or voice_name == "None":
            audio_prompt_path = LANGUAGE_CONFIG.get(language_code, {}).get("audio")
            yield 10, None, f"⚠️ Using default voice for {SUPPORTED_LANGUAGES.get(language_code, language_code)}..."
        else:
            audio_prompt_path = resolve_voice_path(voice_name, language_code)
            if not audio_prompt_path:
                yield 0, None, f"❌ Error: Voice '{voice_name}' not found for {SUPPORTED_LANGUAGES.get(language_code)}."
                return
            yield 10, None, f"Loading voice: {voice_name}..."
        
        # Load model via manager (handles unloading others)
        yield 20, None, "Loading Multilingual TTS model..."
        model = model_manager.get_mtl_model()
        if model is None:
             yield 0, None, "❌ Error: Failed to load Multilingual model."
             return
        
        # Set seed if specified
        if seed_num != 0:
            set_seed(int(seed_num))
            yield 30, None, f"Seed set to {seed_num}"
        
        # Chunk text
        text_chunks = smart_chunk_text(text)
        total_chunks = len(text_chunks)
        generated_wavs = []
        
        # Estimate time
        estimated_time = estimate_generation_time(len(text))
        lang_name = SUPPORTED_LANGUAGES.get(language_code, language_code)
        yield 40, None, f"Generating speech in {lang_name}...\nChunks: {total_chunks}\nEstimated time: {format_time(estimated_time)}"
        
        # Generate audio for each chunk
        for i, chunk in enumerate(text_chunks):
            progress = 40 + int((i / total_chunks) * 50)
            yield progress, None, f"Generating chunk {i+1}/{total_chunks}..."
            
            chunk_wav = model.generate(
                chunk,
                language_id=language_code,
                audio_prompt_path=audio_prompt_path,
                exaggeration=exaggeration,
                temperature=temperature,
                cfg_weight=cfgw,
            )
            generated_wavs.append(chunk_wav)
            
        if not generated_wavs:
             yield 0, None, "❌ Error: No audio generated."
             return
        
        yield 90, None, "Finalizing audio..."
        
        # Concatenate audio chunks
        if len(generated_wavs) > 1:
            full_wav = torch.cat(generated_wavs, dim=-1)
        else:
            full_wav = generated_wavs[0]
        
        # Calculate actual time taken
        total_time = time.time() - start_time
        final_status = f"✅ Generation complete!\nLanguage: {lang_name}\nTime taken: {format_time(total_time)}\nText length: {len(text)} chars\nChunks: {total_chunks}"
        
        yield 100, (model.sr, full_wav.squeeze(0).numpy()), final_status
        
    except Exception as e:
        error_status = f"❌ Error generating speech: {str(e)}"
        yield 0, None, error_status


def convert_voice(input_audio, target_voice_name):
    """Convert voice with progress tracking."""
    try:
        start_time = time.time()
        
        # Input validations
        if not input_audio:
            yield 0, None, "❌ Error: No input audio provided."
            return
        
        yield 20, None, "Loading input audio..."
        
        # Remove gender symbols if present
        clean_name = target_voice_name.replace(" ♂️", "").replace(" ♀️", "")
        
        if not clean_name or clean_name == "None":
            target_voice_path = None
            yield 40, None, "⚠️ No target voice selected - using default..."
        else:
            # Try to find the voice with different gender suffix combinations
            from .voice_manager import VOICES
            possible_names = [
                clean_name,
                f"{clean_name}_male",
                f"{clean_name}_female"
            ]
            
            target_voice_path = None
            for name in possible_names:
                if name in VOICES["samples"]:
                    target_voice_path = VOICES["samples"][name]
                    break
            
            if not target_voice_path:
                yield 0, None, f"❌ Error: Target voice '{target_voice_name}' not found."
                return
            yield 40, None, f"Using target voice: {target_voice_name}..."
        
        # Load model via manager (handles unloading others)
        yield 60, None, "Loading Voice Conversion model..."
        model = model_manager.get_vc_model()
        if model is None:
             yield 0, None, "❌ Error: Failed to load VC model."
             return
        
        yield 70, None, "Converting voice..."
        
        # Convert voice
        wav = model.generate(input_audio, target_voice_path=target_voice_path)
        
        yield 95, None, "Finalizing audio..."
        
        # Calculate actual time taken
        total_time = time.time() - start_time
        final_status = f"✅ Conversion complete!\nTime taken: {format_time(total_time)}"
        
        yield 100, (model.sr, wav.squeeze(0).numpy()), final_status
        
    except Exception as e:
        error_status = f"❌ Error converting voice: {str(e)}"
        yield 0, None, error_status


def generate_turbo_speech(text, voice_name):
    """Generate speech using Turbo model with progress tracking and paralinguistic tag support."""
    try:
        start_time = time.time()
        
        # Input validations
        if not text or not text.strip():
            yield 0, None, "❌ Error: Input text cannot be empty."
            return
        
        if len(text) > 250:
            print(f"ℹ️ Text length: {len(text)} chars - Using smart chunking")
        
        if not voice_name or voice_name == "None":
            yield 0, None, "❌ Error: Please select a voice for Turbo TTS. A reference clip is required."
            return
        else:
            audio_prompt_path = resolve_voice_path(voice_name, "en")
            if not audio_prompt_path:
                yield 0, None, f"❌ Error: Voice '{voice_name}' not found."
                return
            yield 10, None, f"Loading voice: {voice_name}..."
        
        # Load model via manager (handles unloading others)
        yield 20, None, "Loading Turbo TTS model..."
        model = model_manager.get_turbo_model()
        if model is None:
             yield 0, None, "❌ Error: Failed to load Turbo model."
             return
        
        # Chunk text
        text_chunks = smart_chunk_text(text)
        total_chunks = len(text_chunks)
        generated_wavs = []
        
        # Estimate time (Turbo is faster, so reduce estimate)
        estimated_time = estimate_generation_time(len(text)) * 0.3  # Turbo is ~3x faster
        yield 40, None, f"Generating speech with Turbo (English)...\nChunks: {total_chunks}\nEstimated time: {format_time(estimated_time)}\n💡 Tip: Use tags like [chuckle], [laugh], [sigh] for realism!"
        
        # Generate audio for each chunk
        for i, chunk in enumerate(text_chunks):
            progress = 40 + int((i / total_chunks) * 50)
            yield progress, None, f"Generating chunk {i+1}/{total_chunks}..."
            
            chunk_wav = model.generate(
                chunk,
                audio_prompt_path=audio_prompt_path
            )
            generated_wavs.append(chunk_wav)
        
        if not generated_wavs:
             yield 0, None, "❌ Error: No audio generated."
             return

        yield 90, None, "Finalizing audio..."
        
        # Concatenate audio chunks
        if len(generated_wavs) > 1:
            full_wav = torch.cat(generated_wavs, dim=-1)
        else:
            full_wav = generated_wavs[0]
        
        # Calculate actual time taken
        total_time = time.time() - start_time
        final_status = f"✅ Generation complete!\nTime taken: {format_time(total_time)}\nText length: {len(text)} chars\nChunks: {total_chunks}\n⚡ Generated with Turbo (350M params)"
        
        yield 100, (model.sr, full_wav.squeeze(0).numpy()), final_status
        
    except Exception as e:
        error_status = f"❌ Error generating speech: {str(e)}"
        yield 0, None, error_status



def _extract_script_lines(script_text, script_file):
    """Turn a pasted textbox and/or uploaded .txt/.csv/.xlsx into a flat list
    of non-empty lines, in that order. An uploaded file takes priority over
    the textbox. Each line/row is treated as ONE spoken chunk — nothing here
    re-chunks it, so the pause you set lands exactly where the script was
    split, instead of Chatterbox's own sentence-guessing."""
    if script_file:
        path = script_file if isinstance(script_file, str) else getattr(script_file, "name", None)
        if not path or not os.path.exists(path):
            return []
        ext = os.path.splitext(path)[1].lower()
        if ext in (".xlsx", ".xlsm"):
            import openpyxl
            wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
            ws = wb.active
            skip_headers = {"text", "line", "script", "kịch bản", "dòng", "câu", "content"}
            lines = []
            for row in ws.iter_rows(values_only=True):
                cell = row[0] if row else None
                if cell is None:
                    continue
                text = str(cell).strip()
                if text and text.lower() not in skip_headers:
                    lines.append(text)
            return lines
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return [ln.strip() for ln in f if ln.strip()]

    if script_text and script_text.strip():
        return [ln.strip() for ln in script_text.splitlines() if ln.strip()]

    return []




_SENT_END = re.compile(r'(?<=[.!?。！？।؟])\s+')
_SOFT_BREAK = re.compile(r'[,;，、；،]\s*')


def _split_block_by_chars(block, max_chars):
    """Split ONE paragraph/line into <= max_chars pieces: prefer sentence
    boundaries (. ! ?), fall back to commas/semicolons only if a single
    sentence itself exceeds the limit, and never break mid-word if a natural
    boundary exists. Mirrors the 'Script Splitter' Gemini tool's rule set."""
    block = block.strip()
    if not block:
        return []
    if len(block) <= max_chars:
        return [block]

    sentences = [s for s in _SENT_END.split(block) if s.strip()]
    pieces = []
    current = ""
    for sent in sentences:
        candidate = f"{current} {sent}".strip() if current else sent
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            pieces.append(current)
            current = ""
        if len(sent) <= max_chars:
            current = sent
            continue
        # A single sentence longer than max_chars -> split on , ; as fallback
        for part in _SOFT_BREAK.split(sent):
            part = part.strip()
            if not part:
                continue
            candidate = f"{current} {part}".strip() if current else part
            if len(candidate) <= max_chars:
                current = candidate
            else:
                if current:
                    pieces.append(current)
                # last resort: the fragment itself is still too long
                current = part[:max_chars] if len(part) > max_chars else part
    if current:
        pieces.append(current)
    return pieces


def split_script(full_text, max_chars=600):
    """Split a full script into TTS-ready segments. Existing newlines are
    treated as the author's own hard breaks and are never merged across;
    any single line still longer than max_chars gets auto-split at
    sentence/comma boundaries, like the Gemini 'Script Splitter' tool."""
    segments = []
    for block in (full_text or "").splitlines():
        segments.extend(_split_block_by_chars(block, max_chars))
    return segments


def generate_script_to_voice(full_script, script_file, voice_name, pause_ms, max_chars, apply_mastering):
    """Full pipeline: paste a raw script -> auto-split into segments ->
    Turbo-generate each segment -> merge with a silence gap between segments
    -> (optionally) master the merged file with the real Audacity engine
    (Compressor -> Normalize -> Filter Curve EQ, per 'Edit voice.docx')."""
    try:
        start_time = time.time()

        if script_file:
            lines = _extract_script_lines(None, script_file)
            full_script = "\n".join(lines)

        segments = split_script(full_script, max_chars=int(max_chars or 600))
        if not segments:
            yield 0, None, "❌ Error: No text found. Paste a script or upload a .txt/.csv/.xlsx file."
            return

        if not voice_name or voice_name == "None":
            yield 0, None, "❌ Error: Please select a voice."
            return

        audio_prompt_path = resolve_voice_path(voice_name, "en")
        if not audio_prompt_path:
            yield 0, None, f"❌ Error: Voice '{voice_name}' not found."
            return

        yield 5, None, f"Loading Turbo model... ({len(segments)} segments after auto-split)"
        model = model_manager.get_turbo_model()
        if model is None:
            yield 0, None, "❌ Error: Failed to load Turbo model."
            return

        pause_sec = max(0, pause_ms) / 1000.0
        silence = torch.zeros(1, int(model.sr * pause_sec))

        total = len(segments)
        pieces = []
        for i, seg in enumerate(segments):
            progress = 5 + int((i / total) * 65)
            preview = seg if len(seg) <= 60 else seg[:57] + "..."
            yield progress, None, f"Segment {i + 1}/{total} ({len(seg)} chars): {preview}"
            wav = model.generate(seg, audio_prompt_path=audio_prompt_path)
            pieces.append(wav)
            if i < total - 1:
                pieces.append(silence)

        yield 72, None, "Merging segments..."
        full_wav = torch.cat(pieces, dim=-1)
        sr = model.sr

        if not apply_mastering:
            total_time = time.time() - start_time
            status = f"✅ Done (mastering off)!\n{total} segments | {format_time(total_time)}"
            yield 100, (sr, full_wav.squeeze(0).numpy()), status
            return

        yield 78, None, "Mastering (Compressor → Normalize → EQ)..."
        from . import audio_mastering

        try:
            mastered_wav = audio_mastering.apply_master_chain(full_wav.squeeze(0).numpy(), sr)
        except Exception as e:
            total_time = time.time() - start_time
            status = (
                f"⚠️ Mastering failed — returning the UN-mastered voice instead.\n"
                f"{total} segments | {format_time(total_time)}\n\n{e}"
            )
            yield 100, (sr, full_wav.squeeze(0).numpy()), status
            return

        total_time = time.time() - start_time
        status = (
            f"✅ Generation + mastering complete!\n"
            f"{total} segments | {format_time(total_time)}\n"
            f"Chain: Compressor(-15dB, 2:1) → Normalize(-1dB) → Filter Curve EQ"
        )
        yield 100, (sr, mastered_wav), status

    except Exception as e:
        yield 0, None, f"❌ Error: {str(e)}"
