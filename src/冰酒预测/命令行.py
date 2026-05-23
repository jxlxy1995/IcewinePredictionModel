import typer
from sqlalchemy import text

from 冰酒预测.数据库 import 创建会话工厂, 创建数据库引擎, 初始化数据库

app = typer.Typer(help="冰酒足球预测模型 CLI")


@app.command("版本")
def 版本():
    typer.echo("冰酒足球预测模型 0.1.0")


@app.command("初始化数据库")
def 初始化数据库命令():
    engine = 创建数据库引擎()
    初始化数据库(engine)
    typer.echo("数据库初始化完成")


@app.command("数据库状态")
def 数据库状态():
    engine = 创建数据库引擎()
    初始化数据库(engine)
    会话工厂 = 创建会话工厂(engine)
    with 会话工厂() as 会话:
        结果 = 会话.execute(text("select 1")).scalar_one()
    typer.echo(f"数据库连接正常：{结果}")


if __name__ == "__main__":
    app()
