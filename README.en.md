# cogengine-legal

[中文](README.md) · [English](README.en.md)

Current release: [v0.1.3](https://github.com/lukeruc/cogengine-legal/releases/tag/v0.1.3).

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
- **A working directory**: a location for contract data. Further work on the same contract uses the existing directory.

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
| [`legal-preprocess`](src/skills/legal-preprocess/SKILL.md) | Invoke a configured external converter to produce text and metadata ready for registration. |
| [`legal-case`](src/skills/legal-case/SKILL.md) | Organize ingestion, reading, and relationship extraction for one contract; submit results and carry out queries, reconciliation, and corrections. |
| [`legal-initialize`](src/skills/legal-initialize/SKILL.md) | Derive an initial vocabulary from designated materials and complete human review through comments in files. |
| [`legal-vocab`](src/skills/legal-vocab/SKILL.md) | Maintain and revise the vocabulary in response to gaps found in cases or requests from domain professionals. |

### Three CLIs

| Command | Purpose |
|---|---|
| `legal-preprocess` | Run the configured conversion process and check its outputs. |
| `legal-case` | Initialize a contract database, register materials, split clauses, write records, query, group, and reconcile. |
| `legal-vocab` | Create, inspect, modify, and compare vocabularies; aggregate vocabulary gaps found in cases. |

All four skills share the same CLIs. The three commands are installed in a dedicated Python environment. Installed skills use the installation information to invoke them, so the environment does not need to be activated manually for each use.

Installation creates independent copies of the CLIs, skills, reference materials, and registration verification script. The downloaded source can be removed after installation. Skills receive their operating instructions as part of the installation and do not require the project README at runtime.

## Example Vocabulary

The project provides an [example vocabulary](vocab/vocabulary.json) derived from 22 contract documents using this tool. It contains 14 units and 96 slots, illustrating the vocabulary structure and offering a starting point for adaptation. Check its suitability for your particular contract before use.

The example is included in the complete `v0.1.3` source at `vocab/vocabulary.json` and can also be [downloaded separately as JSON](https://raw.githubusercontent.com/lukeruc/cogengine-legal/v0.1.3/vocab/vocabulary.json). Copy the file to your vocabulary working directory and supply its absolute path when ingesting a contract.

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
- **Document conversion programs and their configuration**. Word, PDF, and OCR conversion is provided by external programs; supported file formats depend on the programs configured.

The core Python software has no third-party runtime dependencies. The agent host, model, and external converters must be supplied separately.

### 2. Install the Software and Register the Skills

Download and extract the complete source from the [v0.1.3 release page](https://github.com/lukeruc/cogengine-legal/releases/tag/v0.1.3). Replace the absolute paths below with paths on your machine; `SOURCE_ROOT` is the source root containing `src/`. Run the whole block in a single shell invocation, from any working directory:

```bash
SOURCE_ROOT="/absolute/path/to/cogengine-legal"
PYTHON_BIN="/absolute/path/to/python"
DIST_DIR="/absolute/path/to/legal-dist"
INSTALL_ROOT="/absolute/path/to/legal-install"

"$PYTHON_BIN" "$SOURCE_ROOT/src/scripts/build_release.py" --output-dir "$DIST_DIR" --python "$PYTHON_BIN"
"$PYTHON_BIN" "$SOURCE_ROOT/src/scripts/install_release.py" \
  --install-root "$INSTALL_ROOT" \
  --python "$PYTHON_BIN" \
  --wheel "$DIST_DIR/cogengine_legal-0.1.3-py3-none-any.whl"
```

The installer creates or reuses `.venv` under the installation root, installs the three commands, and copies the four skills and shared reference materials. Then register all four complete skill directories under `<install-root>/skills/` using your host's registration mechanism. Their entry paths must resolve to the installed files. Register the installed directories; `src/skills/` in the source tree has no installation information. Finally, run the registration check in [step 3 of the installation guide](src/README.md#第三步在宿主中注册四个-skill) and confirm that it returns `"host_registration":"verified"`.

`"host_registration":"pending"` in a successful installation receipt means that host registration still needs to be completed. See the [installation and usage guide](src/README.md) (in Chinese) for detailed steps, path binding, and troubleshooting.

### 3. Process Your First Contract

After registration, with the vocabulary and conversion configuration ready, give the agent a request such as the following, replacing the paths with actual file locations:

```text
Use legal-case to ingest the following materials as one contract:

Original contract: /absolute/path/to/contract.docx
Appendix: /absolute/path/to/appendix.pdf
Approved vocabulary: /absolute/path/to/vocabulary.json
DOCX conversion configuration: /absolute/path/to/docx-converter.json
PDF conversion configuration: /absolute/path/to/pdf-converter.json
Contract working root: /absolute/path/to/contracts

Return the contract working directory, database path, reconciliation results
for this run, and any unfinished work.
```

Following the skill, the agent creates the contract working directory, prepares the materials, organizes reading and extraction, and uses the CLI to validate and write the results. After handover, you can ask the agent to query a party's obligations, conditions, and supporting text. Developers can also call the CLI directly; query parameters are documented in the [case CLI reference](src/references/case-cli.md).

## Current Scope and Status

- **Scope**: record what one contract and its constituent documents stipulate. Actual performance, the legal validity of provisions, and analysis across contracts belong to downstream applications.
- **Version**: the current release is [v0.1.3](https://github.com/lukeruc/cogengine-legal/releases/tag/v0.1.3), an initial development release. The steps above build and install from that release's source.
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
| Look up commands and input/output formats | [Case CLI](src/references/case-cli.md) · [Vocabulary CLI](src/references/vocab-cli.md) · [Preprocessing CLI](src/references/preprocess-cli.md) · [Data formats](src/references/data-formats.md) |
| Browse public documentation | [Documentation index](docs/README.md) |

## License

This project is licensed under the [MIT License](LICENSE).
