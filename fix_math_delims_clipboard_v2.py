#!/usr/bin/env python3
import os, re, sys, shutil, subprocess
from typing import Optional, Match, List, Tuple

# ---------- clipboard helpers ----------
def _run(cmd: list, input_text: Optional[str] = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        input=input_text.encode("utf-8") if input_text is not None else None,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )

def get_clipboard() -> str:
    if sys.platform == "darwin":
        return _run(["pbpaste"]).stdout.decode("utf-8", errors="ignore")
    elif os.name == "nt":
        return _run(["powershell","-NoProfile","-Command","Get-Clipboard"]).stdout.decode("utf-8", errors="ignore")
    else:
        if shutil.which("xclip"):  return _run(["xclip","-selection","clipboard","-o"]).stdout.decode("utf-8","ignore")
        if shutil.which("xsel"):   return _run(["xsel","--clipboard","--output"]).stdout.decode("utf-8","ignore")
        return sys.stdin.read()

def set_clipboard(text: str) -> None:
    if sys.platform == "darwin":
        _run(["pbcopy"], input_text=text)
    elif os.name == "nt":
        _run(["powershell","-NoProfile","-Command","Set-Clipboard -Value ([Console]::In.ReadToEnd())"], input_text=text)
    else:
        if shutil.which("xclip"):  _run(["xclip","-selection","clipboard"], input_text=text); return
        if shutil.which("xsel"):   _run(["xsel","--clipboard","--input"], input_text=text); return
        sys.stdout.write(text)

# ---------- protect code & math blocks ----------
BACKTICK_FENCE_RE = re.compile(r"```[^\r\n]*\r?\n[\s\S]*?\r?\n```", re.MULTILINE)
INLINE_CODE_RE    = re.compile(r"`[^`\r\n]*`")
DOLLAR_BLOCK_RE   = re.compile(r"\$\$[\s\S]*?\$\$", re.MULTILINE)

def _protect(text: str) -> Tuple[str, List[str]]:
    sent: List[str] = []
    def keep(s: str, tag: str) -> str:
        sent.append(s); return f"@@{tag}_{len(sent)-1}@@"
    text = BACKTICK_FENCE_RE.sub(lambda m: keep(m.group(0), "CODEFENCE"), text)
    text = INLINE_CODE_RE.sub (lambda m: keep(m.group(0), "INLINE"),    text)
    return text, sent

def _protect_math(text: str, sent: List[str]) -> str:
    return DOLLAR_BLOCK_RE.sub(lambda m: (sent.append(m.group(0)) or f"@@MATH_{len(sent)-1}@@"), text)

def _unprotect(text: str, sent: List[str]) -> str:
    return re.sub(r"@@(?:CODEFENCE|INLINE|MATH)_(\d+)@@", lambda m: sent[int(m.group(1))], text)

# ---------- detectors ----------
LATEX_TOKENS_RE = re.compile(
    r"(\\frac|\\partial|\\nabla|\\mathbf|\\mathrm|\\mathbb|\\vec|\\hat|\\dot|\\ddot|"
    r"\\sum|\\int|\\cdot|\\alpha|\\beta|\\gamma|\\delta|\\theta|\\lambda|\\mu|"
    r"\\sigma|\\phi|\\psi|\\Omega|\\infty|\\leq|\\geq|\\neq|\\approx|\\rightarrow|"
    r"\\left|\\right|\\begin|\\end|\\displaystyle|\\boxed)"
)
MATHISH_OP_RE = re.compile(r"[=+\-*/^_]")
SIMPLE_WORD_RE = re.compile(r"^[A-Za-z]{2,}$")

def looks_like_latex(s: str) -> bool:
    return bool(LATEX_TOKENS_RE.search(s))

def looks_like_mathish(s: str) -> bool:
    if LATEX_TOKENS_RE.search(s): return True
    if MATHISH_OP_RE.search(s):   return True
    if re.search(r"\b[A-Za-z]\s*\(", s): return True      # f(x), T(x,y)
    if re.search(r"\b[dD][xyztr]\b", s): return True      # dx, dy, dt, dr
    if len(s) > 140: return False
    return False

# ---------- conversions ----------
def convert_code_fences(text: str) -> str:
    def repl(m: Match[str]) -> str:
        fence = m.group(0)
        first = fence.splitlines()[0].strip()
        body  = "\n".join(fence.splitlines()[1:-1]).strip()
        if first.startswith("```latex") or first.startswith("```tex"):
            return f"$$\n{body}\n$$"
        return fence
    return BACKTICK_FENCE_RE.sub(repl, text)

def convert_backslash_brackets(text: str) -> str:
    text = re.sub(r"\\\[\s*([\s\S]*?)\s*\\\]", r"$$\n\1\n$$", text)
    text = re.sub(r"\\\(\s*([^\r\n]*?)\s*\\\)", r"$\1$", text)
    return text

def convert_square_bracket_blocks(text: str) -> str:
    """
    Paragraph-level [ ... ] with at least one newline inside -> $$ ... $$.
    Supports CR/LF and trailing spaces.
    """
    patt = re.compile(r"^[ \t]*\[[ \t]*\r?\n([\s\S]*?)\r?\n[ \t]*\][ \t]*$", re.MULTILINE)
    return patt.sub(lambda m: f"\n$$\n{m.group(1).strip()}\n$$\n", text)

def convert_token_plus_paren(text: str) -> str:
    # Join token immediately followed by (...) into one inline math: A(x), T(x,y), 2(1)
    patt = re.compile(r"(?P<pre>[A-Za-z0-9])\(\s*(?P<inner>[^()\r\n]{1,80})\s*\)")
    return patt.sub(lambda m: f"${m.group('pre')}({m.group('inner').strip()})$", text)

def convert_inline_parentheses(text: str) -> str:
    # Remaining (...) that look mathy -> $...$ ; skip plain single-words like "(however)".
    def repl(m: Match[str]) -> str:
        inner = m.group(1)
        if "\n" in inner or "[" in inner or "]" in inner: return m.group(0)
        if SIMPLE_WORD_RE.match(inner.strip()):           return m.group(0)
        if looks_like_latex(inner) or looks_like_mathish(inner) or re.match(r"^[A-Za-z0-9,;:+\-*/^_=.\s]+$", inner):
            return f"${inner.strip()}$"
        return m.group(0)
    # Double parens first
    text = re.sub(r"\(\(([^()\r\n]{1,160})\)\)", lambda m: f"$({m.group(1).strip()})$", text)
    return re.sub(r"\(([^()\r\n]{1,160})\)", repl, text)

def fix_inline_spacing(text: str) -> str:
    # word$math$ -> word $math$
    text = re.sub(r"([A-Za-z0-9])\$(?=[^$])", r"\1 $", text)
    # $math$word -> $math$ word
    text = re.sub(r"\$(?:[^$]+)\$([A-Za-z0-9])", r"$ \1", text)
    # "-$x$" -> "- $x$"
    text = re.sub(r"^-\s*\$", r"- $", text, flags=re.MULTILINE)
    # collapse excessive spaces around inline math
    text = re.sub(r"\s+\$(.+?)\$\s+", r" $\1$ ", text)
    return text

def normalize_dollars(text: str) -> str:
    text = re.sub(r"\${3,}", "$$", text)                     # $$$ -> $$
    text = re.sub(r"\$\s+([^\$]+?)\s+\$", r"$\1$", text)     # trim inside
    text = re.sub(r"\$\$\r?\n([^\r\n]+)\r?\n\$\$", r"$$\1$$", text)  # single-line display
    return text

def convert(text: str) -> str:
    # 1) protect code
    protected, sent = _protect(text)
    # 2) blocks first
    protected = convert_code_fences(protected)
    protected = convert_backslash_brackets(protected)
    protected = convert_square_bracket_blocks(protected)
    # 3) protect new $$...$$
    protected = _protect_math(protected, sent)
    # 4) inline conversions outside math/code
    protected = convert_token_plus_paren(protected)
    protected = convert_inline_parentheses(protected)
    protected = fix_inline_spacing(protected)
    protected = normalize_dollars(protected)
    # 5) restore
    return _unprotect(protected, sent)

def main():
    src = get_clipboard() or sys.stdin.read()
    out = convert(src)
    set_clipboard(out)
    sys.stdout.write(out)

if __name__ == "__main__":
    main()
