"""Configuration file for the Sphinx documentation builder.

For the full list of built-in configuration values, see:
https://www.sphinx-doc.org/en/master/usage/configuration.html
"""

import datetime
import importlib.metadata
import pathlib
import sys
import tomllib

PROJECT_ROOT_DIR = pathlib.Path(__file__).parent.parent.parent
sys.path.insert(0, str((PROJECT_ROOT_DIR / "src").resolve()))

with (PROJECT_ROOT_DIR / "pyproject.toml").open("rb") as configuration_file:
    configuration = tomllib.load(configuration_file)
    project_name = configuration["project"]["name"]
    primary_project_author = configuration["project"]["authors"][0]["name"]
    project_version = importlib.metadata.version(project_name)

# ----------------------------------------------------------------------
# --- Project information ----------------------------------------------
# ----------------------------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = project_name
author = primary_project_author
project_copyright = f"{datetime.datetime.now(tz=datetime.UTC).year}, {author}"
version = project_version
release = version

# ----------------------------------------------------------------------
# --- General configuration --------------------------------------------
# ----------------------------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.duration",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "myst_parser",
]

# ----------------------------------------------------------------------
# --- Builder options --------------------------------------------------
# ----------------------------------------------------------------------
html_theme = "furo"
html_theme_options = {
    "sidebar_hide_name": True,
}
html_logo = "static/images/logos/fastcc.svg"
html_favicon = html_logo

napoleon_google_docstring = False
napoleon_include_private_with_doc = True
napoleon_use_admonition_for_notes = True
napoleon_use_ivar = True

autodoc_default_options = {
    "members": True,
    "undoc-members": False,
    "private-members": False,
    "inherited-members": False,
    "imported-members": False,
    "member-order": "bysource",
    "show-inheritance": True,
}

autosummary_generate = True
