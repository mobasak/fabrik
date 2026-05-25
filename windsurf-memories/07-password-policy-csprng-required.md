# Password Policy - CSPRNG Required

**Tags:** #security #passwords #policy #csprng

All passwords and secrets must use CSPRNG (Cryptographically Secure Pseudo-Random Number Generator):
- Length: 32 characters (adapt down only if system has lower limit)
- Characters: `[a-zA-Z0-9]` (alphanumeric, no special chars for compatibility)
- Generator: Python `secrets` module, Node `crypto.randomBytes`
- Never truncate - generate correct length from start
- Weak passwords like `postgres`, `admin`, `password123` are FORBIDDEN

Python example:
```python
import secrets, string
secret = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))
```

Policy added to /opt/fabrik/windsurfrules
