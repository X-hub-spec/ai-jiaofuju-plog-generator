---
name: xhs-markdown-plog
description: Generate Xiaohongshu/RedNote PLOG image decks from a document title, Markdown-like document content, and image assets. Use when the user asks to make a 小红书 PLOG, 图文长图, Markdown 风格图文, article-to-PLOG deck, or wants title/content/materials converted into clean vertical PLOG pages with a cover page and subsequent text/image pages.
---

# XHS Markdown PLOG

## Goal

Turn a document title, body content, and image assets into a clean Xiaohongshu PLOG deck:

- Page 1: cover page with the title and one strong image.
- Later pages: Markdown-like text and image pages.
- Style: clean article-reading layout with a cover page, generous margins, Markdown-like hierarchy, and no decorative clutter.

Current approved style families:

- `reading`: 书面阅读感. Warm paper background, dark brown/black text, restrained highlights, comfortable long-form reading.
- `pro`: 专业黑金. Deep black cover, light paper body, gold highlights, sharper business/analysis feeling.

Before generating a new PLOG, ask the user to choose between `书面阅读感` and `专业黑金` unless they already specified one of these two styles in the request. Do not offer old color routes such as orange or blue unless the user explicitly asks for more experiments.

## Workflow

1. Gather inputs:
   - Title.
   - Body content, preferably Markdown or plain text with paragraphs.
   - Image assets as absolute local paths.
   - Optional author, subtitle, page size, and output directory.
   - Style choice: ask `这次用「书面阅读感」还是「专业黑金」？` when the user has not specified it.
2. Create an output folder, usually under the current project, for example `output/xhs-markdown-plog/<slug>/`.
3. Build a JSON config for `scripts/build_plog.py`.
4. Run the script to generate `index.html` and copied assets.
5. Open/verify the HTML locally.
6. Export each `.page` element to PNG, usually `exports/page-01.png`, `page-02.png`, etc.
7. Inspect at least the cover and one content page visually before responding.

## Config Shape

Create a JSON file like this:

```json
{
  "title": "Prompt 撤退，未来属于 Loop Engineering",
  "subtitle": "可选副标题",
  "author": "作者：数字生命卡兹克",
  "cover_image": "/absolute/path/cover.webp",
  "assets": [
    "/absolute/path/image-1.webp",
    "/absolute/path/image-2.webp"
  ],
  "content": "正文 Markdown 或纯文本",
  "theme": "reading",
  "canvas": { "width": 1080, "height": 1440 }
}
```

Defaults:

- Canvas: `1080 x 1440` / `3:4`.
- Cover image: `cover_image`, or the first item in `assets`.
- Theme: `reading` or `pro`; ask the user first when missing.
- Output: `index.html`, `assets/`, and `plog-config.used.json`.

## Content Markup

The script supports a small Markdown subset:

- `#`, `##`, `###` headings.
- Blank-line-separated paragraphs.
- `- item` unordered lists.
- `> quote` blockquotes.
- `![caption](/absolute/path/image.webp)` image blocks.
- `{{image:0}}`, `{{image:1}}` to insert images from the `assets` array.
- Fenced code blocks such as <code>```bash</code>...<code>```</code>. Use these for commands, config, or code snippets.
- `---page---` or `<!-- page -->` for manual page breaks.
- Inline `**bold**` and `` `code` ``.

Prefer manual page breaks when the user cares about exact pacing. Otherwise let the script paginate automatically and adjust if a page feels too sparse or crowded.

## Layout Judgment

- Keep the first page simple: one image plus the title, optional subtitle/author.
- Do not put long body text on the cover.
- Use 1 image per page when possible; pair an image with 2-4 paragraphs if it supports the text.
- For long articles, split by semantic sections, not arbitrary character count.
- Avoid tiny text. If a page feels dense, add a page break instead of shrinking below readable size.
- Preserve the user's wording unless they ask for rewriting or condensation.
- For article PLOGs, keep body pages faithful to the source. Do not add explanatory claims, summary judgments, transition sentences, or "核心判断" style text unless those words are in the source or the user explicitly asks for commentary.
- Do not add a large heading to every body page by default. Use body-page headings only when the source already has section headings or the user asks for them.
- Highlight only exact source phrases or source sentences. Do not label highlights with "Auto Highlight", "自动高亮", or similar meta text.
- For code-reader styles, avoid visible line numbers, `//` comment prefixes, page corner marks, or artificial terminal text unless the user explicitly asks for those elements.
- Code blocks must use the approved dark rounded component:
  - Deep dark background, very large rounded corners, generous padding.
  - No top-right copy/download buttons and no decorative browser dots.
  - A small language label such as `Bash` may be shown when it helps, but avoid extra explanatory controls.
  - Internally color-highlight code tokens where useful: commands/functions in red, strings/paths/flags in green, neutral syntax in off-white.
  - Keep code content faithful to the source; do not add invented command prefixes or `//`.
- If a body page has too much blank space, first enlarge or reposition source images, adjust spacing, or merge with adjacent source text. Do not fill empty space by inventing new commentary.
- If the user gives screenshots as references, follow their composition: white background, large margins, black text, simple image insertion.

## Commands

Generate HTML:

```bash
python3 /Users/xuansir/.codex/skills/xhs-markdown-plog/scripts/build_plog.py config.json output/xhs-markdown-plog/my-plog
```

Export PNGs when Playwright is available:

```bash
node /Users/xuansir/.codex/skills/xhs-markdown-plog/scripts/export_pages.mjs output/xhs-markdown-plog/my-plog/index.html output/xhs-markdown-plog/my-plog/exports
```

If the workspace uses bundled Node dependencies, set `NODE_PATH` to the bundled `node_modules` before running the export script. If a screenshot is off by 1px from browser rounding, normalize it with ImageMagick `-extent`.

## Verification

Before final response:

- Confirm `index.html` opens without missing images.
- Confirm page 1 has title and image.
- Confirm later pages contain the text/image content.
- Confirm exported PNG dimensions match the chosen canvas.
- Visually inspect the cover and at least one later page.
