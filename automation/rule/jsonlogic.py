################################################################################
# This is a modified version of the json-logic-py package
# (https://github.com/nadirizr/json-logic-py)
# for a minimal set of operations and customizations (regex operation).
# json-logic-py is python port of the json-logic-js package
# (https://github.com/jwadhams/json-logic-js)
#
# The MIT License (MIT)
#
# Copyright (c) 2015 nadirizr
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
################################################################################

from __future__ import unicode_literals

import logging
import re
from functools import reduce

logger = logging.getLogger(__name__)


def soft_equals(a, b):
    """Implements the '==' operator, which does type JS-style coercion."""
    if isinstance(a, str) or isinstance(b, str):
        return str(a) == str(b)
    if isinstance(a, bool) or isinstance(b, bool):
        return bool(a) is bool(b)
    return a == b


def less(a, b):
    """Implements the '<' operator with JS-style type coercion."""
    types = set([type(a), type(b)])
    if float in types or int in types:
        try:
            a, b = float(a), float(b)
        except TypeError:
            # NaN
            return False
    return a < b


def less_or_equal(a, b):
    """Implements the '<=' operator with JS-style type coercion."""
    return less(a, b) or soft_equals(a, b)


def regex_match(string, pattern):
    """Checks if the string matches the regex pattern."""
    try:
        return bool(re.search(pattern, string))
    except re.error:
        logger.error("Invalid regex pattern: %s", pattern)
        return False


def get_var(data, var_name, not_found=None):
    """Gets variable value from data dictionary."""
    try:
        for key in str(var_name).split("."):
            try:
                data = data[key]
            except TypeError:
                data = data[int(key)]
    except (KeyError, TypeError, ValueError):
        return not_found
    else:
        return data


operations = {
    "==": soft_equals,
    "!=": lambda a, b: not soft_equals(a, b),
    ">": lambda a, b: less(b, a),
    ">=": lambda a, b: less(b, a) or soft_equals(a, b),
    "<": less,
    "<=": less_or_equal,
    "!": lambda a: not a,
    "!!": bool,
    "and": lambda *args: reduce(lambda total, arg: total and arg, args, True),
    "or": lambda *args: reduce(lambda total, arg: total or arg, args, False),
    "in": lambda a, b: a in b if "__contains__" in dir(b) else False,
    "regex": regex_match,
}


def jsonLogic(tests, data=None):
    """Executes the json-logic with given data."""
    if tests is None or not isinstance(tests, dict):
        return tests

    data = data or {}

    operator = list(tests.keys())[0]
    values = tests[operator]

    if not isinstance(values, list) and not isinstance(values, tuple):
        values = [values]

    values = [jsonLogic(val, data) for val in values]

    if operator == "var":
        return get_var(data, *values)

    if operator not in operations:
        raise ValueError("Unrecognized operation %s" % operator)

    return operations[operator](*values)
