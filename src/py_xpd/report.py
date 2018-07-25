"""
Report an error message, and often die.
"""
import sys

PROGRNAME = "py-xpd"

# If enabled, 'info' lines are not printed.
SKIP_INFO = False

class Position:
    def __init__(self, lineno, fname=None, column=None):
        self.lineno = lineno
        self.fname = fname
        self.column = column

    def __str__(self):
        elements = []
        if self.fname is not None:
            elements.append('in "{}"'.format(self.fname))
        elements.append("at line {}".format(self.lineno))
        if self.column is not None:
            elements.append("column {}".format(self.column + 1))
        return ", ".join(elements)

    def __eq__(self, other):
        if not isinstance(other, Position):
            return NotImplemented
        return (self.lineno == other.lineno and
                self.fname == other.fname and
                self.column == other.column)

    def __lt__(self, other):
        if not isinstance(other, Position):
            return NotImplemented
        if self.fname != other.fname:
            if self.fname is None:
                return True
            if other.fname is None:
                return False
            return self.fname < other.fname

        if self.lineno != other.lineno:
            return self.lineno < other.lineno

        if self.column != other.column:
            if self.column is None:
                return True
            if other.column is None:
                return False
            return self.column < other.column
        return False

def unduplicate(lines):
    """
    Remove double line numbers.
    """
    result = []
    last = None
    for line in lines:
        if line == last:
            continue
        last = line
        result.append(last)

    return result

def report_error(lines, mesg, type='error', keep_running=False):
    """
    Format and report an error, warning, or information message.
    Unless L{keep_running} is C{True}, fatal errors are fatal.

    @param lines: Lines concerning the error message. Set to L{None} if not applicable.
    @param keep_running: If C{True}, do not abort execution on error.
    @return Whether a fatal error was produced.
    """
    # Format kind of error.
    if type == 'warning':
        type_text = 'warning'
        fatal = False
    elif type == 'info':
        # Requested to skip printing these lines?
        if SKIP_INFO:
            return False

        type_text = 'info'
        fatal = False
    else:
        type_text = 'ERROR'
        fatal = True

    # Format lines, if present
    if lines is None or len(lines) == 0:
        lines_text = ""
    else:
        assert all(isinstance(pos, Position) for pos in lines)
        lines.sort()
        lines = unduplicate(lines)

        if len(lines) == 1:
            lines_text = " at line {}".format(lines[0])
        elif len(lines) == 2:
            lines_text = " at lines {} and {}".format(lines[0], lines[1])
        else:
            numbers = ", ".join(str(num) for num in lines[:-1])
            lines_text = " at lines {}, and {}".format(numbers, lines[-1])

    print("{} {}{}: {}".format(PROGRNAME, type_text, lines_text, mesg))
    if fatal and not keep_running:
        sys.exit(1)

    return fatal

