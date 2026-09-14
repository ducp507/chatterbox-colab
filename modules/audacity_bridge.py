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
DISPLAY_NUM = ":97"  # fixed, so xdotool always knows where to send keys

_state = {"proc": None, "to_f": None, "from_f": None, "xvfb": None, "wm": None}

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


LAUNCH_LOG = "/tmp/audacity_launch.log"


def _ensure_installed():
    if (shutil.which("audacity") and shutil.which("xdotool")
            and shutil.which("import") and shutil.which("fluxbox")):
        return
    subprocess.run(
        "apt-get -qq update && apt-get install -y -qq audacity xvfb xdotool imagemagick fluxbox",
        shell=True, check=True, capture_output=True, text=True,
    )


def _dump_scripting_config():
    """After Audacity has run at least once, it writes its OWN real config
    to disk with whatever key names *this* version actually uses. Read that
    back instead of guessing further — any line mentioning 'script' (case-
    insensitive) is exactly what needs to be flipped to enable the pipe."""
    hits = []
    for cfg_dir in (AUDACITY_CFG_DIR, os.path.expanduser("~/.config/audacity")):
        cfg_path = os.path.join(cfg_dir, "audacity.cfg")
        if not os.path.exists(cfg_path):
            continue
        try:
            for line in open(cfg_path, encoding="utf-8", errors="ignore"):
                if "script" in line.lower():
                    hits.append(f"{cfg_path}: {line.strip()}")
        except Exception as e:
            hits.append(f"{cfg_path}: (couldn't read: {e})")
    return "\n".join(hits) if hits else "(no 'script' line found in either audacity.cfg — file may not exist yet, or this version doesn't call it that)"


def _pkg_version():
    try:
        out = subprocess.run(
            "dpkg -s audacity 2>/dev/null | grep -i version",
            shell=True, capture_output=True, text=True,
        ).stdout.strip()
        return out or "(dpkg -s audacity returned nothing)"
    except Exception as e:
        return f"(couldn't check: {e})"


def _enable_scripting():
    """mod-script-pipe must be enabled before Audacity's first UI-less launch,
    otherwise it would need a manual click in Preferences > Modules that
    nothing here can perform headlessly. Written to both plausible config
    locations since the exact path can vary by Audacity/distro version."""
    for cfg_dir in (AUDACITY_CFG_DIR, os.path.expanduser("~/.config/audacity")):
        os.makedirs(cfg_dir, exist_ok=True)
        cfg_path = os.path.join(cfg_dir, "audacity.cfg")
        text = open(cfg_path, encoding="utf-8").read() if os.path.exists(cfg_path) else ""
        if "mod-script-pipe=Enabled" not in text:
            if "[Module]" in text:
                text = text.replace("[Module]", "[Module]\nmod-script-pipe=Enabled", 1)
            else:
                text += "\n[Module]\nmod-script-pipe=Enabled\n"
            with open(cfg_path, "w", encoding="utf-8") as f:
                f.write(text)


def _dismiss_dialogs_for(seconds):
    """Blind-dismiss any first-run popup (e.g. 'enable this module?') by
    activating every window and sending Tab+Return / Space / Return every 2s
    — a standard trick for headless GUI automation when the exact dialog
    can't be inspected from here. Xvfb has no window manager, so a plain
    `key` without `windowactivate` first often never reaches the dialog."""
    if not shutil.which("xdotool"):
        return
    env = {**os.environ, "DISPLAY": DISPLAY_NUM}
    end = time.time() + seconds
    while time.time() < end:
        ids = subprocess.run(
            ["xdotool", "search", "--name", "."],
            env=env, capture_output=True, text=True,
        ).stdout.split()
        for wid in ids:
            for key in ("Return", "space", "Tab Return"):
                subprocess.run(
                    ["xdotool", "windowactivate", "--sync", wid, "key", key],
                    env=env, capture_output=True,
                )
        time.sleep(2)


def _debug_screenshot(path="audacity_debug.png"):
    """Save a screenshot of the virtual display so a stuck/silent dialog can
    actually be seen instead of guessed at. Returns the absolute path, or
    None if the screenshot tool isn't available."""
    if not shutil.which("import"):
        return None
    abspath = os.path.abspath(path)
    try:
        subprocess.run(
            ["import", "-display", DISPLAY_NUM, "-window", "root", abspath],
            capture_output=True, timeout=15,
        )
        return abspath if os.path.exists(abspath) else None
    except Exception:
        return None


def _list_windows():
    if not shutil.which("xdotool"):
        return "(xdotool not available)"
    env = {**os.environ, "DISPLAY": DISPLAY_NUM}
    r = subprocess.run(
        ["xdotool", "search", "--name", ".", "getwindowname"],
        env=env, capture_output=True, text=True,
    )
    return r.stdout.strip() or "(no windows found)"


def _ensure_xvfb():
    lock = f"/tmp/.X{DISPLAY_NUM.lstrip(':')}-lock"
    already_up = os.path.exists(lock) and _state["xvfb"] and _state["xvfb"].poll() is None
    if not already_up:
        _state["xvfb"] = subprocess.Popen(
            ["Xvfb", DISPLAY_NUM, "-screen", "0", "1280x1024x24", "-ac"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        time.sleep(2)

    # A bare Xvfb has NO window manager, which makes `xdotool windowactivate`
    # (and therefore every attempt to click/key through a popup dialog)
    # unreliable -- activation requests have nothing to honor them. Run a
    # minimal WM so dialog-dismissal actually works.
    wm_alive = _state.get("wm") and _state["wm"].poll() is None
    if not wm_alive:
        _state["wm"] = subprocess.Popen(
            ["fluxbox"],
            env={**os.environ, "DISPLAY": DISPLAY_NUM},
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        time.sleep(1.5)


def _locate_pipes(timeout=90):
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


def _reset_profile():
    """Wipe Audacity's own profile/session dirs before every launch.

    A screenshot of a stuck run showed the actual cause of every timeout so
    far: Audacity's "Recover unsaved projects?" modal, left over from a
    PRIOR run that got killed mid-launch (by this bridge's own timeout
    handling) instead of exiting cleanly. That dialog blocks everything —
    no console output, no scripting pipe, indefinitely — until someone
    clicks through it. Since this bridge only ever drives Audacity
    programmatically and never wants "recover my last session" behaviour,
    starting from a clean profile every time removes the dialog's cause
    entirely instead of trying to click past it."""
    import shutil as _shutil
    for d in (
        AUDACITY_CFG_DIR,
        os.path.expanduser("~/.config/audacity"),
        os.path.expanduser("~/.local/share/audacity"),
        os.path.expanduser("~/.cache/audacity"),
    ):
        _shutil.rmtree(d, ignore_errors=True)


def _ensure_running():
    if _state["to_f"] and _state["proc"] and _state["proc"].poll() is None:
        return
    _ensure_installed()
    _reset_profile()
    _enable_scripting()
    _ensure_xvfb()

    log_f = open(LAUNCH_LOG, "w")
    _state["proc"] = subprocess.Popen(
        ["audacity"],
        env={**os.environ, "DISPLAY": DISPLAY_NUM},
        stdout=log_f, stderr=subprocess.STDOUT,
    )
    _dismiss_dialogs_for(20)  # in case a first-run "enable module?" popup appeared
    to_path, from_path = _locate_pipes()
    if not to_path:
        proc_alive = _state["proc"].poll() is None
        log_tail = ""
        try:
            with open(LAUNCH_LOG, encoding="utf-8", errors="ignore") as f:
                log_tail = "".join(f.readlines()[-40:])
        except Exception:
            pass
        windows = _list_windows()
        shot = _debug_screenshot()
        cfg_dump = _dump_scripting_config()
        if not proc_alive:
            _state["proc"].kill()
        raise RuntimeError(
            "Audacity's scripting pipe never appeared within 90s.\n"
            f"Process still running: {proc_alive} | installed version: {_pkg_version()}\n"
            f"Open windows on the virtual display: {windows}\n"
            f"'script' lines in Audacity's own config files:\n{cfg_dump}\n"
            + (f"Screenshot saved to: {shot} — open it in Colab's file browser "
               "(folder icon, left sidebar) and send it over.\n"
               if shot else "Screenshot capture failed too.\n")
            + "\nMost likely mod-script-pipe still needs enabling by hand once inside "
            "Audacity's own GUI (Edit > Preferences > Modules), or this apt version "
            "doesn't ship it. Audacity's own stdout/stderr (last 40 lines):\n\n"
            f"{log_tail or '(empty — nothing was printed)'}"
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
