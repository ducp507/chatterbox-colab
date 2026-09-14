"""
Headless Audacity automation via mod-script-pipe.

Runs Anh Tấn's exact mastering chain (documented step-by-step, with screenshots,
in "Edit voice.docx") using the REAL Audacity engine instead of a Python
re-implementation — same effects, same parameters, same DSP code path he uses
by hand. Linux/Colab only (installs Audacity + Xvfb via apt on first use,
cached for the rest of the Colab session).

The 3-effect chain below is transcribed 1:1 from "Edit voice.docx" steps 4-6:
  4. Compressor   — Threshold -15dB, Ratio 2:1, Knee 5dB, Attack 15ms,
                     Release 120ms, Lookahead 1ms, Make-up gain 0dB
  5. Normalize    — peak amplitude to -1.0 dB
  6. Filter Curve EQ — exact curve from EQ.txt (f0..f6 / v0..v6 below)

Protocol reference: Audacity's own scripting pipe client
(scripting/piped-work/pipeclient.py in the Audacity repo) — open both named
pipes once, write "<command>\\r\\n\\n", read lines back until a line equal to
"BatchCommand finished: OK" or "BatchCommand finished: Failed!".
"""
import glob
import os
import select
import shutil
import subprocess
import time

_UID = os.getuid()
TO_PIPE = f"/tmp/audacity_script_pipe.to.{_UID}"
FROM_PIPE = f"/tmp/audacity_script_pipe.from.{_UID}"
AUDACITY_CFG_DIR = os.path.expanduser("~/.audacity-data")

_state = {"proc": None, "to_f": None, "from_f": None}

# Verbatim from "Edit voice.docx" steps 4-6. The FilterCurve line is EQ.txt,
# unchanged, since that file is already valid Audacity macro syntax.
MASTER_CHAIN = [
    (
        "Compressor",
        'Compressor: Threshold="-15" NoiseFloor="-40" Ratio="2" KneeWidth="5" '
        'AttackTime="0.015" ReleaseTime="0.12" Lookahead="0.001" MakeupGain="0" Normalize="0"',
    ),
    (
        "Normalize",
        'Normalize: PeakLevel="-1" ApplyGain="1" RemoveDcOffset="0" StereoIndependent="0"',
    ),
    (
        "FilterCurve EQ",
        'FilterCurve:f0="20" f1="80" f2="120" f3="200" f4="3000" f5="8000" f6="20000" '
        'FilterLength="8191" InterpolateLin="0" InterpolationMethod="B-spline" '
        'v0="0" v1="-6" v2="1" v3="-2" v4="1.5" v5="2" v6="0"',
    ),
]


def _ensure_installed():
    if shutil.which("audacity"):
        return
    subprocess.run(
        "apt-get -qq update && apt-get install -y -qq audacity xvfb",
        shell=True, check=True, capture_output=True, text=True,
    )


def _enable_scripting():
    """mod-script-pipe must be enabled before Audacity's first UI-less launch,
    otherwise it would need a manual click in Preferences > Modules that
    nothing here can perform headlessly."""
    os.makedirs(AUDACITY_CFG_DIR, exist_ok=True)
    cfg_path = os.path.join(AUDACITY_CFG_DIR, "audacity.cfg")
    text = open(cfg_path, encoding="utf-8").read() if os.path.exists(cfg_path) else ""
    if "mod-script-pipe=Enabled" not in text:
        if "[Module]" in text:
            text = text.replace("[Module]", "[Module]\nmod-script-pipe=Enabled", 1)
        else:
            text += "\n[Module]\nmod-script-pipe=Enabled\n"
        with open(cfg_path, "w", encoding="utf-8") as f:
            f.write(text)


def _locate_pipes(timeout=40):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if os.path.exists(TO_PIPE) and os.path.exists(FROM_PIPE):
            return TO_PIPE, FROM_PIPE
        to_g = sorted(glob.glob("/tmp/audacity_script_pipe.to.*"))
        from_g = sorted(glob.glob("/tmp/audacity_script_pipe.from.*"))
        if to_g and from_g:
            return to_g[0], from_g[0]
        time.sleep(0.5)
    return None, None


def _ensure_running():
    if _state["to_f"] and _state["proc"] and _state["proc"].poll() is None:
        return
    _ensure_installed()
    _enable_scripting()
    _state["proc"] = subprocess.Popen(
        ["xvfb-run", "-a", "--server-args=-screen 0 1280x1024x24", "audacity"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    to_path, from_path = _locate_pipes()
    if not to_path:
        raise RuntimeError(
            "Audacity's scripting pipe never appeared within 40s. Most likely "
            "mod-script-pipe still needs enabling by hand once inside Audacity's "
            "own GUI (Edit > Preferences > Modules) — nothing here can click that "
            "headlessly. Screenshot this error and send it over."
        )
    time.sleep(1.0)  # let Audacity finish settling before the first command
    _state["to_f"] = open(to_path, "w")
    _state["from_f"] = open(from_path, "r")


def _send(command, timeout=90):
    _state["to_f"].write(command + "\r\n\n")
    _state["to_f"].flush()
    reply_lines = []
    deadline = time.time() + timeout
    f = _state["from_f"]
    while time.time() < deadline:
        ready, _, _ = select.select([f], [], [], 1.0)
        if not ready:
            continue
        line = f.readline()
        if not line:
            continue
        reply_lines.append(line)
        if line.strip() in ("BatchCommand finished: OK", "BatchCommand finished: Failed!"):
            break
    return "".join(reply_lines)


def apply_master_chain(in_wav_path, out_wav_path):
    """Run the real Audacity Compressor -> Normalize -> Filter Curve EQ chain
    (Edit voice.docx steps 4-6) on in_wav_path via mod-script-pipe, writing
    the result to out_wav_path.

    Raises RuntimeError with Audacity's own response text if any step is
    rejected — that text names the exact bad parameter, which is the fastest
    way to patch MASTER_CHAIN if a macro key name here doesn't match this
    Audacity version.
    """
    _ensure_running()
    log = []

    def run(cmd, label):
        r = _send(cmd)
        log.append(f"{label}: {r.strip()}")
        if "Failed" in r:
            raise RuntimeError(
                "Audacity rejected this step:\n" + cmd + "\n\nResponse:\n" + r +
                "\n\nFull log so far:\n" + "\n".join(log)
            )
        return r

    run(f'Import2: Filename="{in_wav_path}"', "Import2")
    run("SelectAll", "SelectAll")
    for label, cmd in MASTER_CHAIN:
        run(cmd, label)
    run(f'Export2: Filename="{out_wav_path}" NumChannels="1"', "Export2")

    if not os.path.exists(out_wav_path):
        raise RuntimeError(
            "Export2 reported OK but the output file wasn't created.\nFull log:\n"
            + "\n".join(log)
        )

    return log
