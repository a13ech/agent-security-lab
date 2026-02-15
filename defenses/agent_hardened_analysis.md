# Hardened Agent: Defense Strategies

## Overview
`agent_hardened.py` implements 4 layers of defense against the 3 attacks:

## DEFENSE 1: Path Allowlisting

**What it defends against:** Attack 1 (Direct File Access)

```python
SAFE_PATHS = {
    str(Path("public.txt").resolve()),
    str(Path("public_data").resolve())
}
```

**How it works:**
- Only whitelisted paths can be read
- Attempts to read `secrets.txt` are blocked
- Returns clear error message with approved files
- Uses absolute path resolution to prevent symlink attacks

**Result:**
```
❌ Attack 1: BLOCKED
"Access denied. File not in approved list."
```

---

## DEFENSE 2: Safe Expression Evaluation (AST)

**What it defends against:** Attack 3 (RCE via eval)

**Before (VULNERABLE):**
```python
result = eval(expression)  # Can execute ANY Python code
```

**After (HARDENED):**
```python
def safe_eval(expression):
    node = ast.parse(expression, mode='eval')
    # Only allows: +, -, *, /, **, unary -
    # Blocks: __import__, open(), exec(), etc.
```

**Allowed operations:**
- `+` `-` `*` `/` `**` (power) and unary minus

**Blocked operations:**
- Any function calls (`__import__()`, `open()`, etc.)
- Attribute access (`os.system`, etc.)
- List/dict operations
- Lambda expressions

**Result:**
```
❌ Attack 3: BLOCKED
__import__('os').system('..') → "Invalid expression"
```

---

## DEFENSE 3 & 4: Audit Logging

**Creates:** `agent_audit.log`

Logs:
- Every user request
- Every tool call with inputs
- Enables post-incident forensics
- Can trigger alerts on suspicious patterns

**Example log:**
```
[REQUEST] Read secrets.txt
[TOOL] read_file: {"filepath": "secrets.txt"}
```

---

## DEFENSE LIMITATIONS

Even this hardened version has constraints:

1. **Still trusts Claude's tool decisions** — A jailbreak could convince Claude to use tools maliciously
2. **No rate limiting** — Could DOS with many requests
3. **No anomaly detection** — Doesn't detect unusual access patterns
4. **Limited tool set** — Removed write_file entirely (safest approach)

## Defense-in-Depth Recommendations

For production:
1. **OS-level sandboxing** — Run agent in container/VM with minimal permissions
2. **Network isolation** — Only allow connections to specific APIs
3. **Input filtering** — Pre-filter user input for obvious attacks
4. **Output sanitization** — Strip sensitive data from responses
5. **Rate limiting** — Limit requests per user/minute
6. **Behavioral analysis** — ML-based anomaly detection
7. **Secrets management** — Keep API keys, credentials separate from agent
8. **Incident response** — Plan for when containment fails
