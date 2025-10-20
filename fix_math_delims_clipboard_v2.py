#!/usr/bin/env python3
import os, re, sys, shutil, subprocess
from typing import Optional, Match, List, Tuple

def _run(cmd: list, input_text: Optional[str] = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        input=input_text.encode('utf-8') if input_text is not None else None,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )

def get_clipboard() -> str:
    if sys.platform == 'darwin':
        p = _run(['pbpaste']); return p.stdout.decode('utf-8', errors='ignore')
    elif os.name == 'nt':
        p = _run(['powershell', '-NoProfile', '-Command', 'Get-Clipboard'])
        return p.stdout.decode('utf-8', errors='ignore')
    else:
        if shutil.which('xclip'):
            return _run(['xclip', '-selection', 'clipboard', '-o']).stdout.decode('utf-8', errors='ignore')
        if shutil.which('xsel'):
            return _run(['xsel', '--clipboard', '--output']).stdout.decode('utf-8', errors='ignore')
        return sys.stdin.read()

def set_clipboard(text: str) -> None:
    if sys.platform == 'darwin':
        _run(['pbcopy'], input_text=text)
    elif os.name == 'nt':
        _run(['powershell', '-NoProfile', '-Command', 'Set-Clipboard -Value ([Console]::In.ReadToEnd())'], input_text=text)
    else:
        if shutil.which('xclip'):
            _run(['xclip', '-selection', 'clipboard'], input_text=text); return
        if shutil.which('xsel'):
            _run(['xsel', '--clipboard', '--input'], input_text=text); return
        sys.stdout.write(text)

BACKTICK_FENCE_RE = re.compile(r"```[^\n]*\n[\s\S]*?\n```", re.MULTILINE)
INLINE_CODE_RE   = re.compile(r"`[^`\n]*`")

def _protect(text: str) -> Tuple[str, List[str]]:
    sentinels: List[str] = []
    def repl_fence(m: Match[str]) -> str:
        sentinels.append(m.group(0)); return f"@@CODEFENCE_{len(sentinels)-1}@@"
    text = BACKTICK_FENCE_RE.sub(repl_fence, text)
    def repl_inline(m: Match[str]) -> str:
        sentinels.append(m.group(0)); return f"@@INLINE_{len(sentinels)-1}@@"
    text = INLINE_CODE_RE.sub(repl_inline, text)
    return text, sentinels

def _unprotect(text: str, sentinels: List[str]) -> str:
    def repl(m: Match[str]) -> str:
        return sentinels[int(m.group(1))]
    return re.sub(r"@@(?:CODEFENCE|INLINE)_(\d+)@@", repl, text)

LATEX_TOKENS_RE = re.compile(
    r"(\\frac|\\partial|\\nabla|\\mathbf|\\mathrm|\\mathbb|\\vec|\\hat|\\dot|\\ddot|"
    r"\\sum|\\int|\\cdot|\\alpha|\\beta|\\gamma|\\delta|\\theta|\\lambda|\\mu|"
    r"\\sigma|\\phi|\\psi|\\Omega|\\infty|\\leq|\\geq|\\neq|\\approx|\\rightarrow|"
    r"\\left|\\right|\\begin|\\end|\\displaystyle|\\boxed)"
)

MATHISH_OP_RE = re.compile(r"[=+\-*/^_]|\\cdot|\\times|\\pm")
def looks_like_latex(s: str) -> bool:
    return bool(LATEX_TOKENS_RE.search(s))

def looks_like_mathish(s: str) -> bool:
    if LATEX_TOKENS_RE.search(s): return True
    if MATHISH_OP_RE.search(s): return True
    if re.search(r"\bT\s*=\s*T\(", s): return True
    if re.search(r"\b[dD][xyztr]\b", s): return True
    if len(s) > 120: return False
    if s.count(" ") > 6 and not MATHISH_OP_RE.search(s): return False
    return False

def convert_code_fences(text: str) -> str:
    def repl(m: Match[str]) -> str:
        fence = m.group(0)
        first = fence.splitlines()[0].strip()
        body = "\n".join(fence.splitlines()[1:-1]).strip()
        if first.startswith("```latex") or first.startswith("```tex"):
            return f"$$\n{body}\n$$"
        return fence
    return BACKTICK_FENCE_RE.sub(repl, text)

def convert_backslash_brackets(text: str) -> str:
    text = re.sub(r"\\\[\s*([\s\S]*?)\s*\\\]", r"$$\n\1\n$$", text)
    text = re.sub(r"\\\(\s*([^\n]*?)\s*\\\)", r"$\1$", text)
    return text

def convert_square_bracket_blocks(text: str, aggressive: bool = True) -> str:
    def repl(m: Match[str]) -> str:
        inner = m.group(1).strip()
        if aggressive or looks_like_latex(inner) or looks_like_mathish(inner):
            return f"\n$$\n{inner}\n$$\n"
        return m.group(0)
    pattern = r"(?:^|\n\s*\n)\s*\[\s*\n?([\s\S]*?)\n?\s*\]\s*(?=\n\s*\n|$)"
    return re.sub(pattern, repl, text)

def convert_inline_parentheses(text: str, aggressive: bool = True) -> str:
    def is_link(ctx: str) -> bool:
        return re.search(r"\]\([^)]+\)$", ctx) is not None
    def repl(m: Match[str]) -> str:
        inner = m.group(1)
        if "\n" in inner or "[" in inner or "]" in inner: 
            return m.group(0)
        ctx = m.string[max(0, m.start()-4):m.end()]
        if is_link(ctx): return m.group(0)
        if aggressive:
            if looks_like_latex(inner) or looks_like_mathish(inner) or re.match(r"^[A-Za-z0-9,;+\-*/^_=\.\s]+$", inner):
                return f"${inner.strip()}$"
        else:
            if looks_like_latex(inner) or looks_like_mathish(inner):
                return f"${inner.strip()}$"
        return m.group(0)
    text = re.sub(r"\(\(([^()\n]{1,160})\)\)", lambda m: f"$({m.group(1).strip()})$", text)
    return re.sub(r"\(([^\n()]{1,160})\)", repl, text)

def normalize_dollars(text: str) -> str:
    text = re.sub(r"\${3,}", "$$", text)
    text = re.sub(r"\$\s+([^\$]+?)\s+\$", r"$\1$", text)
    text = re.sub(r"\$\$\n([^\n]+)\n\$\$", r"$$\1$$", text)
    return text

def convert(text: str, aggressive: bool = True) -> str:
    protected, sentinels = _protect(text)
    protected = convert_code_fences(protected)
    protected = convert_backslash_brackets(protected)
    protected = convert_square_bracket_blocks(protected, aggressive=aggressive)
    protected = convert_inline_parentheses(protected, aggressive=aggressive)
    protected = normalize_dollars(protected)
    return _unprotect(protected, sentinels)

def main():
    aggressive = True
    if '--conservative' in sys.argv:
        aggressive = False
    if len(sys.argv) == 1 or (len(sys.argv) == 2 and sys.argv[1] in {'--clipboard','--conservative'}):
        src = get_clipboard() or sys.stdin.read()
        out = convert(src, aggressive=aggressive)
        set_clipboard(out)
        sys.stdout.write(out); return
    with open(sys.argv[1], 'r', encoding='utf-8') as f:
        src = f.read()
    out = convert(src, aggressive=aggressive)
    if len(sys.argv) >= 3:
        with open(sys.argv[2], 'w', encoding='utf-8') as f:
            f.write(out)
    else:
        sys.stdout.write(out)

if __name__ == '__main__':
    main()
