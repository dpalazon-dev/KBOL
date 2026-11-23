"""What the approval package shows covers what the digest covers.

The digest includes the whole body and all the fields: none of that may stay hidden, clipped without notice or
disguised in the terminal.
"""

from kbol.package import _CLIP, _line, _outside_clauses, _value

CLAUSE = '<clause id="C1">\nMonday.\n</clause>\n'


def test_text_outside_the_clauses_is_shown_in_a_new_record():
    outside = _outside_clauses(None, CLAUSE + "\nAnd also, on Tuesdays too.\n")
    assert outside == {"before": None, "after": "And also, on Tuesdays too."}


def test_text_outside_the_clauses_is_shown_even_if_a_clause_also_changes():
    before = CLAUSE + "\nOld note.\n"
    after = CLAUSE.replace("Monday", "Tuesday") + "\nNew note.\n"
    assert _outside_clauses(before, after) == {"before": "Old note.", "after": "New note."}


def test_without_changes_outside_the_clauses_nothing_is_reported():
    assert _outside_clauses(CLAUSE, CLAUSE.replace("Monday", "Tuesday")) is None
    assert _outside_clauses(None, CLAUSE) is None


def test_removing_the_outside_text_is_reported_too():
    assert _outside_clauses(CLAUSE + "\nNote.\n", CLAUSE) == {"before": "Note.", "after": None}


def test_control_and_format_characters_do_not_hide_text():
    # An ANSI escape and a bidirectional override mark: in the terminal they could erase or reorder what is seen.
    text = "accept\x1b[2K‮odot"
    visible = _line(text)
    assert "\x1b" not in visible and "‮" not in visible
    assert visible.count("�") == 2 and "accept" in visible and "odot" in visible


def test_line_breaks_fold_without_losing_words():
    assert _line("one\ntwo\r\n\tthree") == "one two three"


def test_a_long_value_says_how_much_is_clipped():
    long_value = "x" * (_CLIP + 40)
    shown = _value(long_value)
    assert shown.startswith("x" * _CLIP) and "+40 characters" in shown and "JSON" in shown
    assert _value("short") == "short"
