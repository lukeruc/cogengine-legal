PRAGMA foreign_keys = ON;
PRAGMA journal_mode = DELETE;
CREATE TABLE case_info (
 singleton INTEGER NOT NULL PRIMARY KEY CHECK(singleton=1),
 case_id TEXT NOT NULL UNIQUE, contract_object_id TEXT NOT NULL UNIQUE,
 created_at TEXT NOT NULL, tool_version TEXT NOT NULL,
 schema_version INTEGER NOT NULL CHECK(schema_version=1),
 value_format_version INTEGER NOT NULL CHECK(value_format_version=1),
 code_version INTEGER NOT NULL CHECK(code_version=1),
 vocabulary_format_version INTEGER NOT NULL CHECK(vocabulary_format_version=1),
 vocabulary_hash TEXT NOT NULL, vocabulary_files_json TEXT NOT NULL,
 unit_config_json TEXT NOT NULL, unit_config_hash TEXT NOT NULL,
 FOREIGN KEY(contract_object_id) REFERENCES objects(object_id)
   DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE vocabulary_units (
 unit_id TEXT NOT NULL PRIMARY KEY, entry_json TEXT NOT NULL
);
CREATE TABLE vocabulary_slots (
 slot_id TEXT NOT NULL PRIMARY KEY, entry_json TEXT NOT NULL
);
CREATE TABLE vocabulary_assignments (
 unit_id TEXT NOT NULL REFERENCES vocabulary_units(unit_id),
 slot_id TEXT NOT NULL REFERENCES vocabulary_slots(slot_id),
 PRIMARY KEY(unit_id,slot_id)
);
CREATE TABLE submissions (
 submission_id TEXT NOT NULL PRIMARY KEY,
 sequence INTEGER NOT NULL UNIQUE CHECK(sequence>=1),
 content_hash TEXT NOT NULL UNIQUE, submitted_by TEXT NOT NULL,
 phase TEXT NOT NULL CHECK(phase IN
 ('init','register','split','preparation','tagging','extraction','correction')),
 input_json TEXT NOT NULL, receipt_json TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE objects (
 object_id TEXT NOT NULL PRIMARY KEY,
 kind TEXT NOT NULL CHECK(kind IN
 ('material','text_version','clause','anchor','node','relation','detail','reference','gap','no_content')),
 created_submission_id TEXT NOT NULL REFERENCES submissions(submission_id)
);
CREATE TABLE record_versions (
 record_id TEXT NOT NULL PRIMARY KEY,
 object_id TEXT NOT NULL REFERENCES objects(object_id),
 revision INTEGER NOT NULL CHECK(revision>=1),
 previous_record_id TEXT REFERENCES record_versions(record_id),
 submission_id TEXT NOT NULL REFERENCES submissions(submission_id),
 status TEXT NOT NULL CHECK(status IN ('active','withdrawn')),
 withdrawal_reason TEXT, data_json TEXT NOT NULL,
 UNIQUE(object_id,revision),
 CHECK((revision=1 AND previous_record_id IS NULL) OR
       (revision>1 AND previous_record_id IS NOT NULL)),
 CHECK((status='active' AND withdrawal_reason IS NULL) OR
       (status='withdrawn' AND revision>1 AND withdrawal_reason IS NOT NULL
        AND length(trim(withdrawal_reason))>0))
);
CREATE UNIQUE INDEX one_successor_per_record ON record_versions(previous_record_id)
 WHERE previous_record_id IS NOT NULL;
CREATE TABLE assertion_sources (
 record_id TEXT NOT NULL REFERENCES record_versions(record_id),
 path TEXT NOT NULL, level INTEGER NOT NULL CHECK(level IN (1,2,3)),
 source_json TEXT NOT NULL, PRIMARY KEY(record_id,path)
);
CREATE TABLE record_links (
 record_id TEXT NOT NULL REFERENCES record_versions(record_id),
 path TEXT NOT NULL,
 target_object_id TEXT REFERENCES objects(object_id),
 target_record_id TEXT REFERENCES record_versions(record_id),
 PRIMARY KEY(record_id,path),
 CHECK((target_object_id IS NULL) != (target_record_id IS NULL))
);
CREATE TABLE materials (
 record_id TEXT NOT NULL PRIMARY KEY REFERENCES record_versions(record_id),
 name TEXT NOT NULL, media_type TEXT NOT NULL, content_hash TEXT NOT NULL,
 registered_order INTEGER NOT NULL UNIQUE CHECK(registered_order>=1),
 original_bytes BLOB NOT NULL, original_path TEXT
);
CREATE TABLE text_versions (
 record_id TEXT NOT NULL PRIMARY KEY REFERENCES record_versions(record_id),
 material_id TEXT NOT NULL REFERENCES objects(object_id),
 version_number INTEGER NOT NULL CHECK(version_number>=1),
 conversion_method TEXT NOT NULL, converter_version TEXT NOT NULL,
 text TEXT NOT NULL, text_hash TEXT NOT NULL, anomalies_json TEXT NOT NULL,
 UNIQUE(material_id,version_number)
);
CREATE TABLE clauses (
 record_id TEXT NOT NULL PRIMARY KEY REFERENCES record_versions(record_id),
 text_version_id TEXT NOT NULL REFERENCES objects(object_id),
 sequence INTEGER NOT NULL CHECK(sequence>=1),
 original_number TEXT, text TEXT NOT NULL,
 start_offset INTEGER NOT NULL CHECK(start_offset>=0),
 end_offset INTEGER NOT NULL CHECK(end_offset>=start_offset),
 tags_json TEXT NOT NULL,
 classification TEXT NOT NULL CHECK(classification IN
 ('unclassified','ordinary','no_content','unmatched'))
);
CREATE TABLE anchors (
 record_id TEXT NOT NULL PRIMARY KEY REFERENCES record_versions(record_id),
 clause_record_id TEXT NOT NULL REFERENCES record_versions(record_id),
 quote TEXT NOT NULL CHECK(length(CAST(quote AS BLOB))>0),
 occurrence INTEGER NOT NULL CHECK(occurrence>=1),
 start_offset INTEGER NOT NULL CHECK(start_offset>=0),
 end_offset INTEGER NOT NULL CHECK(end_offset>start_offset)
);
CREATE TABLE nodes (
 record_id TEXT NOT NULL PRIMARY KEY REFERENCES record_versions(record_id),
 node_kind TEXT NOT NULL CHECK(node_kind IN
 ('subject','event','defined_value','external_benchmark','contract')),
 name TEXT
);
CREATE TABLE relations (
 record_id TEXT NOT NULL PRIMARY KEY REFERENCES record_versions(record_id),
 relation_kind TEXT NOT NULL CHECK(relation_kind IN ('party','contract')),
 unit_id TEXT NOT NULL REFERENCES vocabulary_units(unit_id),
 party_0_id TEXT REFERENCES objects(object_id),
 party_1_id TEXT REFERENCES objects(object_id),
 contract_id TEXT REFERENCES objects(object_id),
 modality TEXT CHECK(modality IN ('obligation','power','permission','immunity')),
 CHECK((relation_kind='party' AND party_0_id IS NOT NULL AND party_1_id IS NOT NULL
        AND party_0_id!=party_1_id AND contract_id IS NULL) OR
       (relation_kind='contract' AND party_0_id IS NULL AND party_1_id IS NULL
        AND contract_id IS NOT NULL))
);
CREATE TABLE details (
 record_id TEXT NOT NULL PRIMARY KEY REFERENCES record_versions(record_id),
 owner_id TEXT NOT NULL REFERENCES objects(object_id),
 slot_id TEXT NOT NULL REFERENCES vocabulary_slots(slot_id),
 value_json TEXT NOT NULL
);
CREATE TABLE references_data (
 record_id TEXT NOT NULL PRIMARY KEY REFERENCES record_versions(record_id),
 reference_kind TEXT NOT NULL CHECK(reference_kind IN
 ('appellation','role','composition','definition','event_of','scope','priority','amendment','redirect','distinct')),
 from_json TEXT NOT NULL, to_json TEXT NOT NULL
);
CREATE TABLE gaps (
 record_id TEXT NOT NULL PRIMARY KEY REFERENCES record_versions(record_id),
 clause_record_id TEXT NOT NULL REFERENCES record_versions(record_id),
 gap_kind TEXT NOT NULL CHECK(gap_kind IN ('unmatched_unit','missing_slot','structure_anomaly')),
 description TEXT NOT NULL, reported_by TEXT NOT NULL
);
CREATE TABLE no_content_records (
 record_id TEXT NOT NULL PRIMARY KEY REFERENCES record_versions(record_id),
 clause_id TEXT NOT NULL REFERENCES objects(object_id), reason TEXT NOT NULL
);
CREATE TABLE case_overviews (
 overview_id TEXT NOT NULL PRIMARY KEY,
 submission_id TEXT NOT NULL UNIQUE REFERENCES submissions(submission_id),
 text_versions_json TEXT NOT NULL, body TEXT NOT NULL, authored_by TEXT NOT NULL
);
CREATE TABLE extraction_completions (
 submission_id TEXT NOT NULL REFERENCES submissions(submission_id),
 clause_id TEXT NOT NULL REFERENCES objects(object_id),
 clause_record_id TEXT NOT NULL REFERENCES record_versions(record_id),
 PRIMARY KEY(submission_id,clause_id)
);
CREATE TABLE reconciliation_reports (
 report_id TEXT NOT NULL PRIMARY KEY,
 checked_sequence INTEGER NOT NULL REFERENCES submissions(sequence),
 scope_json TEXT NOT NULL, rule_version TEXT NOT NULL,
 result_json TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX record_submission ON record_versions(submission_id);
CREATE INDEX sources_level ON assertion_sources(level,record_id);
CREATE INDEX links_object ON record_links(target_object_id);
CREATE INDEX links_record ON record_links(target_record_id);
CREATE INDEX clauses_address ON clauses(text_version_id,sequence);
CREATE INDEX anchor_clause ON anchors(clause_record_id);
CREATE INDEX node_kind ON nodes(node_kind);
CREATE INDEX relation_unit ON relations(unit_id);
CREATE INDEX relation_party_0 ON relations(party_0_id);
CREATE INDEX relation_party_1 ON relations(party_1_id);
CREATE INDEX detail_owner_slot ON details(owner_id,slot_id);
CREATE INDEX reference_type ON references_data(reference_kind);
CREATE INDEX gap_type_clause ON gaps(gap_kind,clause_record_id);
CREATE INDEX completion_clause ON extraction_completions(clause_id);
CREATE VIEW current_records AS
 SELECT r.* FROM record_versions r WHERE NOT EXISTS
 (SELECT 1 FROM record_versions n WHERE n.object_id=r.object_id AND n.revision>r.revision);
CREATE VIEW active_records AS
 SELECT * FROM current_records WHERE status='active';
