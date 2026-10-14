---
name: legal-preprocess
description: 将纯文本直接接收或按显式转换配置处理合同原件，产出可登记的原样文本与元数据。
---

# 预处理

## 固定启动

用安装支持的系统 Python 执行下列片段；替换 skill_file 为宿主交付路径、workspace_root 为本次会话打开目录的绝对路径。工作区在任务期间固定，后续 cd 或合同位置不改变它。

```python
import json
from pathlib import Path
import subprocess
import sys

skill_file = Path("/host/skills/legal-preprocess/SKILL.md").resolve(strict=True)
workspace_root = "/absolute/session/workspace"
script = skill_file.parent.parent.parent / "scripts/prepare_task.py"
result = subprocess.run([sys.executable, str(script), "runtime", "--input", "-"],
    input=json.dumps({"format_version": 1, "skill_file": str(skill_file), "workspace_root": workspace_root}),
    text=True, capture_output=True, check=False)
print(result.stdout, end="")
print(result.stderr, end="", file=sys.stderr)
raise SystemExit(result.returncode)
```

成功回执 result 给出 install_root、python、commands、workspace_root 和 workspaces_file。其余准备辅助用该专用 python；相对资料以本 skill 真实目录为基准。只访问确定路径，不列安装树、读源码/README 或预读全部阶段。故障报告具体路径，不从 PATH 找替代工具。不需要词表的初始化、预处理及续做不读取默认词表配置。

## 输入

原件路径、空输出目录路径；需转换时提供转换配置 JSON 路径。先解析本文件真实目录，读取 `../../runtime.json` 和 `../../references/preprocess-cli.md`。安装信息缺失、格式错误或路径失效时报告安装问题，不从 PATH 另找工具。调用方应明确转换器及支持的文件格式；本 skill 不从文件扩展名猜工具。

## 步骤

1. 核实原件、输出目录；无配置的 .txt/.md/.markdown（大小写不敏感）可直通，其他格式需要适用外部配置。显式配置始终优先，不失败降级。需配置时核对实际程序/解释器/已知适配入口，复用已安装绝对位置，不搜索或安装默认工具。需大量阅读转换质量时可将材料交 reader，记录异常。
2. 从安装信息中取 `commands["legal-preprocess"]` 的绝对路径，按参数数组运行 `--input FILE --output-dir DIR [--converter-config FILE]`。合同入库时进程工作目录为合同工作目录，独立预处理时为调用方指定目录。
3. 读取 stdout 的 JSON 回执，核对绝对路径、原件哈希、文本哈希和异常；把完整回执交给案件或初始化 skill。

## 工具用法与继续条件

实际调用为 `argv=[runtime.commands["legal-preprocess"],"--input",原件绝对路径,"--output-dir",输出目录绝对路径]`；仅显式使用配置时追加 `["--converter-config",配置绝对路径]`。配置是 `{format_version:1,argv:["/absolute/converter",...,"{input}",...,"{output_dir}"]}`；完整参数与输出协议见 `../../references/preprocess-cli.md`。转换器在临时输出目录写 `text.txt` 和 `metadata.json`，统一入口检查格式、字符位置和原件未改动。成功退出 0；参数/产物错误退出 2，文件或进程故障退出 3。失败回执含 `errors[].code/path/message`，不得把残留文件作为成功产物。`FILE_EXISTS` 时选新的空目录；转换失败或质量妨碍阅读时按调用方既有异常处理要求改进源件。预处理不切条款，不判断法律关系。

纯文本严格 UTF-8/无 BOM，原字节不变；编码/BOM 问题通知用户提供合格文本或明确转码安排，不误报缺少转换器。空文本不伪造阅读完成。结果仍在 converted，不建伪配置或复制文本脚本。需要转换却无适用配置时必须向用户明确通知材料、转换类别、缺少配置及下一步；不可执行入口列配置和具体缺失路径，非零退出交付完整诊断及实际故障。受影响材料不登记/不派下游，可继续合法独立部分并如实报告范围。补齐后沿用副本及新空输出目录续做。不得用 echo、丢弃 stderr 或截断管道掩盖原退出状态。若派 reader 检查质量，主会话填写精确文件白名单（范围、用途、时机）并带入角色固定边界。

## 转换质量阅读的派发

派 reader 时直接交三部分正文：本轮仅比较已授权原件可读内容与转换文本、共同材料范围及目标、个别白名单和异常记录输出。reader 不寻找转换器、查看安装实现或写案件提交；未提供可比原件不能证明忠实，只报告能检查的范围。
