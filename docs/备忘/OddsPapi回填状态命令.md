# OddsPapi 回填状态命令备忘

## Git Bash

在项目根目录执行：

```bash
PYTHONPATH=src PYTHONIOENCODING=utf-8 /c/ProgramData/anaconda3/python.exe -m icewine_cli odds-source oddspapi-worker-status --tail-lines 80
```

## 输出重点

- `pid=... status=running`：后台 worker 仍在运行。
- `pid=... status=stopped`：后台 worker 已结束。
- `进度快照`：新 worker 的结构化进度，包括当前联赛、轮次、已处理场次、写入快照、失败数和请求数。
- `最近日志`：worker 原始日志尾部。

## 进度快照文件

新 worker 会写入：

```text
logs/odds/oddspapi-worker-progress.json
```

如需直接查看 JSON：

```bash
cat logs/odds/oddspapi-worker-progress.json
```
