"""
Detect the lines to define a macro and to include a file in a stream of pieces.
"""
from py_xpd import ast, report, tokenize

MAX_INCLUDE_LEVEL = 10

# {{{ DefinePiece, IncludePiece, EndMacroPiece definitions
class DefinePiece:
    def __init__(self):
        self.pos = None
        self.name = None
        self.parameters = []
        self.content = []

        self.storeds = []

    def store(self, piece, where):
        if where == 'position':
            self.pos = piece.pos
        elif where == 'name':
            self.name = piece.get_text()
        elif where == 'parameter':
            # Prevent duplicate parameter names.
            name = piece.get_text()
            for p in self.parameters:
                if name == p.get_text():
                    msg = "Macro definition parameter '{}' is listed more than once"
                    report.report_error([piece.pos, p.pos], msg.format(name))

            self.parameters.append(piece)
        else:
            assert False, "Don't know about '{}'".format(where)

    def __str__(self):
        msg = "**Define {} ({})**"
        msg = msg.format(self.name, ", ".join(p.get_text() for p in self.parameters))
        return msg

ESCAPES = {'n': '\n', 't': '\t'} # \x escape translations where \x is not simply x

def unescape(s):
    """
    Remove string escapes and surrounding quotes.
    """
    assert len(s) >= 0 and s[0] == '"' and s[-1] == '"'
    cs = []
    i, last = 1, len(s) - 1
    while i < last:
        if s[i] == '\\':
            cs.append(ESCAPES.get(s[i+1], s[i+1]))
            i = i + 2
        else:
            cs.append(s[i])
            i = i + 1
    return "".join(cs)

class IncludePiece:
    def __init__(self):
        self.pos = None
        self.filename = None

        self.storeds = []

    def store(self, piece, where):
        if where == 'position':
            self.pos = piece.pos
        elif where == 'filename':
            self.filename = unescape(piece.get_text())
        else:
            assert False, "Don't know about '{}'".format(where)

    def __str__(self):
        return "**Include {}**".format(self.filename)

class EndMacroPiece:
    def __init__(self):
        self.pos = None

        self.storeds = []

    def store(self, piece, where):
        if where == 'position':
            self.pos = piece.pos
        else:
            assert False, "Don't know about '{}'".format(where)

    def __str__(self):
        return "**EndMacro**"
# }}}

# {{{ Statemachine class definitions
class Edge:
    """
    Edge with action to perform if the piece matches.

    @ivar kind: Kind of the piece that matches this edge.
    @ivar text: If not None, the literal text of the piece.
    @ivar goto: If not None, the state identifier to the next state to visit.
    @ivar sequence_action: Action to perform on the sequence.
    @type sequence_action: C{None} or C{str}, one of 'define', 'include',
                           endmacro', 'discard', 'send'

    @ivar store: If set, where to store the piece additionally.
    @type store: C{None} or C{str}, one of 'position', 'filename', 'name', 'parameters'.
    """
    def __init__(self, kind, text=None, goto=None, sequence_action=None, store=None):
        self.kind = kind
        self.text = text
        self.goto = goto
        self.sequence_action = sequence_action
        self.store = store


class MatchState:
    """
    State that gets a new piece from the stream, and matches it against the
    edges. The first matching edge is taken. If an edge is taken, its
    L{sequence_action} is performed. Next, if a sequence exists, the matched
    piece is stored in the sequence. If there is no sequence, the piece is
    copied directly to the output. Finally, the 'store' action is performed,
    which may tell the piece must be stored elsewhere in the sequence as well.

    @ivar state_num: Unique state identification.
    @type state_num: A constant, may be a number.

    @ivar expected_sequence: Sequence type that is expected to exist when entering the state.
    @type expected_sequence: C{str}, one of 'none', 'define', 'endmacro' or 'include'.

    @ivar edges: Edges to check in sequence and take if it matches the current piece.
    @type edges: C{list} of L{Edge}
    """
    def __init__(self, state_num, expected_sequence, edges):
        self.state_num = state_num
        self.expected_sequence = expected_sequence
        self.edges = edges

class FinishState:
    """
    State for finishing a sequence, or terminating the execution.

    @ivar state_num: State number of the state.
    @ivar expected_sequence: Sequence type that is expected to exist when entering the state.
    @ivar goto: Which state to go to next, C{None} means to terminate. This
                should only be done if the entire input stream has been processed.
    """
    def __init__(self, state_num, expected_sequence, goto):
        self.state_num = state_num
        self.expected_sequence = expected_sequence
        self.goto = goto
# }}}
# {{{ State machine matching "define", "include" and "endmacro" sequences.
STATE1 = 1
STATE2 = 2
STATE11 = 11
STATE12 = 12
STATE13 = 13
STATE14 = 14
STATE15 = 15
STATE18 = 18
STATE21 = 21
STATE22 = 22
STATE23 = 23
STATE28 = 28
STATE29 = 29
STATE31 = 31
STATE99 = 99

STATES = [
    # At 'start' of line, trying to detect 'define' or 'include'.
    MatchState(STATE1, 'none', [
        Edge(ast.PIECE_COMMA, goto=STATE2),
        Edge(ast.PIECE_COMMENT, goto=STATE2),
        Edge(ast.PIECE_EOF, goto=STATE99),
        Edge(ast.PIECE_EOL),
        Edge(ast.PIECE_IDENTIFIER, text='define', sequence_action='define', store='position', goto=STATE11),
        Edge(ast.PIECE_IDENTIFIER, text='include', sequence_action='include', store='position', goto=STATE21),
        Edge(ast.PIECE_IDENTIFIER, text='endmacro', sequence_action='endmacro', store='position', goto=STATE31),
        Edge(ast.PIECE_IDENTIFIER, goto=STATE2),
        Edge(ast.PIECE_PARCLOSE, goto=STATE2),
        Edge(ast.PIECE_PAROPEN, goto=STATE2),
        Edge(ast.PIECE_SPACES),
        Edge(ast.PIECE_STRING, goto=STATE2),
        Edge(ast.PIECE_TEXT, goto=STATE2),
    ]),

    # Found 'endmacro'
    FinishState(STATE31, 'endmacro', STATE2),

    # Definitely not a sequence, skip to start of next line.
    MatchState(STATE2, 'none', [
        Edge(ast.PIECE_COMMA),
        Edge(ast.PIECE_COMMENT),
        Edge(ast.PIECE_EOF, goto=STATE99),
        Edge(ast.PIECE_EOL, goto=STATE1),
        Edge(ast.PIECE_IDENTIFIER, text='endmacro', sequence_action='endmacro', store='position', goto=STATE31),
        Edge(ast.PIECE_IDENTIFIER),
        Edge(ast.PIECE_PARCLOSE),
        Edge(ast.PIECE_PAROPEN),
        Edge(ast.PIECE_SPACES),
        Edge(ast.PIECE_STRING),
        Edge(ast.PIECE_TEXT),
    ]),

    # Seen 'define', detect an identifier (the name of the macro)
    MatchState(STATE11, 'define', [
        Edge(ast.PIECE_COMMA, sequence_action='discard', goto=STATE2),
        Edge(ast.PIECE_COMMENT, sequence_action='discard', goto=STATE2),
        Edge(ast.PIECE_EOF, sequence_action='discard', goto=STATE99),
        Edge(ast.PIECE_EOL, sequence_action='discard', goto=STATE1),
        Edge(ast.PIECE_IDENTIFIER, text='define', sequence_action='discard', goto=STATE2),
        Edge(ast.PIECE_IDENTIFIER, text='include', sequence_action='discard', goto=STATE2),
        Edge(ast.PIECE_IDENTIFIER, text='endmacro', sequence_action='endmacro', store='position', goto=STATE31),
        Edge(ast.PIECE_IDENTIFIER, store='name', goto=STATE12),
        Edge(ast.PIECE_PARCLOSE, sequence_action='discard', goto=STATE2),
        Edge(ast.PIECE_PAROPEN, sequence_action='discard', goto=STATE2),
        Edge(ast.PIECE_SPACES),
        Edge(ast.PIECE_STRING, sequence_action='discard', goto=STATE2),
        Edge(ast.PIECE_TEXT, sequence_action='discard', goto=STATE2),
    ]),

    # Seen a macro name, does it have parentheses/parameters?
    MatchState(STATE12, 'define', [
        Edge(ast.PIECE_COMMA, sequence_action='discard', goto=STATE2),
        Edge(ast.PIECE_COMMENT, sequence_action='discard', goto=STATE2),
        Edge(ast.PIECE_EOF, sequence_action='discard', goto=STATE99),
        Edge(ast.PIECE_EOL, sequence_action='discard', goto=STATE1),
        Edge(ast.PIECE_IDENTIFIER, text='endmacro', sequence_action='endmacro', store='position', goto=STATE31),
        Edge(ast.PIECE_IDENTIFIER, sequence_action='discard', goto=STATE2),
        Edge(ast.PIECE_PARCLOSE, sequence_action='discard', goto=STATE2),
        Edge(ast.PIECE_PAROPEN, goto=STATE13),
        Edge(ast.PIECE_SPACES),
        Edge(ast.PIECE_STRING, sequence_action='discard', goto=STATE2),
        Edge(ast.PIECE_TEXT, sequence_action='discard', goto=STATE2),
    ]),

    # Seen open parenthesis, find first parameter or a closing parenthesis
    MatchState(STATE13, 'define', [
        Edge(ast.PIECE_COMMA, sequence_action='discard', goto=STATE2),
        Edge(ast.PIECE_COMMENT, sequence_action='discard', goto=STATE2),
        Edge(ast.PIECE_EOF, sequence_action='discard', goto=STATE99),
        Edge(ast.PIECE_EOL, sequence_action='discard', goto=STATE1),
        Edge(ast.PIECE_IDENTIFIER, text='define', sequence_action='discard', goto=STATE2),
        Edge(ast.PIECE_IDENTIFIER, text='include', sequence_action='discard', goto=STATE2),
        Edge(ast.PIECE_IDENTIFIER, text='endmacro', sequence_action='endmacro', store='position', goto=STATE31),
        Edge(ast.PIECE_IDENTIFIER, store='parameter', goto=STATE14),
        Edge(ast.PIECE_PARCLOSE, goto=STATE18),
        Edge(ast.PIECE_PAROPEN, sequence_action='discard', goto=STATE2),
        Edge(ast.PIECE_SPACES),
        Edge(ast.PIECE_STRING, sequence_action='discard', goto=STATE2),
        Edge(ast.PIECE_TEXT, sequence_action='discard', goto=STATE2),
    ]),

    # Seen parameter name, look for comma or closing parenthesis
    MatchState(STATE14, 'define', [
        Edge(ast.PIECE_COMMA, goto=STATE15),
        Edge(ast.PIECE_COMMENT, sequence_action='discard', goto=STATE2),
        Edge(ast.PIECE_EOF, sequence_action='discard', goto=STATE99),
        Edge(ast.PIECE_EOL, sequence_action='discard', goto=STATE1),
        Edge(ast.PIECE_IDENTIFIER, text='endmacro', sequence_action='endmacro', store='position', goto=STATE31),
        Edge(ast.PIECE_IDENTIFIER, sequence_action='discard', goto=STATE2),
        Edge(ast.PIECE_PARCLOSE, goto=STATE18),
        Edge(ast.PIECE_PAROPEN, sequence_action='discard', goto=STATE2),
        Edge(ast.PIECE_SPACES),
        Edge(ast.PIECE_STRING, sequence_action='discard', goto=STATE2),
        Edge(ast.PIECE_TEXT, sequence_action='discard', goto=STATE2),
    ]),

    # Seen comma, find another parameter
    MatchState(STATE15, 'define', [
        Edge(ast.PIECE_COMMA, sequence_action='discard', goto=STATE2),
        Edge(ast.PIECE_COMMENT, sequence_action='discard', goto=STATE2),
        Edge(ast.PIECE_EOF, sequence_action='discard', goto=STATE99),
        Edge(ast.PIECE_EOL, sequence_action='discard', goto=STATE1),
        Edge(ast.PIECE_IDENTIFIER, text='define', sequence_action='discard', goto=STATE2),
        Edge(ast.PIECE_IDENTIFIER, text='include', sequence_action='discard', goto=STATE2),
        Edge(ast.PIECE_IDENTIFIER, text='endmacro', sequence_action='endmacro', store='position', goto=STATE31),
        Edge(ast.PIECE_IDENTIFIER, store='parameter', goto=STATE14),
        Edge(ast.PIECE_PARCLOSE, sequence_action='discard', goto=STATE2),
        Edge(ast.PIECE_PAROPEN, sequence_action='discard', goto=STATE2),
        Edge(ast.PIECE_SPACES),
        Edge(ast.PIECE_STRING, sequence_action='discard', goto=STATE2),
        Edge(ast.PIECE_TEXT, sequence_action='discard', goto=STATE2),
    ]),

    # Found a macro define with parentheses
    FinishState(STATE18, 'define', STATE2),

    # Seen 'include', find a filename string
    MatchState(STATE21, 'include', [
        Edge(ast.PIECE_COMMA, sequence_action='discard', goto=STATE2),
        Edge(ast.PIECE_COMMENT, sequence_action='discard', goto=STATE2),
        Edge(ast.PIECE_EOF, sequence_action='discard', goto=STATE99),
        Edge(ast.PIECE_EOL, sequence_action='discard', goto=STATE1),
        Edge(ast.PIECE_IDENTIFIER, text='endmacro', sequence_action='endmacro', store='position', goto=STATE31),
        Edge(ast.PIECE_IDENTIFIER, sequence_action='discard', goto=STATE2),
        Edge(ast.PIECE_PARCLOSE, sequence_action='discard', goto=STATE2),
        Edge(ast.PIECE_PAROPEN, sequence_action='discard', goto=STATE2),
        Edge(ast.PIECE_SPACES),
        Edge(ast.PIECE_STRING, store='filename', goto=STATE22),
        Edge(ast.PIECE_TEXT, sequence_action='discard', goto=STATE2),
    ]),

    # Seen a filename string, now an eol/eof!
    #
    # Note: The EOF is used in the match, so it would be stored in the sequence
    # rather than being sent out. Use 'send' to force that.
    MatchState(STATE22, 'include', [
        Edge(ast.PIECE_COMMA, sequence_action='discard', goto=STATE2),
        Edge(ast.PIECE_COMMENT, sequence_action='discard', goto=STATE2),
        Edge(ast.PIECE_EOF, sequence_action='send', goto=STATE29),
        Edge(ast.PIECE_EOL, goto=STATE28),
        Edge(ast.PIECE_IDENTIFIER, text='endmacro', sequence_action='endmacro', store='position', goto=STATE31),
        Edge(ast.PIECE_IDENTIFIER, sequence_action='discard', goto=STATE2),
        Edge(ast.PIECE_PARCLOSE, sequence_action='discard', goto=STATE2),
        Edge(ast.PIECE_PAROPEN, sequence_action='discard', goto=STATE2),
        Edge(ast.PIECE_SPACES),
        Edge(ast.PIECE_STRING, sequence_action='discard', goto=STATE2),
        Edge(ast.PIECE_TEXT, sequence_action='discard', goto=STATE2),
    ]),

    # include + filename + eol found.
    FinishState(STATE28, 'include', STATE1),

    # include + filename + eof found.
    FinishState(STATE29, 'include', STATE99),

    # Done!
    FinishState(STATE99, 'none', None),
]
# }}}

# {{{ State machine execution
def setup_states(states):
    """
    Verify correctness and sanity of the state machine.
    """
    available_states = {}
    for s in states:
        assert s.state_num not in available_states, "State {} is defined more than once".format(s.state_num)
        available_states[s.state_num] = s

    for s in states:
        if isinstance(s, MatchState):
            piece_map = set()
            for edge in s.edges:
                if edge.text is None:
                    piece_map.add(edge.kind)
                assert edge.goto is None or edge.goto in available_states, "Goto {} in state {} does not exist".format(edge.goto, s.state_num)

            assert len(piece_map) == ast.NUM_PIECES, "Edges do not cover all options in state {}.".format(s.state_num)

            if s.expected_sequence is None:
                for edge in s.edges:
                    if edge.goto is None:
                        next_state = s.state_num
                    else:
                        next_state = available_states[edge.goto]

                    if edge.sequence_action in ('define', 'endmacro', 'include'):
                        assert next_state.expected_sequence == edge.sequence_action, \
                               "State {}, kind {} makes incorrect new sequence".format(s.state_num, edge.kind)
                    elif edge.sequence_action in (None, 'send'):
                        assert next_state.expected_sequence == s.expected_sequence, \
                               "State {}, kind {} passes wrong sequence to next state".format(s.state_num, edge.kind)
                    elif edge.sequence_action == 'discard':
                        assert False, "State {}, kind {} discards nothing??".format(s.state_num, edge.kind)
                    else:
                        assert False, "State {}, kind {}, action {}".format(s.state_num, edge.kind, edge.sequence_action)
            else:
                for edge in s.edges:
                    if edge.goto is None:
                        next_state = s
                    else:
                        next_state = available_states[edge.goto]

                    if edge.sequence_action in ('define', 'endmacro', 'include'):
                        assert next_state.expected_sequence == edge.sequence_action, \
                               "State {}, kind {} makes incorrect new sequence".format(s.state_num, edge.kind)
                    elif edge.sequence_action in (None, 'send'):
                        assert next_state.expected_sequence == s.expected_sequence, \
                               "State {}, kind {} passes wrong sequence to next state".format(s.state_num, edge.kind)
                    elif edge.sequence_action == 'discard':
                        assert next_state.expected_sequence == 'none', \
                               "State {}, kind {} incorrectly discards for next state".format(s.state_num, edge.kind)
                    else:
                        assert False, "State {}, kind {}, action {}".format(s.state_num, edge.kind, edge.sequence_action)
        else:
            assert isinstance(s, FinishState)
            if s.goto is None:
                continue

            assert s.goto in available_states, "Successor of finish state {} does not exist".format(s.state_num)
            next_state = available_states[s.goto]
            assert next_state.expected_sequence == 'none', \
                    "Finish state {} cannot finish due to next state".format(s.state_num)

    return available_states

def verify_expected_sequence(sequence, expected_sequence):
    if sequence is None:
        assert expected_sequence == 'none'
    elif isinstance(sequence, DefinePiece):
        assert expected_sequence == 'define'
    elif isinstance(sequence, IncludePiece):
        assert expected_sequence == 'include'
    elif isinstance(sequence, EndMacroPiece):
        assert expected_sequence == 'endmacro'
    else:
        assert False

def match_sequence(stream):
    """
    Run the state machine on 'stream'.

    @param stream: Stream of pieces (from a file).
    @return: Stream of pieces, mixed with L{DefinePiece}, L{IncludePiece}, and
             L{EndMacroPiece} objects.
    """
    available_states = setup_states(STATES)

    cur_state = available_states[STATE1]
    sequence = None
    while cur_state is not None:
        if isinstance(cur_state, MatchState):
            verify_expected_sequence(sequence, cur_state.expected_sequence)

            # Get piece, find a matching edge.
            piece = next(stream)
            #print("State {}, piece {}".format(cur_state.state_num, piece))

            # Find matching edge.
            sel_edge = None
            for edge in cur_state.edges:
                if edge.kind == piece.kind and edge.text is None or edge.text == piece.get_text():
                    sel_edge = edge
                    break

            assert sel_edge

            # Handle sequence action.
            force_send = False
            action = sel_edge.sequence_action
            if action is None:
                pass
            elif action == 'define':
                if sequence is not None:
                    for stored in sequence.storeds:
                        yield stored
                sequence = DefinePiece()
            elif action == 'include':
                if sequence is not None:
                    for stored in sequence.storeds:
                        yield stored
                sequence = IncludePiece()
            elif action == 'endmacro':
                if sequence is not None:
                    for stored in sequence.storeds:
                        yield stored
                sequence = EndMacroPiece()
            elif action == 'discard':
                if sequence is not None:
                    for stored in sequence.storeds:
                        yield stored
                sequence = None
            elif action == 'send':
                force_send = True
            else:
                assert False, "Unknown edge action {} found".format(sel_edge.sequence_action)

            # Ensure no piece gets lost by either storing it or by sending it.
            if not force_send and sequence is not None:
                sequence.storeds.append(piece)
            else:
                yield piece

            # Perform additional store action if requested.
            store = sel_edge.store
            if sel_edge.store is not None:
                sequence.store(piece, sel_edge.store)

            # Select next state.
            if sel_edge.goto is not None:
                cur_state = available_states[sel_edge.goto]
            # else: Stay in the same state.
            continue


        elif isinstance(cur_state, FinishState):
            verify_expected_sequence(sequence, cur_state.expected_sequence)
            #print("Finish state {}".format(cur_state.state_num))

            if sequence is not None:
                yield sequence
            sequence = None

            if cur_state.goto is None:
                cur_state = None
            else:
                cur_state = available_states[cur_state.goto]
            continue

        else:
            assert False, "Weird state class {}".format(repr(cur_state))

    # Verify we're at the end of the stream.
    next(stream)
    assert False, "Sequence detection ended too early!"
# }}}

def read_file(fname, macro_definitions, includes=None):
    """
    Read a file, handling includes, and extracting macro definitions.

    @param fname: File to read.
    @type  fname: C{str}

    @param macro_definitions: Stored macro definitions.
    @type  macro_definitions: C{dict} of L{DefinePiece}

    @param includes: List of includes being performed.
    @type  includes: C{list} of L{IncludePiece} 

    @return: Stream of pieces from all included files, without macro definitions.
    @rtype:  C{generator} of L{Piece}
    """
    if includes is None:
        includes = []

    assert len(includes) <= MAX_INCLUDE_LEVEL

    current_def = None # Not in a macro definition.
    for mixed in match_sequence(tokenize.tokenize(fname)):
        if isinstance(mixed, DefinePiece):
            if current_def is not None:
                msg = "Cannot define a nested macro, perhaps a missing 'endmacro'?"
                report.report_error([mixed.pos, current_def.pos], msg)

            # Warn if a definition gets redefined.
            prev_def = macro_definitions.get(mixed.name)
            if prev_def is not None:
                msg = "Macro '{}' is already defined, overwriting the previous definirion!"
                report.report_error([mixed.pos, prev_def.pos], msg.format(mixed.name), type='warning')

            current_def = mixed
            assert len(current_def.content) == 0
            continue

        elif isinstance(mixed, IncludePiece):
            if current_def is not None:
                msg = "Cannot include a file in a macro definition"
                report.report_error([mixed.pos], msg)

            if len(includes) >= MAX_INCLUDE_LEVEL:
                msg = "Too many includes (infinite recursion?)"
                report.report_error([mixed.pos], msg)

            yield from read_file(mixed.filename, macro_definitions, includes + [mixed])
            continue

        elif isinstance(mixed, EndMacroPiece):
            if current_def is None:
                msg = "Found 'endmacro' keyword without matching 'define'"
                report.report_error([mixed.pos], msg)

            # Strip 'trailing' whitespace from the definition.
            content = current_def.content
            while len(content) > 0 and content[-1].kind in (ast.PIECE_SPACES, ast.PIECE_EOL):
                del content[-1]
            macro_definitions[current_def.name] = current_def
            current_def = None
            continue

        else:
            # Outside a macro definition, pass the piece on for further processing.
            if current_def is None:
                yield mixed
                continue

            # Inside a macro definition, piece must be saved.
            if mixed.kind in (ast.PIECE_SPACES, ast.PIECE_EOL) and len(current_def.content) == 0:
                continue # Skip whitespace at the start.

            if mixed.kind == ast.PIECE_EOF:
                msg = ("Encountered end of file while reading a macro definition, " +
                       "perhaps a missing 'endmacro'?")
                report.report_error([mixed.pos, current_def.pos], msg)

            current_def.content.append(mixed)
            continue
