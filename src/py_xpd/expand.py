"""
Macro call detection and expansion.
"""
from py_xpd import ast, report

MAX_EXPAND_LEVEL = 10

class StreamGetter:
    def __init__(self, stream):
        self.stream = stream

    def get(self):
        try:
            return next(self.stream)
        except StopIteration:
            self.stream = None
            return None

class ListGetter:
    def __init__(self, elements):
        self.elements = elements
        self.index = -1

    def get(self):
        self.index = self.index + 1
        if self.index == len(self.elements):
            self.index = None
            return None

        return self.elements[self.index]

def expand_stream(getter, macro_definitions, parameter_values, expand_nesting):
    """
    Detect macro-calls in the stream, and expand them.

    @param getter: Stream to expand.
    @param macro_definitions: Known macro definitions.
    @param parameter_values: Arguments to insert if found.
    @param expand_nesting: List of macros being expanded.

    @return: Stream of pieces after expansion.
    """
    while True:
        piece = getter.get()
        if piece is None:
            return

        if piece.kind != ast.PIECE_IDENTIFIER:
            yield piece
            continue

        name = piece.get_text()
        arg_value = parameter_values.get(name)
        if arg_value is not None:
            yield from arg_value
            continue

        macro_def = macro_definitions.get(name)
        if macro_def is None and name != 'glue':
            yield piece
            continue

        # Found a proper macro definition or magic 'glue'.
        macro_call = piece
        arguments = find_arguments(getter, macro_call.pos, macro_def)
        if macro_def is None:
            # Magic glue!
            text = "".join(p.get_text() for argval in arguments for p in argval)
            yield ast.StrPiece(ast.PIECE_TEXT, macro_call.pos, text)
            continue

        if len(macro_def.parameters) != len(arguments):
            msg = "Incorrect number of argument for expanding macro '{}' (expected {} found {} arguments)"
            report.report_error([macro_def.pos, macro_call.pos],
                                msg.format(macro_def.name, len(macro_def.parameters), len(arguments)))

        expand_nesting.append((macro_call, macro_def))
        if len(expand_nesting) > MAX_EXPAND_LEVEL:
            msg = "Too many macro expansions, infinite recursion?"
            report.report_error([mc.pos for mc, _def in expand_nesting], msg, ordered_pos=True)

        arg_table = {}
        for argpiece, argval in zip(macro_def.parameters, arguments):
            argname = argpiece.get_text()
            arg_getter = ListGetter(argval)
            assert argname not in arg_table
            arg_table[argname] = list(expand_stream(arg_getter, macro_definitions, parameter_values, expand_nesting))

        content_getter = ListGetter(macro_def.content)
        yield from expand_stream(content_getter, macro_definitions, arg_table, expand_nesting)
        del expand_nesting[-1]

def find_arguments(getter, call_pos, macro_def):
    """
    Find arguments of a macro in the stream.

    @param getter: Stream of pieces.
    @param call_pos: Position of the macro call.
    @param macro_def: Macro being expanded (only used for its name, its
                      position may be nice at some point too).

    @return: Argument list, a list of list of pices, with stripped whitespace around each argument.
    """
    # Find opening parenthesis
    while True:
        piece = getter.get()
        if piece is None:
            msg = "Missing open parentheses for macro call '{}'".format(macro_def.name)
            report.report_error([call_pos], msg)

        if piece.kind == ast.PIECE_SPACES:
            continue

        if piece.kind != ast.PIECE_PAROPEN:
            msg = "Missing open parentheses for macro call '{}'".format(macro_def.name)
            report.report_error([call_pos], msg)

        break

    # Find arguments until error or matching closing parenthesis.
    arguments = []
    while True:
        error, argument, piece = store_argument(getter)
        if error is not None:
            msg = "Missing closing parentheses for macro call '{}'".format(macro_def.name)
            report.report_error([call_pos], msg)

        argpieces, stripped = argument
        if piece.kind == ast.PIECE_PARCLOSE:
            if len(arguments) == 0 and len(argpieces) == 0 and not stripped:
                return arguments # Found "(    )"
            arguments.append(argpieces)
            return arguments

        arguments.append(argpieces)
        assert piece.kind == ast.PIECE_COMMA

def store_argument(getter):
    """
    Find and store a macro argument.

    @param getter: Stream of pieces.
    @param pieces: Destination to store the data.

    @return: error, (saved argument text, stripped-boolean), next piece.
    """
    first_close = None # If set, index of the first closing parenthesis in the argument
    strip_leading = True # If set, strip whitespace.
    argument = []
    while True:
        piece = getter.get()
        if piece is None:
            return 'no-input', None, None
        if piece.kind == ast.PIECE_EOF:
            return 'eof', None, None

        if piece.kind in (ast.PIECE_COMMA, ast.PIECE_PARCLOSE):
            # End reached, strip unprotected trailing whitespace.
            while len(argument) > 0 and argument[-1].kind in (ast.PIECE_SPACES, ast.PIECE_EOL):
                del argument[-1]
            # If argument had parentheses around the entire argument, drop them.
            # This allows injecting leading and trailing whitespace and commas into the argument.
            if (first_close is not None and argument[0].kind == ast.PIECE_PAROPEN and
                    len(argument) - 1 == first_close):
                return None, (argument[1:-1], True), piece

            return None, (argument, False), piece

        # Store pieces, while stripping leading unprotected whitespace.
        if not strip_leading:
            argument.append(piece)
        elif piece.kind not in (ast.PIECE_SPACES, ast.PIECE_EOL):
            argument.append(piece)
            strip_leading = False

        # Nested parentheses, skip everything until matching closing parenthesis.
        if piece.kind == ast.PIECE_PAROPEN:
            error = store_til_matching_close(getter, argument)
            if error is not None:
                return error, None, None

            if first_close is None:
                first_close = len(argument) - 1

def store_til_matching_close(getter, pieces):
    """
    Store input from the getter until a closing parenthesis is encountered, ignoring nested matching pairs.

    @param getter: Stream of pieces.
    @param pieces: Destination to store the data.

    @return: Result of the matching process. 'no-input' if the stream ends
             prematurely, 'eof' if an eof piece is encountered, None if
             everything went fine.
    """
    level = 1
    while level > 0:
        piece = getter.get()
        if piece is None:
            return 'no-input'
        if piece.kind == ast.PIECE_EOF:
            return 'eof'

        pieces.append(piece)
        if piece.kind == ast.PIECE_PAROPEN:
            level = level + 1
        elif piece.kind == ast.PIECE_PARCLOSE:
            level = level - 1
    return None
