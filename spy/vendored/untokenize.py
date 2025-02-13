# Copyright (C) 2013-2018 Steven Myint
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
# BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
# ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""Transform tokens into original source code."""

import tokenize


__version__ = '0.1.1'


TOKENIZE_HAS_ENCODING = hasattr(tokenize, 'ENCODING')

WHITESPACE_TOKENS = frozenset([tokenize.INDENT, tokenize.NEWLINE, tokenize.NL])


def untokenize(tokens):
    """Return source code based on tokens.

    This is like tokenize.untokenize(), but it preserves spacing between
    tokens. So if the original soure code had multiple spaces between
    some tokens or if escaped newlines were used, those things will be
    reflected by untokenize().

    """
    text = ''
    previous_line = ''
    last_row = 0
    last_column = -1
    last_non_whitespace_token_type = None

    for (token_type, token_string, start, end, line) in tokens:
        if TOKENIZE_HAS_ENCODING and token_type == tokenize.ENCODING:
            continue

        (start_row, start_column) = start
        (end_row, end_column) = end

        # Preserve escaped newlines.
        if (
            last_non_whitespace_token_type != tokenize.COMMENT and
            start_row > last_row and
            previous_line.endswith(('\\\n', '\\\r\n', '\\\r'))
        ):
            text += previous_line[len(previous_line.rstrip(' \t\n\r\\')):]

        # Preserve spacing.
        if start_row > last_row:
            last_column = 0
        if start_column > last_column:
            text += line[last_column:start_column]

        text += token_string

        previous_line = line

        last_row = end_row
        last_column = end_column

        if token_type not in WHITESPACE_TOKENS:
            last_non_whitespace_token_type = token_type

    return text
