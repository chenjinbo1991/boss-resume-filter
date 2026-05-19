# 测试目录说明

本目录分三类，避免把稳定回归、浏览器人工验证和历史实验脚本混在一起。

## 稳定单元测试

位置：`tests/unit/`

要求：
- 不依赖真实 `job_config.json`
- 不启动浏览器
- 不访问网络
- 不要求人工登录
- 输出只使用 ASCII 的 `PASS` / `FAIL`

运行：

```powershell
python tests/run_unit_tests.py
```

## 人工/集成测试

位置：`tests/manual/`

这类脚本可能依赖 Chrome、BOSS 页面、人工登录、调试端口或真实网络环境，不纳入默认回归。

## 历史归档脚本

位置：`tests/archive/`

这里存放旧调试脚本和已失效脚本。归档脚本默认不维护、不保证可运行，只作为排查历史问题时的参考。
