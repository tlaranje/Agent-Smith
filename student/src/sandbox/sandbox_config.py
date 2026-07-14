from pydantic import BaseModel, Field
import ast


class SandboxConfig(BaseModel):
    """
    Configuration and static-analysis guardrails for sandboxed code execution.

    Defines which modules can be imported, which filesystem paths can
    be accessed, and basic resource limits for code executed inside
    the sandbox. Also provides AST-based validation helpers to check
    a piece of code against these rules before it is executed.

    Attributes:
        authorized_imports: Module names (or "module.*" wildcards)
            that are allowed to be imported by sandboxed code.
        allowed_directories: Filesystem path prefixes that sandboxed
            code is allowed to read from or write to.
        max_execution_time_seconds: Maximum wall-clock time, in
            seconds, allotted for executing sandboxed code.
        max_memory_mb: Maximum memory, in megabytes, allotted for
            executing sandboxed code.
    """

    authorized_imports: list[str] = Field(default_factory=lambda: [
        "math", "math.*",
        "collections", "collections.*",
        "itertools", "re", "json",
        "typing", "typing.*",
        "functools", "operator",
        "heapq", "bisect", "copy",
        "string", "random",
        "datetime", "datetime.*",
        "array", "cmath",
    ])
    allowed_directories: list[str] = Field(default_factory=lambda: [
        "/testbed/", "/tmp/agent/"
    ])
    max_execution_time_seconds: int = 30
    max_memory_mb: int = 512

    def validate_imports(self, code: str = "") -> bool:
        """
        Check whether all imports in the given code are authorized.

        Parses the code into an AST and inspects every ``import`` and
        ``from ... import ...`` statement, rejecting any module not
        present in ``authorized_imports`` (either as an exact match or
        via a "root.*" wildcard). Also rejects dangerous dynamic calls
        such as ``__import__``, ``eval``, or ``exec``.

        Args:
            code: Source code to validate. An empty/blank string is
                treated as trivially valid.

        Returns:
            True if the code is syntactically valid and only uses
            authorized imports (and no forbidden dynamic calls),
            False otherwise.
        """
        if not code.strip():
            return True
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return False

        for node in ast.walk(tree):
            # Handle plain "import x" / "import x.y" statements.
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name
                    root = name.split(".")[0]

                    if name not in self.authorized_imports and \
                            f"{root}.*" not in self.authorized_imports:
                        return False

            # Handle "from x import y" statements.
            elif isinstance(node, ast.ImportFrom):
                if node.module is None:
                    return False

                root = node.module.split(".")[0]
                if node.module not in self.authorized_imports and \
                        f"{root}.*" not in self.authorized_imports:
                    return False

            # Block dynamic import/eval/exec calls regardless of imports.
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in ["__import__", "eval", "exec"]:
                        return False
        return True

    def validate_paths(self, code: str = "") -> bool:
        """
        Check whether all file paths accessed in the code are allowed.

        Parses the code into an AST and inspects calls to ``open`` as
        well as ``Path(...).open(...)`` / ``PosixPath(...).open(...)``
        patterns, ensuring any literal path argument starts with one
        of the configured ``allowed_directories``.

        Args:
            code: Source code to validate. An empty/blank string is
                treated as trivially valid.

        Returns:
            True if the code is syntactically valid and only accesses
            paths within the allowed directories, False otherwise.
        """
        if not code.strip():
            return True

        try:
            tree = ast.parse(code)
        except SyntaxError:
            return False

        def path_is_allowed(path: str) -> bool:
            """
            Return True if `path` starts with an allowed directory prefix.
            """
            return any(
                path.startswith(d) for d in self.allowed_directories
            )

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue

            # Case 1: direct call to open(...).
            if isinstance(node.func, ast.Name):
                if node.func.id == "open":
                    args = node.args
                    if args and isinstance(args[0], ast.Constant):
                        path = str(args[0].value)
                        if not path_is_allowed(path):
                            return False

            # Case 2: attribute call, e.g. something.open(...).
            elif isinstance(node.func, ast.Attribute):
                if node.func.attr == "open":
                    target = node.func.value

                    # Sub-case: Path("...").open(...) and
                    # PosixPath("...").open(...).
                    if (
                        isinstance(target, ast.Call)
                        and isinstance(target.func, ast.Name)
                        and target.func.id in ("Path", "PosixPath")
                    ):
                        args = target.args
                        if args and isinstance(args[0], ast.Constant):
                            path = str(args[0].value)
                            if not path_is_allowed(path):
                                return False

                    # Sub-case: obj.open("path", ...) with a path argument.
                    args = node.args
                    if args and isinstance(args[0], ast.Constant):
                        path = str(args[0].value)
                        if not path_is_allowed(path):
                            return False

        return True

    def validate_code(self, code: str = "") -> bool:
        """
        Validate that code uses only authorized imports and allowed paths.

        Convenience wrapper that combines `validate_imports` and
        `validate_paths` into a single check.

        Args:
            code: Source code to validate.

        Returns:
            True if the code passes both the import and path
            validation checks, False otherwise.
        """
        return self.validate_imports(code) and self.validate_paths(code)
