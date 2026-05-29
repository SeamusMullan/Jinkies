"""Platform-specific visual effects for Jinkies.

On Windows: applies DWM Aero glass blur behind the main window using
ctypes calls into dwmapi.dll and user32.dll. No-ops silently on
Linux/macOS so the rest of the app is unaffected.
"""

from __future__ import annotations

import sys


def apply_aero_glass(hwnd: int) -> None:
    """Enable DWM blur-behind (Aero glass) on *hwnd*.

    On Windows Vista/7 this enables the full Aero glass effect.
    On Windows 8/8.1 (DWM blur was removed) this is a no-op.
    On Windows 10/11 this enables the Acrylic/Mica-style blur via
    the undocumented SetWindowCompositionAttribute API.
    On non-Windows platforms this is a no-op.

    Args:
        hwnd: The native Win32 window handle (obtain via
            ``widget.winId()`` cast to int).
    """
    if sys.platform != "win32":
        return

    import ctypes
    import ctypes.wintypes

    try:
        _apply_dwm_blur(hwnd, ctypes)
    except Exception:
        pass


def apply_window_effects(widget: object) -> None:
    """Apply platform glass effects to a top-level widget.

    Call this after the widget's native handle is available (i.e. after
    ``widget.show()`` has been called at least once).

    Args:
        widget: A QWidget subclass with a ``winId()`` method.
    """
    if sys.platform != "win32":
        return
    try:
        hwnd = int(widget.winId())  # type: ignore[attr-defined]
        apply_aero_glass(hwnd)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _apply_dwm_blur(hwnd: int, ctypes: object) -> None:
    import ctypes as ct
    import ctypes.wintypes as wt

    # ── Try Vista/7 DWM blur-behind ─────────────────────────────────
    class _MARGINS(ct.Structure):
        _fields_ = [
            ("cxLeftWidth", ct.c_int),
            ("cxRightWidth", ct.c_int),
            ("cyTopHeight", ct.c_int),
            ("cyBottomHeight", ct.c_int),
        ]

    class _DWM_BLURBEHIND(ct.Structure):
        _fields_ = [
            ("dwFlags", wt.DWORD),
            ("fEnable", wt.BOOL),
            ("hRgnBlur", wt.HANDLE),
            ("fTransitionOnMaximized", wt.BOOL),
        ]

    try:
        dwmapi = ct.windll.dwmapi  # type: ignore[attr-defined]

        # Extend frame into client area (full window = all -1)
        margins = _MARGINS(-1, -1, -1, -1)
        dwmapi.DwmExtendFrameIntoClientArea(hwnd, ct.byref(margins))

        # Enable blur-behind
        bb = _DWM_BLURBEHIND()
        bb.dwFlags = 0x00000001 | 0x00000002  # DWM_BB_ENABLE | DWM_BB_BLURREGION
        bb.fEnable = True
        bb.hRgnBlur = None
        dwmapi.DwmEnableBlurBehindWindow(hwnd, ct.byref(bb))
    except Exception:
        pass

    # ── Try Win10/11 undocumented accent policy ──────────────────────
    # SetWindowCompositionAttribute with ACCENT_ENABLE_BLURBEHIND (3)
    # or ACCENT_ENABLE_ACRYLICBLURBEHIND (4) on RS4+
    try:
        class _ACCENT_POLICY(ct.Structure):
            _fields_ = [
                ("AccentState", ct.c_int),
                ("AccentFlags", ct.c_int),
                ("GradientColor", ct.c_int),
                ("AnimationId", ct.c_int),
            ]

        class _WINDOWCOMPOSITIONATTRIBDATA(ct.Structure):
            _fields_ = [
                ("Attribute", ct.c_int),
                ("Data", ct.c_void_p),
                ("SizeOfData", ct.c_size_t),
            ]

        accent = _ACCENT_POLICY()
        # 3 = ACCENT_ENABLE_BLURBEHIND, 4 = ACCENT_ENABLE_ACRYLICBLURBEHIND
        accent.AccentState = 3
        accent.GradientColor = 0xC0DCF0C0  # AABBGGRR — light blue tint, 75% opacity

        data = _WINDOWCOMPOSITIONATTRIBDATA()
        data.Attribute = 19  # WCA_ACCENT_POLICY
        data.Data = ct.cast(ct.byref(accent), ct.c_void_p)
        data.SizeOfData = ct.sizeof(accent)

        user32 = ct.windll.user32  # type: ignore[attr-defined]
        user32.SetWindowCompositionAttribute(hwnd, ct.byref(data))
    except Exception:
        pass
