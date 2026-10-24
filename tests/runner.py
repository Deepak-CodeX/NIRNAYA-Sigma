"""
Zero-dependency test runner executing NIRNAYA unit test suite.

Discovers and runs test cases in tests/unit/, handling:
- Test classes and individual test methods.
- Fixture injection.
- Parametrized test execution.
- Deterministic reporting of passes, failures, and execution duration.
"""

from __future__ import annotations

import importlib
import inspect
import os
import sys
import time
import traceback
from typing import Any, Callable

# Ensure services/decision-core and project root are on sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DECISION_CORE_PATH = os.path.join(PROJECT_ROOT, "services", "decision-core")

if DECISION_CORE_PATH not in sys.path:
    sys.path.insert(0, DECISION_CORE_PATH)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def run_tests() -> int:
    unit_dir = os.path.join(PROJECT_ROOT, "tests", "unit")
    test_files = sorted(
        f[:-3]
        for f in os.listdir(unit_dir)
        if f.startswith("test_") and f.endswith(".py")
    )

    total_runs = 0
    passed = 0
    failed = 0
    errors: list[tuple[str, str]] = []

    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    safe_root = PROJECT_ROOT.encode("ascii", "replace").decode("ascii")
    print(f"============================= NIRNAYA Test Execution =============================")
    print(f"Python: {sys.version.split()[0]} | Platform: {sys.platform}")
    print(f"Root: {safe_root}")
    print(f"Discovered test modules: {len(test_files)}")
    print("---------------------------------------------------------------------------------")

    start_time = time.perf_counter()

    for mod_name in test_files:
        full_mod_name = f"tests.unit.{mod_name}"
        try:
            mod = importlib.import_module(full_mod_name)
        except Exception:
            print(f"ERROR: Failed to import {full_mod_name}")
            traceback.print_exc()
            return 1

        # Collect fixtures at module level
        module_fixtures: dict[str, Callable[[], Any]] = {}
        for name, obj in inspect.getmembers(mod):
            if inspect.isfunction(obj) and getattr(obj, "__fixture__", False):
                module_fixtures[name] = obj

        # Find all test classes
        for cls_name, cls_obj in inspect.getmembers(mod, inspect.isclass):
            if not cls_name.startswith("Test"):
                continue

            instance = cls_obj()
            # Collect class-level fixtures
            class_fixtures: dict[str, Callable[[], Any]] = dict(module_fixtures)
            for name, member in inspect.getmembers(cls_obj):
                if inspect.isfunction(member) and getattr(member, "__fixture__", False):
                    class_fixtures[name] = lambda m=member, inst=instance: m(inst)

            # Find all test methods on this class
            for meth_name, meth in inspect.getmembers(cls_obj, inspect.isfunction):
                if not meth_name.startswith("test_"):
                    continue

                param_meta = getattr(meth, "__parametrize__", None)
                if param_meta:
                    argnames, argvalues = param_meta
                    if isinstance(argnames, str):
                        argnames = [a.strip() for a in argnames.split(",")]

                    for val_tuple in argvalues:
                        total_runs += 1
                        if len(argnames) == 1:
                            param_dict = {argnames[0]: val_tuple}
                        else:
                            param_dict = dict(zip(argnames, val_tuple))

                        # Build complete arguments
                        sig = inspect.signature(meth)
                        call_kwargs = {}
                        for p in list(sig.parameters.values())[1:]:  # skip self
                            if p.name in param_dict:
                                call_kwargs[p.name] = param_dict[p.name]
                            elif p.name in class_fixtures:
                                call_kwargs[p.name] = class_fixtures[p.name]()

                        test_id = f"{cls_name}::{meth_name}[{param_dict}]"
                        try:
                            meth(instance, **call_kwargs)
                            passed += 1
                            sys.stdout.write(".")
                            sys.stdout.flush()
                        except Exception as exc:
                            failed += 1
                            sys.stdout.write("F")
                            sys.stdout.flush()
                            errors.append((test_id, traceback.format_exc()))
                else:
                    total_runs += 1
                    sig = inspect.signature(meth)
                    call_kwargs = {}
                    for p in list(sig.parameters.values())[1:]:  # skip self
                        if p.name in class_fixtures:
                            call_kwargs[p.name] = class_fixtures[p.name]()

                    test_id = f"{cls_name}::{meth_name}"
                    try:
                        meth(instance, **call_kwargs)
                        passed += 1
                        sys.stdout.write(".")
                        sys.stdout.flush()
                    except Exception as exc:
                        failed += 1
                        sys.stdout.write("F")
                        sys.stdout.flush()
                        errors.append((test_id, traceback.format_exc()))

    elapsed = time.perf_counter() - start_time
    print()
    print("---------------------------------------------------------------------------------")

    if errors:
        print("\nFAILURES:")
        for test_id, tb in errors:
            print(f"FAILED {test_id}")
            print(tb)
            print("-" * 60)

    print(
        f"\nResult: {passed} passed, {failed} failed in {elapsed:.3f}s (Total checks: {total_runs})"
    )
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run_tests())
