# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------
import os
import sys

sys.path.insert(0, os.path.abspath("../.."))

# Dummy environment variables so autodoc can import modules that build a
# Settings() object at import time (the secrets have no defaults). setdefault
# never overwrites a value that is already present in the real environment.
os.environ.setdefault("DB_URL", "postgresql+asyncpg://docs:docs@localhost:5432/docs")
os.environ.setdefault("JWT_SECRET", "docs-build-secret")
os.environ.setdefault("MAIL_USERNAME", "docs@example.com")
os.environ.setdefault("MAIL_PASSWORD", "docs-build-password")
os.environ.setdefault("MAIL_FROM", "docs@example.com")
os.environ.setdefault("CLD_NAME", "docs-build")
os.environ.setdefault("CLD_API_KEY", "000000000000000")
os.environ.setdefault("CLD_API_SECRET", "docs-build-secret")

# -- Project information -----------------------------------------------------
project = "Contacts REST API"
copyright = "2026, Makedon"
author = "Makedon"
release = "0.3.0"

# -- General configuration ---------------------------------------------------
extensions = ["sphinx.ext.autodoc"]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# Silence a cross-reference warning emitted by SQLAlchemy's inherited
# ``Base.metadata`` docstring — it does not affect our own documentation.
suppress_warnings = ["ref.ref"]

# -- Options for HTML output -------------------------------------------------
html_theme = "nature"
html_static_path = ["_static"]
