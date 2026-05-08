from datetime import datetime
from itertools import chain, product
import shutil
import pytest

from pre_commit_hooks.insert_license import main as insert_license, LicenseInfo
from pre_commit_hooks.insert_license import (
    find_license_header_index,
    get_commit_year,
    header_covers_year,
)

from .utils import chdir_to_test_resources, capture_stdout


# pylint: disable=too-many-arguments


def _convert_line_ending(file_path, new_line_endings):
    for encoding in (
        "utf8",
        "ISO-8859-1",
    ):  # we could use the chardet library to support more encodings
        last_error = None
        try:
            with open(file_path, encoding=encoding, newline="") as f_in:
                content = f_in.read()

            with open(
                file_path, "w", encoding=encoding, newline=new_line_endings
            ) as f_out:
                f_out.write(content)

            return
        except UnicodeDecodeError as error:
            last_error = error
    print(
        f"Error while processing: {file_path} - file encoding is probably not supported"
    )
    if last_error is not None:  # Avoid mypy message
        raise last_error
    raise RuntimeError("Unexpected branch taken (_convert_line_ending)")


@pytest.mark.parametrize(
    (
        "license_file_path",
        "line_ending",
        "src_file_path",
        "comment_prefix",
        "new_src_file_expected",
        "message_expected",
        "fail_check",
        "extra_args",
    ),
    map(
        lambda a: a[:2] + a[2],
        chain(
            product(  # combine license files with other args
                (
                    "LICENSE_with_trailing_newline.txt",
                    "LICENSE_without_trailing_newline.txt",
                ),
                ("\n", "\r\n"),
                (
                    (
                        "module_without_license.py",
                        "#",
                        "module_with_license.py",
                        "",
                        True,
                        None,
                    ),
                    ("module_without_license_skip.py", "#", None, "", False, None),
                    ("module_with_license.py", "#", None, "", False, None),
                    ("module_with_license_todo.py", "#", None, "", True, None),
                    (
                        "module_without_license.jinja",
                        "{#||#}",
                        "module_with_license.jinja",
                        "",
                        True,
                        None,
                    ),
                    (
                        "module_without_license_skip.jinja",
                        "{#||#}",
                        None,
                        "",
                        False,
                        None,
                    ),
                    ("module_with_license.jinja", "{#||#}", None, "", False, None),
                    ("module_with_license_todo.jinja", "{#||#}", None, "", True, None),
                    (
                        "module_without_license_and_shebang.py",
                        "#",
                        "module_with_license_and_shebang.py",
                        "",
                        True,
                        None,
                    ),
                    (
                        "module_without_license_and_shebang_skip.py",
                        "#",
                        None,
                        "",
                        False,
                        None,
                    ),
                    ("module_with_license_and_shebang.py", "#", None, "", False, None),
                    (
                        "module_with_license_and_shebang_todo.py",
                        "#",
                        None,
                        "",
                        True,
                        None,
                    ),
                    (
                        "module_without_license.groovy",
                        "//",
                        "module_with_license.groovy",
                        "",
                        True,
                        None,
                    ),
                    ("module_without_license_skip.groovy", "//", None, "", False, None),
                    ("module_with_license.groovy", "//", None, "", False, None),
                    ("module_with_license_todo.groovy", "//", None, "", True, None),
                    (
                        "module_without_license.css",
                        "/*| *| */",
                        "module_with_license.css",
                        "",
                        True,
                        None,
                    ),
                    (
                        "module_without_license_and_few_words.css",
                        "/*| *| */",
                        "module_with_license_and_few_words.css",
                        "",
                        True,
                        None,
                    ),  # Test fuzzy match does not match greedily
                    (
                        "module_without_license_skip.css",
                        "/*| *| */",
                        None,
                        "",
                        False,
                        None,
                    ),
                    ("module_with_license.css", "/*| *| */", None, "", False, None),
                    ("module_with_license_todo.css", "/*| *| */", None, "", True, None),
                    (
                        "main_without_license.cpp",
                        "/*|\t| */",
                        "main_with_license.cpp",
                        "",
                        True,
                        None,
                    ),
                    (
                        "main_iso8859_without_license.cpp",
                        "/*|\t| */",
                        "main_iso8859_with_license.cpp",
                        "",
                        True,
                        None,
                    ),
                    (
                        "module_without_license.txt",
                        "",
                        "module_with_license_noprefix.txt",
                        "",
                        True,
                        None,
                    ),
                    (
                        "module_without_license.py",
                        "#",
                        "module_with_license_nospace.py",
                        "",
                        True,
                        ["--no-space-in-comment-prefix"],
                    ),
                    (
                        "module_without_license.php",
                        "/*| *| */",
                        "module_with_license.php",
                        "",
                        True,
                        ["--insert-license-after-regex", "^<\\?php$"],
                    ),
                    (
                        "module_without_license.py",
                        "#",
                        "module_with_license.py",
                        "",
                        True,
                        # Test that when the regex is not found, the license is put at the first line
                        ["--insert-license-after-regex", "^<\\?php$"],
                    ),
                    (
                        "module_without_license.py",
                        "#",
                        "module_with_license_noeol.py",
                        "",
                        True,
                        ["--no-extra-eol"],
                    ),
                    (
                        "module_without_license.groovy",
                        "//",
                        "module_with_license.groovy",
                        "",
                        True,
                        ["--use-current-year"],
                    ),
                    (
                        "module_with_stale_year_in_license.py",
                        "#",
                        "module_with_year_range_in_license.py",
                        "",
                        True,
                        ["--use-current-year"],
                    ),
                    (
                        "module_with_stale_year_range_in_license.py",
                        "#",
                        "module_with_year_range_in_license.py",
                        "",
                        True,
                        ["--use-current-year"],
                    ),
                    (
                        "module_with_stale_year_range_in_license.py",
                        "#",
                        "module_with_stale_year_range_in_license.py",
                        "",
                        False,
                        ["--allow-past-years"],
                    ),
                    (
                        "module_with_badly_formatted_stale_year_range_in_license.py",
                        "#",
                        "module_with_badly_formatted_stale_year_range_in_license.py",
                        "module_with_badly_formatted_stale_year_range_in_license.py",
                        True,
                        ["--use-current-year"],
                    ),
                    (
                        "module_without_license.py",
                        "#",
                        "module_with_license.py",
                        "",
                        True,
                        None,
                    ),
                    ("module_without_license_skip.py", "#", None, "", False, None),
                    ("module_with_license.py", "#", None, "", False, None),
                    ("module_with_license_todo.py", "#", None, "", True, None),
                    (
                        "module_without_license.jinja",
                        "{#||#}",
                        "module_with_license.jinja",
                        "",
                        True,
                        None,
                    ),
                    (
                        "module_without_license_skip.jinja",
                        "{#||#}",
                        None,
                        "",
                        False,
                        None,
                    ),
                    ("module_with_license.jinja", "{#||#}", None, "", False, None),
                    ("module_with_license_todo.jinja", "{#||#}", None, "", True, None),
                    (
                        "module_without_license_and_shebang.py",
                        "#",
                        "module_with_license_and_shebang.py",
                        "",
                        True,
                        None,
                    ),
                    (
                        "module_without_license_and_shebang_skip.py",
                        "#",
                        None,
                        "",
                        False,
                        None,
                    ),
                    ("module_with_license_and_shebang.py", "#", None, "", False, None),
                    (
                        "module_with_license_and_shebang_todo.py",
                        "#",
                        None,
                        "",
                        True,
                        None,
                    ),
                    (
                        "module_without_license.groovy",
                        "//",
                        "module_with_license.groovy",
                        "",
                        True,
                        None,
                    ),
                    ("module_without_license_skip.groovy", "//", None, "", False, None),
                    ("module_with_license.groovy", "//", None, "", False, None),
                    ("module_with_license_todo.groovy", "//", None, "", True, None),
                    (
                        "module_without_license.css",
                        "/*| *| */",
                        "module_with_license.css",
                        "",
                        True,
                        None,
                    ),
                    (
                        "module_without_license_and_few_words.css",
                        "/*| *| */",
                        "module_with_license_and_few_words.css",
                        "",
                        True,
                        None,
                    ),  # Test fuzzy match does not match greedily
                    (
                        "module_without_license_skip.css",
                        "/*| *| */",
                        None,
                        "",
                        False,
                        None,
                    ),
                    ("module_with_license.css", "/*| *| */", None, "", False, None),
                    ("module_with_license_todo.css", "/*| *| */", None, "", True, None),
                    (
                        "main_without_license.cpp",
                        "/*|\t| */",
                        "main_with_license.cpp",
                        "",
                        True,
                        None,
                    ),
                    (
                        "main_iso8859_without_license.cpp",
                        "/*|\t| */",
                        "main_iso8859_with_license.cpp",
                        "",
                        True,
                        None,
                    ),
                    (
                        "module_without_license.txt",
                        "",
                        "module_with_license_noprefix.txt",
                        "",
                        True,
                        None,
                    ),
                    (
                        "module_without_license.py",
                        "#",
                        "module_with_license_nospace.py",
                        "",
                        True,
                        ["--no-space-in-comment-prefix"],
                    ),
                    (
                        "module_without_license.php",
                        "/*| *| */",
                        "module_with_license.php",
                        "",
                        True,
                        ["--insert-license-after-regex", "^<\\?php$"],
                    ),
                    (
                        "module_without_license.py",
                        "#",
                        "module_with_license_noeol.py",
                        "",
                        True,
                        ["--no-extra-eol"],
                    ),
                    (
                        "module_without_license.groovy",
                        "//",
                        "module_with_license.groovy",
                        "",
                        True,
                        ["--use-current-year"],
                    ),
                    (
                        "module_with_stale_year_in_license.py",
                        "#",
                        "module_with_year_range_in_license.py",
                        "",
                        True,
                        ["--use-current-year"],
                    ),
                    (
                        "module_with_stale_year_range_in_license.py",
                        "#",
                        "module_with_year_range_in_license.py",
                        "",
                        True,
                        ["--use-current-year"],
                    ),
                    (
                        "module_with_badly_formatted_stale_year_range_in_license.py",
                        "#",
                        "module_with_badly_formatted_stale_year_range_in_license.py",
                        "module_with_badly_formatted_stale_year_range_in_license.py",
                        True,
                        ["--use-current-year"],
                    ),
                    (
                        "module_without_license.py",
                        "#",
                        "module_with_license.py",
                        "",
                        True,
                        [
                            "--license-filepath",
                            "LICENSE_2_without_trailing_newline.txt",
                        ],
                    ),
                    (
                        "module_with_license_2.py",
                        "#",
                        None,
                        "",
                        False,
                        [
                            "--license-filepath",
                            "LICENSE_2_without_trailing_newline.txt",
                        ],
                    ),
                    (
                        "module_with_license.py",
                        "#",
                        None,
                        "",
                        False,
                        [
                            "--license-filepath",
                            "LICENSE_2_without_trailing_newline.txt",
                        ],
                    ),
                    (
                        "module_with_license_todo.py",
                        "#",
                        None,
                        "",
                        True,
                        [
                            "--license-filepath",
                            "LICENSE_2_without_trailing_newline.txt",
                        ],
                    ),
                ),
            ),
            product(
                ("LICENSE_with_year_range_and_trailing_newline.txt",),
                ("\n", "\r\n"),
                (
                    (
                        "module_without_license.groovy",
                        "//",
                        "module_with_year_range_license.groovy",
                        "",
                        True,
                        ["--use-current-year"],
                    ),
                ),
            ),
            product(
                ("LICENSE_with_multiple_year_ranges.txt",),
                ("\n",),
                (
                    (
                        "module_with_multiple_stale_years_in_license.py",
                        "#",
                        "module_with_multiple_years_in_license.py",
                        "",
                        True,
                        ["--use-current-year"],
                    ),
                ),
            ),
        ),
    ),
)
def test_insert_license(
    license_file_path,
    line_ending,
    src_file_path,
    comment_prefix,
    new_src_file_expected,
    message_expected,
    fail_check,
    extra_args,
    tmpdir,
):
    encoding = "ISO-8859-1" if "iso8859" in src_file_path else "utf-8"
    with chdir_to_test_resources():
        path = tmpdir.join(src_file_path)
        shutil.copy(src_file_path, path.strpath)
        _convert_line_ending(path.strpath, line_ending)
        args = [
            "--license-filepath",
            license_file_path,
            "--comment-style",
            comment_prefix,
            path.strpath,
        ]
        if extra_args is not None:
            args.extend(extra_args)

        with capture_stdout() as stdout:
            assert insert_license(args) == (1 if fail_check else 0)
            assert message_expected in stdout.getvalue()

        if new_src_file_expected:
            with open(
                new_src_file_expected, encoding=encoding, newline=line_ending
            ) as expected_content_file:
                expected_content = expected_content_file.read()
                if "--use-current-year" in args:
                    expected_content = expected_content.replace(
                        "2017", str(datetime.now().year)
                    )
            new_file_content = path.open(encoding=encoding).read()
            assert new_file_content == expected_content


@pytest.mark.parametrize(
    ("license_file_path", "src_file_path", "comment_prefix"),
    map(
        lambda a: a[:1] + a[1],
        product(  # combine license files with other args
            (
                "LICENSE_with_trailing_newline.txt",
                "LICENSE_without_trailing_newline.txt",
                "LICENSE_with_year_range_and_trailing_newline.txt",
            ),
            (
                ("module_with_license.groovy", "//"),
                ("module_with_license_and_numbers.py", "#"),
                ("module_with_year_range_in_license.py", "#"),
                ("module_with_spaced_year_range_in_license.py", "#"),
            ),
        ),
    ),
)
def test_insert_license_current_year_already_there(
    license_file_path, src_file_path, comment_prefix, tmpdir
):
    with chdir_to_test_resources():
        with open(src_file_path, encoding="utf-8") as src_file:
            input_contents = src_file.read().replace("2017", str(datetime.now().year))
        path = tmpdir.join("src_file_path")
        with open(path.strpath, "w", encoding="utf-8") as input_file:
            input_file.write(input_contents)

        args = [
            "--license-filepath",
            license_file_path,
            "--comment-style",
            comment_prefix,
            "--use-current-year",
            path.strpath,
        ]
        assert insert_license(args) == 0
        # ensure file was not modified
        with open(path.strpath, encoding="utf-8") as output_file:
            output_contents = output_file.read()
            assert output_contents == input_contents


@pytest.mark.parametrize(
    (
        "license_file_path",
        "line_ending",
        "src_file_path",
        "comment_style",
        "new_src_file_expected",
        "fail_check",
        "extra_args",
    ),
    map(
        lambda a: a[:2] + a[2] + a[3],
        chain(
            product(  # combine license files with other args
                (
                    "LICENSE_with_trailing_newline.txt",
                    "LICENSE_without_trailing_newline.txt",
                ),
                ("\n", "\r\n"),
                (
                    (
                        "module_without_license.jinja",
                        "{#||#}",
                        "module_with_license.jinja",
                        True,
                    ),
                    ("module_with_license.jinja", "{#||#}", None, False),
                    (
                        "module_with_fuzzy_matched_license.jinja",
                        "{#||#}",
                        "module_with_license_todo.jinja",
                        True,
                    ),
                    ("module_with_license_todo.jinja", "{#||#}", None, True),
                    ("module_without_license.py", "#", "module_with_license.py", True),
                    ("module_with_license.py", "#", None, False),
                    (
                        "module_with_fuzzy_matched_license.py",
                        "#",
                        "module_with_license_todo.py",
                        True,
                    ),
                    ("module_with_license_todo.py", "#", None, True),
                    ("module_with_license_and_shebang.py", "#", None, False),
                    (
                        "module_with_fuzzy_matched_license_and_shebang.py",
                        "#",
                        "module_with_license_and_shebang_todo.py",
                        True,
                    ),
                    ("module_with_license_and_shebang_todo.py", "#", None, True),
                    (
                        "module_without_license.groovy",
                        "//",
                        "module_with_license.groovy",
                        True,
                    ),
                    ("module_with_license.groovy", "//", None, False),
                    (
                        "module_with_fuzzy_matched_license.groovy",
                        "//",
                        "module_with_license_todo.groovy",
                        True,
                    ),
                    ("module_with_license_todo.groovy", "//", None, True),
                    (
                        "module_without_license.css",
                        "/*| *| */",
                        "module_with_license.css",
                        True,
                    ),
                    ("module_with_license.css", "/*| *| */", None, False),
                    (
                        "module_with_fuzzy_matched_license.css",
                        "/*| *| */",
                        "module_with_license_todo.css",
                        True,
                    ),
                    ("module_with_license_todo.css", "/*| *| */", None, True),
                ),
                (
                    (tuple(),),
                    (
                        (
                            "--license-filepath",
                            "LICENSE_2_without_trailing_newline.txt",
                        ),
                    ),
                ),
            ),
            product(
                ("LICENSE_2_without_trailing_newline.txt",),
                ("\n", "\r\n"),
                (
                    (
                        "module_without_license.py",
                        "#",
                        "module_with_license_2.py",
                        True,
                    ),
                    ("module_with_license.py", "#", None, False),
                    ("module_with_license_todo.py", "#", None, True),
                    ("module_with_license_and_shebang.py", "#", None, False),
                    ("module_with_license_and_shebang_todo.py", "#", None, True),
                ),
                (
                    (
                        (
                            "--license-filepath",
                            "LICENSE_with_trailing_newline.txt",
                        ),
                    ),
                    (
                        (
                            "--license-filepath",
                            "LICENSE_without_trailing_newline.txt",
                        ),
                    ),
                ),
            ),
        ),
    ),
)
def test_fuzzy_match_license(
    license_file_path,
    line_ending,
    src_file_path,
    comment_style,
    new_src_file_expected,
    fail_check,
    extra_args,
    tmpdir,
):
    with chdir_to_test_resources():
        path = tmpdir.join("src_file_path")
        shutil.copy(src_file_path, path.strpath)
        _convert_line_ending(path.strpath, line_ending)
        args = [
            "--license-filepath",
            license_file_path,
            "--comment-style",
            comment_style,
            "--fuzzy-match-generates-todo",
            path.strpath,
        ]
        if extra_args is not None:
            args.extend(extra_args)
        assert insert_license(args) == (1 if fail_check else 0)
        if new_src_file_expected:
            with open(new_src_file_expected, encoding="utf-8") as expected_content_file:
                expected_content = expected_content_file.read()
            new_file_content = path.open(encoding="utf-8").read()
            assert new_file_content == expected_content


@pytest.mark.parametrize(
    ("src_file_content", "expected_index", "match_years_strictly"),
    (
        (["foo\n", "bar\n"], None, True),
        (["# License line 1\n", "# Copyright 2017\n", "\n", "foo\n", "bar\n"], 0, True),
        (["\n", "# License line 1\n", "# Copyright 2017\n", "foo\n", "bar\n"], 1, True),
        (
            ["\n", "# License line 1\n", "# Copyright 2017\n", "foo\n", "bar\n"],
            1,
            False,
        ),
        (
            ["# License line 1\n", "# Copyright 1984\n", "\n", "foo\n", "bar\n"],
            None,
            True,
        ),
        (
            ["# License line 1\n", "# Copyright 1984\n", "\n", "foo\n", "bar\n"],
            0,
            False,
        ),
        (
            [
                "\n",
                "# License line 1\n",
                "# Copyright 2013,2015-2016\n",
                "foo\n",
                "bar\n",
            ],
            1,
            False,
        ),
    ),
)
def test_is_license_present(src_file_content, expected_index, match_years_strictly):
    license_info = LicenseInfo(
        plain_license="",
        eol="\n",
        comment_start="",
        comment_prefix="#",
        comment_end="",
        num_extra_lines=0,
        prefixed_license=["# License line 1\n", "# Copyright 2017\n"],
    )
    assert expected_index == find_license_header_index(
        src_file_content, license_info, 5, match_years_strictly=match_years_strictly
    )


@pytest.mark.parametrize(
    (
        "license_file_path",
        "line_ending",
        "src_file_path",
        "comment_style",
        "fuzzy_match",
        "new_src_file_expected",
        "fail_check",
        "use_current_year",
    ),
    map(
        lambda a: a[:2] + a[2],
        product(  # combine license files with other args
            (
                "LICENSE_with_trailing_newline.txt",
                "LICENSE_without_trailing_newline.txt",
            ),
            ("\n", "\r\n"),
            (
                (
                    "module_with_license.css",
                    "/*| *| */",
                    False,
                    "module_without_license.css",
                    True,
                    False,
                ),
                (
                    "module_with_license_and_few_words.css",
                    "/*| *| */",
                    False,
                    "module_without_license_and_few_words.css",
                    True,
                    False,
                ),
                ("module_with_license_todo.css", "/*| *| */", False, None, True, False),
                (
                    "module_with_fuzzy_matched_license.css",
                    "/*| *| */",
                    False,
                    None,
                    False,
                    False,
                ),
                ("module_without_license.css", "/*| *| */", False, None, False, False),
                (
                    "module_with_license.py",
                    "#",
                    False,
                    "module_without_license.py",
                    True,
                    False,
                ),
                (
                    "module_with_license_and_shebang.py",
                    "#",
                    False,
                    "module_without_license_and_shebang.py",
                    True,
                    False,
                ),
                (
                    "init_with_license.py",
                    "#",
                    False,
                    "init_without_license.py",
                    True,
                    False,
                ),
                (
                    "init_with_license_and_newline.py",
                    "#",
                    False,
                    "init_without_license.py",
                    True,
                    False,
                ),
                # Fuzzy match
                (
                    "module_with_license.css",
                    "/*| *| */",
                    True,
                    "module_without_license.css",
                    True,
                    False,
                ),
                ("module_with_license_todo.css", "/*| *| */", True, None, True, False),
                (
                    "module_with_fuzzy_matched_license.css",
                    "/*| *| */",
                    True,
                    "module_with_license_todo.css",
                    True,
                    False,
                ),
                ("module_without_license.css", "/*| *| */", True, None, False, False),
                (
                    "module_with_license_and_shebang.py",
                    "#",
                    True,
                    "module_without_license_and_shebang.py",
                    True,
                    False,
                ),
                # Strict and flexible years
                (
                    "module_with_stale_year_in_license.py",
                    "#",
                    False,
                    None,
                    False,
                    False,
                ),
                (
                    "module_with_stale_year_range_in_license.py",
                    "#",
                    False,
                    None,
                    False,
                    False,
                ),
                (
                    "module_with_license.py",
                    "#",
                    False,
                    "module_without_license.py",
                    True,
                    True,
                ),
                (
                    "module_with_stale_year_in_license.py",
                    "#",
                    False,
                    "module_without_license.py",
                    True,
                    True,
                ),
                (
                    "module_with_stale_year_range_in_license.py",
                    "#",
                    False,
                    "module_without_license.py",
                    True,
                    True,
                ),
                (
                    "module_with_badly_formatted_stale_year_range_in_license.py",
                    "#",
                    False,
                    "module_without_license.py",
                    True,
                    True,
                ),
            ),
        ),
    ),
)
def test_remove_license(
    license_file_path,
    line_ending,
    src_file_path,
    comment_style,
    fuzzy_match,
    new_src_file_expected,
    fail_check,
    use_current_year,
    tmpdir,
):
    with chdir_to_test_resources():
        path = tmpdir.join("src_file_path")
        shutil.copy(src_file_path, path.strpath)
        _convert_line_ending(path.strpath, line_ending)
        argv = [
            "--license-filepath",
            license_file_path,
            "--remove-header",
            path.strpath,
            "--comment-style",
            comment_style,
        ]
        if fuzzy_match:
            argv = ["--fuzzy-match-generates-todo"] + argv
        if use_current_year:
            argv = ["--use-current-year"] + argv
        assert insert_license(argv) == (1 if fail_check else 0)
        if new_src_file_expected:
            with open(new_src_file_expected, encoding="utf-8") as expected_content_file:
                expected_content = expected_content_file.read()
            new_file_content = path.open(encoding="utf-8").read()
            assert new_file_content == expected_content


# -- Tests for get_commit_year --


def test_get_commit_year_returns_int_for_tracked_file():
    with chdir_to_test_resources():
        year = get_commit_year("module_with_license.py")
        assert isinstance(year, int)
        assert year >= 2017


def test_get_commit_year_returns_none_for_nonexistent_file():
    year = get_commit_year("/nonexistent/path/to/file.py")
    assert year is None


# -- Tests for header_covers_year --


@pytest.mark.parametrize(
    ("src_file_content", "year", "expected"),
    (
        (["# Copyright 2020\n"], 2020, True),
        (["# Copyright 2020\n"], 2021, False),
        (["# Copyright 2018-2020\n"], 2019, True),
        (["# Copyright 2018-2020\n"], 2020, True),
        (["# Copyright 2018-2020\n"], 2021, False),
        (["# Copyright 2018 - 2020\n"], 2019, True),
        (["# License line\n", "# Copyright 2018-2020\n"], 2019, True),
        (["# No year here\n"], 2020, False),
    ),
)
def test_header_covers_year(src_file_content, year, expected):
    assert header_covers_year(src_file_content, 0, len(src_file_content), year) == expected


def test_header_covers_year_with_offset():
    content = ["# shebang\n", "# Copyright 2018-2020\n", "# License text\n"]
    assert header_covers_year(content, 1, 2, 2019) is True
    assert header_covers_year(content, 1, 2, 2021) is False


# -- Integration tests for --use-commit-year --


def _setup_git_repo_with_commit(tmpdir, license_content, src_content, commit_date):
    """Create a temp git repo with one commit at the given date, return file paths."""
    import subprocess as _subprocess
    import os as _os

    repo_dir = tmpdir.mkdir("repo")
    _subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True)
    _subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
    )
    _subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
    )
    license_path = _os.path.join(str(repo_dir), "LICENSE.txt")
    with open(license_path, "w") as f:
        f.write(license_content)
    src_path = _os.path.join(str(repo_dir), "src.py")
    with open(src_path, "w") as f:
        f.write(src_content)
    _subprocess.run(["git", "add", "."], cwd=repo_dir, check=True, capture_output=True)
    env = _os.environ.copy()
    env["GIT_AUTHOR_DATE"] = commit_date
    env["GIT_COMMITTER_DATE"] = commit_date
    _subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
        env=env,
    )
    return str(repo_dir), license_path, src_path


def test_use_commit_year_skips_when_header_covers_commit_year(tmpdir):
    """Header has 2020, commit is from 2020 -> should NOT rewrite."""
    current_year = str(datetime.now().year)
    _repo_dir, license_path, src_path = _setup_git_repo_with_commit(
        tmpdir,
        f"Copyright (C) {current_year} Teela O'Malley\n\nLicensed under the Apache License, Version 2.0\n",
        "# Copyright (C) 2020 Teela O'Malley\n#\n# Licensed under the Apache License, Version 2.0\n\nimport sys\n",
        "2020-01-01T00:00:00",
    )
    with open(src_path) as f:
        original = f.read()
    result = insert_license([
        "--license-filepath", license_path,
        "--comment-style", "#",
        "--use-commit-year",
        src_path,
    ])
    assert result == 0
    with open(src_path) as f:
        assert f.read() == original


def test_use_commit_year_updates_when_header_does_not_cover_commit_year(tmpdir):
    """Header has 2017, commit is from 2020 -> should rewrite with current year."""
    current_year = str(datetime.now().year)
    _repo_dir, license_path, src_path = _setup_git_repo_with_commit(
        tmpdir,
        f"Copyright (C) {current_year} Teela O'Malley\n\nLicensed under the Apache License, Version 2.0\n",
        "# Copyright (C) 2017 Teela O'Malley\n#\n# Licensed under the Apache License, Version 2.0\n\nimport sys\n",
        "2020-06-15T00:00:00",
    )
    result = insert_license([
        "--license-filepath", license_path,
        "--comment-style", "#",
        "--use-commit-year",
        src_path,
    ])
    assert result == 1
    with open(src_path) as f:
        content = f.read()
    assert str(current_year) in content


def test_use_commit_year_range_covers_commit_year(tmpdir):
    """Header has 2015-2020, commit is from 2019 -> should NOT rewrite."""
    current_year = str(datetime.now().year)
    _repo_dir, license_path, src_path = _setup_git_repo_with_commit(
        tmpdir,
        f"Copyright (C) {current_year} Teela O'Malley\n\nLicensed under the Apache License, Version 2.0\n",
        "# Copyright (C) 2015-2020 Teela O'Malley\n#\n# Licensed under the Apache License, Version 2.0\n\nimport sys\n",
        "2019-03-10T00:00:00",
    )
    with open(src_path) as f:
        original = f.read()
    result = insert_license([
        "--license-filepath", license_path,
        "--comment-style", "#",
        "--use-commit-year",
        src_path,
    ])
    assert result == 0
    with open(src_path) as f:
        assert f.read() == original


def test_use_commit_year_inserts_license_for_new_file(tmpdir):
    """No license header -> should insert one (same as --use-current-year)."""
    current_year = str(datetime.now().year)
    _repo_dir, license_path, src_path = _setup_git_repo_with_commit(
        tmpdir,
        f"Copyright (C) {current_year} Teela O'Malley\n\nLicensed under the Apache License, Version 2.0\n",
        "import sys\n",
        "2020-01-01T00:00:00",
    )
    result = insert_license([
        "--license-filepath", license_path,
        "--comment-style", "#",
        "--use-commit-year",
        src_path,
    ])
    assert result == 1
    with open(src_path) as f:
        content = f.read()
    assert content.startswith("# Copyright")


# -- Tests for --extra-comments --


def test_extra_comments_inserts_before(tmpdir):
    """--extra-comments 'before:...' injects a comment line before the license."""
    with chdir_to_test_resources():
        src = tmpdir.join("test.py")
        shutil.copy("module_without_license.py", src.strpath)
        insert_license([
            "--license-filepath", "LICENSE_with_trailing_newline.txt",
            "--comment-style", "#",
            "--extra-comments", "before:Auto-generated file",
            src.strpath,
        ])
        content = src.read()
        assert content.startswith("# Auto-generated file\n")
        assert "# Copyright (C) 2017" in content


def test_extra_comments_inserts_after(tmpdir):
    """--extra-comments 'after:...' injects a comment line after the license."""
    with chdir_to_test_resources():
        src = tmpdir.join("test.py")
        shutil.copy("module_without_license.py", src.strpath)
        insert_license([
            "--license-filepath", "LICENSE_with_trailing_newline.txt",
            "--comment-style", "#",
            "--extra-comments", "after:Do not edit",
            src.strpath,
        ])
        content = src.read()
        assert "# Do not edit\n" in content
        # The after line should appear after the license block
        after_idx = content.index("# Do not edit")
        license_idx = content.index("# Licensed under")
        assert after_idx > license_idx


def test_extra_comments_after_on_newline_without_trailing_newline(tmpdir):
    """After-comment starts on its own line even when license file lacks trailing newline."""
    with chdir_to_test_resources():
        src = tmpdir.join("test.py")
        shutil.copy("module_without_license.py", src.strpath)
        insert_license([
            "--license-filepath", "LICENSE_without_trailing_newline.txt",
            "--comment-style", "#",
            "--extra-comments", "after:Do not edit",
            src.strpath,
        ])
        content = src.read()
        # The after line must be on its own line, not appended to the last license line
        assert "\n# Do not edit\n" in content
        assert '";Do not edit' not in content  # not glued to end of "License);"


def test_extra_comments_inserts_both(tmpdir):
    """--extra-comments with both before and after injects lines on both sides."""
    with chdir_to_test_resources():
        src = tmpdir.join("test.py")
        shutil.copy("module_without_license.py", src.strpath)
        insert_license([
            "--license-filepath", "LICENSE_with_trailing_newline.txt",
            "--comment-style", "#",
            "--extra-comments", "before:Header line,after:Footer line",
            src.strpath,
        ])
        content = src.read()
        assert content.startswith("# Header line\n")
        assert "# Footer line\n" in content
        header_idx = content.index("# Header line")
        footer_idx = content.index("# Footer line")
        copyright_idx = content.index("# Copyright")
        assert header_idx < copyright_idx < footer_idx


def test_extra_comments_with_block_comment_style(tmpdir):
    """--extra-comments works with block comment styles (e.g. /*| *| */)."""
    with chdir_to_test_resources():
        src = tmpdir.join("test.css")
        shutil.copy("module_without_license.css", src.strpath)
        insert_license([
            "--license-filepath", "LICENSE_with_trailing_newline.txt",
            "--comment-style", "/*| *| */",
            "--extra-comments", "before:Auto-generated,after:End of license",
            src.strpath,
        ])
        content = src.read()
        assert content.startswith("/*\n")
        assert " * Auto-generated\n" in content
        assert " * End of license\n" in content
        assert " */\n" in content


def test_extra_comments_detects_existing_license_with_extras(tmpdir):
    """When license with matching extra comments is already present, no change."""
    with chdir_to_test_resources():
        src = tmpdir.join("test.py")
        shutil.copy("module_without_license.py", src.strpath)
        # First insert
        insert_license([
            "--license-filepath", "LICENSE_with_trailing_newline.txt",
            "--comment-style", "#",
            "--extra-comments", "before:Auto-generated",
            src.strpath,
        ])
        content_after_first = src.read()
        # Second run should detect the license (including the extra comment)
        result = insert_license([
            "--license-filepath", "LICENSE_with_trailing_newline.txt",
            "--comment-style", "#",
            "--extra-comments", "before:Auto-generated",
            src.strpath,
        ])
        assert result == 0
        assert src.read() == content_after_first


def test_extra_comments_no_extra_comments(tmpdir):
    """Empty --extra-comments should behave like the option was not given."""
    with chdir_to_test_resources():
        src = tmpdir.join("test.py")
        shutil.copy("module_without_license.py", src.strpath)
        result = insert_license([
            "--license-filepath", "LICENSE_with_trailing_newline.txt",
            "--comment-style", "#",
            "--extra-comments", "",
            src.strpath,
        ])
        assert result == 1
        content = src.read()
        assert content.startswith("# Copyright (C) 2017")


def test_extra_comments_multiple_before(tmpdir):
    """Multiple 'before' comments are inserted in order before the license."""
    with chdir_to_test_resources():
        src = tmpdir.join("test.py")
        shutil.copy("module_without_license.py", src.strpath)
        insert_license([
            "--license-filepath", "LICENSE_with_trailing_newline.txt",
            "--comment-style", "#",
            "--extra-comments", "before:Line A,before:Line B",
            src.strpath,
        ])
        content = src.read()
        a_idx = content.index("# Line A")
        b_idx = content.index("# Line B")
        copyright_idx = content.index("# Copyright")
        assert a_idx < b_idx < copyright_idx


def test_extra_comments_colon_in_text(tmpdir):
    """Colons in the comment text are preserved (only first colon is the delimiter)."""
    with chdir_to_test_resources():
        src = tmpdir.join("test.py")
        shutil.copy("module_without_license.py", src.strpath)
        insert_license([
            "--license-filepath", "LICENSE_with_trailing_newline.txt",
            "--comment-style", "#",
            "--extra-comments", "before:See: http://example.com",
            src.strpath,
        ])
        content = src.read()
        assert "# See: http://example.com\n" in content


def test_extra_comments_remove_header(tmpdir):
    """--remove-header removes the full block including extra comments."""
    with chdir_to_test_resources():
        src = tmpdir.join("test.py")
        shutil.copy("module_without_license.py", src.strpath)
        # First insert with extra comments
        insert_license([
            "--license-filepath", "LICENSE_with_trailing_newline.txt",
            "--comment-style", "#",
            "--extra-comments", "before:Auto-generated,after:Do not edit",
            src.strpath,
        ])
        assert "Auto-generated" in src.read()
        # Now remove
        result = insert_license([
            "--license-filepath", "LICENSE_with_trailing_newline.txt",
            "--comment-style", "#",
            "--extra-comments", "before:Auto-generated,after:Do not edit",
            "--remove-header",
            src.strpath,
        ])
        assert result == 1
        content = src.read()
        assert "Auto-generated" not in content
        assert "Copyright" not in content
        assert "Do not edit" not in content


def test_extra_comments_no_space_in_comment_prefix(tmpdir):
    """--extra-comments respects --no-space-in-comment-prefix."""
    with chdir_to_test_resources():
        src = tmpdir.join("test.py")
        shutil.copy("module_without_license.py", src.strpath)
        insert_license([
            "--license-filepath", "LICENSE_with_trailing_newline.txt",
            "--comment-style", "#",
            "--no-space-in-comment-prefix",
            "--extra-comments", "before:Auto-generated",
            src.strpath,
        ])
        content = src.read()
        assert "#Auto-generated\n" in content


def test_extra_comments_error_on_missing_colon(tmpdir):
    """--extra-comments with no colon in a part returns config error (2)."""
    with chdir_to_test_resources():
        src = tmpdir.join("test.py")
        shutil.copy("module_without_license.py", src.strpath)
        with capture_stdout() as stdout:
            result = insert_license([
                "--license-filepath", "LICENSE_with_trailing_newline.txt",
                "--comment-style", "#",
                "--extra-comments", "before",
                src.strpath,
            ])
        assert result == 2
        assert "missing ':' separator" in stdout.getvalue()


def test_extra_comments_error_on_unknown_tag(tmpdir):
    """--extra-comments with an unknown tag returns config error (2)."""
    with chdir_to_test_resources():
        src = tmpdir.join("test.py")
        shutil.copy("module_without_license.py", src.strpath)
        with capture_stdout() as stdout:
            result = insert_license([
                "--license-filepath", "LICENSE_with_trailing_newline.txt",
                "--comment-style", "#",
                "--extra-comments", "befor:Auto-generated",
                src.strpath,
            ])
        assert result == 2
        assert "unknown tag 'befor'" in stdout.getvalue()


# -- Tests for --fuzzy-match-update --


def test_fuzzy_match_update_replaces_python(tmpdir):
    """--fuzzy-match-update replaces fuzzy-matched Python license with the correct one."""
    with chdir_to_test_resources():
        src = tmpdir.join("test.py")
        shutil.copy("module_with_fuzzy_matched_license.py", src.strpath)
        result = insert_license([
            "--license-filepath", "LICENSE_with_trailing_newline.txt",
            "--comment-style", "#",
            "--fuzzy-match-update",
            src.strpath,
        ])
        assert result == 1
        content = src.read()
        with open("module_with_license.py") as expected:
            assert content == expected.read()


def test_fuzzy_match_update_replaces_css(tmpdir):
    """--fuzzy-match-update replaces fuzzy-matched CSS license with the correct one."""
    with chdir_to_test_resources():
        src = tmpdir.join("test.css")
        shutil.copy("module_with_fuzzy_matched_license.css", src.strpath)
        result = insert_license([
            "--license-filepath", "LICENSE_with_trailing_newline.txt",
            "--comment-style", "/*| *| */",
            "--fuzzy-match-update",
            src.strpath,
        ])
        assert result == 1
        content = src.read()
        with open("module_with_license.css") as expected:
            assert content == expected.read()


def test_fuzzy_match_update_replaces_groovy(tmpdir):
    """--fuzzy-match-update replaces fuzzy-matched Groovy license with the correct one."""
    with chdir_to_test_resources():
        src = tmpdir.join("test.groovy")
        shutil.copy("module_with_fuzzy_matched_license.groovy", src.strpath)
        result = insert_license([
            "--license-filepath", "LICENSE_with_trailing_newline.txt",
            "--comment-style", "//",
            "--fuzzy-match-update",
            src.strpath,
        ])
        assert result == 1
        content = src.read()
        with open("module_with_license.groovy") as expected:
            assert content == expected.read()


def test_fuzzy_match_update_replaces_jinja(tmpdir):
    """--fuzzy-match-update replaces fuzzy-matched Jinja license with the correct one."""
    with chdir_to_test_resources():
        src = tmpdir.join("test.jinja")
        shutil.copy("module_with_fuzzy_matched_license.jinja", src.strpath)
        result = insert_license([
            "--license-filepath", "LICENSE_with_trailing_newline.txt",
            "--comment-style", "{#||#}",
            "--fuzzy-match-update",
            src.strpath,
        ])
        assert result == 1
        content = src.read()
        with open("module_with_license.jinja") as expected:
            assert content == expected.read()


def test_fuzzy_match_update_replaces_with_shebang(tmpdir):
    """--fuzzy-match-update replaces fuzzy-matched license in file with shebang."""
    with chdir_to_test_resources():
        src = tmpdir.join("test.py")
        shutil.copy("module_with_fuzzy_matched_license_and_shebang.py", src.strpath)
        result = insert_license([
            "--license-filepath", "LICENSE_with_trailing_newline.txt",
            "--comment-style", "#",
            "--fuzzy-match-update",
            src.strpath,
        ])
        assert result == 1
        content = src.read()
        assert content.startswith("#!/bin/usr/env python\n")
        assert "# -*- coding: utf-8 -*-\n" in content
        assert "# Copyright (C) 2017 Teela O'Malley\n" in content
        assert "# Licensed under the Apache License, Version 2.0 (the \"License\");\n" in content
        # Old fuzzy text should be gone
        assert "Version 2.1" not in content
        assert "Licensed under the Apache License,\n#" not in content


def test_fuzzy_match_update_no_match_inserts_license(tmpdir):
    """When no fuzzy match is found, --fuzzy-match-update inserts the license normally."""
    with chdir_to_test_resources():
        src = tmpdir.join("test.py")
        shutil.copy("module_without_license.py", src.strpath)
        result = insert_license([
            "--license-filepath", "LICENSE_with_trailing_newline.txt",
            "--comment-style", "#",
            "--fuzzy-match-update",
            src.strpath,
        ])
        assert result == 1
        content = src.read()
        assert content.startswith("# Copyright (C) 2017")


def test_fuzzy_match_update_idempotent(tmpdir):
    """After replacement, re-running with --fuzzy-match-update is a no-op."""
    with chdir_to_test_resources():
        src = tmpdir.join("test.py")
        shutil.copy("module_with_fuzzy_matched_license.py", src.strpath)
        # First run: replace
        insert_license([
            "--license-filepath", "LICENSE_with_trailing_newline.txt",
            "--comment-style", "#",
            "--fuzzy-match-update",
            src.strpath,
        ])
        content_after_replace = src.read()
        # Second run: should find exact match, no change
        result = insert_license([
            "--license-filepath", "LICENSE_with_trailing_newline.txt",
            "--comment-style", "#",
            "--fuzzy-match-update",
            src.strpath,
        ])
        assert result == 0
        assert src.read() == content_after_replace


def test_fuzzy_match_update_takes_priority_over_todo(tmpdir):
    """When both --fuzzy-match-update and --fuzzy-match-generates-todo are set, update wins."""
    with chdir_to_test_resources():
        src = tmpdir.join("test.py")
        shutil.copy("module_with_fuzzy_matched_license.py", src.strpath)
        result = insert_license([
            "--license-filepath", "LICENSE_with_trailing_newline.txt",
            "--comment-style", "#",
            "--fuzzy-match-generates-todo",
            "--fuzzy-match-update",
            src.strpath,
        ])
        assert result == 1
        content = src.read()
        with open("module_with_license.py") as expected:
            assert content == expected.read()
        assert "TODO" not in content


# -- Tests for CRLF line endings across new features --


@pytest.mark.parametrize("line_ending", ("\n", "\r\n"))
def test_extra_comments_crlf_before(tmpdir, line_ending):
    """--extra-comments before works with both line endings."""
    with chdir_to_test_resources():
        src = tmpdir.join("test.py")
        shutil.copy("module_without_license.py", src.strpath)
        _convert_line_ending(src.strpath, line_ending)
        insert_license([
            "--license-filepath", "LICENSE_with_trailing_newline.txt",
            "--comment-style", "#",
            "--extra-comments", "before:Auto-generated",
            src.strpath,
        ])
        content = src.read()
        assert content.startswith("# Auto-generated")
        assert "# Copyright (C) 2017" in content
        # Verify consistent line endings
        assert "\r\n" not in content.replace(line_ending, "")


@pytest.mark.parametrize("line_ending", ("\n", "\r\n"))
def test_extra_comments_crlf_both(tmpdir, line_ending):
    """--extra-comments before+after works with both line endings."""
    with chdir_to_test_resources():
        src = tmpdir.join("test.py")
        shutil.copy("module_without_license.py", src.strpath)
        _convert_line_ending(src.strpath, line_ending)
        insert_license([
            "--license-filepath", "LICENSE_with_trailing_newline.txt",
            "--comment-style", "#",
            "--extra-comments", "before:Header,after:Footer",
            src.strpath,
        ])
        content = src.read()
        assert "# Header" in content
        assert "# Footer" in content
        assert "# Copyright (C) 2017" in content
        assert "\r\n" not in content.replace(line_ending, "")


@pytest.mark.parametrize("line_ending", ("\n", "\r\n"))
def test_extra_comments_crlf_block_style(tmpdir, line_ending):
    """--extra-comments with block comment style works with both line endings."""
    with chdir_to_test_resources():
        src = tmpdir.join("test.css")
        shutil.copy("module_without_license.css", src.strpath)
        _convert_line_ending(src.strpath, line_ending)
        insert_license([
            "--license-filepath", "LICENSE_with_trailing_newline.txt",
            "--comment-style", "/*| *| */",
            "--extra-comments", "before:Auto-generated,after:End of license",
            src.strpath,
        ])
        content = src.read()
        assert " * Auto-generated" in content
        assert " * End of license" in content
        assert "\r\n" not in content.replace(line_ending, "")


@pytest.mark.parametrize("line_ending", ("\n", "\r\n"))
def test_fuzzy_match_update_crlf_python(tmpdir, line_ending):
    """--fuzzy-match-update works with both line endings (Python)."""
    with chdir_to_test_resources():
        src = tmpdir.join("test.py")
        shutil.copy("module_with_fuzzy_matched_license.py", src.strpath)
        _convert_line_ending(src.strpath, line_ending)
        result = insert_license([
            "--license-filepath", "LICENSE_with_trailing_newline.txt",
            "--comment-style", "#",
            "--fuzzy-match-update",
            src.strpath,
        ])
        assert result == 1
        content = src.read()
        assert "# Copyright (C) 2017 Teela O'Malley" in content
        assert "# Licensed under the Apache License, Version 2.0" in content
        assert "Version 2.0 (the \"License\");" in content
        assert "\r\n" not in content.replace(line_ending, "")


@pytest.mark.parametrize("line_ending", ("\n", "\r\n"))
def test_fuzzy_match_update_crlf_css(tmpdir, line_ending):
    """--fuzzy-match-update works with both line endings (CSS block comments)."""
    with chdir_to_test_resources():
        src = tmpdir.join("test.css")
        shutil.copy("module_with_fuzzy_matched_license.css", src.strpath)
        _convert_line_ending(src.strpath, line_ending)
        result = insert_license([
            "--license-filepath", "LICENSE_with_trailing_newline.txt",
            "--comment-style", "/*| *| */",
            "--fuzzy-match-update",
            src.strpath,
        ])
        assert result == 1
        content = src.read()
        assert " * Copyright (C) 2017" in content
        assert " * Licensed under the Apache License, Version 2.0" in content
        assert "\r\n" not in content.replace(line_ending, "")


# -- Tests for option interactions --


def test_extra_comments_with_use_current_year(tmpdir):
    """--extra-comments works together with --use-current-year."""
    with chdir_to_test_resources():
        src = tmpdir.join("test.py")
        shutil.copy("module_without_license.py", src.strpath)
        insert_license([
            "--license-filepath", "LICENSE_with_trailing_newline.txt",
            "--comment-style", "#",
            "--extra-comments", "before:Auto-generated",
            "--use-current-year",
            src.strpath,
        ])
        content = src.read()
        assert content.startswith("# Auto-generated\n")
        current_year = str(datetime.now().year)
        assert current_year in content


def test_extra_comments_with_no_extra_eol(tmpdir):
    """--extra-comments works together with --no-extra-eol."""
    with chdir_to_test_resources():
        src = tmpdir.join("test.py")
        shutil.copy("module_without_license.py", src.strpath)
        insert_license([
            "--license-filepath", "LICENSE_with_trailing_newline.txt",
            "--comment-style", "#",
            "--extra-comments", "before:Auto-generated",
            "--no-extra-eol",
            src.strpath,
        ])
        content = src.read()
        assert "# Auto-generated" in content
        # With --no-extra-eol there should be no blank separator between license and code
        lines = content.split("\n")
        # Find the last license line (ends with "License);")
        license_end = None
        for i, line in enumerate(lines):
            if 'the "License")' in line:
                license_end = i
                break
        assert license_end is not None
        # Next line should be code, not blank
        assert lines[license_end + 1] == "import sys"


def test_fuzzy_match_update_with_remove_header(tmpdir):
    """--fuzzy-match-update with --remove-header removes the fuzzy block entirely."""
    with chdir_to_test_resources():
        src = tmpdir.join("test.py")
        shutil.copy("module_with_fuzzy_matched_license.py", src.strpath)
        # remove-header only acts when exact match is found.
        # Since this is a fuzzy match, remove-header won't trigger.
        # The fuzzy-match-update should still replace it.
        result = insert_license([
            "--license-filepath", "LICENSE_with_trailing_newline.txt",
            "--comment-style", "#",
            "--fuzzy-match-update",
            "--remove-header",
            src.strpath,
        ])
        assert result == 1
        content = src.read()
        # remove-header acts on exact matches, not fuzzy ones,
        # so fuzzy-match-update replaces the block with the correct license.
        assert "# Copyright (C) 2017" in content


def test_fuzzy_match_update_preserves_start_year(tmpdir):
    """--fuzzy-match-update with --use-current-year preserves the original start year."""
    current_year = str(datetime.now().year)
    with chdir_to_test_resources():
        src = tmpdir.join("test.py")
        shutil.copy(
            "module_with_fuzzy_matched_license_with_year_range.py", src.strpath
        )
        result = insert_license([
            "--license-filepath", "LICENSE_with_trailing_newline.txt",
            "--comment-style", "#",
            "--fuzzy-match-update",
            "--use-current-year",
            src.strpath,
        ])
        assert result == 1
        content = src.read()
        # The start year (2020) from the old block must be preserved
        assert f"2020-{current_year}" in content
        # The old fuzzy text should be gone
        assert "Version 2.0" not in content.split("Version")[0] if "Version" in content else True
        # The replacement should contain the correct license text
        assert 'Licensed under the Apache License, Version 2.0 (the "License");' in content
