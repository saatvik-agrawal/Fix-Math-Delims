# 🧮 Fix-Math-Delims (for macOS)

**Seamlessly copy math from ChatGPT (on macOS) to Obsidian with perfect LaTeX rendering. No additional plugins like 'linter' required in Obsidian.**

---

## 🚀 Overview

When you copy mathematical explanations from ChatGPT into** ** **Obsidian** , the math often breaks because:

* ChatGPT uses** **`\[ ... \]` and** **`\( ... \)` delimiters,
* NotebookLM and Obsidian expect** **`$...$` and** **`$$...$$`,
* Matrices, vectors, and parentheses sometimes nest incorrectly, and
* Markdown snippets can produce strange placeholder tokens.

This tool —** ****Fix-Math-Delims** — automatically converts copied Markdown to** ** **Obsidian-compatible math** , preserving readability and fixing formatting on the fly.

---

## ✨ Features

| Feature                                  | Description                                                                                                              |
| :--------------------------------------- | :----------------------------------------------------------------------------------------------------------------------- |
| 🔄**Clipboard Automation**         | Automatically converts whatever you copied from ChatGPT and pastes back into your clipboard.                            |
| 🧩**Bracket Conversion**           | Converts `\[...\]` and `\(...\)` to `$$...$$` and `$...$`.                                                       |
| 🧠**Smart Inline Math Detection**  | Wraps inline math (like `(x+y)` or `(dT=2(1)+3(0))`) in `$...$` without breaking plain English parentheses.        |
| 🧱**Matrix Repair**                | Fixes `bmatrix`, `pmatrix`, etc., by adding proper `\\` and `[3pt]` row spacing.                                 |
| 🧾**Display-Block Conversion**     | Converts `[ ... ]` multi-line equations into full `$$ ... $$` blocks.                                                |
| 🪄**No Placeholder Leaks**         | v4.3 fixes prior issues with `@@INL_###@@` tokens by reordering the pipeline.                                          |
| ✍️**aText / Hotkey Integration** | Fully compatible with macOS automation tools like**aText** ,  **Keyboard Maestro** , or  **Raycast** . |

---

## 🧰 Requirements

| System         | Version                                     |
| :------------- | :------------------------------------------ |
| macOS          | ✅ Tested on macOS 14+                      |
| Python         | ≥ 3.9 (ships with macOS)                   |
| Clipboard Tool | `pbpaste` / `pbcopy` (default on macOS) |

---

## 🛠️ Installation

1. **Download**
   Simply download the "fix_math_delims_clipboard.py" file. I recommend you to save it in a permanent directory such as your user home folder to avoid accidental deletions.

2. **Ensure executable permission**

   ```bash
   chmod +x fix_math_delims_clipboard.py # enter your full file path.
   ```
3. **(Optional) Install dependencies**
   None required — only Python standard library.
4. **Test manually**
   Copy some ChatGPT text containing** **`\[ ... \]` math, then run:
   **IMP: Ensure you copy the entire ChatGPT output using the copy button in ChatGPT.**

   ```bash
   python3 fix_math_delims_clipboard.py # again, enter full file path.
   ```

   Paste anywhere — the math should render perfectly in Obsidian.

---

## ⚡ Quick Automation with aText (Mac)

To bind this to a keyboard shortcut (so you do not need to manually execute the file each time), consider using macOS Shortcuts, macOS automator or AText. AText is a popular text replacement utility available for macOS and Windows. Below is how automate it with AText.

1. Open** ****AText** → add a** ** **New Snippet** .
2. Select **Scipt** > then **Shell**.
3. Paste this script as the** ** **snippet body** :
   ```bash
   #!/bin/zsh
   /opt/homebrew/bin/python3 "/Users/YOURNAME/Github Repos/Fix-Math-Delims/fix_math_delims_clipboard.py" # Get clipboard, run converter, and replace clipboard
   osascript -e 'tell application "System Events" to keystroke "v" using command down' # Paste result
   ```
4. Assign a hotkey (e.g.** **`⌘⇧V`) or abbreviation (e.g.** **`gptmath`).

Now, just:

* Copy from ChatGPT → hit your aText trigger → automatically pasted into Obsidian.
  Instant clean** **`$...$` and** **`$$...$$` math!

---

## 🧩 Examples

### **Input (from ChatGPT)**

```
[
\mathbf{dr} =
\begin{bmatrix}
dx[3pt]
dy[3pt]
dz
\end{bmatrix}
]
```

### **Output (copied into Clipboard)**

```markdown
$$
\mathbf{dr} =
\begin{bmatrix}
dx\\[3pt]
dy\\[3pt]
dz
\end{bmatrix}
$$
```

---

### **Inline Example**

**Input**

```
If you move 1 m east (x), 0 m north (y): (dT=2(1)+3(0)=2) °C → warmer.
```

**Output**

```
If you move 1 m east $x$, 0 m north $y$: $dT=2(1)+3(0)=2$ °C → warmer.
```

---

## 🧠 How It Works

The script processes your clipboard through several** ** **phases** :

1. **Protection Layer**
   Temporarily hides inline code, code fences, and existing** **`$$...$$` blocks.
2. **Conversions**
   * Converts** **`\[...\]` →** **`$$...$$`
   * Converts** **`\(...\)` →** **`$...$`
   * Converts** **`[…]` blocks →** **`$$...$$`
   * Repairs matrices and spacing
3. **Heuristic Wrapping**
   Detects likely math expressions (e.g.,** **`(x+y)`,** **`(dT=2(1)+3(0))`)
   and wraps them in** **`$...$`.
4. **Outer Parentheses Logic**
   Wraps only the** ***outermost* math expressions, preventing nested** **`$` errors.
5. **Spacing Normalization**
   Cleans** **`$ x $ → $x$`,** **`$x$word → $x$ word`, etc.
6. **Clipboard Replacement**
   The final Markdown is written back to clipboard automatically.

---

## 🧩 Folder Layout

```
Fix-Math-Delims/
├── fix_math_delims_clipboard.py
├── README.md
└── Dev Files/
    ├── fix_math_delims_clipboard_v1.py
    ├── fix_math_delims_clipboard_v4.py
    ├── more notes.md
    ├── README_OLD.md

```
---

## 🧩 Troubleshooting

| Problem                           | Likely Cause                                                        | Fix                                       |
| :-------------------------------- | :------------------------------------------------------------------ | :---------------------------------------- |
| aText says “no file”            | Ensure your script path has**no leading space** after quotes. |                                           |
| Clipboard doesn’t change         | macOS automation may require accessibility permission for aText.    |                                           |

---

## 🧭 Why It Matters

ChatGPT exports Markdown in** ****non-standard LaTeX syntax** — designed for web display, not local Markdown engines.
Obsidian (and many static site generators) rely on** ** **MathJax** , which expects** **`$...$` and** **`$$...$$` delimiters.

This script bridges that formatting gap — enabling a** ****smooth copy-paste workflow** from AI tools to your personal knowledge system.

---

## 🤝 Contributing

Pull requests and issues are welcome!
Some future improvements:

* Detect block environments (`align`,** **`cases`) more elegantly.
* Add support for Windows auto-clipboard flow.
* Possible Chrome based browser extension for one-click copy directly in the browser.
* Add GUI toggle for “inline-only” vs “block-only” mode.
* Future plans to include in-text copy from chatGPT, so you do not have to copy the entire output.

---

## 🪪 License

MIT License © 2025 Saatvik Agrawal
Use freely, modify boldly, attribute kindly.
