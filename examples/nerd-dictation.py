# ~/.config/nerd-dictation/nerd-dictation.py
# Text processing configuration for Mint Dictation
# Handles: punctuation, capitalization, common names, contractions, tech terms

import re
import socket
from pathlib import Path

# ---------------------------------------------------------------------------
# Voice stop command — say these phrases to stop recording
# ---------------------------------------------------------------------------

STOP_PHRASES = ["stop recording", "stop dictation"]

_IPC_SOCKET = Path.home() / ".cache" / "mint-dictation" / "ipc.sock"


def _send_stop_command():
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(2)
        sock.connect(str(_IPC_SOCKET))
        sock.sendall(b"stop")
        sock.close()
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Punctuation — say the word to insert the punctuation
# ---------------------------------------------------------------------------

CLOSING_PUNCTUATION = {
    "period": ".",
    "full stop": ".",
    "dot": ".",
    "comma": ",",
    "question mark": "?",
    "exclamation mark": "!",
    "exclamation point": "!",
    "colon": ":",
    "semicolon": ";",
    "close quote": '"',
    "close paren": ")",
    "close bracket": "]",
    "close brace": "}",
    "ellipsis": "...",
    "dash": " —",
    "hyphen": "-",
}

OPENING_PUNCTUATION = {
    "open quote": '"',
    "open paren": "(",
    "open bracket": "[",
    "open brace": "{",
}

# ---------------------------------------------------------------------------
# Special actions — say these to perform actions
# ---------------------------------------------------------------------------

SPECIAL_ACTIONS = {
    "new line": "\n",
    "newline": "\n",
    "new paragraph": "\n\n",
    "tab key": "\t",
}

# ---------------------------------------------------------------------------
# Word replacements — VOSK outputs lowercase, fix capitalization here
# ---------------------------------------------------------------------------

WORD_REPLACE = {
    # Pronoun
    "i": "I",

    # Common contractions (VOSK often splits these)
    "i'm": "I'm",
    "i've": "I've",
    "i'll": "I'll",
    "i'd": "I'd",
    "don't": "don't",
    "doesn't": "doesn't",
    "didn't": "didn't",
    "won't": "won't",
    "wouldn't": "wouldn't",
    "couldn't": "couldn't",
    "shouldn't": "shouldn't",
    "can't": "can't",
    "isn't": "isn't",
    "aren't": "aren't",
    "wasn't": "wasn't",
    "weren't": "weren't",
    "hasn't": "hasn't",
    "haven't": "haven't",
    "hadn't": "hadn't",
    "it's": "it's",
    "that's": "that's",
    "there's": "there's",
    "they're": "they're",
    "we're": "we're",
    "you're": "you're",
    "let's": "let's",
    "what's": "what's",
    "who's": "who's",
    "he's": "he's",
    "she's": "she's",

    # Tech terms
    "linux": "Linux",
    "ubuntu": "Ubuntu",
    "debian": "Debian",
    "api": "API",
    "apis": "APIs",
    "url": "URL",
    "urls": "URLs",
    "html": "HTML",
    "css": "CSS",
    "json": "JSON",
    "http": "HTTP",
    "https": "HTTPS",
    "sql": "SQL",
    "gui": "GUI",
    "cli": "CLI",
    "ssh": "SSH",
    "git": "Git",
    "github": "GitHub",
    "copilot": "Copilot",
    "vscode": "VSCode",
    "javascript": "JavaScript",
    "typescript": "TypeScript",
    "python": "Python",
    "npm": "npm",
    "node": "Node",
    "nodejs": "Node.js",
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "aws": "AWS",
    "gcp": "GCP",
    "azure": "Azure",
    "cpu": "CPU",
    "gpu": "GPU",
    "ram": "RAM",
    "ssd": "SSD",
    "usb": "USB",
    "wifi": "WiFi",
    "bluetooth": "Bluetooth",
    "ip": "IP",
    "ai": "AI",
    "llm": "LLM",
    "gpt": "GPT",
    "pdf": "PDF",
    "ok": "OK",
    "yaml": "YAML",
    "toml": "TOML",
    "tcp": "TCP",
    "udp": "UDP",
    "dns": "DNS",

    # Days and months
    "monday": "Monday",
    "tuesday": "Tuesday",
    "wednesday": "Wednesday",
    "thursday": "Thursday",
    "friday": "Friday",
    "saturday": "Saturday",
    "sunday": "Sunday",
    "january": "January",
    "february": "February",
    "march": "March",
    "april": "April",
    "may": "May",
    "june": "June",
    "july": "July",
    "august": "August",
    "september": "September",
    "october": "October",
    "november": "November",
    "december": "December",

    # Common names (add your own here)
    "ethan": "Ethan",
    "google": "Google",
    "microsoft": "Microsoft",
    "apple": "Apple",
    "amazon": "Amazon",
    "windows": "Windows",
    "firefox": "Firefox",
    "chrome": "Chrome",
    "reddit": "Reddit",
    "slack": "Slack",
    "discord": "Discord",
    "spotify": "Spotify",
    "netflix": "Netflix",
    "youtube": "YouTube",
    "twitter": "Twitter",
    "facebook": "Facebook",
    "instagram": "Instagram",
    "nvidia": "NVIDIA",
    "intel": "Intel",
    "amd": "AMD",
    "dell": "Dell",
    "lenovo": "Lenovo",
    "cinnamon": "Cinnamon",
    "english": "English",
    "spanish": "Spanish",
    "french": "French",
    "german": "German",
    "american": "American",
    "european": "European",
    "america": "America",
    "europe": "Europe",

    # Filler words to remove
    "um": "",
    "uh": "",
    "umm": "",
    "uhh": "",
    "hmm": "",
}

# ---------------------------------------------------------------------------
# Regex replacements — for patterns like "i'm", "i'll" at start of words
# ---------------------------------------------------------------------------

WORD_REPLACE_REGEX = (
    (r"^i'(.*)", r"I'\1"),
)
WORD_REPLACE_REGEX = tuple(
    (re.compile(match), replacement)
    for (match, replacement) in WORD_REPLACE_REGEX
)

# ---------------------------------------------------------------------------
# Multi-word replacements
# ---------------------------------------------------------------------------

TEXT_REPLACE_REGEX = (
    (r"\b" "e-mail" r"\b", "email"),
    (r"\b" "data type" r"\b", "data-type"),
    (r"\b" "copy on write" r"\b", "copy-on-write"),
    (r"\b" "key word" r"\b", "keyword"),
    (r"\b" "web site" r"\b", "website"),
    (r"\b" "v s code" r"\b", "VSCode"),
    (r"\b" "v s. code" r"\b", "VSCode"),
    (r"\b" "g p t" r"\b", "GPT"),
)
TEXT_REPLACE_REGEX = tuple(
    (re.compile(match), replacement)
    for (match, replacement) in TEXT_REPLACE_REGEX
)


# ---------------------------------------------------------------------------
# Main Processing Function
# ---------------------------------------------------------------------------

def nerd_dictation_process(text):
    # Check for voice stop command
    text_lower = text.strip().lower()
    for phrase in STOP_PHRASES:
        if phrase in text_lower:
            _send_stop_command()
            # Remove the stop phrase, return any text before it
            idx = text_lower.index(phrase)
            text = text[:idx].strip()
            if not text:
                return ""
            break

    # Multi-word regex replacements
    for match, replacement in TEXT_REPLACE_REGEX:
        text = match.sub(replacement, text)

    # Special actions (new line, new paragraph, etc.)
    for trigger, action in SPECIAL_ACTIONS.items():
        text = text.replace(trigger, action)

    # Closing punctuation: "hello period" -> "hello."
    for match, replacement in CLOSING_PUNCTUATION.items():
        text = text.replace(" " + match, replacement)

    # Opening punctuation: "open quote hello" -> '"hello'
    for match, replacement in OPENING_PUNCTUATION.items():
        text = text.replace(match + " ", replacement)

    # Process individual words
    words = text.split(" ")
    for i, w in enumerate(words):
        w_init = w

        # Direct word replacement
        w_test = WORD_REPLACE.get(w)
        if w_test is not None:
            w = w_test
        # Also try lowercase lookup for mixed-case VOSK output
        elif w.lower() in WORD_REPLACE:
            w = WORD_REPLACE[w.lower()]

        # Regex word replacement
        if w_init == w:
            for match, replacement in WORD_REPLACE_REGEX:
                w_test = match.sub(replacement, w)
                if w_test != w:
                    w = w_test
                    break

        words[i] = w

    # Strip empty words (from filler removal)
    words = [w for w in words if w]

    # Capitalize after sentence-ending punctuation
    result = " ".join(words)
    result = re.sub(
        r'([.!?]\s+)([a-z])',
        lambda m: m.group(1) + m.group(2).upper(),
        result,
    )

    return result
