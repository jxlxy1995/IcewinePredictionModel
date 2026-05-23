# 冰酒足球预测模型

本项目用于构建足球亚盘和大小球预测推荐系统。

## 本地 Python

固定使用：

`C:\ProgramData\anaconda3\python.exe`

## 时间规则

所有涉及时间的展示、记录、配置和业务判断，均使用北京时间。

## API-Football 配置

在 `.env` 中配置：

```env
API_FOOTBALL_KEY=your_key
```

`.env` 已被 git 忽略，不要提交密钥。

## 手动同步

```powershell
icewine sync upcoming --days 1
icewine sync odds --days 1
```

开发阶段默认每日请求预算为 100，请优先使用少量联赛和短时间窗口。
