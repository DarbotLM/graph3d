import pytest

from graph3d.cli_api import (
    ExtractProfileArgs,
    parse_corpus_profile,
    parse_extract_profile_args,
    valid_corpus_profiles,
)


def test_valid_corpus_profiles_are_stable_and_sorted():
    assert valid_corpus_profiles() == ("all", "product", "schemas", "session", "tests", "worked")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, None),
        ("", None),
        ("  ", None),
        ("PRODUCT", "product"),
        (" tests ", "tests"),
    ],
)
def test_parse_corpus_profile_normalizes_legacy_blank_and_named_profiles(raw, expected):
    assert parse_corpus_profile(raw) == expected


def test_parse_corpus_profile_rejects_unknown_profile():
    with pytest.raises(ValueError, match="unknown corpus profile"):
        parse_corpus_profile("docs")


def test_parse_extract_profile_args_removes_profile_and_preserves_other_args():
    parsed = parse_extract_profile_args(
        ["--backend", "claude", "--profile", "PRODUCT", "--no-cluster"]
    )

    assert parsed == ExtractProfileArgs(
        profile="product",
        args=("--backend", "claude", "--no-cluster"),
    )


def test_parse_extract_profile_args_supports_equals_form_and_last_wins():
    parsed = parse_extract_profile_args(["--profile=tests", "--profile=schemas"])

    assert parsed.profile == "schemas"
    assert parsed.args == ()


@pytest.mark.parametrize("args", [["--profile"], ["--profile", ""], ["--profile="]])
def test_parse_extract_profile_args_requires_non_empty_profile(args):
    with pytest.raises(ValueError, match="--profile requires a non-empty value"):
        parse_extract_profile_args(args)
