import re


LABELS = ["question", "doubt", "learn", "understanding", "other"]


_patterns = {
"question": re.compile(r"\?\s*$|^what|^how|^why|^when|^where|^which|^who", re.I),
"doubt": re.compile(r"(not sure|don'?t (know|understand)|confus|unclear|stuck)", re.I),
"learn": re.compile(r"(teach me|explain|guide me|learn|tutorial|how to)", re.I),
"understanding": re.compile(r"(so you mean|if I understand|let me recap|in other words)", re.I),
}


def classify_message(text: str) -> str:
    t = text.strip()
    for label, rx in _patterns.items():
        if rx.search(t):
            return label
    return "other"