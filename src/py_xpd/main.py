"""
Main program entry point.
"""
import getopt, sys, os
from py_xpd import tokenize, match2, report, expand, ast

VERSION = "@VERSION@"

def print_help():
    """
    Output online help information about options and arguments.
    """
    print()
    print("Expand macro calls to their definitions.")
    print()
    print("Usage: py-xpd [options] [FILE]")
    print("with options:")
    print("  -h, --help            Print help")
    print("  -o OUT, --output=OUT  Store output in file OUT")
    print()
    print("Test and debug options:")
    print("  --debug-tokenize      Output tokenized stream of the input")
    print("  --debug-matched       Output tokenized stream after matching define/include")
    # XXX Print documentation as an extensive help.

    if not VERSION.startswith('@'):
        print()
        print("Version: " + VERSION)

    print()

class CommandLineArguments:
    def __init__(self):
        self.in_fname = None
        self.out_fname = None
        self.debug_tokenize = False
        self.debug_matched = False

def process_commandline():
    """
    Perform command-line processing, return the found arguments.

    @return: Command-line arguments.
    @rtype:  L{CommandLineArguments}
    """
    short_opts = 'ho:'
    long_opts = ['help', 'output=', 'debug-tokenize', "debug-matched"]
    try:
        opts, args = getopt.getopt(sys.argv[1:], short_opts, long_opts)
    except getopt.GetoptError as ex:
        report.report_error(None, str(ex))

    get_help = False
    cla = CommandLineArguments()
    for opt, val in opts:
        if opt in ('-h', '--help'):
            get_help = True
            continue

        if opt in ('-o', '--output'):
            cla.out_fname = val
            continue

        if opt == '--debug-tokenize':
            cla.debug_tokenize = True
            continue

        if opt == '--debug-matched':
            cla.debug_matched = True
            continue

        assert False, "Unknown option '{}' encountered".format((opt, val))

    if get_help:
        print_help()
        sys.exit(0)

    if len(args) > 1:
        msg = "At most one file may be given for processing, found {}".format(len(args))
        report.report_error(None, msg)

    if len(args) == 1:
        cla.in_fname = args[0]

        return cla

def run():
    cla = process_commandline()

    if cla.debug_tokenize:
        for p in tokenize.tokenize(cla.in_fname):
            print("{}".format(p))
        return

    if cla.debug_matched:
        stream = tokenize.tokenize(cla.in_fname)
        for p in match2.match_sequence(stream):
            print("{}".format(p))
        return

    macro_definitions = {}
    stream = match2.read_file(cla.in_fname, macro_definitions)
    getter = expand.StreamGetter(stream)

    if cla.out_fname is None:
        for piece in expand.expand_stream(getter, macro_definitions, {}, []):
            if piece.kind != ast.PIECE_EOF:
                sys.stdout.write(piece.get_text())
    else:
        with open(cla.out_fname, "w") as handle:
            for piece in expand.expand_stream(getter, macro_definitions, {}, []):
                if piece.kind != ast.PIECE_EOF:
                    handle.write(piece.get_text())
