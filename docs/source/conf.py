import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent.resolve()))

# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'Lawo Device Factory'
copyright = '2025, Thomas Sutton'
author = 'Thomas Sutton'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.autodoc",       # Pulls docstrings automatically
    "sphinx.ext.napoleon",      # Supports Google/NumPy style docstrings
    "sphinx.ext.viewcode",      # Adds source code links
    # "sphinx_autodoc_typehints"  # Optional: type hints in docs
    'sphinx.ext.autosummary'
]
autosummary_generate = True

templates_path = ['_templates']
exclude_patterns = []



# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'furo'
html_theme_options = {}
html_theme_path = []
html_static_path = ['_static']
