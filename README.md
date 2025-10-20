## How to use?

1. Download and save the Python file in a permanent place in your directory.
2. Then make it executable using the below command.
3. Use Atext or similar tools to use this as quick shortcut to convert copied content into Obsidian Ready Math. See the Atext section below for help with using atext.

## Which Python file?

### Use version 2 for aggressive conversion.

This version helpful if you are copying long paragraphs with multiple bits of math.

* **Paragraph** **`[ ... ]` blocks** now convert to** **`$$ ... $$` even if they’re simple algebra (no explicit** **`\frac`, etc.).
* **Inline** **`( ... )`** converts to** **`$...$` when it looks “math-ish” (operators, equals, dx/dy/dz,** **`T = T(…)`, etc.).
* **Double parens** `((...))` handled first and replaced with a single inline** **`$ (... ) $`.
* Still** ****won’t touch** fenced code** **`…` or inline code** **``…``.

### Use version 1 for light conversion.

Helpful if you are just copying specific parts of a longer response and just touching the math.

* Converts:
  * `\(...\)` →** **`$...$` (inline math)
  * `\[...\]` →** **`$$ ... $$` (display math)
  * `latex …<span class="Apple-converted-space"> </span>`→** **`$$ … $$` (optional)
  * Paragraph** **`[ ... ]` blocks that look like LaTeX →** **`$$ … $$`
* **Does not** touch fenced code blocks (`…`) or inline code (``…``).

## AText Snippet for MacOS.

1. Select an abbreviation and optionally a hotkey.
2. Then select Script followed by Shell.
3. Now paste the below code snippet in the provided space.

```
#!/bin/zsh
# Get clipboard, run converter, and replace clipboard
/usr/bin/python3 "/Users/username/fix_math_delims_clipboard.py" # moodify with your own file path
# Paste result
osascript -e 'tell application "System Events" to keystroke "v" using command down'
```
