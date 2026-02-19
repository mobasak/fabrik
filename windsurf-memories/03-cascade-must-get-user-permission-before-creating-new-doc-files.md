# Cascade Must Get User Permission Before Creating New Doc Files

**Tags:** #enforcement #documentation #files #permission #mandatory

## No New Doc Files Without Permission (MANDATORY)

Before creating ANY new .md file, I MUST:
1. Check if existing file can be extended
2. Check if content can be inlined (like in scaffold.py)
3. Ask user: "I need to create [filename]. Is this okay?"
4. Wait for user approval

**Preferred alternatives to new files:**
- Extend existing files
- Inline generation in code (like .gitignore, .env.example in scaffold.py)
- Add section to existing documentation

**Violation:** Creating new .md files without explicit user permission.
