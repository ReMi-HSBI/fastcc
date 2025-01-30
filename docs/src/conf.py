"""Configuration file for the Sphinx documentation builder.

For the full list of built-in configuration values, see the documentation:
https://www.sphinx-doc.org/en/master/usage/configuration.html
"""

import datetime
import importlib.metadata
import pathlib
import tomllib

PROJECT_ROOT_DIR = pathlib.Path(__file__).parent.parent.parent
with (PROJECT_ROOT_DIR / "pyproject.toml").open("rb") as configuration_file:
    configuration = tomllib.load(configuration_file)
    project_name = configuration["project"]["name"]
    primary_project_author = configuration["project"]["authors"][0]["name"]
    project_version = importlib.metadata.version(project_name)

# --- Project information ----------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information
project = project_name
author = primary_project_author
copyright = f"{datetime.datetime.now(tz=datetime.UTC).year}, {author}"  # noqa: A001
release = project_version

# --- General configuration --------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration
extensions = [
    "sphinx.ext.napoleon",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.viewcode",
]
templates_path = ["templates"]

napoleon_google_docstring = False
napoleon_include_private_with_doc = True
napoleon_use_admonition_for_notes = True

# --- Options for HTML output ------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output
html_theme = "furo"
html_logo = "static/images/fastci_logo.svg"
html_theme_options = {
    "sidebar_hide_name": True,
}
