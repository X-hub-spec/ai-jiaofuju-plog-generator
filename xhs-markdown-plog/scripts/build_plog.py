#!/usr/bin/env python3
"""Build a simple Markdown-style XHS PLOG HTML deck from JSON config."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
from html import escape
from pathlib import Path
from typing import Any


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


def slugify(value: str) -> str:
    value = re.sub(r"\s+", "-", value.strip().lower())
    value = re.sub(r"[^a-z0-9\u4e00-\u9fff-]+", "", value)
    return value[:64] or "asset"


def copy_asset(src: str, asset_dir: Path, used_names: set[str]) -> str:
    path = Path(src).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"Image asset not found: {src}")

    stem = slugify(path.stem)
    suffix = path.suffix.lower() or ".png"
    name = f"{stem}{suffix}"
    index = 2
    while name in used_names:
        name = f"{stem}-{index}{suffix}"
        index += 1
    used_names.add(name)

    dest = asset_dir / name
    shutil.copy2(path, dest)
    return f"assets/{name}"


def inline_markdown(text: str) -> str:
    text = escape(text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    return text


def highlight_code_line(line: str) -> str:
    html = escape(line)
    html = re.sub(r"(&quot;[^&]*?&quot;|&#x27;[^&]*?&#x27;)", r'<span class="code-string">\1</span>', html)
    html = re.sub(r"(^|\s)(--[\w-]+)", r'\1<span class="code-flag">\2</span>', html)
    html = re.sub(r"(^|\s)(/[^\s<]+)", r'\1<span class="code-path">\2</span>', html)
    html = re.sub(r"^(\s*)([A-Za-z_][\w.-]*)(?=\s|$)", r'\1<span class="code-command">\2</span>', html)
    return html


def render_code_block(code: str, language: str = "") -> str:
    label = escape(language.strip() or "Code")
    lines = "\n".join(
        f'<span class="code-line">{highlight_code_line(line)}</span>'
        for line in code.rstrip("\n").split("\n")
    )
    return f'<pre class="code-block"><span class="code-label">{label}</span><code>{lines}</code></pre>'


def split_long_paragraph(text: str, max_chars: int = 170) -> list[str]:
    if len(text) <= max_chars:
        return [text]

    sentences = re.split(r"(?<=[。！？!?；;])", text)
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        if not sentence:
            continue
        if current and len(current) + len(sentence) > max_chars:
            chunks.append(current.strip())
            current = sentence
        else:
            current += sentence
    if current.strip():
        chunks.append(current.strip())
    return chunks or [text]


def parse_markdown(content: str, asset_refs: list[str]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    paragraph: list[str] = []
    list_items: list[str] = []
    code_lines: list[str] = []
    code_language = ""
    in_code = False

    def flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            text = " ".join(line.strip() for line in paragraph).strip()
            for chunk in split_long_paragraph(text):
                blocks.append({"type": "p", "text": chunk})
            paragraph = []

    def flush_list() -> None:
        nonlocal list_items
        if list_items:
            blocks.append({"type": "ul", "items": list_items})
            list_items = []

    def flush_code() -> None:
        nonlocal code_lines, code_language, in_code
        if in_code:
            blocks.append({"type": "code", "code": "\n".join(code_lines), "language": code_language})
            code_lines = []
            code_language = ""
            in_code = False

    for raw_line in content.replace("\r\n", "\n").split("\n"):
        line = raw_line.strip()

        fence_match = re.match(r"^```([\w.+-]*)\s*$", line)
        if fence_match:
            if in_code:
                flush_code()
            else:
                flush_paragraph()
                flush_list()
                in_code = True
                code_language = fence_match.group(1)
                code_lines = []
            continue

        if in_code:
            code_lines.append(raw_line.rstrip())
            continue

        if not line:
            flush_paragraph()
            flush_list()
            continue

        if line in {"---page---", "<!-- page -->"}:
            flush_paragraph()
            flush_list()
            blocks.append({"type": "pagebreak"})
            continue

        image_match = re.match(r"!\[([^\]]*)\]\(([^)]+)\)", line)
        asset_match = re.match(r"\{\{image:(\d+)\}\}", line)
        if image_match or asset_match:
            flush_paragraph()
            flush_list()
            if image_match:
                caption, src = image_match.groups()
                blocks.append({"type": "image", "src": src.strip(), "caption": caption.strip()})
            else:
                index = int(asset_match.group(1))
                if index >= len(asset_refs):
                    raise IndexError(f"Image index out of range: {index}")
                blocks.append({"type": "image", "src": asset_refs[index], "caption": ""})
            continue

        heading_match = re.match(r"^(#{1,3})\s+(.+)$", line)
        if heading_match:
            flush_paragraph()
            flush_list()
            level = len(heading_match.group(1))
            blocks.append({"type": f"h{level}", "text": heading_match.group(2).strip()})
            continue

        if line.startswith(">"):
            flush_paragraph()
            flush_list()
            blocks.append({"type": "quote", "text": line.lstrip(">").strip()})
            continue

        list_match = re.match(r"^[-*]\s+(.+)$", line)
        if list_match:
            flush_paragraph()
            list_items.append(list_match.group(1).strip())
            continue

        paragraph.append(line)

    flush_paragraph()
    flush_list()
    flush_code()
    return blocks


def block_weight(block: dict[str, Any], page_height: int) -> int:
    scale = page_height / 1920
    kind = block["type"]
    if kind == "pagebreak":
        return 99999
    if kind == "image":
        return int(650 * scale)
    if kind == "ul":
        return int((120 + sum(max(1, math.ceil(len(item) / 26)) * 58 for item in block["items"])) * scale)
    if kind == "quote":
        return int((150 + math.ceil(len(block["text"]) / 28) * 52) * scale)
    if kind == "code":
        lines = max(1, len(block.get("code", "").splitlines()))
        longest = max((len(line) for line in block.get("code", "").splitlines()), default=20)
        return int((160 + lines * 52 + max(0, longest - 36) * 8) * scale)
    if kind == "h1":
        return int(230 * scale)
    if kind == "h2":
        return int(190 * scale)
    if kind == "h3":
        return int(150 * scale)
    return int((95 + math.ceil(len(block["text"]) / 24) * 60) * scale)


def paginate(blocks: list[dict[str, Any]], page_height: int) -> list[list[dict[str, Any]]]:
    max_weight = int(page_height * 0.78)
    pages: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    total = 0

    for block in blocks:
        if block["type"] == "pagebreak":
            if current:
                pages.append(current)
            current = []
            total = 0
            continue

        weight = block_weight(block, page_height)
        if current and total + weight > max_weight:
            pages.append(current)
            current = [block]
            total = weight
        else:
            current.append(block)
            total += weight

    if current:
        pages.append(current)
    return pages


def render_block(block: dict[str, Any], copied_lookup: dict[str, str], asset_dir: Path, used_names: set[str]) -> str:
    kind = block["type"]
    if kind in {"h1", "h2", "h3"}:
        return f"<{kind}>{inline_markdown(block['text'])}</{kind}>"
    if kind == "p":
        return f"<p>{inline_markdown(block['text'])}</p>"
    if kind == "quote":
        return f"<blockquote>{inline_markdown(block['text'])}</blockquote>"
    if kind == "code":
        return render_code_block(block.get("code", ""), block.get("language", ""))
    if kind == "ul":
        items = "".join(f"<li>{inline_markdown(item)}</li>" for item in block["items"])
        return f"<ul>{items}</ul>"
    if kind == "image":
        src = block["src"]
        if src in copied_lookup:
            final_src = copied_lookup[src]
        elif Path(src).expanduser().suffix.lower() in IMAGE_EXTS and Path(src).expanduser().exists():
            final_src = copy_asset(src, asset_dir, used_names)
            copied_lookup[src] = final_src
        else:
            final_src = src
        caption = block.get("caption") or ""
        caption_html = f"<figcaption>{inline_markdown(caption)}</figcaption>" if caption else ""
        return f'<figure><img src="{escape(final_src)}" alt="{escape(caption)}" />{caption_html}</figure>'
    return ""


def render_html(config: dict[str, Any], pages: list[list[dict[str, Any]]], copied_lookup: dict[str, str], out_dir: Path, used_names: set[str]) -> str:
    canvas = config.get("canvas") or {}
    width = int(canvas.get("width", 1080))
    height = int(canvas.get("height", 1440))
    title = config["title"]
    subtitle = config.get("subtitle", "")
    author = config.get("author", "")
    cover_src = copied_lookup.get(config.get("cover_image", ""), "")
    theme = str(config.get("theme") or "reading").strip().lower()
    if theme not in {"reading", "pro"}:
        theme = "reading"
    theme_class = f"theme-{theme}"

    page_html: list[str] = []
    cover_image_html = f'<div class="cover-media"><img src="{escape(cover_src)}" alt="" /></div>' if cover_src else ""
    subtitle_html = f"<p class=\"subtitle\">{inline_markdown(subtitle)}</p>" if subtitle else ""
    author_html = f"<p class=\"author\">{inline_markdown(author)}</p>" if author else ""
    page_html.append(
        f"""
        <section class="page cover {theme_class}">
          {cover_image_html}
          <div class="cover-copy">
            <h1>{inline_markdown(title)}</h1>
            {subtitle_html}
            {author_html}
          </div>
        </section>
        """
    )

    for page_blocks in pages:
        content = "\n".join(render_block(block, copied_lookup, out_dir / "assets", used_names) for block in page_blocks)
        page_html.append(f'<section class="page content {theme_class}"><article>{content}</article></section>')

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{escape(title)} - PLOG</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: #e9e9e9;
      color: #171717;
      font-family: Georgia, "Times New Roman", "Songti SC", "Noto Serif CJK SC", "SimSun", serif;
    }}
    .deck {{
      width: min({width}px, calc(100vw - 24px));
      margin: 0 auto;
      padding: 28px 0 72px;
      display: grid;
      gap: 28px;
    }}
    .page {{
      width: {width}px;
      height: {height}px;
      max-width: 100%;
      aspect-ratio: {width} / {height};
      position: relative;
      overflow: hidden;
      background: var(--paper);
      box-shadow: 0 18px 52px rgba(0,0,0,.14);
      --paper: #fbf5e9;
      --ink: #2f251b;
      --muted: #806b56;
      --line: #e2d2bd;
      --cover-bg: #efe3ce;
      --cover-text: #3a2a1e;
      --accent: #8e5b2c;
      --accent-soft: rgba(190, 145, 82, .22);
      --code-bg: #151515;
      --code-text: #f2f1ed;
      --code-muted: #d3d0c8;
      --code-red: #ff5a52;
      --code-green: #5ee37b;
      --code-border: rgba(255,255,255,.08);
    }}
    .theme-pro {{
      --paper: #f4f3ee;
      --ink: #171615;
      --muted: #6d665b;
      --line: #d8d3c8;
      --cover-bg: #191716;
      --cover-text: #f4efe4;
      --accent: #d7aa49;
      --accent-soft: rgba(215, 170, 73, .22);
      --code-bg: #141414;
      --code-text: #f4f1ea;
      --code-muted: #d8d2c3;
      --code-red: #ff5d57;
      --code-green: #58e37d;
      --code-border: rgba(215,170,73,.18);
    }}
    .cover {{
      display: flex;
      flex-direction: column;
      background: var(--cover-bg);
      color: var(--cover-text);
    }}
    .cover-media {{
      width: 100%;
      height: 48%;
      margin-top: 6%;
      overflow: hidden;
      background: #fff;
    }}
    .cover-media img {{
      width: 100%;
      height: 100%;
      object-fit: contain;
      display: block;
    }}
    .cover-copy {{
      padding: 64px 72px 72px;
    }}
    h1, h2, h3, p, blockquote, ul, figure {{
      margin-top: 0;
    }}
    .cover h1 {{
      margin-bottom: 56px;
      color: var(--cover-text);
      font-size: 72px;
      line-height: 1.18;
      font-weight: 600;
      letter-spacing: 0;
    }}
    .subtitle, .author {{
      margin-bottom: 34px;
      color: var(--cover-text);
      font-size: 38px;
      line-height: 1.65;
    }}
    .author {{
      margin-top: 90px;
      padding-top: 36px;
      border-top: 4px solid #888;
      font-size: 36px;
    }}
    .content article {{
      padding: 82px 72px;
      height: 100%;
      color: var(--ink);
    }}
    .content h1 {{
      margin-bottom: 42px;
      font-size: 62px;
      line-height: 1.35;
      font-weight: 650;
    }}
    .content h2 {{
      margin: 12px 0 42px;
      font-size: 54px;
      line-height: 1.38;
      font-weight: 650;
    }}
    .content h3 {{
      margin: 10px 0 36px;
      font-size: 48px;
      line-height: 1.42;
      font-weight: 650;
    }}
    .content p {{
      margin-bottom: 46px;
      font-size: 43px;
      line-height: 1.86;
      font-weight: 400;
      letter-spacing: 0;
    }}
    .content strong {{
      font-weight: 700;
      color: var(--accent);
    }}
    code {{
      padding: 0 .18em;
      border-radius: .18em;
      background: var(--accent-soft);
      color: var(--accent);
      font-family: "SFMono-Regular", Consolas, monospace;
      font-size: .9em;
    }}
    .code-block {{
      margin: 48px 0 56px;
      padding: 44px 52px 46px;
      border: 1px solid var(--code-border);
      border-radius: 56px;
      background: var(--code-bg);
      color: var(--code-text);
      font-family: "SFMono-Regular", ui-monospace, Menlo, Consolas, monospace;
      font-size: 30px;
      line-height: 1.42;
      font-weight: 650;
      white-space: pre-wrap;
      word-break: break-word;
      box-shadow: inset 0 1px 0 rgba(255,255,255,.04), 0 16px 34px rgba(0,0,0,.12);
    }}
    .code-block code {{
      display: block;
      padding: 0;
      border-radius: 0;
      background: transparent;
      color: inherit;
      font: inherit;
    }}
    .code-label {{
      display: block;
      margin-bottom: 28px;
      color: var(--code-muted);
      font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif;
      font-size: 24px;
      font-weight: 800;
    }}
    .code-line {{
      display: block;
      min-height: 1.42em;
    }}
    .code-command {{
      color: var(--code-red);
    }}
    .code-string,
    .code-flag,
    .code-path {{
      color: var(--code-green);
    }}
    blockquote {{
      margin-bottom: 48px;
      padding-left: 28px;
      border-left: 5px solid var(--accent);
      color: var(--ink);
      font-size: 42px;
      line-height: 1.75;
    }}
    ul {{
      margin-bottom: 48px;
      padding-left: 1.35em;
      font-size: 42px;
      line-height: 1.72;
    }}
    li {{
      margin-bottom: 18px;
    }}
    figure {{
      margin: 48px 0 58px;
    }}
    figure img {{
      width: 100%;
      max-height: 680px;
      object-fit: contain;
      display: block;
      background: color-mix(in srgb, var(--paper) 88%, #fff);
    }}
    figcaption {{
      margin-top: 16px;
      color: var(--muted);
      font-size: 28px;
      line-height: 1.45;
      text-align: center;
    }}
    @media (max-width: 720px) {{
      .deck {{
        width: calc(100vw - 18px);
        gap: 18px;
      }}
    }}
  </style>
</head>
<body>
  <main class="deck">
    {"".join(page_html)}
  </main>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a Markdown-style XHS PLOG HTML deck.")
    parser.add_argument("config", help="Path to JSON config.")
    parser.add_argument("output_dir", help="Output directory.")
    args = parser.parse_args()

    config_path = Path(args.config).expanduser().resolve()
    out_dir = Path(args.output_dir).expanduser().resolve()
    asset_dir = out_dir / "assets"
    asset_dir.mkdir(parents=True, exist_ok=True)

    config = json.loads(config_path.read_text(encoding="utf-8"))
    if not config.get("title"):
        raise ValueError("Config must include title.")

    used_names: set[str] = set()
    copied_lookup: dict[str, str] = {}
    assets = [str(path) for path in config.get("assets", [])]

    cover_image = config.get("cover_image") or (assets[0] if assets else "")
    if cover_image:
        copied_lookup[cover_image] = copy_asset(cover_image, asset_dir, used_names)
        config["cover_image"] = cover_image

    asset_refs: list[str] = []
    for asset in assets:
        if asset in copied_lookup:
            asset_refs.append(copied_lookup[asset])
        else:
            copied = copy_asset(asset, asset_dir, used_names)
            copied_lookup[asset] = copied
            asset_refs.append(copied)

    content = config.get("content", "")
    blocks = parse_markdown(content, asset_refs)
    height = int((config.get("canvas") or {}).get("height", 1920))
    pages = paginate(blocks, height)
    html = render_html(config, pages, copied_lookup, out_dir, used_names)

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_text(html, encoding="utf-8")
    (out_dir / "plog-config.used.json").write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({
        "output_dir": str(out_dir),
        "html": str(out_dir / "index.html"),
        "page_count": 1 + len(pages),
        "assets": sorted(str(path.name) for path in asset_dir.iterdir())
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
