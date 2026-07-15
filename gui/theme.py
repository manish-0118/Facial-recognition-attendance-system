# gui/theme.py
"""
Central theme system. To switch the entire app's color scheme,
change ACTIVE_THEME to any key in _THEMES, then restart the app.
"""

# ── Theme selector ────────────────────────────────────────────────────────
ACTIVE_THEME = "dark_navy"   # options: "dark_navy", "light_slate"

# ── Theme definitions ─────────────────────────────────────────────────────
_THEMES = {
	"dark_navy": {
		# Backgrounds
		"BG_ROOT":        "#0A0F1C",
		"BG_SURFACE":     "#111827",
		"BG_ELEVATED":    "#1C252E",
		"BG_SURFACE_ALT": "#1F2937",
		"BG_ROW_ODD":     "#111827",
		"BG_ROW_EVEN":    "#1A2332",
		"BG_HOVER":       "#1E3A5F",
		# Sidebar
		"SIDEBAR_BG":     "#0D1424",
		"SIDEBAR_ACTIVE": "#1D4ED8",
		"SIDEBAR_HOVER":  "#1E2D45",
		# Accent
		"ACCENT":         "#2563EB",
		"ACCENT_HOVER":   "#1D4ED8",
		"ACCENT_SUBTLE":  "#1E3A5F",
		# Status
		"SUCCESS":        "#16A34A",
		"SUCCESS_BG":     "#14532D",
		"WARNING":        "#D97706",
		"WARNING_BG":     "#78350F",
		"DANGER":         "#DC2626",
		"DANGER_HOVER":   "#B91C1C",
		"DANGER_BG":      "#7F1D1D",
		# Stat card accents
		"STAT_BLUE":      "#2563EB",
		"STAT_TEAL":      "#0D9488",
		"STAT_GREEN":     "#16A34A",
		"STAT_PURPLE":    "#7C3AED",
		# Text
		"TEXT_PRIMARY":   "#F9FAFB",
		"TEXT_SECONDARY": "#9CA3AF",
		"TEXT_MUTED":     "#6B7280",
		"TEXT_LINK":      "#60A5FA",
		# Borders
		"BORDER":         "#374151",
		"BORDER_SUBTLE":  "#1F2937",
		# Inputs
		"INPUT_BG":            "#1F2937",
		"INPUT_BORDER":        "#374151",
		"INPUT_BORDER_FOCUS":  "#2563EB",
        # Input highlight + dropdown bg
        "INPUT_HIGHLIGHT":     "#2A3A5C",
        "DROPDOWN_BG":         "#1A2235",
		# Buttons
		"BTN_SECONDARY":     "#1F2937",
		"BTN_SECONDARY_HVR": "#374151",
		"BTN_DANGER":        "#DC2626",
		"BTN_DANGER_HVR":    "#B91C1C",
		"BTN_SUCCESS":       "#16A34A",
		"BTN_SUCCESS_HVR":   "#15803D",
		"BTN_ADD_HVR":       "#22C55E",
		# CTk mode
		"CTK_MODE": "dark",
	},

	"light_slate": {
		# Backgrounds
		"BG_ROOT":        "#F8FAFC",
		"BG_SURFACE":     "#FFFFFF",
		"BG_ELEVATED":    "#F5F7FA",
		"BG_SURFACE_ALT": "#F1F5F9",
		"BG_ROW_ODD":     "#FFFFFF",
		"BG_ROW_EVEN":    "#F8FAFC",
		"BG_HOVER":       "#EFF6FF",
		# Sidebar
		"SIDEBAR_BG":     "#1E293B",
		"SIDEBAR_ACTIVE": "#2563EB",
		"SIDEBAR_HOVER":  "#334155",
		# Accent
		"ACCENT":         "#2563EB",
		"ACCENT_HOVER":   "#1D4ED8",
		"ACCENT_SUBTLE":  "#DBEAFE",
		# Status
		"SUCCESS":        "#16A34A",
		"SUCCESS_BG":     "#DCFCE7",
		"WARNING":        "#D97706",
		"WARNING_BG":     "#FEF9C3",
		"DANGER":         "#DC2626",
		"DANGER_HOVER":   "#B91C1C",
		"DANGER_BG":      "#FEE2E2",
		# Stat card accents
		"STAT_BLUE":      "#2563EB",
		"STAT_TEAL":      "#0D9488",
		"STAT_GREEN":     "#16A34A",
		"STAT_PURPLE":    "#7C3AED",
		# Text
		"TEXT_PRIMARY":   "#0F172A",
		"TEXT_SECONDARY": "#64748B",
		"TEXT_MUTED":     "#94A3B8",
		"TEXT_LINK":      "#2563EB",
		# Borders
		"BORDER":         "#E2E8F0",
		"BORDER_SUBTLE":  "#F1F5F9",
		# Inputs
		"INPUT_BG":            "#F8FAFC",
		"INPUT_BORDER":        "#CBD5E1",
		"INPUT_BORDER_FOCUS":  "#2563EB",
        # Input highlight + dropdown bg
        "INPUT_HIGHLIGHT":     "#DBEAFE",
        "DROPDOWN_BG":         "#F8FAFC",
		# Buttons
		"BTN_SECONDARY":     "#F1F5F9",
		"BTN_SECONDARY_HVR": "#E2E8F0",
		"BTN_DANGER":        "#DC2626",
		"BTN_DANGER_HVR":    "#B91C1C",
		"BTN_SUCCESS":       "#16A34A",
		"BTN_SUCCESS_HVR":   "#15803D",
		"BTN_ADD_HVR":       "#15803D",
		# CTk mode
		"CTK_MODE": "light",
	},
}

# ── Export active theme tokens at module level ─────────────────────────────
# This means all existing imports like `theme.ACCENT` continue to work
# with zero changes in any other file.
_t = _THEMES[ACTIVE_THEME]

BG_ROOT        = _t["BG_ROOT"]
BG_SURFACE     = _t["BG_SURFACE"]
BG_ELEVATED    = _t["BG_ELEVATED"]
BG_SURFACE_ALT = _t["BG_SURFACE_ALT"]
BG_ROW_ODD     = _t["BG_ROW_ODD"]
BG_ROW_EVEN    = _t["BG_ROW_EVEN"]
BG_HOVER       = _t["BG_HOVER"]

SIDEBAR_BG     = _t["SIDEBAR_BG"]
SIDEBAR_ACTIVE = _t["SIDEBAR_ACTIVE"]
SIDEBAR_HOVER  = _t["SIDEBAR_HOVER"]

ACCENT         = _t["ACCENT"]
ACCENT_HOVER   = _t["ACCENT_HOVER"]
ACCENT_SUBTLE  = _t["ACCENT_SUBTLE"]

SUCCESS        = _t["SUCCESS"]
SUCCESS_BG     = _t["SUCCESS_BG"]
WARNING        = _t["WARNING"]
WARNING_BG     = _t["WARNING_BG"]
DANGER         = _t["DANGER"]
DANGER_HOVER   = _t["DANGER_HOVER"]
DANGER_BG      = _t["DANGER_BG"]

STAT_BLUE      = _t["STAT_BLUE"]
STAT_TEAL      = _t["STAT_TEAL"]
STAT_GREEN     = _t["STAT_GREEN"]
STAT_PURPLE    = _t["STAT_PURPLE"]

TEXT_PRIMARY   = _t["TEXT_PRIMARY"]
TEXT_SECONDARY = _t["TEXT_SECONDARY"]
TEXT_MUTED     = _t["TEXT_MUTED"]
TEXT_LINK      = _t["TEXT_LINK"]

BORDER         = _t["BORDER"]
BORDER_SUBTLE  = _t["BORDER_SUBTLE"]

INPUT_BG           = _t["INPUT_BG"]
INPUT_BORDER       = _t["INPUT_BORDER"]

BTN_SECONDARY     = _t["BTN_SECONDARY"]
BTN_SECONDARY_HVR = _t["BTN_SECONDARY_HVR"]
BTN_DANGER        = _t["BTN_DANGER"]
BTN_DANGER_HVR    = _t["BTN_DANGER_HVR"]
BTN_SUCCESS       = _t["BTN_SUCCESS"]
BTN_SUCCESS_HVR   = _t["BTN_SUCCESS_HVR"]
BTN_ADD_HVR       = _t["BTN_ADD_HVR"]

CTK_MODE = _t["CTK_MODE"]
INPUT_HIGHLIGHT = _t["INPUT_HIGHLIGHT"]