"""Calibration sample: what came in without approval in the decisive-only mode.

Approving less must not hide errors. This tool reads the integration receipts, gathers the records that came in
without approval (`decisive` mode, non-decisive records) and writes a sheet to review them by sample.
It only reads: it records nothing, changes no receipt and does not decide whether anything was right.

    uv run python tools/calibration/sample.py ~/.kbol/<repo>/receipts [--size 10] [--since INSTANT] [--output SHEET.md]

The sample is deterministic: it sorts by the SHA-256 of `operation_id` and ID, so two runs over the same receipts
give the same sheet and nobody picks by hand what is reviewed. It exits with 0 if there is a sample and with 3 if
there is nothing to sample, which is not the same as "all good": it says so.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path


def candidates(folder, since=None):
    """(unapproved, receipts_read, unreadable): records that came in without approval, one per receipt and ID."""
    unapproved, read, unreadable = [], 0, []
    for path in sorted(Path(folder).glob("*.json")):
        try:
            receipt = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            unreadable.append(path.name)
            continue
        if not isinstance(receipt, dict) or receipt.get("state") != "integrated":
            continue
        read += 1
        if receipt.get("approval_mode") != "decisive":
            continue
        if since and str(receipt.get("recorded_at") or "") < since:
            continue
        decisive = set(receipt.get("decisive") or [])
        for ident in receipt.get("records") or []:
            if ident not in decisive:
                unapproved.append(
                    {
                        "operation_id": receipt.get("operation_id"),
                        "id": ident,
                        "integrated_revision": receipt.get("integrated_revision"),
                        "recorded_at": receipt.get("recorded_at"),
                        "actor": receipt.get("actor"),
                    }
                )
    return unapproved, read, unreadable


def sample(unapproved, size):
    """The first `size` by the SHA-256 of operation and ID: deterministic and with no choice by hand."""

    def key(c):
        return hashlib.sha256(f"{c['operation_id']}\x00{c['id']}".encode()).hexdigest()

    return sorted(unapproved, key=key)[:size]


def sheet(chosen, total, read, unreadable):
    lines = [
        "# Calibration sample",
        "",
        f"Integration receipts read: {read}. Records that came in without approval: {total}. "
        f"In the sample: {len(chosen)}.",
    ]
    if unreadable:
        lines.append(f"Unreadable receipts, not counted: {', '.join(unreadable)}.")
    lines += [
        "",
        "For each one, check something concrete: should it have asked for approval? Is its content correct?",
        "",
        "| Operation | Record | Integrated revision | Recorded | Actor | Should it have escalated? | Notes |",
        "|---|---|---|---|---|---|---|",
    ]
    lines += [
        f"| {c['operation_id']} | {c['id']} | {str(c['integrated_revision'])[:12]} | {c['recorded_at']} | "
        f"{c['actor']} |  |  |"
        for c in chosen
    ]
    return "\n".join(lines) + "\n"


def main(argv=None):
    p = argparse.ArgumentParser(description="Calibration sample of what came in without approval")
    p.add_argument("receipts", help="receipts folder of the installation")
    p.add_argument("--size", type=int, default=10)
    p.add_argument("--since", help="only receipts recorded since this instant (ISO 8601, UTC)")
    p.add_argument("--output", help="file where to write the sheet; by default, standard output")
    args = p.parse_args(argv)
    if not Path(args.receipts).is_dir():
        print(f"The receipts folder does not exist: {args.receipts}", file=sys.stderr)
        return 1
    if args.size < 1:
        print("The sample size is an integer greater than zero", file=sys.stderr)
        return 1
    unapproved, read, unreadable = candidates(args.receipts, args.since)
    if not unapproved:
        print(
            f"No sample: {read} integration receipts read and no record came in without approval. "
            "There is nothing to calibrate; that does not say that what was integrated is right.",
            file=sys.stderr,
        )
        return 3
    text = sheet(sample(unapproved, args.size), len(unapproved), read, unreadable)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8", newline="\n")
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
