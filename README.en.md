# cogengine-legal

[中文](README.md) · [English](README.en.md)

Current release: [v0.1.5](https://github.com/lukeruc/cogengine-legal/releases/tag/v0.1.5).

**Infrastructure for working with legal relationship information.** The project currently focuses on contracts. It organizes contractual rights and obligations, conditions, restrictions, and their connections into structured records linked to the original text, for querying, verification, and use in downstream applications.

The main output is a SQLite contract database containing the original files, full text, relationship records, source references, and revision history. The aim is to make reading the database equivalent to reading the contract: users should be able to retrieve what the contract stipulates and check each record against its source.

## The Problem This Project Addresses

When an agent handles contract work, one correct result does not establish that the same method can be used reliably over time in production. Organizing context can help the agent read and understand the material, but the results still need checking, and omissions and misunderstandings need to be located and corrected.

This project has agents extract legal relationships using shared recording conventions, while software validates and stores the results. Contract content, source references, and correction history become records that can be maintained and reused across tasks. Applications such as contract review, performance management, and dispute analysis can add their own rules, facts, and judgments on top of these records.

For a fuller explanation, see [An Engineering Approach to Representing Legal Relationships](docs/legal-relations-engineering.en.md).

## Inputs and Outputs

### What You Provide

- **Contract materials**: one contract and its constituent documents, such as the main agreement, appendices, and supplemental agreements.
- **A reviewed vocabulary**: the categories of legal relationships, the information to record, and the conventions for expressing it. Users can prepare the vocabulary themselves or derive and review it using this project's initialization skill.
- **Conversion configuration**: when working with Word documents, PDFs, or scans, an explicitly selected conversion program and instructions for invoking it.
- **Workspace configuration**: register a contract output root and available vocabularies for the directory opened in the agent session. New cases use these defaults, with explicit overrides for the current task. Further work on the same contract uses its existing directory.

### What You Receive

| Output | Contents and Purpose |
|---|---|
| Contract database, `contract.sqlite` | Original files, full text, the vocabulary used for the case, parties and legal relationships, detailed conditions and values, source references, and revision history. Supports querying, verification, and transfer as a whole. |
| Contract working directory | Working copies of inputs, converted text, reading notes, extraction files, tool receipts, and reports, for resuming work and investigating problems. |
| Handover for the current run | The database location, processing scope, reconciliation results, unfinished work, and limitations in the materials or what the model can represent. |

Each new contract's data is kept under `contract-YYYYMMDDTHHMMSSZ[-NN]/` within the specified working root, with the database at the root of that contract directory. The software installation directory and contract working directories are separate.

## A Short Example

Consider this illustrative provision:

> Party A is the buyer and Party B is the seller. The total contract price is RMB 1 million. The buyer shall pay the seller 20% of the total contract price within 30 days after successful acceptance.

This arrangement can be represented as a set of connected records:

| Information | Illustrative Record |
|---|---|
| Parties | Party A is the buyer; Party B is the seller. |
| Payment relationship | The buyer owes the payment; the seller receives it. |
| Basis for the amount | The total contract price is RMB 1 million; this payment is calculated as 20% of that price. |
| Payment deadline | Within 30 days after successful acceptance. |
| Source references | Party designations, the total price, the payment, and its trigger each link to the sentences supporting them. |

A query for this payment obligation can retrieve the amount, its calculation basis, and the deadline, with source references for verification. The records preserve the meaning of “total contract price × 20%” and “within 30 days after successful acceptance.” Recording the acceptance condition does not mean that acceptance has actually occurred.

## Included Tools

The project includes four skills for agents and three command-line tools for carrying out operations. Skills describe how to organize tasks, read materials, and hand over results; the CLIs validate, store, and query data.

### Four Skills

| Skill | Purpose |
|---|---|
| [`legal-preprocess`](src/skills/legal-preprocess/SKILL.md) | Receive Markdown/TXT directly, or invoke an explicitly configured converter to produce text and metadata. |
| [`legal-case`](src/skills/legal-case/SKILL.md) | Organize ingestion, reading, and relationship extraction for one contract; submit results and carry out queries, reconciliation, and corrections. |
| [`legal-initialize`](src/skills/legal-initialize/SKILL.md) | Derive an initial vocabulary from designated materials and complete human review through comments in files. |
| [`legal-vocab`](src/skills/legal-vocab/SKILL.md) | Maintain and revise the vocabulary in response to gaps found in cases or requests from domain professionals. |

### Three CLIs

| Command | Purpose |
|---|---|
| `legal-preprocess` | Receive plain text or run an explicit conversion configuration, then check the outputs. |
| `legal-case` | Initialize a contract database, register materials, split clauses, write records, query, group, and reconcile. |
| `legal-vocab` | Create, inspect, modify, and compare vocabularies; aggregate vocabulary gaps found in cases. |

All four skills share the same CLIs. The three commands are installed in a dedicated Python environment. Installed skills use the installation information to invoke them, so the environment does not need to be activated manually for each use.

Installation creates independent copies of the CLIs, skills, reference materials, and registration verification script. The downloaded source can be removed after installation. Skills receive their operating instructions as part of the installation and do not require the project README at runtime.

## Example Vocabulary

The project provides an [example vocabulary](vocab/vocabulary.json) derived from 22 contract documents using this tool. It contains 14 units and 96 slots, illustrating the vocabulary structure and offering a starting point for adaptation. Check its suitability for your particular contract before use.

The example is included in the complete `v0.1.5` source at `vocab/vocabulary.json` and can also be [downloaded separately as JSON](https://raw.githubusercontent.com/lukeruc/cogengine-legal/v0.1.5/vocab/vocabulary.json). Save it in your vocabulary working directory, then register it in the workspace's vocabulary list as described below. The installer does not automatically make this example the default.

## Getting Started

### Recommended: Ask an Agent to Install It

Copy the following prompt to your agent:

```text
Please install and configure cogengine-legal for me. Project URL: https://github.com/lukeruc/cogengine-legal. First read the project README and the installation guide it links to, then follow the documentation to complete the installation and configuration.
```

### 1. Prepare the Prerequisites

- **Python 3.11, 3.12, or 3.13**, with `sqlite3`, `venv`, and pip. Building also requires `setuptools>=68` and `wheel`.
- **An agent host that can run skills**: it must be able to read complete skill directories and their referenced files, run local commands, organize subtasks, and receive human feedback through files.
- **An appropriate, approved vocabulary**. A vocabulary is required before contract ingestion. If none is available, use `legal-initialize` to derive and review one after installation and skill registration. The user assigns materials to vocabulary induction or acceptance testing.
- **Conversion programs and configuration when needed**. Word, PDF, and OCR conversion is provided by external programs; supported file formats depend on the programs configured.

The core Python software has no third-party runtime dependencies. The agent host, model, and external converters must be supplied separately.

UTF-8 files without a BOM can be processed directly when their extension is `.md`, `.markdown`, or `.txt` (case insensitive). DOCX files, PDFs, and scans require an explicitly configured converter; the agent reports missing configuration. An explicit conversion configuration takes priority when provided. Installing this project does not install converters.

### 2. Install the Software and Register the Skills

Download and extract the complete source from the [v0.1.5 release page](https://github.com/lukeruc/cogengine-legal/releases/tag/v0.1.5). Replace the absolute paths below with paths on your machine; `SOURCE_ROOT` is the source root containing `src/`. Run the whole block in a single shell invocation, from any working directory:

```bash
SOURCE_ROOT="/absolute/path/to/cogengine-legal"
PYTHON_BIN="/absolute/path/to/python"
DIST_DIR="/absolute/path/to/legal-dist"
INSTALL_ROOT="/absolute/path/to/legal-install"

"$PYTHON_BIN" "$SOURCE_ROOT/src/scripts/build_release.py" --output-dir "$DIST_DIR" --python "$PYTHON_BIN"
"$PYTHON_BIN" "$SOURCE_ROOT/src/scripts/install_release.py" \
  --install-root "$INSTALL_ROOT" \
  --python "$PYTHON_BIN" \
  --wheel "$DIST_DIR/cogengine_legal-0.1.5-py3-none-any.whl"
```

The installer creates or reuses `.venv` under the installation root, installs the three commands, and copies the four skills and shared reference materials. Then register all four complete skill directories under `<install-root>/skills/` using your host's registration mechanism. Their entry paths must resolve to the installed files. Register the installed directories; `src/skills/` in the source tree has no installation information. Finally, run the registration check in [step 3 of the installation guide](src/README.md#第三步在宿主中注册四个-skill) and confirm that it returns `"host_registration":"verified"`.

`"host_registration":"pending"` in a successful installation receipt means that host registration still needs to be completed. See the [installation and usage guide](src/README.md) (in Chinese) for detailed steps, path binding, and troubleshooting.

### 3. Configure the Workspace and Default Vocabulary

**The workspace is the directory opened in the agent session.** It may differ from the locations of the original contract, the installation, and the contract outputs. Changing the shell directory during a task does not change the workspace.

The installer creates an empty configuration in `<install-root>/workspaces.json`. Before creating the first case, register the workspace, its contract output root, and its vocabulary path list. You can ask the agent to do this:

```text
Configure cogengine-legal for the workspace opened in this session:
Installation directory: /absolute/path/to/legal-install
Contract output root: /absolute/path/to/contracts
Register /absolute/path/to/vocabularies/construction-v1.json as the default vocabulary.
Preserve any existing registrations for other workspaces and vocabularies.
```

Each workspace uses a UTF-8 plain-text list under `<install-root>/vocabularies/`, referenced by `workspaces.json`. For example, `vocabularies/workspace-1.txt`:

```text
/absolute/path/to/vocabularies/construction-v1.json
/absolute/path/to/vocabularies/supply-v1.json
```

**Use one absolute vocabulary file path per line. The first nonblank line is the default.** The vocabulary files can live outside the installation directory; the list only records their paths. Edit it directly or explicitly ask the agent to make a change:

| Action | Method and Effect |
|---|---|
| Register another vocabulary | Append its absolute path. The first entry in an empty list becomes the default. |
| Change the default | Move the desired path to the first nonblank line. |
| Use another vocabulary for one task | Specify an already registered absolute path in the ingestion request. The list order stays unchanged. |
| Remove a registration | Delete its line; the vocabulary file remains. Removing the default makes the next entry the default. |
| Revise and use a vocabulary | `legal-vocab` creates a separate file and preserves the original. Explicitly request registration of the new file, and a change of default if wanted. |

Do not include comments, quotes, relative paths, `~`, environment variables, or duplicate paths. Unregistered files are not selected automatically. An invalid default produces an error rather than silently selecting the next entry.

**New cases copy and freeze the selected vocabulary. Existing cases keep their frozen version.** Changing the default does not change existing cases; software upgrades preserve workspace configuration and vocabulary lists. If you do not yet have a vocabulary, use `legal-initialize` to create and review one, then register it. See [installation step 4](src/README.md#第四步配置工作区与默认词表) for the complete configuration example (in Chinese).

### 4. Process Your First Contract

Once configured, a request usually only needs to identify the contract materials:

```text
Use legal-case to create a new case for /absolute/path/to/contract.md,
using this workspace's default vocabulary and contract output root.
Return the contract working directory, database path, reconciliation results
for this run, and any unfinished work.
```

List any appendices or supplemental agreements as well, and supply the appropriate conversion configuration for DOCX/PDF materials. To override a default for this task, provide the absolute path of a registered vocabulary or a different contract output root. To resume an existing case, provide its original contract working directory.

Following the skill, the agent creates the contract working directory, prepares the materials, organizes reading and extraction, and uses the CLI to validate and write the results. After handover, you can ask the agent to query a party's obligations, conditions, and supporting text. Developers can also call the CLI directly; query parameters are documented in the [case CLI reference](src/references/case-cli.md).

## Current Scope and Status

- **Scope**: record what one contract and its constituent documents stipulate. Actual performance, the legal validity of provisions, and analysis across contracts belong to downstream applications.
- **Version**: the current release is [v0.1.5](https://github.com/lukeruc/cogengine-legal/releases/tag/v0.1.5), an initial development release. The steps above build and install from that release's source.
- **Implementation**: four skills, three CLIs, and installation and registration verification scripts are available. [Automated tests](src/tests/) are maintained alongside the source.
- **Quality limits**: software can check explicit constraints such as formats, references, source anchors, and clause coverage. Passing validation does not prove that the contract's meaning has been represented completely and accurately; extraction quality must be assessed against the particular contract.
- **Vocabulary and materials**: vocabulary coverage, original document quality, and model performance all affect the result. Information that cannot be represented, or lacks sufficient supporting material, must be identified at handover. Finding no record does not establish that the contract contains no such provision.

## Documentation

The project essays are available in both languages. The installation guide, skills, and technical references linked below are currently in Chinese.

| Reading Goal | Document |
|---|---|
| Understand the project's ideas and technical approach | [An Engineering Approach to Representing Legal Relationships](docs/legal-relations-engineering.en.md) · [中文](docs/legal-relations-engineering.md) |
| Understand the project from a legal practitioner's perspective | [An Engineering Approach to Representing Legal Relationships (Lawyers' Edition)](docs/legal-relations-engineering-for-lawyers.en.md) · [中文](docs/legal-relations-engineering-for-lawyers.md) |
| Install, register, upgrade, and troubleshoot | [Installation and usage guide](src/README.md) |
| Manage workspaces and default vocabularies | [Configuration and path list examples](src/README.md#第四步配置工作区与默认词表) |
| Look up commands and input/output formats | [Case CLI](src/references/case-cli.md) · [Vocabulary CLI](src/references/vocab-cli.md) · [Preprocessing CLI](src/references/preprocess-cli.md) · [Data formats](src/references/data-formats.md) |
| Browse public documentation | [Documentation index](docs/README.md) |

## License

This project is licensed under the [MIT License](LICENSE).
