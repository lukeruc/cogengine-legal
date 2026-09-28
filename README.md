# cogengine-legal

面向单份合同的法律关系建模底座。程序将合同原文、结构化权利义务记录和溯源锚保存在 SQLite 中。当前发行版本为 `0.1.0`。

仓库的 `src/` 是完整交付源码目录。三个命令共用一个专用 Python 环境，四个 skill 共用这些命令。合同原件、词表工作副本和建模产物另存于合同工作目录。

## 快速安装

准备带 `sqlite3`、`venv`、pip 的 Python 3.11、3.12 或 3.13。构建 wheel 还需要 `setuptools>=68` 和 `wheel`。在仓库根目录执行以下命令，并把示例绝对路径改为本机路径：

```bash
cd src
PYTHON_BIN=/absolute/path/to/python
DIST_DIR=/absolute/path/to/legal-dist
INSTALL_ROOT=/absolute/path/to/legal-install

"$PYTHON_BIN" scripts/build_release.py --output-dir "$DIST_DIR" --python "$PYTHON_BIN"
"$PYTHON_BIN" scripts/install_release.py \
  --install-root "$INSTALL_ROOT" \
  --python "$PYTHON_BIN" \
  --wheel "$DIST_DIR/cogengine_legal-0.1.0-py3-none-any.whl"
```

安装脚本创建或复用 `<install-root>/.venv`，核对三个命令和运行资源，并生成 `<install-root>/runtime.json`。成功回执中的 `"host_registration":"pending"` 表示程序已安装，还需按宿主现有机制注册安装根 `skills/` 下的四个完整 skill 目录：`legal-case`、`legal-vocab`、`legal-preprocess`、`legal-initialize`。只复制单个 `SKILL.md` 不构成完整安装。

注册后可用[注册核对脚本](src/scripts/verify_registration.py)检查宿主实际看到的四个 `SKILL.md` 路径和命令。完整的安装前检查、注册核对示例、命令绑定、重装与故障处理见[详细安装说明](src/README.md)。

安装后的 skill 从 `runtime.json` 取得命令的绝对路径，不需要手动激活环境或设置 `PYTHONPATH`。合同数据保存在调用方指定工作根下的 `contract-YYYYMMDDTHHMMSSZ[-NN]/`，数据库为其中的 `contract.sqlite`；安装目录与合同目录分开。DOCX、PDF、OCR 的实际转换程序需另行显式配置。
