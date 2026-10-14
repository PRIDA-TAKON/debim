"""
Lightweight pure-Python CliRunner for testing argparse-based CLI applications
without external dependencies like typer.testing.
"""

import io
import sys
from typing import List, Optional, Any, Union

class Result:
    def __init__(self, exit_code: int, output: str, stdout: str = "", stderr: str = ""):
        self.exit_code = exit_code
        self.output = output
        self.stdout = stdout
        self.stderr = stderr

class CliRunner:
    def invoke(
        self,
        app: Any,
        args: Optional[List[str]] = None,
        input: Optional[Union[str, bytes]] = None,
        env: Optional[dict] = None,
    ) -> Result:
        args = list(args) if args is not None else []
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        old_stdin = sys.stdin

        captured_stdout = io.StringIO()
        captured_stderr = io.StringIO()

        sys.stdout = captured_stdout
        sys.stderr = captured_stderr

        if input is not None:
            if isinstance(input, bytes):
                input_str = input.decode("utf-8")
            else:
                input_str = str(input)
            sys.stdin = io.StringIO(input_str)

        exit_code = 0
        try:
            if callable(app):
                app(args)
            elif hasattr(app, "invoke"):
                app.invoke(args)
            elif hasattr(app, "__call__"):
                app(args)
            else:
                raise TypeError("app is not callable")
        except SystemExit as e:
            if isinstance(e.code, int):
                exit_code = e.code
            elif e.code is None:
                exit_code = 0
            else:
                exit_code = 1
        except Exception as e:
            sys.stderr.write(str(e) + "\n")
            exit_code = 1
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            sys.stdin = old_stdin

        stdout_val = captured_stdout.getvalue()
        stderr_val = captured_stderr.getvalue()
        output_val = stdout_val + stderr_val

        return Result(exit_code=exit_code, output=output_val, stdout=stdout_val, stderr=stderr_val)
