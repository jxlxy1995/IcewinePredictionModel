# 冰酒足球预测模型

本项目用于构建足球亚盘和大小球预测推荐系统。当前重点包括比赛基础数据同步、历史赔率回填、模型训练、推荐记录复盘和本地 Web 控制台。

## 本地 Python

固定使用：

```powershell
C:\ProgramData\anaconda3\python.exe
```

## 时间规则

所有涉及时间的展示、记录、配置和业务判断，均使用北京时间。

## 本地敏感文件

不要提交以下内容：

- `.env`
- API key
- `local_data/`
- SQLite 数据库
- `logs/`
- `web/node_modules/`
- `web/dist/`

## API-Football 配置

在 `.env` 中配置：

```env
API_FOOTBALL_KEY=your_key
```

`.env` 已被 git 忽略，不要提交密钥。

## Web 控制台

后端启动：

```powershell
.\scripts\start_web_api.ps1
```

前端启动：

```powershell
.\scripts\start_web_frontend.ps1
```

默认地址：

```text
前端：http://127.0.0.1:5173
后端：http://127.0.0.1:8000
```

前端会优先请求后端 API；如果后端未启动或公司环境没有真实数据库，会自动回退到 mock 数据。

## 常用验证

后端测试：

```powershell
$env:PYTHONPATH='src'
C:\ProgramData\anaconda3\python.exe -m pytest -q
```

前端构建：

```powershell
cd web
npm install
npm run build
```

## 手动同步示例

```powershell
icewine sync upcoming --days 1
icewine sync odds --days 1
```

开发阶段请优先使用少量联赛和短时间窗口，避免浪费 API 请求额度。
