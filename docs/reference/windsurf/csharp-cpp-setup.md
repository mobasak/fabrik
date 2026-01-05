# C#, .NET, and C++ Development Setup

**Last Updated:** 2026-01-05

> ⚠️ **Not Currently Used by Fabrik**
>
> This documentation is preserved for reference. Fabrik's stack is Python + TypeScript/JavaScript.
> If you need C#/.NET/C++ support in the future, follow this guide.

---

## Overview

Windsurf uses open-source tooling for compiling, linting, and debugging. Microsoft's proprietary Visual Studio components cannot be redistributed.

This guide covers:
- **.NET / C#** – targeting both .NET Core and .NET Framework (via Mono)
- **C / C++** – using clang-based tooling

---

## 1. .NET / C# Development

### .NET Core / .NET 6+

**Extensions:**
| Extension | Purpose |
|-----------|---------|
| `muhammad-sammy.csharp` | OmniSharp LS + NetCoreDbg (F5 debugging) |
| `ms-dotnettools.vscode-dotnet-runtime` | Auto-installs missing runtimes/SDKs |
| `fernandoescolar.vscode-solution-explorer` | Navigate .NET solutions and projects |

**Build:** `dotnet build`

### .NET Framework via Mono

**Extensions:**
| Extension | Purpose |
|-----------|---------|
| `chrisatwindsurf.mono-debug` | Debug adapter for Mono |
| `muhammad-sammy.csharp` | Language features |

**Requirements:**
- Install Mono tool-chain in workspace
- Toggle off "Omnisharp: Use Modern Net" in settings for .NET Framework projects

**Build:** `mcs Program.cs`

### Configure tasks.json

Create `.vscode/tasks.json`:

```json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "build-dotnet",
      "type": "shell",
      "command": "dotnet",
      "args": ["build", "YourProject.csproj"],
      "group": "build",
      "problemMatcher": "$msCompile"
    },
    {
      "label": "build-mono",
      "type": "shell",
      "command": "mcs",
      "args": ["YourProgram.cs"],
      "group": "build"
    }
  ]
}
```

### Configure launch.json

Create `.vscode/launch.json`:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": ".NET Core Launch",
      "type": "coreclr",
      "request": "launch",
      "preLaunchTask": "build-dotnet",
      "program": "${workspaceFolder}/bin/Debug/net6.0/YourApp.dll",
      "cwd": "${workspaceFolder}",
      "args": []
    },
    {
      "name": "Mono Launch",
      "type": "mono",
      "request": "launch",
      "preLaunchTask": "build-mono",
      "program": "${workspaceFolder}/YourProgram.exe",
      "cwd": "${workspaceFolder}"
    }
  ]
}
```

### CLI Commands

```bash
# .NET Core
dotnet build
dotnet run

# Mono / .NET Framework
mcs Program.cs
mono Program.exe
```

### .NET Framework Limitations

⚠️ Mixed assemblies (C++/CLI) or complex Visual Studio dependencies have significant limitations. These typically require Visual Studio's proprietary build system.

**Recommended approaches:**
- Use Windsurf alongside Visual Studio for code generation/editing
- Migrate compatible portions to .NET Core where possible

---

## 2. C / C++ Development

### Required Extensions

| Extension | Purpose |
|-----------|---------|
| `Codeium.windsurf-cpptools` | Bundle with LSP, debugging, CMake support |

**Or install individually:**
| Extension | Purpose |
|-----------|---------|
| `llvm-vs-code-extensions.vscode-clangd` | clangd language server |
| `vadimcn.vscode-lldb` | Native debugger (LLDB) for C/C++/Rust |
| `ms-vscode.cmake-tools` | CMake project integration |

### Configure Build Tasks

Create `.vscode/tasks.json`:

```json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "build-cpp",
      "type": "shell",
      "command": "clang++",
      "args": ["-g", "main.cpp", "-o", "main"],
      "group": "build",
      "problemMatcher": "$gcc"
    }
  ]
}
```

---

## 3. Notes & Gotchas

- **Open-source only** – decline proprietary Microsoft tooling prompts
- **Container vs Host** – SDKs/compilers must be inside Windsurf workspace container
- **Keyboard shortcuts:**
  - `Ctrl/⌘ + Shift + B` → compile using active build task
  - `F5` → debug using selected launch.json config

---

## 4. Setup Checklist

1. Install required extensions for your language stack
2. Create `.vscode/tasks.json` with build commands
3. Create `.vscode/launch.json` with executable paths
4. For Mono: install runtime, verify `mono --version`
5. Update file paths and project names
6. Test: `Ctrl+Shift+B` to build, `F5` to debug

---

## See Also

- [Windsurf Docs - C#/C++ Setup](https://docs.windsurf.com)
- [Recommended Extensions](recommended-extensions.md)
