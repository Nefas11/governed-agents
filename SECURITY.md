# Security

## Prompt-Injection Detection Patterns

The prompt-injection detector uses simple, detection-only regex patterns to flag high-risk phrases. Current patterns include:

- "ignore all instructions"
- "ignore any instructions"
- "ignore previous instructions"
- "ignore all previous instructions"

These patterns are **not** used for filtering or transformation; they are only used for detection and reporting.
