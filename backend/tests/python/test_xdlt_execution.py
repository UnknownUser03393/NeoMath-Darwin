from __future__ import annotations

from neomath.xdlt import lower_to_semantic_ir, parse_xdlt
from neomath.xdlt.execution import ExecutionEngine, ExecutionRequest, PythonRunner
from neomath.xdlt.execution.result import ImageOutput
from neomath.xdlt.graph import build_dependency_graph


def _run(source: str, timeout: float = 20.0, **inputs) -> dict:
    runner = PythonRunner(timeout=timeout)
    request = ExecutionRequest(
        exec_id="exec:test",
        language="python",
        source=source,
        inputs=inputs,
    )
    return runner.execute(request).to_dict()


# --- python runner ----------------------------------------------------------


def test_runner_success_with_stdout() -> None:
    result = _run('print("hello")')
    assert result["status"] == "success"
    assert "hello" in result["stdout"]


def test_runner_json_output() -> None:
    result = _run(
        "from xdlt_runtime import output\n"
        'output.json({"a": 1, "b": [2, 3]})'
    )
    assert result["status"] == "success"
    assert result["outputs"][0]["kind"] == "json"
    assert result["outputs"][0]["value"] == {"a": 1, "b": [2, 3]}


def test_runner_text_output() -> None:
    result = _run('from xdlt_runtime import output\noutput.text("hi")')
    assert result["status"] == "success"
    assert result["outputs"][0] == {"kind": "text", "text": "hi"}


def test_runner_exception_is_failed() -> None:
    result = _run("1 / 0")
    assert result["status"] == "failed"
    assert "ZeroDivisionError" in result["message"]


def test_runner_timeout() -> None:
    result = _run("while True:\n    pass", timeout=2.0)
    assert result["status"] == "timeout"


def test_runner_process_isolation_on_os_exit() -> None:
    result = _run("import os\nos._exit(7)")
    assert result["status"] == "failed"
    assert "worker exited" in result["message"]


def test_runner_process_isolation_on_sys_exit() -> None:
    result = _run("import sys\nsys.exit(3)")
    assert result["status"] == "failed"


def test_runner_injects_inputs_as_sympy() -> None:
    result = _run(
        "from xdlt_runtime import output\noutput.json({'alpha': alpha})",
        alpha=__import__("sympy").Symbol("alpha", real=True, positive=True),
    )
    assert result["outputs"][0]["value"] == {"alpha": "alpha"}


def test_runner_math_output() -> None:
    result = _run('from xdlt_runtime import output\noutput.math("x^2")')
    assert result["outputs"][0]["kind"] == "math"
    assert result["outputs"][0]["expression"] == "x^2"


# --- cache ------------------------------------------------------------------


def test_cache_hit_on_identical_input_then_miss_on_change(tmp_path) -> None:
    hw = """#exec:plot(python) {
print("hello")
}
"""
    ir = lower_to_semantic_ir(parse_xdlt(hw))
    engine = ExecutionEngine(cache_dir=tmp_path)

    first = engine.execute_document(ir, build_dependency_graph(ir))
    assert first["results"][0].status == "success"
    assert first["results"][0].cached is False
    assert first["cacheHits"] == []

    second = engine.execute_document(ir, build_dependency_graph(ir))
    assert second["results"][0].cached is True
    assert second["cacheHits"] == ["exec:plot"]

    changed_ir = lower_to_semantic_ir(parse_xdlt(hw.replace("hello", "world")))
    third = engine.execute_document(changed_ir, build_dependency_graph(changed_ir))
    assert third["results"][0].cached is False
    assert third["results"][0].stdout == "world\n"


# --- engine end to end ------------------------------------------------------


def test_engine_end_to_end_acceptance(tmp_path) -> None:
    hw = """#context {
    alpha: Real & Positive
}

$$ #eq:a
x + alpha
$$

#assert:test(using=sympy) {
    claim substitute(#eq:a, x=0) == alpha
}

#exec:plot(
    python,
    inputs=[alpha]
) {
from xdlt_runtime import output

output.json({
    "alpha": alpha
})
}

#fig:data(
    source=#exec:plot[0]
) {
    Generated result.
}
"""
    ir = lower_to_semantic_ir(parse_xdlt(hw))
    graph = build_dependency_graph(ir)
    engine = ExecutionEngine(cache_dir=tmp_path)
    outcome = engine.execute_document(ir, graph)

    assert outcome["results"][0].exec_id == "exec:plot"
    assert outcome["results"][0].status == "success"
    assert outcome["results"][0].outputs[0].to_dict()["value"] == {"alpha": "alpha"}

    verified = {v["assertionId"]: v["status"] for v in outcome["verificationResults"]}
    assert verified == {"assert:test": "valid"}

    assert outcome["nodeStates"]["exec:plot"] == "clean"
    assert outcome["nodeStates"]["result:exec.plot/0"] == "clean"
    assert outcome["nodeStates"]["fig:data"] == "clean"
    assert outcome["nodeStates"]["assert:test"] == "clean"


def test_successful_execution_with_stdout_only_keeps_figure_clean(tmp_path) -> None:
    hw = """#exec:plot(python) {
print("done")
}

#fig:data(source=#exec:plot[0]) {
    Generated.
}
"""
    ir = lower_to_semantic_ir(parse_xdlt(hw))
    graph = build_dependency_graph(ir)
    engine = ExecutionEngine(cache_dir=tmp_path)
    outcome = engine.execute_document(ir, graph)
    assert outcome["results"][0].status == "success"
    assert outcome["nodeStates"]["exec:plot"] == "clean"
    assert outcome["nodeStates"]["result:exec.plot/0"] == "clean"
    assert outcome["nodeStates"]["fig:data"] == "clean"


def test_failed_execution_blocks_figure(tmp_path) -> None:
    hw = """#exec:plot(python) {
raise RuntimeError("boom")
}

#fig:data(source=#exec:plot[0]) {
    Generated.
}
"""
    ir = lower_to_semantic_ir(parse_xdlt(hw))
    graph = build_dependency_graph(ir)
    engine = ExecutionEngine(cache_dir=tmp_path)
    outcome = engine.execute_document(ir, graph)

    assert outcome["results"][0].status == "failed"
    assert outcome["nodeStates"]["exec:plot"] == "failed"
    assert outcome["nodeStates"]["result:exec.plot/0"] == "unavailable"
    assert outcome["nodeStates"]["fig:data"] == "blocked"


def test_execution_is_deterministic_and_topologically_ordered(tmp_path) -> None:
    hw = """#exec:a(python) {
print("a")
}

#exec:b(python) {
print("b")
}
"""
    ir = lower_to_semantic_ir(parse_xdlt(hw))
    engine = ExecutionEngine(cache_dir=tmp_path)
    first = engine.execute_document(ir, build_dependency_graph(ir))
    second = engine.execute_document(ir, build_dependency_graph(ir))
    assert [r.exec_id for r in first["results"]] == ["exec:a", "exec:b"]
    assert [r.exec_id for r in second["results"]] == ["exec:a", "exec:b"]
    assert second["cacheHits"] == ["exec:a", "exec:b"]


def test_image_output_roundtrip(tmp_path) -> None:

    engine = ExecutionEngine(cache_dir=tmp_path)
    cache = engine.cache
    from neomath.xdlt.execution import ExecutionResult

    result = ExecutionResult(
        exec_id="exec:img",
        status="success",
        outputs=[ImageOutput(data_base64="aGVsbG8=", mime="image/png", name="plot.png")],
    )
    cache.store(result, "sha256:abc", "env", "1.0")
    loaded = cache.load("exec:img", "sha256:abc", "env", "1.0")
    assert loaded is not None
    assert loaded.outputs[0].data_base64 == "aGVsbG8="
    assert loaded.outputs[0].name == "plot.png"


def test_verification_is_reused_via_cache(tmp_path) -> None:
    hw = """$$ #eq:a
x + 0 = 0
$$

#assert:test {
    claim substitute(#eq:a, x=0)
}
"""
    ir = lower_to_semantic_ir(parse_xdlt(hw))
    engine = ExecutionEngine(cache_dir=tmp_path)
    first = engine.execute_document(ir, build_dependency_graph(ir))
    second = engine.execute_document(ir, build_dependency_graph(ir))
    assert first["verificationResults"][0]["cached"] is False
    assert second["verificationResults"][0]["cached"] is True
    assert second["verificationResults"][0]["status"] == "valid"
