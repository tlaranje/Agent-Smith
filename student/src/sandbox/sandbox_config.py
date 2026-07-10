from pydantic import BaseModel, Field
import ast


class SandboxConfig(BaseModel):
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
        if not code.strip():
            return True
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return False

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name
                    root = name.split(".")[0]

                    if name not in self.authorized_imports and \
                       f"{root}.*" not in self.authorized_imports:
                        return False

            elif isinstance(node, ast.ImportFrom):
                if node.module is None:
                    return False

                root = node.module.split(".")[0]
                if node.module not in self.authorized_imports and \
                   f"{root}.*" not in self.authorized_imports:
                    return False

            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in ["__import__", "eval", "exec"]:
                        return False
        return True

    def validate_paths(self, code: str = "") -> bool:
        if not code.strip():
            return True

        try:
            tree = ast.parse(code)
        except SyntaxError:
            return False

        def path_is_allowed(path: str) -> bool:
            return any(
                path.startswith(d) for d in self.allowed_directories
            )

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue

            if isinstance(node.func, ast.Name):
                if node.func.id == "open":
                    args = node.args
                    if args and isinstance(args[0], ast.Constant):
                        path = str(args[0].value)
                        if not path_is_allowed(path):
                            return False

            elif isinstance(node.func, ast.Attribute):
                if node.func.attr == "open":
                    target = node.func.value

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

                    args = node.args
                    if args and isinstance(args[0], ast.Constant):
                        path = str(args[0].value)
                        if not path_is_allowed(path):
                            return False

        return True

    def validate_code(self, code: str = "") -> bool:
        return self.validate_imports(code) and self.validate_paths(code)
