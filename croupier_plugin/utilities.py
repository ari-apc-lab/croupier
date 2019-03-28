'''
Copyright (c) 2019 HLRS. All rights reserved.

This file is part of Croupier.

Croupier is free software: you can redistribute it and/or modify it
under the terms of the Apache License, Version 2.0 (the License) License.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT ANY WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT, IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT
OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

See README file for full disclaimer information and LICENSE file for full
license information in the project root.

@author: Sergiy Gogolenko
         High-Performance Computing Center. Stuttgart
         e-mail: hpcgogol@hlrs.de

utilities.py:
Set of useful utilities for passing files, composing Shell scripts, etc
'''


# Import proper implementation of shell lexical quoting
try:                 # python3
    from shlex import quote as shlex_quote  # noqa: F401
except ImportError:  # python2
    # from shellescape import quote as shlex_quote
    from pipes import quote as shlex_quote  # noqa: F401
