from scripts import closure_acceptance


def _check(name: str, *, passed: bool = True) -> closure_acceptance.Check:
    return closure_acceptance.Check(name, ["python", "-m", name], passed, 0.01, "tail")


def test_static_only_success_is_not_full_acceptance() -> None:
    report = closure_acceptance._build_report(
        commit="a" * 40,
        branch="fix/report",
        dirty="",
        checks=[_check("ruff-check"), _check("mypy")],
        full_run=False,
    )

    assert report["acceptance_mode"] == "static-only"
    assert report["tests"] == {
        "required_for_full_acceptance": True,
        "executed": False,
        "passed": None,
    }
    assert report["executed_checks_passed"] is True
    assert report["full_acceptance_passed"] is False
    assert report["all_passed"] is False


def test_full_success_requires_executed_passing_pytest() -> None:
    report = closure_acceptance._build_report(
        commit="b" * 40,
        branch="fix/report",
        dirty="",
        checks=[_check("pytest-full"), _check("ruff-check")],
        full_run=True,
    )

    assert report["acceptance_mode"] == "full"
    assert report["tests"] == {
        "required_for_full_acceptance": True,
        "executed": True,
        "passed": True,
    }
    assert report["executed_checks_passed"] is True
    assert report["full_acceptance_passed"] is True
    assert report["all_passed"] is True


def test_full_acceptance_requires_clean_exact_commit() -> None:
    dirty_report = closure_acceptance._build_report(
        commit="b" * 40,
        branch="fix/report",
        dirty=" M README.md",
        checks=[_check("pytest-full"), _check("ruff-check")],
        full_run=True,
    )
    unidentified_report = closure_acceptance._build_report(
        commit="",
        branch="fix/report",
        dirty="",
        checks=[_check("pytest-full"), _check("ruff-check")],
        full_run=True,
    )

    assert dirty_report["executed_checks_passed"] is True
    assert dirty_report["all_passed"] is False
    assert unidentified_report["all_passed"] is False


def test_failed_executed_check_fails_both_summaries() -> None:
    report = closure_acceptance._build_report(
        commit="c" * 40,
        branch="fix/report",
        dirty="",
        checks=[_check("pytest-full"), _check("mypy", passed=False)],
        full_run=True,
    )

    assert report["executed_checks_passed"] is False
    assert report["full_acceptance_passed"] is False
    assert report["all_passed"] is False
