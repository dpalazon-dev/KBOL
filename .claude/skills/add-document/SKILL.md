---
name: add-document
description: Adds a document (PDF with a text layer, Word, spreadsheet, PowerPoint or HTML) to a KBOL knowledge base so it can be cited in a checkable way and browsed as a folder. Use it when a document has to be registered as a source, when a sentence or a figure from it has to be cited in a record, when asking what an already added document says, or when checking that its citations resolve. It does not work for scanned PDFs.
---
<!-- Exported by kbol 0.13.0 with `kbol export_skills`. Edit it in kbol/skills/ of KBOL, not here. -->

# Add a document

A PDF becomes citable when three things exist: the original stored with its fingerprint, a representation of that original (`structure-v1`) and a citation that `kbol citations` checks against both. This skill produces all three. It does not accept knowledge: the source records and the facts come in as proposals, through the procedure of the installation where they are registered.

The tools are in KBOL's `tools/di`, with their own environment (pinned Docling, on CPU). All commands are run from that folder. The store is `$KBOL_STATE/<repository>/store`, with the installation's name in `KBOL_REPOSITORY` (without that variable, `~/.kbol/default/store`); for a test that must leave no trace, point `KBOL_STORE` to a temporary folder before starting.

## 1. Add

```bash
cd <KBOL root>/tools/di
uv sync                                         # first time only
uv run python -m di add <file or URL> --name <short name> > <work folder outside KBOL>/add.json
```

`--name` is the name of the document folder (`usad`, `cra-2024`): lowercase, no spaces. The format comes from the extension; an origin without extension is taken as PDF, and `--format html` (or `docx`, `pptx`, `xlsx`, `pdf`) declares it when the URL does not say. It takes two or three seconds per page, plus a good minute to start. Progress goes to standard error and does not pollute the JSON. The output contains:

- `original` and, depending on the format, `docling`, `structure` and `markdown`: the fingerprint (`sha256`) of each object and the data for its source record.
- `crosscheck` (PDF only): the summary of comparing the structure with a second reading (pypdf).
- `folder`: where the document folder was left and how many sections, tables and figures it has.
- `review`: what has to be looked at before citing.

| Format | What is cited | How |
|---|---|---|
| PDF, PowerPoint | The structure | By page (`pdf-v1:p=…`; in a PowerPoint, the slide) |
| Word, spreadsheet | The Markdown exported by Docling | By lines (`lines-v1:…`) |
| HTML | The Markdown produced by MarkItDown | By lines; it has no structure or folder |

## The document folder: where to start reading it

It is left in `documents/<name>/`, next to the store. It is the way to understand the document without opening the original:

- `index.md`: what it is, the list of sections with their pages, the tables, the figures and the segmentation warnings.
- `contents/NN-<title>.md`: one section per file. The header gives its path in the document, its part type (method, results…), its pages or lines, which bibliography references it calls and which tables and figures it contains.
- `resources/tables/table-M.md`: the table and, below it, each value with its row and its headers ("USAD · SWaT › Without › F1 = 0.7917 (p. 7)"). For a question about a figure, start here.
- `resources/bibliography.md`: the entries, with the key used by the `<ref key="17">` marks in the text.

The folder is not edited: it is regenerated. To cite, do not simply copy from the body of these files: locate the citation as step 4 says, against the structure or the Markdown.

## 2. Read `review` before going on

Each object in the store is at `<store>/sha256/<fingerprint>`, without extension. The crosscheck report (`crosscheck.sha256`) and the structure (`structure.sha256`) are JSON. The report gives, per page, the recall, the support and the discrepant numbers one by one; it does not give the lost text. To see what Docling read on a page, look at `units[].text` in the structure: that is also where you choose what to cite.

| Warning | What it means | What to do |
|---|---|---|
| Pages without a text layer | They are images: Docling read nothing on them | Do not cite those pages. A fully scanned PDF cannot be added with this skill: say so and stop |
| Pages where the structure loses text | pypdf sees text the structure does not have | Compare the structure's text on that page with the PDF before citing from it, or do not cite from it. It is usually a page of formulas |
| Pages with text that pypdf does not see there | Text assigned to another page, or formulas and symbols each reader writes differently | Check in the PDF the page of whatever you cite from there |
| Missing or unsupported numbers | A number is in one reading and not in the other | If you are going to cite a figure from that page, compare it with the PDF by eye. Equation numbers and page ranges are usually noise; a figure in a table is not |
| Pages without any unit | The structure does not cover that page | Nothing can be cited from it |

A clean crosscheck does not prove the reading is correct: both readers share the PDF's text layer, and the crosscheck does not measure reading order or meaning. It tells you where to look.

## 3. Write the three source records

One per object, with a new ID (`SRC-` plus a UUID). The scope, class, author and ID prefix of the other records are the installation's; copy the shape of its existing records. Three fields do not come from the command and you fill them in: `origin` carries the real provenance of the document (publisher, DOI, URL), not just the local path it was captured from; `access` is free text saying who may read it; dates go in ISO 8601 with a zone (`2026-11-10T17:49:21+01:00`). A value with braces, commas or colons goes in single quotes. The fields that come from `add.json`:

```yaml
# Original
type: source
subtype: original
title: '<document title>: PDF'
origin: <where it came from and when: original.origins and original.captured_at>
location: store:sha256/<original.sha256>
format: application/pdf
sha256: <original.sha256>
access: <who may read it; inherits the document's restriction>
```

```yaml
# DoclingDocument
type: source
subtype: derived
title: '<title>: DoclingDocument'
location: store:sha256/<docling.sha256>
format: application/json
sha256: <docling.sha256>
access: <the original's>
derived_from: [<ID of the original's source record>]
processor: docling
processor_version: <docling.version>
configuration_ref: '{"configuration": <docling.configuration>, "versions": <docling.versions>}'
processed_at: <docling.processed_at>
processing: processed
```

```yaml
# Structure: the representation the records cite
type: source
subtype: derived
title: '<title>: unit structure (structure-v1)'
location: store:sha256/<structure.sha256>
format: application/json
sha256: <structure.sha256>
access: <the original's>
derived_from: [<ID of the DoclingDocument's source record>]
processor: kbol-di/generic
processor_version: '<structure.version>'
configuration_ref: 'KBOL tools/di, code sha256 <structure.code_sha256>, configuration <structure.configuration as JSON>'
processed_at: <today's date, with a zone>
processing: processed
quality:
  pypdf_crosscheck:
    method: Per-page crosscheck with pypdf (kbol-di crosscheck, report <crosscheck.sha256> in the store)
    result: <conforming if review is empty; partial otherwise>
    limits: <the summary in one sentence: recall, support, discrepant numbers and affected pages>
  reading_order:
    method: not_evaluated
```

Write in `quality` what the report says, also when it is bad. Do not put `conforming` because the process finished, and do not leave out the structure's warnings (`structure.warnings`) that affect what is going to be cited.

## 4. Cite

For each sentence or figure, get its page and its region:

```bash
uv run python -m di locate <docling.sha256> "<literal quotation, exactly as in the PDF>"
```

It returns a list of findings; each one, one region per page. With the result, the citation is written in the record's `sources`:

```yaml
sources:
- id: s1
  resource: <ID of the original's source record>
  representation_id: <ID of the structure's source record>
  hash: <original.sha256>
  anchor: pdf-v1:p=<p>;r=<r[0]>,<r[1]>,<r[2]>,<r[3]>
  context: <the literal quotation>
```

- Empty list: the sentence is not there as written. Shorten it or fix the quotes and dashes; do not accept it.
- More than one finding: the sentence appears in several places. Choose by looking at the PDF, or lengthen the quotation until it is unique.
- A finding with two regions: the sentence crosses a page break. Cite the page where it starts.
- A table is located cell by cell: search for the value alone (`"63.74"`), not the row. The citation carries that value in `context`. Which row and column it belongs to is in the structure: the table's unit (`section=n;table=m`) gives in `cells` each value with its page, its headers and its row label (`"headers": ["SWaT", "Without", "F1"], "row_label": ["USAD"]`). Write it in the body of the record. If the value repeats, the cells say which is which; choose by headers and row, not by the first finding of `locate`.
- To place what you cite, use the unit's `path` ("5 Experiments › 5.3 Training time") and its `part_type` (results, method…). If the passage cites the bibliography, the unit's `references` gives the keys and `references` at the root of the structure, their entries.
- Regions come as text with four decimals: copy them as they are. The region of a sentence is that of its whole paragraph.
- The literal quotation is text from the document, not a summary. What the record claims goes in its body; what the document says goes in `context`.

### Word, spreadsheet or HTML: by lines of the Markdown

They have no pages: they are cited by lines of their Markdown representation (`markdown.sha256` in the output), which needs its own derived source record with `format: text/markdown` and `derived_from` pointing to the DoclingDocument (for an HTML, to the original). To find the lines, each file in `contents/` gives in `lines` those its section takes up; within that range, search for the sentence in the Markdown in the store and note its start and end line.

```yaml
sources:
- id: s1
  resource: <ID of the original's source record>
  representation_id: <ID of the Markdown's source record>
  hash: <original.sha256>
  anchor: lines-v1:<start>-<end>
  context: <the literal quotation, exactly as in the Markdown>
```

## 5. Check

With the source records and the records in a folder of the installation:

```bash
cd <installation root>
uv run kbol citations . --folder <records folder> --store <store>
```

If the installation does not have KBOL in its environment, `uv run --project <KBOL root> kbol citations <installation root> …`. The output is a JSON with one row per citation, the `count` per state and the `warnings`; with any broken citation the command ends with exit code 3 and state `partial`. Every citation has to come out `resolved`. The other states:

| State | Usual cause |
|---|---|
| `broken` | The page is not that one, the literal quotation is not on that page or a fingerprint does not match |
| `uncheckable` | The original or the structure is not in this machine's store, or `--store` is missing |
| `inconsistent`, `ambiguous` | Only in citations of norms with a logical part (`norm-v1`) |

A `broken` citation is not fixed by changing the page until it passes: go back to `locate` and look at the PDF.

`resolved` means the fingerprints match and the literal quotation is in the text of that page. It does not check the region or that the record claims the same as the document: a person reviews that with the page open.

## Limits

- A scanned PDF cannot be added: without a text layer, Docling reads nothing and no crosscheck is possible.
- Word, spreadsheets, PowerPoint and HTML have no second reading to crosscheck against: review by eye whatever you cite from them. Citing a Word file or an HTML by lines needs KBOL 0.10.0 or later.
- Two columns at most. A page with another layout keeps Docling's order and says so in the warnings.
- Formulas are not read: they remain as a gap, and their numbers show up as missing numbers.
- EU and BOE norms have their own profile (`norm-v1`) with citation by article and measured against the publisher's text: for them, the separate commands in `tools/di/README.md`, not `add`.
- Reprocessing with another version or configuration gives another fingerprint: it is another derivation, with its own source record. Citations already written keep pointing to the previous one.
