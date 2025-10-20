## What is this?

A simple snippet using Python to convert copied text from ChatGPT into text that is pastable and legible in obsidian. The copied text then does not require any additional plugins or changes in Obsidian.

## How to use?

1. Download and save the Python file in a permanent place in your directory.
2. Then make it executable using the below command.
   ```
   chmod +x fix_math_delims_clipboard_v2.py # write the full file path
   ```
3. Use Atext or similar tools to use this as quick shortcut to convert copied content into Obsidian Ready Math. See the Atext section below for help with using atext.

## Which Python file?

### Use version 2 for aggressive conversion.

This version helpful if you are copying long paragraphs with multiple bits of math.

* **Paragraph** **`[ ... ]` blocks** now convert to** **`$$ ... $$` even if they’re simple algebra (no explicit** **`\frac`, etc.).
* **Inline** **`( ... )`** converts to** **`$...$` when it looks “math-ish” (operators, equals, dx/dy/dz,** **`T = T(…)`, etc.).
* **Double parens** `((...))` handled first and replaced with a single inline** **`$ (... ) $`.
* Still** ****won’t touch** fenced code** **`…` or inline code** **``…``.

#### Additional Updates to V2

* Converts bracket blocks first, then** ****protects** **…**…**** from further edits.
* Converts** ****token+paren** as a unit (e.g.,** **`2(1)` →** **`$2(1)$`,** **`T(x,y)` →** **`$T(x,y)$`).
* Cleans** ****spacing** around inline math (before/after words and list dashes).
* Merges adjacent inline blocks like** **`$\nabla T$\cdot$\mathbf{dr}$` →** **`$\nabla T \cdot \mathbf{dr}$`.

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
/usr/bin/python3 "/Users/username/fix_math_delims_clipboard.py" # moodify with your own file path; Use Homebrew python if you have it; otherwise /usr/bin/python3
# Paste result
osascript -e 'tell application "System Events" to keystroke "v" using command down'
```

# Notes

- File path names are case and whitespace sensitive.
- Remove "\\" which are replaced for " " (spaces) in file path when copying file path from finder in MacOS.
