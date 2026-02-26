"""Configuration file for the Sphinx documentation builder.

For the full list of built-in configuration values, see the documentation:
https://www.sphinx-doc.org/en/master/usage/configuration.html
"""

import datetime
import importlib.metadata
import pathlib
import sys
import tomllib

PROJECT_ROOT_DIR = pathlib.Path(__file__).parent.parent.parent

sys.path.insert(0, str(PROJECT_ROOT_DIR / "src"))

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
version = project_version

# --- General configuration --------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration
templates_path = ["_templates"]

extensions = [
    "sphinx.ext.napoleon",  # support for numpy-style doc-strings
    "sphinx.ext.autodoc",  # automatic documentation from doc-strings
    "sphinx.ext.autosummary",  # generate API documentation
    "sphinx.ext.viewcode",  # add links to highlighted source code
]

napoleon_google_docstring = False
napoleon_include_private_with_doc = True
napoleon_use_admonition_for_notes = True

autodoc_default_options = {
    "members": True,  # https://www.sphinx-doc.org/en/master/usage/extensions/autodoc.html#directive-option-automodule-members
    "undoc-members": False,  # https://www.sphinx-doc.org/en/master/usage/extensions/autodoc.html#directive-option-automodule-undoc-members
    "private-members": False,  # https://www.sphinx-doc.org/en/master/usage/extensions/autodoc.html#directive-option-automodule-private-members
    "inherited-members": False,  # https://www.sphinx-doc.org/en/master/usage/extensions/autodoc.html#directive-option-autoclass-inherited-members
    "imported-members": False,  # https://www.sphinx-doc.org/en/master/usage/extensions/autodoc.html#directive-option-automodule-imported-members
    "member-order": "bysource",  # https://www.sphinx-doc.org/en/master/usage/extensions/autodoc.html#directive-option-automodule-member-order
    "show-inheritance": True,  # https://www.sphinx-doc.org/en/master/usage/extensions/autodoc.html#directive-option-autoclass-show-inheritance
    "class-doc-from": "init",  # https://www.sphinx-doc.org/en/master/usage/extensions/autodoc.html#directive-option-autoclass-class-doc-from
}

autosummary_generate = True

# --- Options for HTML output ------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output
html_theme = "furo"
html_logo = "static/images/logos/fastcc.svg"
html_theme_options = {
    "sidebar_hide_name": True,
}
