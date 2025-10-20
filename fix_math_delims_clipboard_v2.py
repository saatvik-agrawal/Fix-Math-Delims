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
    if re.search(r"\b[dD][A-Za-z]+\b", s): return True    # dx, dT, dP...
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
    # Paragraph-level [ ... ] with at least one newline inside -> $$ ... $$.
    patt = re.compile(r"^[ \t]*\[[ \t]*\r?\n([\s\S]*?)\r?\n[ \t]*\][ \t]*$", re.MULTILINE)
    return patt.sub(lambda m: f"\n$$\n{m.group(1).strip()}\n$$\n", text)

def convert_token_paren_numeric(text: str) -> str:
    # Wrap 2(1), 3(0), x(1), T(x,y) as one inline math run.
    patt = re.compile(r"(?P<pre>[A-Za-z0-9])\(\s*(?P<inner>[A-Za-z0-9 ,+\-*/^_=.:;\\]+?)\s*\)")
    return patt.sub(lambda m: f"${m.group('pre')}({m.group('inner').strip()})$", text)

def convert_inline_parentheses(text: str) -> str:
    ALLOW_EXACT = {"x","y","z","T","v","u"}
    def repl(m: Match[str]) -> str:
        inner = m.group(1).strip()
        if "\n" in inner or "[" in inner or "]" in inner: return m.group(0)
        if "$" in inner:  # prevent nested-dollar artifacts
            return m.group(0)
        if inner in ALLOW_EXACT or re.match(r"^d[A-Za-z]+$", inner):  # (dx), (dT)
            return f"${inner}$"
        if looks_like_latex(inner) or looks_like_mathish(inner) or re.match(r"^[A-Za-z0-9,;:+\-*/^_=.\s]+$", inner):
            if SIMPLE_WORD_RE.match(inner):  # plain word
                return m.group(0)
            return f"${inner}$"
        return m.group(0)
    text = re.sub(r"\(\(([^()\r\n]{1,160})\)\)", lambda m: f"$({m.group(1).strip()})$", text)
    return re.sub(r"\(([^()\r\n]{1,160})\)", repl, text)

# ---------- matrix fixes inside $$...$$ ----------
MATH_BLOCK_RE = re.compile(r"\$\$([\s\S]*?)\$\$", re.MULTILINE)
MATRIX_ENV_RE = re.compile(r"\\begin\{(bmatrix|pmatrix|vmatrix|Bmatrix|Vmatrix|matrix)\}([\s\S]*?)\\end\{\1\}", re.MULTILINE)

def _fix_matrix_rows(env_body: str) -> str:
    lines = env_body.strip("\n").splitlines()
    # Normalize [Npt] -> \\[Npt] on each line
    for i, line in enumerate(lines):
        lines[i] = re.sub(r"(?<!\\)\[(\d+pt)\]", r"\\[\1]", line.rstrip())

    # Add \\ between consecutive non-empty lines when missing
    fixed = []
    for i, line in enumerate(lines):
        cur = line.rstrip()
        fixed.append(cur)
        last = (i == len(lines) - 1)
        if last: break
        nxt = lines[i+1].lstrip()
        if not nxt:  # blank next line: no break
            continue
        # if current already ends with \\ or \\[Npt] or has trailing & (common row pattern), leave it
        if re.search(r"(\\\\(\[\d+pt\])?\s*|&\s*)$", cur):
            continue
        # otherwise insert a row break line
        fixed.append(r"\\")
    return "\n".join(fixed)

def fix_matrices_in_math_blocks(text: str) -> str:
    def fix_env(m: Match[str]) -> str:
        env, body = m.group(1), m.group(2)
        return f"\\begin{{{env}}}\n{_fix_matrix_rows(body)}\n\\end{{{env}}}"
    def repl_math(m: Match[str]) -> str:
        inner = m.group(1)
        inner = MATRIX_ENV_RE.sub(fix_env, inner)
        return f"$${inner}$$"
    return MATH_BLOCK_RE.sub(repl_math, text)

# ---------- spacing & normalization ----------
def fix_inline_spacing(text: str) -> str:
    text = re.sub(r"([A-Za-z0-9])\$(?=[^$])", r"\1 $", text)             # word$ -> word $
    text = re.sub(r"\$([^$]+)\$([A-Za-z0-9])", r"$\1$ \2", text)         # $math$word -> $math$ word
    text = re.sub(r"\$\s+([^\$]*?)\s+\$", r"$\1$", text)                 # $ T $ -> $T$
    text = re.sub(r"^-\s*\$\s*([^\$]*?)\s*\$", r"- $\1$", text, flags=re.MULTILINE)  # -$x$ -> - $x$
    text = re.sub(r"\s+\$(.+?)\$\s+", r" $\1$ ", text)                   # collapse around inline
    return text

def normalize_dollars(text: str) -> str:
    text = re.sub(r"\${3,}", "$$", text)
    text = re.sub(r"\$\$\r?\n([^\r\n]+)\r?\n\$\$", r"$$\1$$", text)      # one-line display
    return text

def convert(text: str) -> str:
    # 1) protect code
    protected, sent = _protect(text)
    # 2) blocks first
    protected = convert_code_fences(protected)
    protected = convert_backslash_brackets(protected)
    protected = convert_square_bracket_blocks(protected)
    # 3) matrix fixes INSIDE $$...$$ (before protecting math)
    protected = fix_matrices_in_math_blocks(protected)
    # 4) protect $$...$$ so inline steps don't touch
    protected = _protect_math(protected, sent)
    # 5) inline conversions (ORDER matters)
    protected = convert_token_paren_numeric(protected)    # 2(1), 3(0), T(x,y)
    protected = convert_inline_parentheses(protected)     # (dx), (x,y), (T)
    protected = fix_inline_spacing(protected)
    protected = normalize_dollars(protected)
    # 6) restore
    return _unprotect(protected, sent)

def main():
    src = get_clipboard() or sys.stdin.read()
    out = convert(src)
    set_clipboard(out)
    # do NOT print (prevents aText double-insert)
    # sys.stdout.write(out)

if __name__ == "__main__":
    main()
