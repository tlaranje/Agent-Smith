import time

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from student.src.sandbox.sandbox import Sandbox
from student.src.sandbox.sandbox_config import SandboxConfig

console = Console()

results = []


def run_test(name, config, code, expected_success, check_fn=None):
    console.rule(f"[bold cyan]{name}")

    sandbox = Sandbox("MBPP", config=config)
    try:
        sandbox.build()
        sandbox.start()

        start = time.time()
        output, success = sandbox.execute(code)
        elapsed = time.time() - start

        console.print(Panel(output, title="Output", expand=False))
        console.print(f"success={success} elapsed={elapsed:.1f}s")

        passed = success == expected_success
        if check_fn is not None:
            passed = passed and check_fn(output, elapsed)

        results.append((name, passed))

        if passed:
            console.print("[bold green]PASSED[/bold green]")
        else:
            console.print("[bold red]FAILED[/bold red]")

    except Exception as e:
        console.print(f"[bold red]ERROR: {e}[/bold red]")
        results.append((name, False))

    finally:
        sandbox.stop()


def test_1_base_success():
    run_test(
        name="1. Base success (put_archive)",
        config=SandboxConfig(),
        code="print('hello from sandbox')\n",
        expected_success=False,
        check_fn=lambda out, _: "hello from sandbox" in out,
    )


def test_2_final_answer():
    run_test(
        name="2. final_answer full flow",
        config=SandboxConfig(),
        code="final_answer('42')\n",
        expected_success=True,
        check_fn=lambda out, _: out.strip() == "42",
    )


def test_3_size_limit():
    run_test(
        name="3. max_memory_mb limit (int fix)",
        config=SandboxConfig(max_memory_mb=0),
        code="print(1)\n",
        expected_success=False,
        check_fn=lambda out, _: "too large" in out,
    )


def test_4_timeout():
    run_test(
        name="4. max_execution_time_seconds timeout",
        config=SandboxConfig(
            max_execution_time_seconds=3,
            authorized_imports=["time"],
        ),
        code="import time\ntime.sleep(10)\n",
        expected_success=False,
        check_fn=lambda out, elapsed: (
            "[TIMEOUT]" in out and elapsed < 8
        ),
    )


def test_5_config_injection():
    run_test(
        name="5. Injected SandboxConfig respected",
        config=SandboxConfig(
            authorized_imports=["math"],
            max_execution_time_seconds=2,
            max_memory_mb=1,
        ),
        code="import os\nprint(os.getcwd())\n",
        expected_success=False,
        check_fn=lambda out, _: "disallowed import" in out,
    )


def print_summary():
    table = Table(title="Resumo dos testes")
    table.add_column("Teste", style="cyan")
    table.add_column("Resultado", style="bold")

    all_passed = True
    for name, passed in results:
        status = "[green]PASSOU[/green]" if passed else "[red]FALHOU[/red]"
        table.add_row(name, status)
        all_passed = all_passed and passed

    console.print(table)

    if all_passed:
        console.print("\n[bold green]Todos os testes passaram.[/bold green]")
    else:
        console.print("\n[bold red]Alguns testes falharam.[/bold red]")


def main():
    test_1_base_success()
    test_2_final_answer()
    test_3_size_limit()
    test_4_timeout()
    test_5_config_injection()
    print_summary()


if __name__ == "__main__":
    main()
