PIECE_COMMA = 'comma'
PIECE_COMMENT = "comment"
PIECE_EOF = "eof"
PIECE_EOL = "newline"
PIECE_IDENTIFIER = 'identifier'
PIECE_PARCLOSE = 'parclose'
PIECE_PAROPEN = 'paropen'
PIECE_SPACES = 'whitespace'
PIECE_STRING = 'string'
PIECE_TEXT = 'text'
NUM_PIECES = 10

class Piece:
    """
    A piece of a line of text.

    @ivar kind: Kind of piece, one of the PIECE_* constants.
    @type kind: C{str}

    @ivar pos: Position of the piece.
    @type pos: L{Position}
    """
    def __init__(self, kind, pos):
        self.kind = kind
        self.pos = pos

    def get_length(self):
        raise NotImplementedError("Implement me in {}".format(type(self)))

    def get_text(self):
        raise NotImplementedError("Implement me in {}".format(type(self)))

    def __str__(self):
        text = "*Piece({}, {}): {}*"
        return text.format(self.kind, self.pos, repr(self.get_text()))


class SubstrPiece(Piece):
    """
    Piece holding the line text containing the piece. Note that pos.column must
    be correct or this piece falls to pieces.

    @ivar length: Length of the text of the piece.
    @type length: C{int}

    @ivar line_text: Text of the line containing the piece.
    @type line_text: C{str}
    """
    def __init__(self, kind, pos, length, line_text):
        assert pos.column is not None
        Piece.__init__(self, kind, pos)
        self.length = length
        self.line_text = line_text

    def get_length(self):
        return self.length

    def get_text(self):
        return self.line_text[self.pos.column : self.pos.column + self.length]

class StrPiece(Piece):
    """
    Piece having a string of it own containing the text.

    @ivar text: Text of the piece.
    @type text: C{str}
    """
    def __init__(self, kind, pos, text):
        Piece.__init__(self, kind, pos)
        self.text = text

    def get_length(self):
        return len(self.text)

    def get_text(self):
        return self.text
