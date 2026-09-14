# chatterbox-colab

Clean, self-rebuilt packaging of **Chatterbox TTS + Turbo** (Resemble AI, MIT).
Only the audited source is here — `app.py`, `modules/`, `src/chatterbox/`, 20 voice
samples. No bundled interpreter, no prebuilt binaries. Model weights are pulled at
runtime straight from Hugging Face (`ResembleAI/chatterbox`, `ResembleAI/chatterbox-turbo`).

## Run on Colab (primary)

1. Open `Chatterbox_TTS_Colab.ipynb` in Google Colab
   (`colab.research.google.com/github/ducp507/chatterbox-colab/blob/main/Chatterbox_TTS_Colab.ipynb`).
2. Runtime → Change runtime type → **GPU**.
3. Runtime → **Run all**. Wait for `Running on public URL: https://xxxx.gradio.live`.

**Per session** (~6–10 min total): pip install (~3–5 min) + Audacity install for the
Script to Voice tab (~1 min, cell 4) + model download (~2–4 min). The notebook and
code persist; the VM's disk does not. To skip the model re-download, enable the
Drive cache cell (step 5 in the notebook).

## Tabs

- **⚡ Turbo TTS / 🎤 TTS Main / 🌍 Multilingual / 🔄 Voice Conversion / 🧬 Clone Voice** — as shipped upstream.
- **🎬 Script to Voice** — paste a full script (not pre-split); it auto-splits into
  segments (sentence-aware, char-limit, like the Gemini "Script Splitter" tool),
  generates each with Turbo, merges with a pause between segments, then masters the
  result through a **real, headless Audacity** instance (`modules/audacity_bridge.py`,
  via `mod-script-pipe`) running the exact Compressor → Normalize → Filter Curve EQ
  chain documented in "Edit voice.docx" — same engine, same parameters, not a
  reimplementation. Toggle mastering off to A/B against the raw voice.

## Run locally on Apple Silicon (secondary)

Needs **~15 GB free disk**. Device auto-detects CUDA → MPS → CPU.

```bash
./run.sh          # first run builds .venv + downloads weights; later runs start in ~20s
```

Opens `http://127.0.0.1:7860` (no public link locally).

## What was changed vs the original Windows package

| File | Change |
|------|--------|
| `modules/config.py` | device detection now `cuda → mps → cpu` (was `cuda → cpu`) |
| `modules/generation_functions.py` | `torch.cuda.manual_seed*` guarded behind `cuda.is_available()` |
| `modules/model_manager.py` | `empty_cache()` per backend; `gc.collect()` always |
| `app.py` | `.launch(share=…)` driven by `GRADIO_SHARE` env (1 on Colab, unset locally) |

Nothing else in `modules/` or `src/` was touched; `src/chatterbox/` already had MPS support upstream.
