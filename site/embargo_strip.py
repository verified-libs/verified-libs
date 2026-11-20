"""Embargo markup in markdown (DECISIONS 2026-11-12), shared by
site/build.py and lab/tools/public-export.py:

  <!-- embargo -->          whole lines up to <!-- /embargo -->: left out
  ... <!-- embargo-line -->  a single line ending with this marker: left out
                             (fits table rows: the comment is an extra cell
                             that renderers ignore)
  <!-- public-only          lines up to a line "-->": the public text, hidden
  ...                        in the private repository (an HTML comment) and
  -->                        unwrapped in public builds
"""
import re

_BLOCK = re.compile(r"^[ \t]*<!-- embargo -->.*?^[ \t]*<!-- /embargo -->[ \t]*\n?", re.S | re.M)
_LINE = re.compile(r"^.*<!-- embargo-line -->[ \t]*\n?", re.M)
_PUBLIC = re.compile(r"^[ \t]*<!-- public-only[ \t]*\n(.*?)^[ \t]*-->[ \t]*\n?", re.S | re.M)


def strip_embargo(text):
    """The public version of a markdown text."""
    text = _BLOCK.sub("", text)
    text = _LINE.sub("", text)
    return _PUBLIC.sub(lambda m: m.group(1), text)
