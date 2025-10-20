#!/usr/bin/env python3
import os
import re
import sys
import shutil
import subprocess
from typing import Match, List, Tuple
from typing import Optional

# ------------- Clipboard helpers -------------
# def _run(cmd: list, input_text: str | None = None) -> subprocess.CompletedProcess: ## removed as not compatibale with python 3.9
def _run(cmd: list, input_text: Optional[str] = None) -> subprocess.CompletedProcess:

    return subprocess.run(
        cmd,
        input=input_text.encode("utf-8") if input_text is not None else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

def get_clipboard() -> str:
    if sys.platform == "darwin":
        # macOS
        p = _run(["pbpaste"])
        return p.stdout.decode("utf-8", errors="ignore")
    elif os.name == "nt":
        # Windows (PowerShell)
        ps = ["powershell", "-NoProfile", "-Command", "Get-Clipboard"]
        p = _run(ps)
        return p.stdout.decode("utf-8", errors="ignore")
    else:
        # Linux / others
        if shutil.which("xclip"):
            p = _run(["xclip", "-selection", "clipboard", "-o"])
            return p.stdout.decode("utf-8", errors="ignore")
        if shutil.which("xsel"):
            p = _run(["xsel", "--clipboard", "--output"])
            return p.stdout.decode("utf-8", errors="ignore")
        # Last resort: read from stdin
        return sys.stdin.read()

def set_clipboard(text: str) -> None:
    if sys.platform == "darwin":
        _run(["pbcopy"], input_text=text)
    elif os.name == "nt":
        ps = ["powershell", "-NoProfile", "-Command", "Set-Clipboard -Value ([Console]::In.ReadToEnd())"]
        _run(ps, input_text=text)
    else:
        if shutil.which("xclip"):
            _run(["xclip", "-selection", "clipboard"], input_text=text)
            return
        if shutil.which("xsel"):
            _run(["xsel", "--clipboard", "--input"], input_text=text)
            return
        # Last resort: print to stdout
        sys.stdout.write(text)

# ------------- Protection for code blocks -------------
BACKTICK_FENCE_RE = re.compile(r"```[^\n]*\n[\s\S]*?\n```", re.MULTILINE)
INLINE_CODE_RE   = re.compile(r"`[^`\n]*`")

def _protect(text: str) -> tuple[str, list[str]]:
    sentinels: list[str] = []
    def repl_fence(m: Match[str]) -> str:
        sentinels.append(m.group(0))
        return f"@@CODEFENCE_{len(sentinels)-1}@@"
    text = BACKTICK_FENCE_RE.sub(repl_fence, text)

    def repl_inline(m: Match[str]) -> str:
        sentinels.append(m.group(0))
        return f"@@INLINE_{len(sentinels)-1}@@"
    text = INLINE_CODE_RE.sub(repl_inline, text)
    return text, sentinels

def _unprotect(text: str, sentinels: list[str]) -> str:
    def repl(m: Match[str]) -> str:
        idx = int(m.group(1))
        return sentinels[idx]
    return re.sub(r"@@(?:CODEFENCE|INLINE)_(\d+)@@", repl, text)

# ------------- Conversions -------------
LATEX_TOKENS_RE = re.compile(
    r"(\\frac|\\partial|\\nabla|\\mathbf|\\mathrm|\\mathbb|\\vec|\\hat|\\dot|\\ddot|"
    r"\\sum|\\int|\\cdot|\\alpha|\\beta|\\gamma|\\delta|\\theta|\\lambda|\\mu|"
    r"\\sigma|\\phi|\\psi|\\Omega|\\infty|\\leq|\\geq|\\neq|\\approx|\\rightarrow|"
    r"\\left|\\right|\\begin|\\end|\\displaystyle)"
)

def looks_like_latex(s: str) -> bool:
    if LATEX_TOKENS_RE.search(s):
        return True
    if re.search(r"[A-Za-z0-9]\s*[\^_]\s*[{(]?[A-Za-z0-9+\\-]+", s):
        return True
    return False

def convert_code_fences(text: str) -> str:
    # Convert ```latex/tex ... ``` to $$ ... $$
    def repl(m: Match[str]) -> str:
        fence = m.group(0)
        first_line = fence.splitlines()[0].strip()
        body = "\n".join(fence.splitlines()[1:-1])
        if first_line.startswith("```latex") or first_line.startswith("```tex"):
            body = body.strip()
            return f"$$\n{body}\n$$"
        return fence
    return BACKTICK_FENCE_RE.sub(repl, text)

def convert_backslash_brackets(text: str) -> str:
    # \[ ... \]  -> $$ ... $$
    text = re.sub(r"\\\[\s*([\s\S]*?)\s*\\\]", r"$$\n\1\n$$", text)
    # \( ... \)  -> $ ... $
    text = re.sub(r"\\\(\s*([^\n]*?)\s*\\\)", r"$\1$", text)
    return text

def convert_square_bracket_blocks(text: str) -> str:
    # Paragraph-level [ ... ] blocks -> $$ ... $$ if it looks like LaTeX
    def repl(m: Match[str]) -> str:
        inner = m.group(1).strip()
        if looks_like_latex(inner):
            return f"\n$$\n{inner}\n$$\n"
        return m.group(0)
    pattern = r"(?:^|\n\s*\n)\s*\[\s*\n?([\s\S]*?)\n?\s*\]\s*(?=\n\s*\n|$)"
    return re.sub(pattern, repl, text)

def avoid_double_wrapping(text: str) -> str:
    text = re.sub(r"\${3,}", "$$", text)  # collapse $$$+ to $$
    text = re.sub(r"\$\s+([^\$]+?)\s+\$", r"$\1$", text)  # trim spaces inside $ ... $
    return text

def convert(text: str) -> str:
    protected, sentinels = _protect(text)
    protected = convert_code_fences(protected)
    protected = convert_backslash_brackets(protected)
    protected = convert_square_bracket_blocks(protected)
    protected = avoid_double_wrapping(protected)
    return _unprotect(protected, sentinels)

def main():
    # Default: clipboard -> clipboard
    if len(sys.argv) == 1 or (len(sys.argv) == 2 and sys.argv[1] == "--clipboard"):
        src = get_clipboard()
        if not src:
            # If clipboard empty, read stdin as a fallback
            src = sys.stdin.read()
        out = convert(src)
        set_clipboard(out)
        # Also echo to stdout so it's visible in terminals
        sys.stdout.write(out)
        return

    # File mode (backward compatible)
    if len(sys.argv) >= 2:
        with open(sys.argv[1], "r", encoding="utf-8") as f:
            src = f.read()
        out = convert(src)
        if len(sys.argv) >= 3:
            with open(sys.argv[2], "w", encoding="utf-8") as f:
                f.write(out)
        else:
            sys.stdout.write(out)

if __name__ == "__main__":
    main()
