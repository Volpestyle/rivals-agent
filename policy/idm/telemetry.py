"""Best-effort observability; scientific and checkpoint writes never use this."""


def emit(callback, *args, **kwargs):
    if callback is None:
        return
    try:
        callback(*args, **kwargs)
    except Exception as exc:
        try:
            print("IDM telemetry unavailable: " + repr(exc), flush=True)
        except Exception:
            pass  # A closed log pipe must not stop healthy compute either.
