# kbol-di · Document Intelligence

KBOL's Document Intelligence tools: they take a document from its origin to a representation that `kbol citations` can check and a folder that can be browsed and related. They were born with the first pilot (regulation: CRA, R. 2025/2392, NIS2 and ENS); since 0.2 they serve any PDF and since 0.3 Word, spreadsheets, PowerPoint and HTML. A separate uv project so that Docling and torch do not enter the core or the installations. It does not integrate records or enable `ingest`: it produces artifacts in a store and the data to write derived sources.

Contract: the locators of `kbol/locator.py`; the resolver that checks them is `kbol citations`. The procedure to add a document and cite it is in the [add-document](../../.claude/skills/add-document/SKILL.md) skill.

```bash
cd tools/di
uv sync                      # docling 2.142.1, exclude-newer 2026-10-24, CPU
uv run python -m pytest -q
uv run python -m di add <URL or file> --name usad   # end to end, with its folder
uv run python -m di locate <sha256 of the Docling JSON> "<literal quote>"
```

| Format | Processor | Representation that is cited | Citation | Crosscheck |
|---|---|---|---|---|
| PDF with a text layer | Docling, with figures as images | Generic structure | `pdf-v1:p=…` | pypdf, per page |
| PowerPoint | Docling | Generic structure (one slide per page) | `pdf-v1:p=<slide>` | none |
| Word, spreadsheet | Docling | Its Markdown export | `lines-v1:…` with `representation_id` | none |
| HTML | MarkItDown | The Markdown it produces | `lines-v1:…` with `representation_id` | none |

The format comes from the origin's extension. An origin without extension (the URL of a PDF on EUR-Lex) is treated as PDF, as always; `--format pdf|docx|pptx|xlsx|html` declares it by hand when the origin does not say or has another extension.

Citing a representation by lines, and not the original, needs KBOL 0.10.0 or later. An HTML file has no structure or folder: only its Markdown.

## The document folder

With `--name`, `add` generates `documents/<name>/` next to the store (or in `--destination`); `di project <sha256 of the structure> --name <name>` regenerates it without processing again.

```
documents/usad/
  usad.pdf                       the original
  index.md                       what the document is and what is in the folder
  contents/NN-<title>.md         one section per file
  resources/tables/table-M.md    each table in Markdown and each value with its headers
  resources/figures/figure-M.*   the image and its record
  resources/bibliography.md      the bibliography entries with their key
```

Each file has an OKF-style YAML header: `id` (`usad#section=17`), `type`, `title`, `description`, and what is specific to its type. A section adds `number`, `depth`, `parent`, `children`, `path`, `part_type`, `pages` (or `lines` in a document without pages), `references`, `resources`, `origin` (the fingerprints and the units of the structure it covers) and `generated`. The body is the text of the document with XML marks that do not alter it: `<page n="7"/>`, `<ref key="17">[17]</ref>`, `<resource type="table" id="table-2" ref="…">caption</resource>`, `<note>`, `<formula>`.

The folder is a generated view, not registered knowledge: it comes from the same computation as the structure, is regenerated whole and is not edited by hand (if the destination folder exists and this tool did not generate it, it is left untouched). Citations are written against the structure or the Markdown, with the page or lines each file states. Since it contains a copy of the document, it goes outside the repository.

The standalone commands, which `add` chains and the regulation flow uses one by one:

```bash
uv run python -m di capture <URL or file> --media-type application/pdf
uv run python -m di process <sha256 of the original> [--format .pdf|.docx|.pptx|.xlsx|.html]
uv run python -m di structure <sha256 of the Docling JSON> --original <sha256> [--profile norm [--reorder] | --profile generic [--no-correct]]
uv run python -m di fidelity <sha256 of the structure> --original <sha256> [--editor <sha256> --type eurlex|boe]
```

The store is `KBOL_STORE` or `$KBOL_STATE/<repo>/store`, where the repository is the name of the installation's local state and is given in `KBOL_REPOSITORY`; without that variable it is `default` (by default, `~/.kbol/default/store`). It keeps `sha256/<fingerprint>` for each object (never overwritten) and `meta/<fingerprint>.json` with its origins and the date of the first capture.

## Two structure profiles

Both produce `structure-v1`, the representation the resolver reads: `profile`, `original_sha256`, `pages` (`p`, `width`, `height`) and `units`, each with `key`, `level`, `pages`, `regions` (`p`, `r`) and `text`. What changes is how the document is grouped and, with it, how it is cited.

| | `norm` | `generic` |
|---|---|---|
| For | EU and BOE regulatory drafting | Any other PDF: report, paper, manual, contract |
| Units | Recital, article, paragraph, point, letter, annex… (`norm-v1`) | Section per page (`section=n;page=p`), table and figure with caption |
| Citation | Logical and physical: `norm-v1:art=14;ap=2 @ pdf-v1:p=37;r=…` | Physical only: `pdf-v1:p=8;r=…` |
| Fidelity | Per unit against the publisher's text (EUR-Lex, BOE) | Per-page crosscheck with pypdf |
| Reading order | Docling's; `--reorder` corrects it | Corrected, together with labels and floats; `--no-correct` keeps what Docling gives |

The `norm-v1` keys (`cons`, `anx`, `parte`, `cap`, `sec`, `art`, `ap`, `pto`, `let`, `num`) are those of the locator, and the `norm` profile reads the Spanish text of EUR-Lex and the BOE (`Artículo`, `ANEXO`, `Parte`, `Clase`, `CAPÍTULO`); fidelity looks for Spanish negations, exceptions and dates.

Since segmenter 0.2, each unit of the generic profile also carries its context in the document, without interpreting what it says:

| Field | In | What it is |
|---|---|---|
| `number`, `depth`, `parent` | section | Numbering ("5.3"), level and key of the containing section, taken from the numbering of the heading |
| `path` | section, table, figure | Headings from the root: `["5 Experiments and results", "5.3 Training time"]` |
| `part_type` | section, table, figure | `abstract`, `introduction`, `related_work`, `method`, `experiments`, `results`, `conclusions`, `references`, `appendix` or `acknowledgments`; a subsection without a type of its own inherits its parent's. Headings are recognized in English and in Spanish |
| `references` | section | Bibliography keys that piece cites ("17", or "feng 2021" in author-year style) |
| `caption` | table, figure | Its caption ("Table 2: Performance comparison…") |
| `cells` | table | Each value with its page, `row`, `col`, the `headers` of its column (`["SWaT", "Without", "F1"]`) and its `row_label` (`["USAD"]`) |

The structure also carries `references` at the root: the bibliography entries with their key, text, pages and section. A citation in the text without an entry in the bibliography is left in `warnings`. The `text` of each unit is still the PDF's: the resolved headers go apart so they are not cited as if they were written that way.

The keys of the generic profile are deliberately not a `norm-v1` locator: they name units of this representation and not a stable division of the document. The section is split by page so that the page of the citation is really checked; a paragraph split across two pages resolves on both.

What the resolver checks in a physical-only citation is the fingerprint of the original and of the representation, that the page exists and that the literal quote is in the text of that page. The region (`r=`) is written so that a person can find the passage, but `kbol citations` does not check it if the citation has no logical part: a wrong region on the right page passes.

## Modules

| Module | What it does | Limits |
|---|---|---|
| `store` | Capture by URL or file, rereads and checks the fingerprint; idempotent retry | One writer; no locking |
| `process` | Docling on CPU, without OCR, tables in accurate mode and figures as images at double resolution; saves the native DoclingDocument JSON and, for Word and spreadsheets, its Markdown; an HTML file goes through MarkItDown | Finishing does not prove fidelity; a scanned PDF comes out empty; the four regulations of the first pilot were processed without images |
| `structure` | `norm-v1` units with pages, regions and text; recovers headings that Docling left as page headers, drops table-of-contents entries and replaces the U+0840 glyph that Docling reads instead of U+2003 in the BOE, all declared in `warnings` | EU and BOE drafting |
| `generic` | Units by heading, page, table and figure of any PDF; an algorithm, table or figure label does not open a section, nor does a repeated heading, and each table or figure goes to the section that mentions it, all declared in `warnings` | The section is the one Docling detects; without a numbered caption, a float stays where it lands |
| `context` | Section hierarchy by numbering, part type by heading, table cells with headers resolved through merged cells, and numeric or author-year bibliography calls | Docling gives all headings the same level: without numbering there is no hierarchy; the type is inferred from the heading and not from the content; an item "1." after "3.3" is taken as an item and warned; brackets with numbers greater than the bibliography do not count as citations |
| `order` | Per-page reading order from the position of the blocks: bands, two columns and lines; leaves a page it does not understand untouched and says so | Two columns at most; does not read the content |
| `editor` | Units according to the EUR-Lex HTML and the BOE XML, without footnotes | The inner points of a EUR-Lex annex are measured at the level of the annex |
| `fidelity` | Per norm unit: existence and uniqueness, word recall, dates, negations and exceptions; document: recall and split words against pypdf | Tables are measured by their text, not cell by cell |
| `crosscheck` | Without an editor: per page, how much of what pypdf reads is in the structure and vice versa, and numbers one by one; declares pages without a text layer | Two readings of the same text layer share its errors; does not measure order or meaning; does not detect a text placed on the page next to its own |
| `locate` | Page and region of a literal quote, to write its `pdf-v1` | Does not search footnotes; walks Docling's order, so a quote straddling two blocks that `order` moves may not be found |
| `add` | Chains capture, processing, generic structure, crosscheck (PDF only) and, with `--name`, the folder; returns the data for the source records and what to review | Does not write records or judge quality |
| `project` | Navigable folder of the document from its structure: index, one section per file with its context, tables, figures and bibliography | Regenerable view; does not delete a folder it did not generate |

## What was measured

Correcting the reading order in the four regulations of the first pilot, measured with `fidelity` against the publisher's text (10 Nov 2026, DoclingDocument from Docling 2.142.1 already in the store). Without `--reorder`, the units came out byte for byte the same as those registered then.

| Regulation | Unique units | Mean recall | Article order | Pages reordered |
|---|---|---|---|---|
| CRA | 600 → 607 of 607 | 0.9982 → 0.9997 | 0.9859 → 1.0 | 3 of 81 |
| NIS2 | 603 of 603, same | 0.9999, same | 1.0, same | 3 of 73 |
| R. 2025/2392 | 16 of 16, same | 1.0, same | 1.0, same | 1 of 11 |
| ENS | 178 → 179 of 187 | 0.9788 → 0.9929 | 0.9524, same | 81 of 90 |

No metric gets worse. `--reorder` is not the default in the norm profile because it would change the derivations that the registered facts already cite: using it produces a new derivation, and replacing the previous one is a decision for whoever maintains those records. The artifact without `--reorder` keeps its units, but not its record: `code_sha256` changes whenever `structure.py` changes. Since 0.13 the structure is written in English (`structure-v1`, `units`, `key`…), so a structure produced now is a new artifact with a new fingerprint, even with the same units as one registered under 0.12 (`estructura-v1`).

The generic profile was tested end to end, with the pinned Docling, on a two-column ACM paper (11 pages, 110 s on CPU): sections in their order, citations resolved on their page and broken on the next one, and a pypdf crosscheck of 0.996 recall and 0.998 support, with the formula page as the only warning. Segmentation and ordering were also tested on DoclingDocuments from another Docling version (2.150, with OCR) of three more papers: two-column IEEE, single-column Springer and a 42-page review. Reports with graphic design, slides, forms and any three-column layout remain untested.
