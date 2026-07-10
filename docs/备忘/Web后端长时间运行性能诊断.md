# Web 后端长时间运行性能诊断

## 使用场景

当 Web 服务刚启动时响应正常，但连续运行数小时后比赛筛选等操作明显变慢时，使用本文命令采集后端进程的资源快照。

这些命令只读取 Windows 进程和服务状态，不会修改代码、数据库或运行中的任务。单次执行只输出当前时刻的状态，不会自动持续监控。

## 采集后端进程资源快照

在 PowerShell 中执行：

```powershell
$backendPid = Get-NetTCPConnection -LocalPort 8000 -State Listen |
    Select-Object -First 1 -ExpandProperty OwningProcess

Get-Process -Id $backendPid |
    Select-Object Id,
        @{Name='WorkingSetMB';Expression={[math]::Round($_.WorkingSet64 / 1MB, 1)}},
        @{Name='PrivateMB';Expression={[math]::Round($_.PrivateMemorySize64 / 1MB, 1)}},
        HandleCount,
        @{Name='Threads';Expression={$_.Threads.Count}}
```

第一段命令查找正在监听后端端口 `8000` 的进程编号，第二段命令输出该进程当前的资源占用。

不要把变量命名为 `$pid`。PowerShell 变量不区分大小写，而 `$PID` 是内置只读变量，因此本文使用 `$backendPid`。

如果命令没有返回进程编号，先用下面的命令确认后端是否正在运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\start_web.ps1 status
```

## 输出字段说明

输出示例：

```text
Id     WorkingSetMB PrivateMB HandleCount Threads
-----  ------------ --------- ----------- -------
12345         420.5     610.2         286      18
```

| 字段 | 含义 | 诊断重点 |
| --- | --- | --- |
| `Id` | 后端进程编号 | 服务重启后会变化，用于确认比较的是不是同一个进程 |
| `WorkingSetMB` | 当前实际驻留在物理内存中的内存量 | 会受 Windows 内存调度影响，允许小幅上下波动 |
| `PrivateMB` | 主要由该进程独占、已经申请的内存量 | 判断 Python 缓存或对象是否持续累积时，优先观察这个指标 |
| `HandleCount` | 进程持有的文件、数据库连接、套接字和事件等系统句柄数量 | 持续增长可能表示文件、连接或其他资源没有释放 |
| `Threads` | 进程当前线程数量 | 持续增长可能表示后台线程或任务线程没有退出 |

没有适用于所有机器的固定告警数值。应在同一台机器、相近使用负载下比较变化趋势，而不是只看某一次采样的绝对值。

## 建议采样时点

至少记录以下三个时点：

1. 服务刚启动，并且比赛筛选响应正常时。
2. 服务运行约 10 小时，比赛筛选已经明显变慢，但尚未重启时。
3. 重启服务并再次确认筛选恢复后。

变慢时不要立即重启。先采集资源快照，并查询是否存在运行中的自动任务：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/paper-automation/tasks |
    Select-Object id, status, trigger_at, started_at, finished_at
```

重点关注 `status` 为 `running` 的任务。采集完成后再根据现场需要重启服务。

## 保存采样结果

如需把每次采样追加保存到工程的 `.web` 临时目录，可以执行：

```powershell
$backendPid = Get-NetTCPConnection -LocalPort 8000 -State Listen |
    Select-Object -First 1 -ExpandProperty OwningProcess
$backendProcess = Get-Process -Id $backendPid

[pscustomobject]@{
    SampleTime   = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
    ProcessId    = $backendProcess.Id
    WorkingSetMB = [math]::Round($backendProcess.WorkingSet64 / 1MB, 1)
    PrivateMB    = [math]::Round($backendProcess.PrivateMemorySize64 / 1MB, 1)
    HandleCount  = $backendProcess.HandleCount
    Threads      = $backendProcess.Threads.Count
} | Export-Csv -Path '.web\backend-resource-samples.csv' `
    -Append -NoTypeInformation -Encoding utf8
```

采样文件路径为：

```text
.web/backend-resource-samples.csv
```

`.web/` 已被 Git 忽略，不要把现场进程数据提交到版本库。

## 结果判断

| 观察结果 | 优先怀疑方向 |
| --- | --- |
| `PrivateMB` 和 `WorkingSetMB` 随运行时间明显增长，线程和句柄基本稳定 | 无界缓存或 Python 对象持续累积 |
| `PrivateMB` 很高，但 `WorkingSetMB` 明显较低 | 部分进程内存可能已经被换出到磁盘，容易出现明显卡顿 |
| `HandleCount` 持续成倍增长 | 数据库连接、文件、网络连接或其他句柄没有正确释放 |
| `Threads` 持续增长 | 后台线程或任务线程泄漏 |
| 内存基本稳定，但变慢时存在 `running` 自动任务 | 自动任务执行期间的 CPU、磁盘或 SQLite 读写竞争 |
| 各项资源基本稳定，且没有运行中的自动任务 | 继续检查单次筛选请求的数据量、查询耗时和外部接口等待 |
| 重启后资源占用下降且筛选立即恢复 | 优先检查后端进程内缓存、未完成请求和内存累积 |

对于当前比赛筛选变慢问题，如果只有 `PrivateMB` 或 `WorkingSetMB` 明显增长，而 `HandleCount`、`Threads` 和自动任务状态都保持稳定，优先检查 Web 响应缓存和筛选请求产生的大量临时对象。

## 记录模板

协作者反馈现场情况时，建议同时提供以下信息：

| 采样时点 | 北京时间 | 进程 ID | WorkingSetMB | PrivateMB | HandleCount | Threads | 自动任务状态 | 筛选体感或耗时 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| 刚启动 |  |  |  |  |  |  |  |  |
| 运行约 10 小时并变慢 |  |  |  |  |  |  |  |  |
| 重启后 |  |  |  |  |  |  |  |  |

为了便于比较，三个时点应尽量使用相同的比赛日期范围、联赛、状态和赔率状态筛选条件。
