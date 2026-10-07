---
name: legal-initialize
description: 从用户指定的归纳语料经两遍提取与两道人审生成首版法律关系词表；适用于词表初始化。
---

# 首版词表初始化

## 安装路径

将下列占位路径替换为宿主提供的本文件绝对路径，先解析符号链接，再取父目录：

```python
from pathlib import Path

skill_dir = Path("/host/skills/legal-initialize/SKILL.md").resolve(strict=True).parent
install_root = skill_dir.parent.parent
runtime_path = install_root / "runtime.json"
print(runtime_path)
print(install_root / "references")
```

先完成上述定位，再按输出的绝对路径读取资料。本文件中的相对资料路径均以 `skill_dir` 为基准，与 shell 工作目录无关。CLI 的绝对路径从核验后的 `runtime.json` 取得。本 skill、参考资料及 CLI 均使用安装目录内的副本。

读取安装信息后，核对 `format_version` 为整数 `1`、`release_version` 为非空字符串、`install_root` 等于上述真实安装根、`environment_root` 指向其中的 `.venv`。`python` 及 `commands` 中的 `legal-case`、`legal-vocab`、`legal-preprocess` 必须是该环境内存在且可执行的绝对路径；保留环境内 Python 的启动路径。安装信息不符时报告安装问题，停止依赖它的业务调用。

## 输入与依赖

用户事先指定语料用途：`induction`、`rule_exam`、`held_out`、`legal_checklist`。还需工作目录、正式词表目标路径、需转换材料的原件与转换配置。按本文件真实目录读取 `../../runtime.json`、`../../references/vocab-cli.md`、`../../references/data-formats.md`；按当前遍次读取本目录 `references/first-pass.md` 或 `references/second-pass.md`。安装信息缺失、格式错误或路径失效时报告安装问题，不从 PATH 另找工具。转换用 `../legal-preprocess/SKILL.md`，真实合同建模验收用 `../legal-case/SKILL.md`。

## 两遍两道人审

1. 整理 `corpus.json`，记录每份材料用途、合同种类、来源、原件/文本路径与哈希、转换元数据。非 induction 不进入单元或槽的归纳证据集。
2. 第一遍按条款提取主题、可约定点、摘句、当事方和原文模态词，依据 `first-pass.md` 形成 `units-review.md`，用户直接写意见。
3. 读取第一道人审意见，整理 `units-approved.json`；未收到意见时停在此环节。
4. 第二遍依已审单元提取槽、值结构、例句、归属与条件适用说明，依据 `second-pass.md` 形成 `slots-review.md`；用户直接写意见。
5. 读取第二道人审意见，整理最终变更文件。主会话用词表 CLI 创建正式空词表并提交批准后的条目；形成词表、证据包、判定表，附残留条款、规则考卷表达结果和法律清单查漏结果。

## 工具用法与交接

从安装信息中取 `commands["legal-vocab"]` 的绝对路径，以指定工作目录为进程工作目录，按参数数组运行 `argv=[runtime.commands["legal-vocab"],"init","--vocabulary",词表绝对路径]`，再以 `--vocabulary FILE --input CHANGE.json` 提交正式条目。`list/show/diff` 用于检查结果；完整参数和文件格式见 `../../references/vocab-cli.md`、`../../references/data-formats.md`。保留 stdout、stderr 与退出码；不要用案件 `init` 代替词表生成。成功交付三件套路径、词表哈希、工具回执和未完成事项。错误需按 code/path 修正；人工意见有冲突或不能解释时向用户核实。工具不机械解析自然语言意见。
