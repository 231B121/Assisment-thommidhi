# Output Validator

## How to Run
Ensure Python 3.10+ is installed. Run the test suite using standard library only:

```bash
python3 validate_outputs.py
```

To import in Python code:
```python
from validate_outputs import validate_outputs
valid_entries, failure_counts = validate_outputs(raw_strings)
```

## Unhandled Failure and Rationale
We deliberately do not strip markdown code fences (e.g., ````json ... ````) or conversational preambles emitted by language models.

When a model wraps an otherwise valid JSON object in backticks or introductory text, standard `json.loads` raises a decode error, counted as `json_decode_error`. We intentionally avoid heuristic text-cleaning or regex extraction: sanitizing model output conflates schema validation with prompt recovery. The validator strictly enforces the raw output contract, ensuring upstream prompt-engineering defects remain visible rather than silently patched.
