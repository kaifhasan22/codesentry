"""Best-effort credential redaction across every analyzer and AI boundary."""
import re

_ASSIGNMENT = re.compile(r"""(?im)((?:[\w]*?(?:password|passwd|api_key|secret|token|private_key)[\w]*)\s*(?::[^=\n]{0,80})?=\s*)(["'])([^\n]*?)\2""")
_TOKENS = re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-(?:ant-)?[A-Za-z0-9_-]{20,}|AKIA[A-Z0-9]{16}|eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)\b")
_PRIVATE_KEY = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?(?:-----END [A-Z ]*PRIVATE KEY-----|$)", re.S)

def redact(text):
    if not text:
        return text
    text = _ASSIGNMENT.sub(lambda m: m[1] + m[2] + '<redacted credential>' + m[2], text)
    text = _TOKENS.sub('<redacted credential>', text)
    return _PRIVATE_KEY.sub('<redacted private key>', text)
