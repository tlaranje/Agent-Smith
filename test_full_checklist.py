import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

try:
    import docker as docker_sdk
    _docker_client = docker_sdk.from_env()
    _docker_client.ping()
    DOCKER_AVAILABLE = True
except Exception:
    DOCKER_AVAILABLE = False

requires_docker = pytest.mark.skipif(
    not DOCKER_AVAILABLE,
    reason="Docker não está disponível neste ambiente.",
)


# ---------------------------------------------------------------------------
# 1. Ficheiros e estrutura obrigatória do repositório
# ---------------------------------------------------------------------------

class TestRequiredFiles:
    def test_readme_exists(self):
        assert (ROOT / "README.md").exists(), (
            "README.md em falta na raiz do repositório."
        )

    def test_readme_first_line_format(self):
        readme = ROOT / "README.md"
        if not readme.exists():
            pytest.skip("README.md não existe ainda.")
        first_line = readme.read_text(encoding="utf-8").splitlines()[0]
        assert first_line.startswith("*") and first_line.endswith("*"), (
            "A primeira linha do README deve estar em itálico "
            "(*This project has been created as part of the 42 "
            "curriculum by <login>*)."
        )

    def test_benchmark_report_exists(self):
        assert (ROOT / "BENCHMARK_REPORT.md").exists(), (
            "BENCHMARK_REPORT.md em falta na raiz do repositório."
        )

    def test_mcp_tools_mbpp_filename(self):
        assert (ROOT / "mcp_tools_mbpp.py").exists()

    def test_mcp_tools_swebench_filename(self):
        assert (ROOT / "mcp_tools_swebench.py").exists(), (
            "O enunciado exige o nome exato 'mcp_tools_swebench.py' "
            "(sem underscore entre 'swe' e 'bench') na raiz."
        )

    def test_no_hardcoded_api_keys(self):
        import re as _re
        suspicious_re = _re.compile(
            r"(sk-[a-zA-Z0-9]{10,}|AIzaSy[a-zA-Z0-9_\-]{20,}|"
            r"api_key\s*=\s*[\"'][A-Za-z0-9_\-]{10,}[\"'])"
        )
        offenders = []
        for path in ROOT.rglob("*.py"):
            if ".git" in path.parts or "node_modules" in path.parts:
                continue
            if path.name == "test_full_checklist.py":
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if suspicious_re.search(text):
                offenders.append(str(path))
        assert not offenders, f"Possíveis API keys hardcoded: {offenders}"

    def test_env_file_not_committed(self):
        env_file = ROOT / ".env"
        if not env_file.exists():
            return
        gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        assert ".env" in gitignore, (
            ".env existe mas não está no .gitignore."
        )


# ---------------------------------------------------------------------------
# 2. Extração de código multi-formato (code_extractor.py)
# ---------------------------------------------------------------------------

class TestCodeExtractor:
    @pytest.fixture(autouse=True)
    def _import_module(self):
        from student.src.parser.code_extractor import extract_code
        self.extract_code = extract_code

    def test_python_block(self):
        text = "Thought: ...\n```python\nresult = 1 + 1\nprint(result)\n```"
        r = self.extract_code(text)
        assert r.matched_format == "python"
        assert "result = 1 + 1" in r.code
        assert not r.malformed

    def test_python_block_malformed_syntax(self):
        text = "```python\ndef f(:\n```"
        r = self.extract_code(text)
        assert r.matched_format == "python"
        assert r.malformed

    def test_xml_invoke(self):
        text = (
            '<invoke name="read_file">'
            '<parameter name="filepath">/testbed/a.py</parameter>'
            '</invoke>'
        )
        r = self.extract_code(text)
        assert r.matched_format == "xml"
        assert "read_file(" in r.code
        assert "filepath=" in r.code

    def test_json_tool_call(self):
        text = (
            '<tool_call>{"name": "search_code", '
            '"arguments": {"pattern": "flatten"}}</tool_call>'
        )
        r = self.extract_code(text)
        assert r.matched_format == "json"
        assert "search_code(" in r.code

    def test_json_tool_call_malformed(self):
        text = "<tool_call>{not valid json</tool_call>"
        r = self.extract_code(text)
        assert r.matched_format == "json"
        assert r.malformed

    def test_react_format(self):
        text = 'Action: list_files\nAction Input: {"directory": "/testbed"}'
        r = self.extract_code(text)
        assert r.matched_format == "react"
        assert "list_files(" in r.code

    def test_no_match_reports_none(self):
        r = self.extract_code("just plain text, no code, no tool call")
        assert r.matched_format == "none"
        assert r.malformed

    def test_empty_input(self):
        r = self.extract_code("")
        assert r.matched_format == "none"
        assert r.malformed


# ---------------------------------------------------------------------------
# 3. SandboxConfig: imports e paths (sem Docker)
# ---------------------------------------------------------------------------

class TestSandboxConfig:
    @pytest.fixture(autouse=True)
    def _import_module(self):
        from student.src.sandbox.sandbox_config import SandboxConfig
        self.config = SandboxConfig()

    def test_allowed_import(self):
        assert self.config.validate_imports("import math\n")

    def test_disallowed_import(self):
        assert not self.config.validate_imports("import os\n")

    def test_disallowed_import_from(self):
        assert not self.config.validate_imports(
            "from subprocess import run\n"
        )

    def test_eval_blocked(self):
        assert not self.config.validate_imports("eval('1+1')\n")

    def test_exec_blocked(self):
        assert not self.config.validate_imports("exec('1+1')\n")

    def test_dunder_import_blocked(self):
        assert not self.config.validate_imports(
            "__import__('os').system('ls')\n"
        )

    def test_open_inside_allowed_dir(self):
        assert self.config.validate_paths(
            "open('/testbed/file.py')\n"
        )

    def test_open_outside_allowed_dir(self):
        assert not self.config.validate_paths(
            "open('/etc/passwd')\n"
        )

    def test_path_open_outside_allowed_dir(self):
        assert not self.config.validate_paths(
            "from pathlib import Path\nPath('/etc/passwd').open()\n"
        )

    def test_syntax_error_rejected(self):
        assert not self.config.validate_imports("def f(:\n")
        assert not self.config.validate_paths("def f(:\n")

    def test_empty_code_is_valid(self):
        assert self.config.validate_code("")


# ---------------------------------------------------------------------------
# 4. Sandbox + Docker: isolamento e limites reais
# ---------------------------------------------------------------------------

@requires_docker
class TestSandboxDocker:
    @pytest.fixture(autouse=True)
    def _setup(self):
        from student.src.sandbox.sandbox import Sandbox
        from student.src.sandbox.sandbox_config import SandboxConfig
        self.Sandbox = Sandbox
        self.SandboxConfig = SandboxConfig

    def _make_sandbox(self, **config_kwargs):
        sandbox = self.Sandbox(
            "MBPP", config=self.SandboxConfig(**config_kwargs)
        )
        sandbox.build()
        sandbox.start()
        return sandbox

    def test_basic_execution(self):
        sandbox = self._make_sandbox()
        try:
            output, success = sandbox.execute("print('hello')\n")
            assert "hello" in output
        finally:
            sandbox.stop()

    def test_final_answer_inside_container(self):
        sandbox = self._make_sandbox()
        try:
            output, success = sandbox.execute("final_answer('42')\n")
            assert success
            assert output.strip() == "42"
        finally:
            sandbox.stop()

    def test_disallowed_import_rejected_before_execution(self):
        sandbox = self._make_sandbox()
        try:
            output, success = sandbox.execute("import os\nprint(1)\n")
            assert not success
            assert "disallowed import" in output.lower()
        finally:
            sandbox.stop()

    def test_timeout_enforced(self):
        sandbox = self._make_sandbox(
            max_execution_time_seconds=3,
            authorized_imports=["time", "time.*"],
        )
        try:
            start = time.time()
            output, success = sandbox.execute(
                "import time\ntime.sleep(30)\n"
            )
            elapsed = time.time() - start
            assert not success
            assert "TIMEOUT" in output
            assert elapsed < 10
        finally:
            sandbox.stop()

    def test_memory_limit_enforced(self):
        sandbox = self._make_sandbox(max_memory_mb=64)
        try:
            output, success = sandbox.execute(
                "x = bytearray(500 * 1024 * 1024)\nprint(len(x))\n"
            )
            assert not success
        finally:
            sandbox.stop()

    def test_no_network_access(self):
        sandbox = self._make_sandbox(
            authorized_imports=["socket", "socket.*"]
        )
        try:
            code = (
                "import socket\n"
                "s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n"
                "s.settimeout(3)\n"
                "s.connect(('8.8.8.8', 53))\n"
                "print('CONNECTED')\n"
            )
            output, success = sandbox.execute(code)
            assert "CONNECTED" not in output
        finally:
            sandbox.stop()

    def test_keyboard_interrupt_not_swallowed(self):
        sandbox = self._make_sandbox()
        try:
            output, success = sandbox.execute(
                "raise KeyboardInterrupt()\n"
            )
            assert not success
        finally:
            sandbox.stop()


# ---------------------------------------------------------------------------
# 5. MCP tools: MBPP (via container real)
# ---------------------------------------------------------------------------

@requires_docker
class TestMBPPMCPTools:
    @pytest.fixture(autouse=True)
    def _setup(self):
        from student.src.sandbox.sandbox import Sandbox
        from student.src.sandbox.sandbox_config import SandboxConfig
        self.sandbox = Sandbox("MBPP", config=SandboxConfig())
        self.sandbox.build()
        self.sandbox.start()
        yield
        self.sandbox.stop()

    def test_run_tests_success(self):
        self.sandbox.mcp_client.call_tool(
            "set_current_task_tests",
            test_list=["assert soma(2, 3) == 5"],
        )
        code = "def soma(a, b):\n    return a + b\n"
        result = self.sandbox.mcp_client.call_tool("run_tests", code=code)
        assert "SUCCESS" in result

    def test_run_tests_failure(self):
        self.sandbox.mcp_client.call_tool(
            "set_current_task_tests",
            test_list=["assert soma(2, 3) == 999"],
        )
        code = "def soma(a, b):\n    return a + b\n"
        result = self.sandbox.mcp_client.call_tool("run_tests", code=code)
        assert "FAILURE" in result

    def test_unknown_tool_reports_available_tools(self):
        result = self.sandbox.mcp_client.call_tool("does_not_exist")
        assert "Unknown tool name" in result
        assert "run_tests" in result

    def test_generate_manual_lists_tools(self):
        manual = self.sandbox.mcp_client.generate_manual()
        assert "run_tests" in manual
        assert "set_current_task_tests" in manual


# ---------------------------------------------------------------------------
# 6. MCP tools: SWE-bench (mandatory tools)
# ---------------------------------------------------------------------------

@requires_docker
class TestSWEBenchMCPTools:
    @pytest.fixture(autouse=True)
    def _setup(self):
        from student.src.sandbox.sandbox import Sandbox
        from student.src.sandbox.sandbox_config import SandboxConfig
        self.sandbox = Sandbox("SWE_BENCH", config=SandboxConfig())
        self.sandbox.build()
        self.sandbox.eval_script = "echo 'placeholder eval script'"
        self.sandbox.start()
        yield
        self.sandbox.stop()

    def test_all_mandatory_tools_exposed(self):
        expected = {
            "read_file", "edit_file", "list_files",
            "search_code", "search_function_or_class_definition_in_code",
            "find_references", "run_tests", "get_patch", "run_command",
        }
        tools = {t.name for t in self.sandbox.mcp_client.list_tools()}
        missing = expected - tools
        assert not missing, f"Tools mandatórias em falta: {missing}"

    def test_read_file_format(self):
        self.sandbox.mcp_client.call_tool(
            "run_command",
            command="printf 'a\\nb\\nc\\n' > /testbed/sample.txt",
            workdir="/testbed",
        )
        output = self.sandbox.mcp_client.call_tool(
            "read_file", filepath="/testbed/sample.txt",
            start_line=1, end_line=3,
        )
        assert "1:" in output and "2:" in output and "3:" in output

    def test_edit_file_exact_match_required(self):
        self.sandbox.mcp_client.call_tool(
            "run_command",
            command="printf 'hello world\\n' > /testbed/edit.txt",
            workdir="/testbed",
        )
        result = self.sandbox.mcp_client.call_tool(
            "edit_file",
            filepath="/testbed/edit.txt",
            old_str="not present in the file",
            new_str="replacement",
        )
        assert "error" in result.lower() or "not found" in result.lower()

    def test_search_code_format(self):
        output = self.sandbox.mcp_client.call_tool(
            "search_code", pattern="def ", file_pattern="*.py"
        )
        assert ":" in output

    def test_get_patch_after_edit(self):
        self.sandbox.mcp_client.call_tool(
            "run_command",
            command="printf 'a\\n' > /testbed/patchable.py",
            workdir="/testbed",
        )
        self.sandbox.mcp_client.call_tool(
            "run_command", command="cd /testbed && git add -A",
        )
        self.sandbox.mcp_client.call_tool(
            "edit_file",
            filepath="/testbed/patchable.py",
            old_str="a\n",
            new_str="b\n",
        )
        patch = self.sandbox.mcp_client.call_tool("get_patch")
        assert "patchable.py" in patch

    def test_run_command_returns_exit_code_info(self):
        output = self.sandbox.mcp_client.call_tool(
            "run_command", command="exit 7", workdir="/testbed"
        )
        assert "7" in output


# ---------------------------------------------------------------------------
# 7. Limites de iteração/tokens (mockando o LLM)
# ---------------------------------------------------------------------------

class _FakeResponse:
    def __init__(self, content, input_tokens=10, output_tokens=10):
        self.content = content
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class _FakeLLMAlwaysWrong:
    api_url = "fake://test"
    model_name = "fake-model"

    def generate_messages(self, messages):
        return _FakeResponse("```python\nprint('nope')\n```")


@requires_docker
class TestMBPPAgentLimits:
    def test_max_iterations_reached(self):
        from student.src.agent.mbpp_agent import MBPPAgent
        from student.src.sandbox.sandbox import Sandbox
        from student.src.parser import MBPPTaskInput

        sandbox = Sandbox("MBPP")
        agent = MBPPAgent(
            sandbox=sandbox,
            llms={"fake": [_FakeLLMAlwaysWrong()]},
            max_iterations=3,
        )
        task = MBPPTaskInput(
            task_id=1,
            task_definition="dummy",
            function_definition="def f(): ...",
            test_list=["assert True"],
        )
        result = agent.solve(task)
        assert result.iterations == 3
        assert result.success is False
        assert result.error == "Maximum iterations reached"


# ---------------------------------------------------------------------------
# 8. Verificação estrutural do BENCHMARK_REPORT.md
# ---------------------------------------------------------------------------

class TestBenchmarkReportContent:
    def test_has_minimum_required_sections(self):
        report = ROOT / "BENCHMARK_REPORT.md"
        if not report.exists():
            pytest.skip("BENCHMARK_REPORT.md ainda não existe.")
        text = report.read_text(encoding="utf-8").lower()
        required_sections = [
            "setup", "results", "reliability", "ablation", "conclusion",
        ]
        missing = [s for s in required_sections if s not in text]
        assert not missing, f"Secções em falta no relatório: {missing}"

    def test_at_least_five_models_mentioned(self):
        report = ROOT / "BENCHMARK_REPORT.md"
        if not report.exists():
            pytest.skip("BENCHMARK_REPORT.md ainda não existe.")
        # Heurística simples: conta linhas de tabela markdown "| model |"
        text = report.read_text(encoding="utf-8")
        pipe_rows = [
            line for line in text.splitlines() if line.count("|") >= 2
        ]
        assert len(pipe_rows) >= 5, (
            "O relatório parece ter menos de 5 linhas de resultados "
            "numa tabela — confirmar manualmente se cobre >=5 modelos."
        )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
