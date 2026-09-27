"""The physical-input kill switch: any real keyboard or mouse input stops the agent's pad (fit review, L4).

A separate SENTINEL process listens to raw input with RIDEV_INPUTSINK, so it hears the devices while the game has focus,
and it keeps working if the executor hangs (a hung executor would have a hung kill switch). It reports, one line per
message on stdout:
  READY {...}      raw-input registration succeeded (keyboard and mouse); nothing is reported before it
  HB <t>           heartbeat, every HEARTBEAT_S
  EV <t>           a control-affecting packet from a real device (rate-limited to one line per EVENT_EVERY_S)
  TRIP {...}       the first such packet since the last arm (latched)
  ARMED            reply to REARM: the latch is cleared and a trip now also starts the kill timer
and reads, on stdin: REARM (clear the latch and arm), ACK (the executor saw the trip and is stopping), and TEST_TRIP
(tests only: a trip as if a device had sent one; it can only stop more).
Armed, a trip that the executor does not ACK within TRIP_KILL_S terminates the executor's process, which unplugs its
virtual pad (ViGEm removes a target when its client closes). The sentinel exits when the executor does.

Control-affecting is the importer's definition (agent/human_demos.py _control_affecting): every key packet; a mouse
packet with motion, button or wheel flags, or absolute coordinates. Packets whose device handle is 0 are injected
(SendInput) and never trip: the virtual pad is not a keyboard or mouse at all.

The executor side is PhysicalInput: start() waits for READY, check() returns None or the reason to stop (sentinel not
running, heartbeat stale, tripped while armed), pre_run() is the positive test before any pad opens: a physical touch
must trip the same check() within its timeout, then the hands must be off for QUIET_S, then it arms.

    python -m agent.physical_input --sentinel --parent PID      (started by PhysicalInput; Windows only)
"""
import argparse
import json
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HEARTBEAT_S = 0.1
HEARTBEAT_STALE_S = 0.5          # check() fails when the last heartbeat is older than this
EVENT_EVERY_S = 0.05
TRIP_KILL_S = 1.0                # armed: an un-ACKed trip terminates the executor after this long
READY_TIMEOUT_S = 5.0
PRE_RUN_TOUCH_S = 30.0           # the operator's touch must arrive within this
QUIET_S = 3.0                    # then no physical input for this long before arming
QUIET_TIMEOUT_S = 90.0
TRIPPED = "physical keyboard or mouse input (kill switch)"


def control_affecting(kind, *, flags=0, button_flags=0, dx=0, dy=0):
    """The importer's rule on one raw packet: kind "key" or "mouse"; mouse `flags` bit 0 is MOUSE_MOVE_ABSOLUTE."""
    if kind == "key":
        return True
    if kind != "mouse":
        return False
    return bool(dx or dy or button_flags or (flags & 1))


def trips(kind, handle, **fields):
    """A packet trips the switch when it is control-affecting and comes from a real device (handle != 0)."""
    return bool(handle) and control_affecting(kind, **fields)


# --- the executor's side ------------------------------------------------------------------------------------------

class Refused(Exception):
    pass


class PhysicalInput:
    """The sentinel's client. `command` is injectable for tests (any process speaking the line protocol)."""

    def __init__(self, command=None, clock=time.monotonic):
        self.command = command or [sys.executable, "-u", "-m", "agent.physical_input", "--sentinel",
                                   "--parent", str(__import__("os").getpid())]
        self.clock = clock
        self.proc = None
        self.ready = self.armed = self.tripped = self.acked = False
        self.info, self.trip = None, None
        self.last_hb = self.last_event = None
        self._armed_reply = threading.Event()
        self._lock = threading.Lock()

    def start(self, timeout=READY_TIMEOUT_S):
        kw = {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)} if sys.platform == "win32" else {}
        self.proc = subprocess.Popen(self.command, cwd=str(ROOT), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.DEVNULL, text=True, bufsize=1, **kw)
        threading.Thread(target=self._read, daemon=True).start()
        end = self.clock() + timeout
        while self.clock() < end:
            if self.ready:
                return self.info
            if self.proc.poll() is not None:
                break
            time.sleep(0.02)
        self.close()
        raise Refused("the physical-input sentinel did not register raw input (no READY): no pad opened")

    def _read(self):
        for line in self.proc.stdout:
            word, _, rest = line.strip().partition(" ")
            now = self.clock()
            with self._lock:
                if word == "READY":
                    self.info, self.ready, self.last_hb = json.loads(rest or "{}"), True, now
                elif word == "HB":
                    self.last_hb = now
                elif word == "EV":
                    self.last_event = now
                elif word == "TRIP":
                    self.tripped, self.trip, self.last_event = True, json.loads(rest or "{}"), now
                elif word == "ARMED":
                    self._armed_reply.set()

    def _send(self, word):
        try:
            self.proc.stdin.write(word + "\n")
            self.proc.stdin.flush()
        except (OSError, ValueError):
            pass

    def check(self):
        """None while input may continue, else the reason to release and stop. Cheap: called before every write."""
        with self._lock:
            if self.proc is None or self.proc.poll() is not None or not self.ready:
                return "the physical-input sentinel is not running"
            if self.last_hb is None or self.clock() - self.last_hb > HEARTBEAT_STALE_S:
                return "the physical-input sentinel's heartbeat is stale"
            if self.tripped:
                if self.armed and not self.acked:
                    self.acked = True
                    self._send("ACK")
                return TRIPPED
        return None

    def rearm(self, timeout=2.0):
        with self._lock:
            self._armed_reply.clear()
            self.tripped, self.trip, self.acked = False, None, False
        self._send("REARM")
        if not self._armed_reply.wait(timeout):
            raise Refused("the physical-input sentinel did not confirm REARM")
        with self._lock:
            self.armed = True

    def pre_run(self, out=print, sleep=time.sleep, touch_s=PRE_RUN_TOUCH_S, quiet_s=QUIET_S,
                quiet_timeout_s=QUIET_TIMEOUT_S, ready_to_arm=lambda: True):
        """The positive test: a dry run of check() that only a physical touch can stop, then hands off, then arm.

        Nothing is sent. Raises Refused unless the touch trips check() within `touch_s` and, afterwards, `quiet_s`
        pass with no physical input while `ready_to_arm()` holds (the game in front), within `quiet_timeout_s`."""
        if self.check() is not None:
            raise Refused(f"before the touch test: {self.check()}")
        out(f"KILL-SWITCH TEST: touch the mouse or a key now (within {touch_s:.0f} s). Nothing is sent.")
        end = self.clock() + touch_s
        reason = None
        while self.clock() < end:
            reason = self.check()
            if reason is not None:
                break
            sleep(0.05)
        if reason != TRIPPED:
            raise Refused(f"the touch test failed: {reason or 'no physical input seen'}; no pad opened")
        out(f"Touch seen ({self.trip}). Bring the game to the front and let go: arming after {quiet_s:.0f} s of "
            "no keyboard or mouse input.")
        end = self.clock() + quiet_timeout_s
        while self.clock() < end:
            with self._lock:
                last = self.last_event
            if self.clock() - (last or 0.0) >= quiet_s and ready_to_arm():
                self.rearm()
                if self.check() is not None:
                    raise Refused(f"after arming: {self.check()}")
                out("Armed: any keyboard or mouse input now stops the run.")
                return
            sleep(0.05)
        raise Refused("hands never left the keyboard and mouse (or the game was not in front); no pad opened")

    def close(self):
        if self.proc is not None and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(2)
            except subprocess.TimeoutExpired:
                self.proc.kill()


# --- the sentinel (Windows) ---------------------------------------------------------------------------------------

def sentinel(parent_pid):  # pragma: no cover - needs a Windows desktop session
    import ctypes
    from ctypes import wintypes as w

    user32, kernel32 = ctypes.WinDLL("user32", use_last_error=True), ctypes.WinDLL("kernel32", use_last_error=True)
    WM_INPUT, WM_TIMER, RID_INPUT, RIDEV_INPUTSINK = 0x00FF, 0x0113, 0x10000003, 0x00000100
    RIM_TYPEMOUSE, RIM_TYPEKEYBOARD = 0, 1
    HWND_MESSAGE = w.HWND(-3)
    SYNCHRONIZE, PROCESS_TERMINATE = 0x00100000, 0x0001
    LRESULT = ctypes.c_ssize_t
    WNDPROC = ctypes.WINFUNCTYPE(LRESULT, w.HWND, w.UINT, w.WPARAM, w.LPARAM)

    class RAWINPUTDEVICE(ctypes.Structure):
        _fields_ = [("usUsagePage", w.USHORT), ("usUsage", w.USHORT), ("dwFlags", w.DWORD), ("hwndTarget", w.HWND)]

    class RAWINPUTHEADER(ctypes.Structure):
        _fields_ = [("dwType", w.DWORD), ("dwSize", w.DWORD), ("hDevice", w.HANDLE), ("wParam", w.WPARAM)]

    class RAWMOUSE(ctypes.Structure):
        # usFlags, then a ULONG-aligned union {ulButtons; {usButtonFlags, usButtonData}}
        _fields_ = [("usFlags", w.USHORT), ("_pad", w.USHORT), ("usButtonFlags", w.USHORT),
                    ("usButtonData", w.USHORT), ("ulRawButtons", w.ULONG), ("lLastX", w.LONG), ("lLastY", w.LONG),
                    ("ulExtraInformation", w.ULONG)]

    class RAWKEYBOARD(ctypes.Structure):
        _fields_ = [("MakeCode", w.USHORT), ("Flags", w.USHORT), ("Reserved", w.USHORT), ("VKey", w.USHORT),
                    ("Message", w.UINT), ("ExtraInformation", w.ULONG)]

    class WNDCLASS(ctypes.Structure):
        _fields_ = [("style", w.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
                    ("cbWndExtra", ctypes.c_int), ("hInstance", w.HINSTANCE), ("hIcon", w.HICON),
                    ("hCursor", w.HANDLE), ("hbrBackground", w.HBRUSH), ("lpszMenuName", w.LPCWSTR),
                    ("lpszClassName", w.LPCWSTR)]

    user32.DefWindowProcW.restype = LRESULT
    user32.DefWindowProcW.argtypes = (w.HWND, w.UINT, w.WPARAM, w.LPARAM)
    user32.GetRawInputData.argtypes = (w.HANDLE, w.UINT, ctypes.c_void_p, ctypes.POINTER(w.UINT), w.UINT)
    user32.CreateWindowExW.restype = w.HWND
    user32.CreateWindowExW.argtypes = (w.DWORD, w.LPCWSTR, w.LPCWSTR, w.DWORD, ctypes.c_int, ctypes.c_int,
                                       ctypes.c_int, ctypes.c_int, w.HWND, w.HMENU, w.HINSTANCE, w.LPVOID)
    kernel32.OpenProcess.restype = w.HANDLE

    parent = kernel32.OpenProcess(SYNCHRONIZE | PROCESS_TERMINATE, False, int(parent_pid))
    if not parent:
        sys.exit(2)
    state = {"armed": False, "tripped": False, "trip_t": None, "acked": False, "last_ev": 0.0}
    lock = threading.Lock()
    hdr_size = ctypes.sizeof(RAWINPUTHEADER)
    buf = ctypes.create_string_buffer(256)

    def say(line):
        sys.stdout.write(line + "\n")
        sys.stdout.flush()

    def on_input(lparam):
        size = w.UINT(ctypes.sizeof(buf))
        if user32.GetRawInputData(lparam, RID_INPUT, buf, ctypes.byref(size), hdr_size) in (0, 0xFFFFFFFF):
            return
        hdr = RAWINPUTHEADER.from_buffer_copy(buf, 0)
        handle = hdr.hDevice or 0
        if hdr.dwType == RIM_TYPEMOUSE:
            m = RAWMOUSE.from_buffer_copy(buf, hdr_size)
            kind, fields = "mouse", {"flags": m.usFlags, "button_flags": m.usButtonFlags, "dx": m.lLastX,
                                     "dy": m.lLastY}
        elif hdr.dwType == RIM_TYPEKEYBOARD:
            k = RAWKEYBOARD.from_buffer_copy(buf, hdr_size)
            kind, fields, detail_key = "key", {}, {"vkey": k.VKey, "flags": k.Flags}
        else:
            return
        if not trips(kind, handle, **fields):
            return
        now = time.monotonic()
        with lock:
            if now - state["last_ev"] >= EVENT_EVERY_S:
                state["last_ev"] = now
                say(f"EV {now:.3f}")
            if not state["tripped"]:
                state.update(tripped=True, trip_t=now, acked=False)
                detail = {"kind": kind, "device": int(handle), **(fields if kind == "mouse" else detail_key)}
                say("TRIP " + json.dumps(detail))

    def on_timer():
        say(f"HB {time.monotonic():.3f}")
        if kernel32.WaitForSingleObject(parent, 0) == 0:          # the executor has exited
            user32.PostQuitMessage(0)
            return
        with lock:
            late = (state["armed"] and state["tripped"] and not state["acked"]
                    and time.monotonic() - state["trip_t"] > TRIP_KILL_S)
        if late:                                                   # a hung executor: unplug its pad by ending it
            kernel32.TerminateProcess(parent, 3)
            say("KILLED executor: trip not acknowledged")

    @WNDPROC
    def proc(hwnd, msg, wparam, lparam):
        if msg == WM_INPUT:
            on_input(lparam)
        elif msg == WM_TIMER:
            on_timer()
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def stdin_loop():
        for line in sys.stdin:
            word = line.strip()
            with lock:
                if word == "REARM":
                    state.update(armed=True, tripped=False, trip_t=None, acked=False)
                    say("ARMED")
                elif word == "ACK":
                    state["acked"] = True
                elif word == "TEST_TRIP":                          # tests only: a trip as if from a device (it can
                    now = time.monotonic()                         # only stop more, never allow input)
                    state["last_ev"] = now
                    say(f"EV {now:.3f}")
                    if not state["tripped"]:
                        state.update(tripped=True, trip_t=now, acked=False)
                        say("TRIP " + json.dumps({"kind": "test", "device": None}))

    hinst = kernel32.GetModuleHandleW(None)
    wc = WNDCLASS(lpfnWndProc=proc, hInstance=hinst, lpszClassName="RivalsPhysicalInputSentinel")
    if not user32.RegisterClassW(ctypes.byref(wc)):
        sys.exit(2)
    hwnd = user32.CreateWindowExW(0, wc.lpszClassName, "sentinel", 0, 0, 0, 0, 0, HWND_MESSAGE, None, hinst, None)
    if not hwnd:
        sys.exit(2)
    devices = (RAWINPUTDEVICE * 2)(RAWINPUTDEVICE(1, 2, RIDEV_INPUTSINK, hwnd), RAWINPUTDEVICE(1, 6, RIDEV_INPUTSINK, hwnd))
    if not user32.RegisterRawInputDevices(devices, 2, ctypes.sizeof(RAWINPUTDEVICE)):
        sys.exit(2)                                                 # no READY: the executor refuses to start
    user32.SetTimer(hwnd, 1, int(HEARTBEAT_S * 1000), None)
    threading.Thread(target=stdin_loop, daemon=True).start()
    say("READY " + json.dumps({"devices": ["mouse", "keyboard"], "flags": "RIDEV_INPUTSINK", "pid": __import__("os").getpid()}))
    msg = w.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sentinel", action="store_true", required=True)
    ap.add_argument("--parent", type=int, required=True)
    a = ap.parse_args(argv)
    if sys.platform != "win32":
        sys.exit(2)
    sentinel(a.parent)


if __name__ == "__main__":
    main()
