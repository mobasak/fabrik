# Markdown Cheatsheet

Quick reference for writing clean, AI-friendly Markdown.

---

## Headings
```md
# H1 – Title (one per document)
## H2 – Section
### H3 – Subsection
#### H4
```

## Emphasis
```md
**Bold** — importance
*Italic* — nuance
***Bold italic***
```

## Lists
```md
- Bullet item
- Bullet item
  - Nested item

1. First
2. Second
3. Third

- [ ] Not done
- [x] Done
```

## Code
````md
Inline: `git status`

Block:
```python
def hello():
    print("Hello")
```
````

Rules: triple backticks, always specify language if known, blank line before and after.

## Blockquotes
```md
> This is a blockquote
>> Nested quote
```

## Links & Images
```md
[Link text](https://example.com)
[Local file](docs/spec.md)
![Alt text](image.png)
```

## Tables
```md
| Column A | Column B |
|----------|----------|
| A1       | B1       |

| Left | Center | Right |
|:-----|:------:|------:|
```

## Horizontal Rule
```md
---
```

## Comments
```md
<!-- Not rendered -->
```

## Escaping
```md
\*Not italic\*
\# Not a heading
```

---

## AI-Friendly Markdown Rules

These matter for prompt quality and RAG retrieval:

| Rule | Why |
|---|---|
| One H1 per document | Semantic root for chunking |
| No skipped heading levels (## → ### not ## → ####) | Preserves hierarchy |
| Blank lines around headings, lists, code blocks | Parser boundary signals |
| Fenced code blocks only (never indented code) | AI treats indented code inconsistently |
| Always specify code language | Enables syntax-aware processing |
| Meaningful link text (not "click here") | Retrieval anchor |
| Alt text on images | Accessibility + AI description |
| Keep tables simple and atomic | Multi-line cells break parsers |
| No commented-out content blocks | Confuses AI + pollutes diffs |
| Structure before wording | Headings and lists first, prose second |

---

## Minimal Markdown (80/20)

If you know only this, you are productive:

```md
# Title
## Section
- Bullet
- Bullet
**Important**
```code block```
```
