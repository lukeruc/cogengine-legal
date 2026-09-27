# 预处理 CLI 用法

从完整交付目录运行：

```bash
python -m legal.preprocess_cli --input /path/original.pdf --output-dir /path/converted --converter-config /path/converter.json
```

三个参数必需。输出目录应不存在或为空。配置是严格 JSON：

```json
{"format_version":1,"argv":["/absolute/path/to/converter","--input","{input}","--output-dir","{output_dir}"]}
```

`argv[0]` 为实际外部程序的绝对路径。`{input}` 与 `{output_dir}` 各作为完整参数出现一次；程序直接接收参数，不经 shell。外部程序在临时目录根生成严格 UTF-8、无 BOM 的 `text.txt`，以及 `metadata.json`。元数据完整结构为 `{name,media_type,conversion_method,converter_version,anomalies}`；前四项为非空字符串，`anomalies` 是 `{code,message,start_offset?,end_offset?}` 数组，位置按文本字符计，两端同时存在且落在全文内。

成功回执：`{ok:true,input,output_dir,text,metadata,original_hash,text_hash,anomalies}`。路径为绝对路径，哈希为 SHA-256。转换器日志在 stderr，stdout 只保留 JSON 结果。转换失败报 `CONVERTER_FAILED`，产物错误报 `CONVERTER_OUTPUT_INVALID`，转换期间原件改变报 `ORIGINAL_CHANGED`；失败不发布成功产物。非空输出目录报 `FILE_EXISTS`，不覆盖已有文件。

案件入库时使用成功回执中的路径：

```bash
python -m legal.case_cli register --db /path/case.sqlite --original /path/original.pdf --text /path/converted/text.txt --metadata /path/converted/metadata.json
```

再次转换已有素材时，由调用方在用于登记的元数据中加 `material_id`；预处理本身不猜案件身份。初始化语料可直接记录转换回执与文件哈希，不因此建立案件库。
