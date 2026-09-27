---
name: legal-preprocess
description: 将一份合同原件经显式配置的转换程序转成可登记的原样文本与元数据；适用于文件转换。
---

# 预处理

## 输入

原件路径、空输出目录路径、转换配置 JSON 路径。先从本文件真实目录读取 `../../README.md` 和 `../../references/preprocess-cli.md`。调用方应明确转换器及支持的文件格式；本 skill 不从文件扩展名猜工具。

## 步骤

1. 核实原件、输出目录及配置路径。需大量阅读转换质量时可将材料交读手，记录异常。
2. 从完整交付目录运行 `python -m legal.preprocess_cli --input FILE --output-dir DIR --converter-config FILE`。
3. 读取 stdout 的 JSON 回执，核对绝对路径、原件哈希、文本哈希和异常；把完整回执交给案件或初始化 skill。

## 工具用法与继续条件

配置是 `{format_version:1,argv:["/absolute/converter",...,"{input}",...,"{output_dir}"]}`。转换器在临时输出目录写 `text.txt` 和 `metadata.json`，统一入口检查格式、字符位置和原件未改动。成功退出 0；参数/产物错误退出 2，文件或进程故障退出 3。失败回执含 `errors[].code/path/message`，不得把残留文件作为成功产物。`FILE_EXISTS` 时选新的空目录；转换失败或质量妨碍阅读时按调用方既有异常处理要求改进源件。预处理不切条款，不判断法律关系。
