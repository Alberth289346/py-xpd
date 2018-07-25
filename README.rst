======
py-xpd
======
Python macro eXPanDer, a macro processor written in Python.

Introduction
============
There are not many macro processors available, especially for a Python-based
toolset. The `py-xpd` reduces this gap by providing a relatively simple macro
language.

Language primitives
===================
The program tokenizes the lines, and recognizes the following primitives.

Include
-------
To include another file, use

    include "myfile"

at a line of its own. The content of the file 'myfile' replaces the line.
Nesting of includes is allowed up to a maximum. There is no conditional
inclusion or avoiding recursive inclusion.

Macro definition
----------------
A macro is defined like

    define myname(a, b)
    ...
    endmacro

Introduces the macro named 'myname' taking two arguments. The *define* keyword
must be the first word of the line and the parentheses are obligatory. You can
have 0 or more parameters, which are listed inside the parentheses. The
*endmacro* keyword denotes the end of the macro definition, it must be after
the closing parentheses in the file, but may be put at the same line as
'define', that is

    define macro oneline() this is one line endmacro

is valid too. The content of the definition is everything between the closing
parenthesis and the *endmacro* keyword. Leading and trailing white space of the
content is discarded.

A macro definition must be entirely in one file. Also, you cannot include files
inside a macro definition. Also, you cannot define a macro inside a macro
definition (that is, no nested macro definitions).

Macro call
----------
Invoking a macro is done with 'calling' it with a function-like syntax, as in

    myname(first argument, second argument)

It starts with the name of the definition that must be invoked, followed by
the arguments of the call, one value for each parameter, inside parentheses.
Here the first parameter 'a' gets value 'first argument', and second
parameter 'b' gets value 'second argument'. Argument values may span several
lines if desired. The separating comma and the leading and trailing white space
of each argument is discarded.

Like the macro definition, invoking a macro must also be entirely in one file.
Arguments may invoke macros as well, and they are expanded first.

To invoke a macro with an empty argument, an argument starting or ending with
whitespace, or an argument with commas at the outermost level, py-xpd
recognizes arguments that have a pair of parentheses around the entire text,
like '(a value)'. The outer parentheses are stripped away, but everything
inside is preserved. Therefore, '()' is an empty argument, '( )' is an argument
consisting of a single space, '(a,b)' is the argument 'a,b', and '((a, b))' is
the argument '(a, b)'.


Glue
----
There is one pre-defined macro named *glue*. It takes any number of arguments,
and concatenates them into a single value. Its primary use is to construct
names from several parts. Such a single value is never interpreted as the name
of a macro.
