import base64
import glob
import hashlib
import os
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

import click
import tomli
from click import Option, echo, style

from . import ERROR_MSG_PREFIX


def nonceify(body: str) -> str:
    """
    Nonceify the changelog body!

    Generate hopefully-unique string of characters meant to prevent filename collisions. by computing the
    MD5 hash of the text, converting it to base64 (using the "urlsafe" alphabet), and taking the first
    6 characters of that.
    """
    digest = hashlib.md5(body.encode("utf-8")).digest()  # noqa: S303
    return base64.urlsafe_b64encode(digest)[0:6].decode("ascii")


def _out(message: Optional[str] = None, nl: bool = True, **styles: Any) -> None:
    if message is not None:
        if "bold" not in styles:
            styles["bold"] = True
        message = style(message, **styles)
    echo(message, nl=nl, err=True)


def _err(message: Optional[str] = None, nl: bool = True, **styles: Any) -> None:
    if message is not None:
        if "fg" not in styles:
            styles["fg"] = "red"
        message = style(message, **styles)
    echo(message, nl=nl, err=True)


def out(message: Optional[str] = None, nl: bool = True, **styles: Any) -> None:
    """Utility function to output a styled message to console."""
    _out(message, nl=nl, **styles)


def err(message: Optional[str] = None, nl: bool = True, **styles: Any) -> None:
    """Utility function to output a styled error message to console."""
    _err(message, nl=nl, **styles)


class NotRequiredIf(Option):
    def __init__(self, *args, **kwargs):
        self.not_required_if = kwargs.pop("not_required_if")
        assert self.not_required_if, "'not_required_if' parameter required"  # noqa: S101
        kwargs["help"] = (
            kwargs.get("help", "")
            + " NOTE: This argument is mutually exclusive with %s" % self.not_required_if
        ).strip()
        super(NotRequiredIf, self).__init__(*args, **kwargs)

    def handle_parse_result(self, ctx: click.Context, opts: Mapping[str, Any], args: List[str]):
        we_are_present = self.name in opts
        other_present = self.not_required_if in opts

        if other_present:
            if we_are_present:
                err(
                    f"{ERROR_MSG_PREFIX} Illegal usage. `%s` is mutually exclusive with `%s`"
                    % (self.name, self.not_required_if),
                    fg="red",
                )
                ctx.exit(code=1)
            else:
                self.prompt = None

        return super(NotRequiredIf, self).handle_parse_result(ctx, opts, args)


def sanitize_section(section):
    """Cleans up a section string, making it viable as a directory name."""
    return section.replace("/", "-").lower()


def glob_fragments(version: str, sections: List[str]) -> List[str]:
    filenames = []
    base = os.path.join("news", version)

    if version != "next":
        wildcard = base + ".md"
        filenames.extend(glob.glob(wildcard))
    else:
        for section in sections:
            wildcard = os.path.join(base, sanitize_section(section), "*.md")
            entries = glob.glob(wildcard)
            entries.sort(reverse=True)
            deletables = [x for x in entries if x.endswith("/README.md")]
            for filename in deletables:
                entries.remove(filename)
            filenames.extend(entries)

    return filenames


def get_metadata_from_file(path: Path) -> dict:
    #  path = Path(Path.cwd(), f"news/next/pr-{self.gh_pr}.{self.news_type}.{self.nonce}.md")
    new_fragment_file = path.stem
    date, gh_pr, news_type, nonce = new_fragment_file.split(".")

    with open(path, "r", encoding="utf-8") as file:
        news_entry = file.read()

    metadata = {"date": date, "gh_pr": gh_pr, "news_type": news_type, "nonce": nonce, "new_entry": news_entry}
    return metadata


def get_project_meta() -> Tuple[str, str]:
    with open("pyproject.toml", "rb") as pyproject:
        file_contents = tomli.load(pyproject)

    version = file_contents["tool"]["poetry"]["version"]
    name = file_contents["tool"]["poetry"]["name"]
    return name, version


def load_toml_config() -> Dict[str, Any]:
    config_path = Path(Path.cwd(), "scripts/news/config.toml")
    default_config_url = "URL HERE PLEASE"

    if not config_path.exists():
        err(
            f"Configuration not found. Create a config file at '{config_path}', and see "
            f"'{default_config_url}' for an example configuration. "
        )
        sys.exit(1)
    try:
        with open(config_path, mode="r") as file:
            toml_dict = tomli.loads(file.read())
    except tomli.TOMLDecodeError as e:
        message = "Invalid changelog news configuration at {}\n{}".format(
            config_path,
            "".join(traceback.format_exception_only(type(e), e)),
        )
        err(message)
        sys.exit(1)
    else:
        return toml_dict
