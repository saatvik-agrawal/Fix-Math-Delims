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

def _unprotect_inl_only(text: str, sent: List[str]) -> str:
    return re.sub(r"@@INL_(\d+)@@", lambda m: sent[int(m.group(1))], text)

# ---------- detectors ----------
LATEX_TOKENS_RE = re.compile(
    r"(\\frac|\\partial|\\nabla|\\mathbf|\\mathrm|\\mathbb|\\vec|\\hat|\\dot|\\ddot|"
    r"\\sum|\\int|\\cdot|\\alpha|\\beta|\\gamma|\\delta|\\theta|\\lambda|\\mu|"
    r"\\sigma|\\phi|\\psi|\\Omega|\\infty|\\leq|\\geq|\\neq|\\approx|\\rightarrow|"
    r"\\left|\\right|\\begin|\\end|\\displaystyle|\\boxed)"
)
MATHISH_OP_RE = re.compile(r"[=+\-*/^_]")
def looks_like_latex(s: str) -> bool: return bool(LATEX_TOKENS_RE.search(s))

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
    s = text; stack=[]; pairs=[]
    for i,ch in enumerate(s):
        if ch=='(':
            stack.append(i)
        elif ch==')' and stack:
            start=stack.pop(); pairs.append((start,i))
    if not pairs: return text

    def is_math_outer(content: str) -> bool:
        if '$' in content: return False
        c=content.strip()
        if len(c)<5: return False
        if MATHISH_OP_RE.search(c) or looks_like_latex(c): return True
        return False

    cand=[]
    for a,b in pairs:
        inner=s[a+1:b]
        if is_math_outer(inner): cand.append((a,b))
    if not cand: return text
    cand.sort(key=lambda t:(t[0],-t[1]))

    selected=[]
    for a,b in cand:
        if any(pa<=a and b<=pb for (pa,pb) in selected): continue
        selected.append((a,b))

    out=[]; pos=0
    for a,b in sorted(selected,key=lambda t:t[0]):
        if a<pos: continue
        out.append(s[pos:a])
        inner=s[a+1:b].strip()
        token=f"@@INL_{len(sent)}@@"
        sent.append(f"$${inner}$$" if ("\n" in inner or "\\begin{" in inner) else f"${inner}$")
        out.append(token); pos=b+1
    out.append(s[pos:])
    return "".join(out)

# ---------- inline conversions ----------
def convert_token_paren_numeric(text: str) -> str:
    patt = re.compile(r"(?P<pre>[A-Za-z0-9])\(\s*(?P<inner>[A-Za-z0-9 ,+\-*/^_=.:;\\]+?)\s*\)")
    return patt.sub(lambda m: f"${m.group('pre')}({m.group('inner').strip()})$", text)

def convert_inline_parentheses(text: str) -> str:
    ALLOW={"x","y","z","T","v","u"}
    def is_inline_math_candidate(s: str) -> bool:
        if looks_like_latex(s): return True
        if any(ch in s for ch in "=+*/^_"): return True
        if re.search(r"\d", s): return True
        if re.search(r"^[A-Za-z]\s*\([^()\n]*\)$", s): return True
        if s in ALLOW or re.match(r"^d[A-Za-z]+$", s): return True
        return False

    def repl(m: Match[str]) -> str:
        inner=m.group(1)
        if "\n" in inner or "[" in inner or "]" in inner or "$" in inner: return m.group(0)
        s=inner.strip()
        if s in ALLOW or re.match(r"^d[A-Za-z]+$", s): return f"${s}$"
        if is_inline_math_candidate(s): return f"${s}$"
        return m.group(0)

    text = re.sub(r"\(\(([^()\r\n]{1,160})\)\)", lambda m: f"$({m.group(1).strip()})$", text)
    return re.sub(r"\(([^()\r\n]{1,160})\)", repl, text)

# ---------- math block regex ----------
MATH_BLOCK_RE  = re.compile(r"\$\$([\s\S]*?)\$\$", re.MULTILINE)

# Include 'cases' along with matrix-like envs
MATRIX_ENV_RE  = re.compile(
    r"\\begin\{(bmatrix|pmatrix|vmatrix|Bmatrix|Vmatrix|matrix|cases)\}([\s\S]*?)\\end\{\1\}",
    re.MULTILINE
)

# ---------- line/row fixers ----------
def _fix_matrix_rows(env_body: str) -> str:
    rows_in  = env_body.strip("\n").splitlines()
    rows_out: List[str] = []
    for i, raw in enumerate(rows_in):
        line = raw.rstrip()
        if not line:
            rows_out.append(line); continue

        # 1) Single "\" at EOL -> "\\" (proper break)
        line = re.sub(r"(?<!\\)\\\s*$", r"\\", line)

        # 2) Move trailing [3pt] into \\[3pt]
        m = re.match(r"^(.*?)(?<!\\)\[\s*(\d+pt)\s*\]\s*$", line)
        if m:
            core = m.group(1).rstrip()
            pt   = m.group(2)
            # If already ends with \\ or \\[..], reduce to one \ then append \\[pt]
            if re.search(r"\\\\(\[\d+pt\])?\s*$", core):
                core = re.sub(r"\\\\(\[\d+pt\])?\s*$", r"\\", core)
            rows_out.append(f"{core}\\\\[{pt}]")
            continue

        # 3) If not last non-empty line and not already ended with \\ or &, append \\.
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

# Catch-all: single "\" at EOL inside ANY $$...$$ block
def fix_trailing_single_slashes_in_math(text: str) -> str:
    def repl(m: Match[str]) -> str:
        body = m.group(1)
        lines = body.splitlines()
        out = [re.sub(r"(?<!\\)\\\s*$", r"\\", ln) for ln in lines]
        return "$$\n" + "\n".join(out) + "\n$$"
    return MATH_BLOCK_RE.sub(repl, text)

# Promote envs found inside inline $...$ to display
ENV_IN_INLINE_RE = re.compile(r"\$([^$]*\\begin\{[A-Za-z*]+\}[\s\S]*?\\end\{[A-Za-z*]+\}[^$]*)\$")
def promote_envs_inline_to_display(text: str) -> str:
    return ENV_IN_INLINE_RE.sub(r"$$\1$$", text)

# ---------- spacing/normalization ----------
def ensure_blank_lines_around_display(text: str) -> str:
    # Guarantee a blank line before and after $$...$$
    text = re.sub(r"[ \t]*\$\$\s*\n", r"\n$$\n", text)
    text = re.sub(r"\n\s*\$\$\s*[ \t]*", r"\n$$", text)  # normalize borders
    # Insert blank line before $$ if missing
    text = re.sub(r"([^\n])\n\$\$", r"\1\n\n$$", text)
    # Insert blank line after $$ if missing
    text = re.sub(r"\$\$\n([^\n])", r"$$\n\n\1", text)
    # Specific: if $$ followed immediately by a numbered list, ensure blank line
    text = re.sub(r"\$\$\s*\n\s*(?=(\d+\.) )", "$$\n\n", text)
    return text

def fix_inline_spacing(text: str) -> str:
    # Remove spaces immediately inside SINGLE-$ borders (not $$)
    text = re.sub(r"(?<!\$)\$\s+", "$", text)          # "$ x" -> "$x"
    text = re.sub(r"\s+\$(?!\$)", "$", text)           # "x $" -> "x$"
    # Ensure a space after $math$ when glued to alnum
    text = re.sub(r"\$([^$]+)\$([A-Za-z0-9])", r"$\1$ \2", text)
    # Normalize spaces around inline math (when surrounded by spaces)
    text = re.sub(r"\s+\$(.+?)\$\s+", r" $\1$ ", text)
    # NEW: collapse any "$  something" that slipped through
    text = re.sub(r"(?<!\$)\$\s+([^\$])", r"$\1", text)  # "$ w" -> "$w"
    return text


def normalize_dollars(text: str) -> str:
    text = re.sub(r"\${3,}", "$$", text)
    text = re.sub(r"\$\$\r?\n([^\r\n]+)\r?\n\$\$", r"$$\1$$", text)  # one-line $$...$$
    return text

# ---------- master pipeline (v4.8) ----------
def convert(text: str) -> str:
    protected, sent = _protect(text)
    protected = convert_code_fences(protected)
    protected = convert_backslash_brackets(protected)
    protected = convert_square_bracket_blocks(protected)

    # Fix any pre-existing $$…$$ blocks early
    protected = fix_matrices_in_math_blocks(protected)

    # Protect existing $$…$$
    protected = _protect_math(protected, sent)

    # Create new math from parentheses
    protected = protect_outer_math_parens(protected, sent)

    # Inline conversions
    protected = convert_token_paren_numeric(protected)
    protected = convert_inline_parentheses(protected)

    # Promote inline envs to display
    protected = promote_envs_inline_to_display(protected)

    # Materialize @@INL_*@@ for late passes
    protected = _unprotect_inl_only(protected, sent)

    # LATE PASSES (order matters):
    # 1) Generic single "\" -> "\\" inside ANY $$...$$
    protected = fix_trailing_single_slashes_in_math(protected)
    # 2) Env-specific row logic (matrices + cases)
    protected = fix_matrices_in_math_blocks(protected)

    # Spacing and normalization
    protected = ensure_blank_lines_around_display(protected)
    protected = fix_inline_spacing(protected)
    protected = normalize_dollars(protected)

    # Restore protected content
    return _unprotect(protected, sent)

def main():
    src = get_clipboard() or sys.stdin.read()
    out = convert(src)
    set_clipboard(out)

if __name__ == "__main__":
    main()
