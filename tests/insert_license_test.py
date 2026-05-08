from datetime import datetime
from itertools import chain, product
import shutil
import pytest

from pre_commit_hooks.insert_license import main as insert_license, LicenseInfo
from pre_commit_hooks.insert_license import find_license_header_index

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




# -- CRLF and option interaction tests for --extra-comments --

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
