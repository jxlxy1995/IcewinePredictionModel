# Repository Instructions For Codex

Read `Agent.md` before working in this repository. The rules below are the
first things to apply in every Codex session.

## Runtime

- Default shell is PowerShell.
- Repository path: `D:\project\IcewinePredictionModel`
- Always use this Python interpreter:
  - PowerShell: `C:\ProgramData\anaconda3\python.exe`
  - Git Bash: `/c/ProgramData/anaconda3/python`
- Do not try plain `python` or `python3` first unless explicitly checking PATH
  behavior.
- Common Python environment variables:

```powershell
$env:PYTHONPATH='src'
$env:PYTHONIOENCODING='utf-8'
```

## Bash Commands

When a command uses bash syntax, run it through Git Bash from PowerShell:

```powershell
& 'C:\Program Files\Git\bin\bash.exe' -lc 'cd /d/project/IcewinePredictionModel && /c/ProgramData/anaconda3/python -m pytest'
```

Use PowerShell syntax for PowerShell commands, and Git Bash syntax only inside
`bash.exe -lc`.

## Git Commit Messages

- Git commit messages must be written in Chinese.
- Keep commits focused. Stage only files related to the requested change.
- Before committing code changes, run focused verification for the touched area
  when practical.
