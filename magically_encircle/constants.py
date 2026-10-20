"""Application-wide constants and Windows key definitions."""

from __future__ import annotations

APP_NAME = "magicallyEncircle"
APP_DISPLAY_NAME = "magicallyEncircle"
APP_MUTEX = "Local\\magicallyEncircleWin"

# Draw trigger
TRIGGER_ALT_LEFT = "altLeft"
TRIGGER_MIDDLE = "middleButton"

# Multi-stroke mode (Alt + left only)
MULTI_DOUBLE_PRESS = "doublePress"
MULTI_SINGLE_PRESS = "singlePress"

# Close action
CLOSE_WINDOW = "closeWindow"
CLOSE_TAB = "closeTab"
CLOSE_QUIT_APP = "quitApp"

# Recognition thresholds (ported from the macOS app)
SYMBOL_THRESHOLD = 0.72
CUSTOM_THRESHOLD = 0.75
SAMPLE_COUNT = 64
SQUARE_SIZE = 250.0

# Overlay timing
FADE_DURATION = 1.6
FRAME_INTERVAL = 1.0 / 60.0
GUIDE_GROW_DURATION = 0.28
GUIDE_INSET = 20.0

# Drawing thresholds
MIN_GESTURE_LENGTH = 30.0
HOLD_DURATION = 1.0
DOUBLE_TAP_INTERVAL = 0.4
TAP_MAX_DURATION = 0.3

# Windows virtual key codes
VK_LBUTTON = 0x01
VK_RBUTTON = 0x02
VK_MBUTTON = 0x04
VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12
VK_PAUSE = 0x13
VK_CAPITAL = 0x14
VK_ESCAPE = 0x1B
VK_SPACE = 0x20
VK_TAB = 0x09
VK_W = 0x57
VK_PRIOR = 0x21
VK_NEXT = 0x22
VK_END = 0x23
VK_HOME = 0x24
VK_LEFT = 0x25
VK_UP = 0x26
VK_RIGHT = 0x27
VK_DOWN = 0x28
VK_SNAPSHOT = 0x2C
VK_INSERT = 0x2D
VK_DELETE = 0x2E
VK_LWIN = 0x5B
VK_RWIN = 0x5C
VK_NUMPAD0 = 0x60
VK_F1 = 0x70
VK_F4 = 0x73
VK_F24 = 0x87
VK_OEM_1 = 0xBA
VK_OEM_PLUS = 0xBB
VK_OEM_COMMA = 0xBC
VK_OEM_MINUS = 0xBD
VK_OEM_PERIOD = 0xBE
VK_OEM_2 = 0xBF
VK_OEM_3 = 0xC0
VK_OEM_4 = 0xDB
VK_OEM_5 = 0xDC
VK_OEM_6 = 0xDD
VK_OEM_7 = 0xDE

# Modifier bit flags (values match the Windows MOD_* constants, so they can
# also be used with RegisterHotKey if that is ever needed).
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008

# Windows hook / message constants
WH_KEYBOARD_LL = 13
WH_MOUSE_LL = 14
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WM_MBUTTONDOWN = 0x0207
WM_MBUTTONUP = 0x0208
WM_MOUSEWHEEL = 0x020A
WM_MOUSEHWHEEL = 0x020E
WM_QUIT = 0x0012
WM_APP = 0x8000

# Overlay extended window styles
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOPMOST = 0x00000008

SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
HWND_TOPMOST = -1

WDA_NONE = 0x00000000
WDA_EXCLUDEFROMCAPTURE = 0x00000011

# Keyboard hook flags
LLKHF_INJECTED = 0x10
LLMHF_INJECTED = 0x01

# Virtual desktop / monitor
MONITOR_DEFAULTTONEAREST = 2

# SendInput
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_SCANCODE = 0x0008

# Key names used in the UI.  Letters and digits are handled algorithmically.
KEY_NAMES = {
    VK_ESCAPE: "Esc",
    VK_SPACE: "Space",
    0x08: "Backspace",
    0x09: "Tab",
    0x0D: "Enter",
    VK_PRIOR: "PageUp",
    VK_NEXT: "PageDown",
    VK_END: "End",
    VK_HOME: "Home",
    VK_LEFT: "←",
    VK_UP: "↑",
    VK_RIGHT: "→",
    VK_DOWN: "↓",
    VK_SNAPSHOT: "PrintScreen",
    VK_INSERT: "Insert",
    VK_DELETE: "Delete",
    VK_LWIN: "Win",
    VK_RWIN: "Win",
    VK_OEM_1: ";",
    VK_OEM_PLUS: "=",
    VK_OEM_COMMA: ",",
    VK_OEM_MINUS: "-",
    VK_OEM_PERIOD: ".",
    VK_OEM_2: "/",
    VK_OEM_3: "`",
    VK_OEM_4: "[",
    VK_OEM_5: "\\",
    VK_OEM_6: "]",
    VK_OEM_7: "'",
    VK_PAUSE: "Pause",
    VK_CAPITAL: "CapsLock",
}
KEY_NAMES.update({VK_F1 + i: f"F{i + 1}" for i in range(24)})
KEY_NAMES.update({VK_NUMPAD0 + i: f"Num{i}" for i in range(10)})
