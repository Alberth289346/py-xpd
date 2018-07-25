"""
Read a file, tokenize it, and detect special lines.
"""
import re, sys
from py_xpd import ast, report

SPACES_PAT = re.compile('[ \\t]+')
STRING_PAT = re.compile('"[^"\\\\]*(?:\\\\.[^"\\\\]*)*"')
IDENTIFIER_PAT = re.compile('\\b[A-Za-z_][A-Za-z0-9_]*')

def find_end_of_block_comment_piece(line, search_start):
    """
    Find where a block comment piece ends at the given line, where 'search_start' is inside the comment.

    @return End position, and 'end-of-comment found'
    """
    i = line.find("*/", search_start)
    if i < 0:
        if line[-1] == '\n':
            return len(line) - 1, False
        else:
            return len(line), False
    return i + 2, True

def line_stream_file(fname):
    """
    Construct a stream of lines from an input file.

    @param fname: Name of the file to stream, C{None} means stdin.
    @type  fname: C{None} or C{str}

    @return: Lines from the input.
    @rtype:  C{Generator} of C{str}
    """
    if fname is None:
        for line in sys.stdin:
            yield line

    else:
        with open(fname) as handle:
            for line in handle:
                yield line


def tokenize(fname):
    """
    Tokenize a file.

    @param fname: Name of the file to stream, C{None} means stdin.
    @type  fname: C{None} or C{str}

    @return: Pieces from the input file.
    @rtype:  C{Generator} of L{Piece}
    """
    comment_mode = False # Whether parsing block comment.
    lineno = 1
    for line in line_stream_file(fname):
        col = 0
        while col < len(line):
            if line[col] == '\n':
                pos = report.Position(lineno, fname=fname, column=col)
                eol_piece = ast.StrPiece(ast.PIECE_EOL, pos, '\n')
                yield eol_piece
                col = col + 1
                continue

            if comment_mode:
                end, eoc_found = find_end_of_block_comment_piece(line, col)
                pos = report.Position(lineno, fname=fname, column=col)
                yield ast.SubstrPiece(ast.PIECE_COMMENT, pos, end - col, line)
                col = end
                if eoc_found:
                    comment_mode = False

                continue

            else:
                # Non-comment mode
                best = None
                best_start = None
                best_end = None
                for entry in [(SPACES_PAT, None, ast.PIECE_SPACES),
                              (STRING_PAT, None, ast.PIECE_STRING),
                              (IDENTIFIER_PAT, None, ast.PIECE_IDENTIFIER),
                              (None, '/*', ast.PIECE_COMMENT),
                              (None, '//', ast.PIECE_COMMENT),
                              (None, '(', ast.PIECE_PAROPEN),
                              (None, ')', ast.PIECE_PARCLOSE),
                              (None, ',', ast.PIECE_COMMA) ]:
                    if entry[0] is not None:
                        m = entry[0].search(line, col)
                        if not m:
                            continue

                        start = m.start()
                        end = m.end()
                    else:
                        start = line.find(entry[1], col)
                        if start < 0:
                            continue

                        end = start + len(entry[1])

                    if best_start is None or best_start > start:
                        best = entry
                        best_start = start
                        best_end = end

                        if best_start == 0:
                            break # It cannot get better than this.

                # Nothing matched, must be non-interesting text.
                if best_start is None:
                    if line[-1] == '\n':
                        end = len(line) - 1
                    else:
                        end = len(line)

                    pos = report.Position(lineno, fname=fname, column=col)
                    yield ast.SubstrPiece(ast.PIECE_TEXT, pos, end - col, line)
                    col = end
                    continue

                if best_start > col:
                    # Part before the match must be non-interesting.
                    pos = report.Position(lineno, fname=fname, column=col)
                    yield ast.SubstrPiece(ast.PIECE_TEXT, pos, best_start - col, line)
                    col = best_start

                # Deal with the best entry
                if best[1] == '/*': # Block comment
                    end, eoc_found = find_end_of_block_comment_piece(line, col + 2)
                    pos = report.Position(lineno, fname=fname, column=col)
                    yield ast.SubstrPiece(ast.PIECE_COMMENT, pos, end - col, line)
                    col = end
                    if not eoc_found:
                        comment_mode = True

                    continue

                if best[1] == '//': # Line comment, add everything but the terminating newline.
                    if line[-1] == '\n':
                        end = len(line) - 1
                    else:
                        end = len(line)

                    pos = report.Position(lineno, fname=fname, column=col)
                    yield ast.SubstrPiece(best[2], pos, end - col, line)
                    col = end
                    continue

                # Return the matched piece.
                pos = report.Position(lineno, fname=fname, column=col)
                yield ast.SubstrPiece(best[2], pos, best_end - best_start, line)
                col = best_end
                continue

        # End of line reached
        lineno = lineno + 1

    # All lines read and tokenized.
    pos = report.Position(lineno, fname=fname, column=0)
    yield ast.StrPiece(ast.PIECE_EOF, pos, 'EOF-EOF-EOF')
