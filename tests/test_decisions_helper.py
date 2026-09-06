# T01 merge-owner behavior contracts


def test_merge_owner_prints_last_matching_owner_and_strips_bold(tmp_path, capsys):
    _repo(
        tmp_path,
        "repo",
        (
            "| id | when | who | what | why | where |\n"
            "|---|---|---|---|---|---|\n"
            "| D-001 | d | w | MERGE OWNER: alpha | why | here |\n"
            "| D-002 | d | w | **MERGE OWNER: beta** — current | why | here |\n"
        ),
    )
    rc = dec.main(["--merge-owner", str(tmp_path / "repo")])
    captured = capsys.readouterr()
    assert rc == 0
    assert captured.out.strip() == "beta"
    assert captured.err == ""


def test_merge_owner_reports_undeclared_for_non_opening_phrase(tmp_path, capsys):
    _repo(
        tmp_path,
        "repo",
        (
            "| id | when | who | what | why | where |\n"
            "|---|---|---|---|---|---|\n"
            "| D-001 | d | w | recorded MERGE OWNER: alpha | why | here |\n"
        ),
    )
    rc = dec.main(["--merge-owner", str(tmp_path / "repo")])
    captured = capsys.readouterr()
    assert rc == 3
    assert captured.out.strip() == "UNDECLARED"


def test_merge_owner_reports_unreadable_ledger(tmp_path, capsys):
    repo = tmp_path / "repo"
    repo.mkdir()
    rc = dec.main(["--merge-owner", str(repo)])
    captured = capsys.readouterr()
    assert rc == 1
    assert captured.out == ""
    assert "decisions: cannot read" in captured.err
