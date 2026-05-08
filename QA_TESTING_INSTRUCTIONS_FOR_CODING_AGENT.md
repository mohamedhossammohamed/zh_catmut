# QA Acceptance Instructions for Coding Agent

The adversarial QA runner is located outside the repository on the Desktop:

```bash
/Users/mohammedhossam/Desktop/zh_catmut_adversarial_qa.pyz
```

It is a direct-run compiled QA artifact. Run it as a black-box acceptance gate.
Do not unzip, extract, inspect, decompile, disassemble, modify, or copy its
contents. Use the objective-level feedback to improve the production
implementation and satisfy the documented API contract.

## Required Precondition

The production package must be built and importable as a normal Python package
named `zh_catmut`.

The expected public API is:

```python
from zh_catmut import remap_categorical, remap_codes_inplace
```

The expected native package internals are:

```python
from zh_catmut._loader import load_native
from zh_catmut import _abi
```

## Install Runtime QA Dependencies

From the repository root, use a clean environment and install the package plus
runtime QA dependencies:

```bash
python -m pip install -U pip
python -m pip install -e .
python -m pip install pytest numpy pandas
```

## View Acceptance Objectives

To see the objective IDs and summaries:

```bash
python /Users/mohammedhossam/Desktop/zh_catmut_adversarial_qa.pyz --list-objectives
```

Use these objectives as the acceptance targets. Implement correct, general
production behavior for each objective rather than matching any particular test
case.

## Run the QA Gate

From the repository root:

```bash
python /Users/mohammedhossam/Desktop/zh_catmut_adversarial_qa.pyz
```

The runner prints objective-level feedback. A failing run includes:

- failed objective ID;
- objective summary;
- exception type;
- failure detail;
- traceback;
- final pass/fail summary.

Example feedback shape:

```text
[FAIL] OBJ-006: Native ABI gates null pointers and massively oversized lengths without crashing
       objective_failed: Native ABI gates null pointers and massively oversized lengths without crashing
       exception_type: ObjectiveFailure
       failure_detail: null codes pointer should return the documented status, got a different status
...
QA SUMMARY: passed=10, failed=1, total_executed=11
```

## Feedback Loop

When an objective fails:

1. Read the failed objective ID and failure detail.
2. Map the failure back to the API contract and implementation plan.
3. Fix the production behavior generally.
4. Re-run the QA gate.

To rerun only one objective after a targeted fix:

```bash
python /Users/mohammedhossam/Desktop/zh_catmut_adversarial_qa.pyz --only OBJ-006
```

To stop on the first failing objective:

```bash
python /Users/mohammedhossam/Desktop/zh_catmut_adversarial_qa.pyz --fail-fast
```

To save machine-readable feedback:

```bash
python /Users/mohammedhossam/Desktop/zh_catmut_adversarial_qa.pyz --json-results qa_results.json
```

## Performance Gate Configuration

The runner includes a strict native performance objective. Use the default target
unless the project owner explicitly changes it:

```bash
ZH_CATMUT_PERF_N=2000000 \
ZH_CATMUT_PERF_THRESHOLD_SECONDS=0.25 \
python /Users/mohammedhossam/Desktop/zh_catmut_adversarial_qa.pyz
```

Do not tune implementation behavior for the QA artifact itself. Optimize the
actual native remapping path according to the architecture: contiguous memory,
validated primitive C-ABI inputs, no unnecessary allocations, and predictable
batch execution.

## Rules

- Do not inspect or alter the QA artifact.
- Do not skip objectives.
- Do not weaken thresholds unless the project owner explicitly changes the
  acceptance target.
- Do not add test-specific branches or hardcoded special cases.
- Focus on satisfying the public API contract, native ABI contract, memory-safety
  gates, deterministic semantics, Copy-on-Write safety, and performance
  objectives.
