"""
Exports the configuration to the configuration default files.

This is intented to be used as a local pre-commit hook, which runs if the modmail/config.py file is changed.
"""
import json
import pathlib
import sys
import typing
from collections import defaultdict

import atoml
import attr
import dotenv
import marshmallow
import yaml

import modmail.config


MODMAIL_CONFIG_DIR = pathlib.Path(modmail.config.__file__).parent
ENV_EXPORT_FILE = MODMAIL_CONFIG_DIR.parent / ".env.template"
APP_JSON_FILE = MODMAIL_CONFIG_DIR.parent / "app.json"
METADATA_PREFIX = "modmail_"


def export_default_conf() -> None:
    """Export default configuration as both toml and yaml to the preconfigured locations."""
    conf = modmail.config.get_default_config()
    dump: dict = modmail.config.ConfigurationSchema().dump(conf)

    # Sort the dictionary configuration.
    # This is the only place where the order of the config should matter, when exporting in a specific style
    def sort_dict(d: dict) -> dict:
        """Takes a dict and sorts it, recursively."""
        sorted_dict = {x[0]: x[1] for x in sorted(d.items(), key=lambda e: e[0])}

        for k, v in d.items():
            if not isinstance(v, dict):
                continue
            sorted_dict[k] = sort_dict(v)

        return sorted_dict

    dump = sort_dict(dump)
    autogen_gen_notice = f"Directly run scripts/{__file__.rsplit('/',1)[-1]!s} to generate."
    doc = atoml.document()
    doc.add(atoml.comment("This is an autogenerated TOML document."))
    doc.add(atoml.comment(autogen_gen_notice))
    doc.add(atoml.nl())

    doc.update(dump)

    # toml

    with open(MODMAIL_CONFIG_DIR / (modmail.config.AUTO_GEN_FILE_NAME + ".toml"), "w") as f:
        atoml.dump(doc, f)

    # yaml
    with open(MODMAIL_CONFIG_DIR / (modmail.config.AUTO_GEN_FILE_NAME + ".yaml"), "w") as f:
        f.write("# This is an autogenerated YAML document.\n")
        f.write(f"# {autogen_gen_notice}\n")
        yaml.dump(dump, f, indent=4, Dumper=yaml.SafeDumper)


def export_env_and_app_json_conf() -> None:
    """
    Exports required configuration variables to .env.template.

    Does NOT export *all* settable variables!

    Export the *required* environment variables to `.env.template`.
    Required environment variables are any Config.default.bot variables that default to marshmallow.missing

    TODO: as of right now, all configuration values can be configured with environment variables.
    However, this method only exports the MODMAIL_BOT_ *required* varaibles to the template files.
    This will be rewritten to support full unload and the new modmail.config.ConfigMetadata class.

    This means that in the end our exported variables are all prefixed with MODMAIL_BOT_,
    and followed by the uppercase name of each field.
    """
    env_prefix = modmail.config.ENV_PREFIX + modmail.config.BOT_ENV_PREFIX
    default = modmail.config.get_default_config()
    req_env_values: typing.Dict[str, attr.Attribute.metadata] = dict()
    fields = attr.fields(default.bot.__class__)
    for attribute in fields:
        if attribute.default is marshmallow.missing:
            req_env_values[env_prefix + attribute.name.upper()] = defaultdict(str, attribute.metadata)

    # dotenv modifies currently existing files, but we want to erase the current file
    ENV_EXPORT_FILE.unlink(missing_ok=True)
    ENV_EXPORT_FILE.touch()

    for k, v in req_env_values.items():
        dotenv.set_key(ENV_EXPORT_FILE, k, v[modmail.config.METADATA_TABLE].export_environment_prefill)

    # the rest of this is designated for the app.json file
    with open(APP_JSON_FILE) as f:
        try:
            app_json: typing.Dict = json.load(f)
        except Exception as e:
            print(
                "Oops! Please ensure the app.json file is valid json! "
                "If you've made manual edits, you may want to revert them."
            )
            raise e
    app_json_env = defaultdict(str)
    for env_var, meta in req_env_values.items():
        options = defaultdict(
            str,
            {
                "description": meta[modmail.config.METADATA_TABLE].description,
                "required": meta[modmail.config.METADATA_TABLE].app_json_required
                or meta.get("required", False),
            },
        )
        if (value := meta[modmail.config.METADATA_TABLE].app_json_default) is not None:
            options["value"] = value
        app_json_env[env_var] = options
    app_json["env"] = app_json_env
    with open(APP_JSON_FILE, "w") as f:
        json.dump(app_json, f, indent=4)
        f.write("\n")


def main() -> None:
    """
    Exports the default configuration.

    There's several parts to this export.
    First, export the default configuration to the default locations.

    Next, export the *required* configuration variables to the .env.template

    In addition, export to app.json when exporting .env.template.
    """
    export_default_conf()

    export_env_and_app_json_conf()


if __name__ == "__main__":
    print("Exporting configuration to default files. If they exist, overwriting their contents.")
    sys.exit(main())
