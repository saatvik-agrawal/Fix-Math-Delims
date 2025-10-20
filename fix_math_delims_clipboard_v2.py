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
    return re.sub(r"@@(?:CODEFENCE|INLINE|MATH|INL)_(\d+)@@", lambda m: sent[int(m.group(1))], text)

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
    patt = re.compile(r"^[ \t]*\[[ \t]*\r?\n([\s\S]*?)\r?\n[ \t]*\][ \t]*$", re.MULTILINE)
    return patt.sub(lambda m: f"\n$$\n{m.group(1).strip()}\n$$\n", text)

# ---------- stack-based outer math parentheses ----------
def protect_outer_math_parens(text: str, sent: List[str]) -> str:
    s = text
    stack = []
    pairs = []  # (start, end)
    for i, ch in enumerate(s):
        if ch == '(':
            stack.append(i)
        elif ch == ')' and stack:
            start = stack.pop()
            pairs.append((start, i))
    if not pairs:
        return text

    def is_math_outer(content: str) -> bool:
        if '$' in content:
            return False
        c = content.strip()
        if len(c) < 5:
            return False
        if MATHISH_OP_RE.search(c) or looks_like_latex(c):
            return True
        return False

    candidates = []
    for (a, b) in pairs:
        inner = s[a+1:b]
        if is_math_outer(inner):
            candidates.append((a, b))

    if not candidates:
        return text

    candidates.sort(key=lambda t: (t[0], -t[1]))
    selected = []
    for a, b in candidates:
        if any(pa <= a and b <= pb for (pa, pb) in selected):
            continue
        selected.append((a, b))

    result_parts = []
    pos = 0
    for a, b in sorted(selected, key=lambda t: t[0]):
        if a < pos:
            continue
        result_parts.append(s[pos:a])
        inner = s[a+1:b].strip()
        token = f"@@INL_{len(sent)}@@"
        sent.append(f"${inner}$")
        result_parts.append(token)
        pos = b + 1
    result_parts.append(s[pos:])
    return "".join(result_parts)

# ---------- inline conversions ----------
def convert_token_paren_numeric(text: str) -> str:
    # Wrap 2(1), 3(0), x(1), T(x,y) as one inline math run.
    patt = re.compile(r"(?P<pre>[A-Za-z0-9])\(\s*(?P<inner>[A-Za-z0-9 ,+\-*/^_=.:;\\]+?)\s*\)")
    return patt.sub(lambda m: f"${m.group('pre')}({m.group('inner').strip()})$", text)

def convert_inline_parentheses(text: str) -> str:
    ALLOW_EXACT = {"x","y","z","T","v","u"}

    # v4.2 stricter check: require real math signals, digits, function call, or d-variables.
    def is_inline_math_candidate(inner: str) -> bool:
        if looks_like_latex(inner):  # \frac, \nabla, \alpha, ...
            return True
        # strong math operators / relations (exclude a plain hyphen-only prose trigger)
        if any(ch in inner for ch in "=+*/^_"):
            return True
        # digits anywhere -> likely a math eval, coordinates, etc.
        if re.search(r"\d", inner):
            return True
        # function call like f(x) or T(x,y)
        if re.search(r"^[A-Za-z]\s*\([^()\n]*\)$", inner):
            return True
        # standalone variable or d-something like dx, dT
        if inner in ALLOW_EXACT or re.match(r"^d[A-Za-z]+$", inner):
            return True
        return False

    def repl(m: Match[str]) -> str:
        inner = m.group(1)
        if "\n" in inner or "[" in inner or "]" in inner:
            return m.group(0)
        if "$" in inner:
            return m.group(0)

        inner_stripped = inner.strip()
        if inner_stripped in ALLOW_EXACT or re.match(r"^d[A-Za-z]+$", inner_stripped):
            return f"${inner_stripped}$"

        if is_inline_math_candidate(inner_stripped):
            return f"${inner_stripped}$"

        # otherwise, leave normal prose parentheses alone
        return m.group(0)

    # ((x+y)) -> $ (x+y) $
    text = re.sub(r"\(\(([^()\r\n]{1,160})\)\)", lambda m: f"$({m.group(1).strip()})$", text)
    return re.sub(r"\(([^()\r\n]{1,160})\)", repl, text)

# ---------- matrix fixes ----------
MATH_BLOCK_RE  = re.compile(r"\$\$([\s\S]*?)\$\$", re.MULTILINE)
MATRIX_ENV_RE  = re.compile(r"\\begin\{(bmatrix|pmatrix|vmatrix|Bmatrix|Vmatrix|matrix)\}([\s\S]*?)\\end\{\1\}", re.MULTILINE)

def _fix_matrix_rows(env_body: str) -> str:
    rows_in  = env_body.strip("\n").splitlines()
    rows_out: List[str] = []
    for i, raw in enumerate(rows_in):
        line = raw.rstrip()
        if not line:
            rows_out.append(line); continue
        # move trailing [3pt] into a proper \\[3pt]
        m = re.match(r"^(.*?)(?<!\\)\[\s*(\d+pt)\s*\]\s*$", line)
        if m:
            core = m.group(1).rstrip()
            pt   = m.group(2)
            if re.search(r"\\\\(\[\d+pt\])?\s*$", core):
                core = re.sub(r"\\\\(\[\d+pt\])?\s*$", r"\\", core)
            rows_out.append(f"{core}\\\\[{pt}]")
        else:
            if re.search(r"(\\\\(\[\d+pt\])?\s*|&\s*)$", line):
                rows_out.append(line)
            else:
                is_last_nonempty = all(not r.strip() for r in rows_in[i+1:])
                rows_out.append(line if is_last_nonempty else f"{line}\\\\")
    return "\n".join(rows_out)

def fix_matrices_in_math_blocks(text: str) -> str:
    def fix_env(m: Match[str]) -> str:
        env, body = m.group(1), m.group(2)
        return f"\\begin{{{env}}}\n{_fix_matrix_rows(body)}\n\\end{{{env}}}"
    def repl_math(m: Match[str]) -> str:
        inner = m.group(1)
        inner = MATRIX_ENV_RE.sub(fix_env, inner)
        return f"$${inner}$$"
    return MATH_BLOCK_RE.sub(repl_math, text)

# ---------- spacing & normalization (v4.2) ----------
def fix_inline_spacing(text: str) -> str:
    # 0) Strip inner spaces immediately inside inline math: $ x $ -> $x$
    text = re.sub(r"\$(\s*)([^$]*?)(\s*)\$", r"$\2$", text)

    # 1) Ensure a space before $ when attached to a word/number: word$ -> word $
    text = re.sub(r"([A-Za-z0-9])\$(?=[^$])", r"\1 $", text)

    # 2) Ensure a space after $math$ when followed by a word/number: $x$word -> $x$ word
    text = re.sub(r"\$([^$]+)\$([A-Za-z0-9])", r"$\1$ \2", text)

    # 3) Collapse any remaining inner spaces around math content (safety)
    text = re.sub(r"\$\s+([^\$]*?)\s+\$", r"$\1$", text)

    # 4) Remove a space before punctuation after inline math: $x$ , -> $x$,
    text = re.sub(r"\$\s+([,.;:!?])", r"$\1", text)

    # 5) Normalize spaces around inline math only when surrounded by spaces
    text = re.sub(r"\s+\$(.+?)\$\s+", r" $\1$ ", text)

    return text

def normalize_dollars(text: str) -> str:
    text = re.sub(r"\${3,}", "$$", text)
    # one-line $$...$$ normalization
    text = re.sub(r"\$\$\r?\n([^\r\n]+)\r?\n\$\$", r"$$\1$$", text)
    return text

# ---------- master pipeline ----------
def convert(text: str) -> str:
    protected, sent = _protect(text)
    protected = convert_code_fences(protected)
    protected = convert_backslash_brackets(protected)
    protected = convert_square_bracket_blocks(protected)
    protected = fix_matrices_in_math_blocks(protected)
    protected = protect_outer_math_parens(protected, sent)
    protected = _protect_math(protected, sent)
    protected = convert_token_paren_numeric(protected)
    protected = convert_inline_parentheses(protected)
    protected = fix_inline_spacing(protected)
    protected = normalize_dollars(protected)
    return _unprotect(protected, sent)

def main():
    src = get_clipboard() or sys.stdin.read()
    out = convert(src)
    set_clipboard(out)
    # do NOT print (prevents aText double-insert)
    # sys.stdout.write(out)

if __name__ == "__main__":
    main()
