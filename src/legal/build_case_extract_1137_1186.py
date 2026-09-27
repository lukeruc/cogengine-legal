"""Build the reviewed extraction payload for clauses 1137–1186 of this test case."""

import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "work/case-onshore-2025-01-08"
DB = sqlite3.connect(ROOT / "case.sqlite")
DB.row_factory = sqlite3.Row
V = json.loads((Path(__file__).resolve().parents[2] / "work/vocab-init-2026-09-27/vocabulary.json").read_text())
UID = {x["name"]: x["id"] for x in V["units"]}
SID = {x["name"]: x["id"] for x in V["slots"]}
ROWS = {x["sequence"]: dict(x) for x in DB.execute("SELECT c.sequence,c.record_id,r.object_id,c.classification,c.text FROM clauses c JOIN active_records r ON r.record_id=c.record_id WHERE c.sequence BETWEEN 1137 AND 1186")}
EMP = "bbf0778f-95de-4857-b2b1-e5bc9f18390b"
CON = "0f58295a-5784-4bce-a035-02eb9606f6e4"
CONTRACT = "74a42a47-bae1-406f-a843-a0d82d564007"
HASH = "e8d6063ea96af9ff87fe2a2dbe8e55ba76a92ccc638a78b96fc21578600df80e"
CASE = "d928a7a3-773a-4b03-8377-97ecdc7de98d"


class Batch:
    def __init__(self, name, sequences):
        self.name = name
        self.sequences = sequences
        self.records = []
        self.issues = []
        for n in sequences:
            row = ROWS[n]
            assert row["classification"] == "ordinary", (n, row["classification"])
            self.records.append({"local_id": f"{name}_anchor_{n}", "kind": "anchor", "data": {"clause": {"record_id": row["record_id"]}, "quote": row["text"]}, "evidence": []})

    def a(self, n):
        return {"local_id": f"{self.name}_anchor_{n}"}

    def ev(self, *ns):
        return [{"path": "", "source": {"level": 1, "anchors": [self.a(n) for n in ns]}}]

    def rel(self, key, ns, unit, actor, target, nature1="obligor", nature2="recipient", modality="obligation"):
        local = f"{self.name}_relation_{key}"
        self.records.append({"local_id": local, "kind": "relation", "data": {"relation_kind": "party", "unit_id": UID[unit], "parties": [{"subject": {"object_id": actor}, "nature": nature1}, {"subject": {"object_id": target}, "nature": nature2}], "modality": modality}, "evidence": self.ev(*ns)})
        return local

    def contract_rel(self, key, ns, unit, modality=None):
        local = f"{self.name}_relation_{key}"
        self.records.append({"local_id": local, "kind": "relation", "data": {"relation_kind": "contract", "unit_id": UID[unit], "subject": {"object_id": CONTRACT}, "modality": modality}, "evidence": self.ev(*ns)})
        return local

    def detail(self, key, owner, ns, slot, text):
        self.records.append({"local_id": f"{self.name}_detail_{key}", "kind": "detail", "data": {"owner": {"local_id": owner}, "slot_id": SID[slot], "value": {"form": "text", "surface": text}}, "evidence": self.ev(*ns)})

    def gap(self, key, n, kind, description):
        self.records.append({"local_id": f"{self.name}_gap_{key}", "kind": "gap", "data": {"clause": {"record_id": ROWS[n]["record_id"]}, "gap_kind": kind, "description": description, "reported_by": "Codex: clauses 1137–1186 extraction"}, "evidence": self.ev(n)})

    def save(self):
        obj = {"format_version": 1, "case_id": CASE, "vocabulary_hash": HASH, "submitted_by": "Codex: clauses 1137–1186 extraction", "phase": "extraction", "covered_clauses": [{"object_id": ROWS[n]["object_id"], "record_id": ROWS[n]["record_id"]} for n in self.sequences], "records": self.records, "issues": self.issues}
        path = ROOT / f"extraction-middle-{self.name}.json"
        path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")
        print(path, len(self.sequences), len(self.records))


A = Batch("payments_1137_1167", [1137,1138,1140,1143,1144,1146,1147,1149,1150,1151,1152,1153,1154,1155,1156,1160,1163,1164,1165,1166,1167])
r=A.rel("1137_performance_ld",[1137],"责任与违约救济",CON,EMP)
A.detail("1137_ld",r,[1137],"责任与救济方式","compensate and pay the Employer the Performance LDs")
A.detail("1137_cap",r,[1137],"责任与救济方式","subject to the Performance LDs Cap")
A.detail("1137_calculation",r,[1137],"责任与救济方式","as calculated in accordance with [Schedule \\[•\\] (Performance Guarantee and Tests)]{.mark}")
A.gap("1137_cap",1137,"missing_slot","履约违约金依据未附的附表计算，且受履约违约金上限约束；当前词表没有计算式与上限结构槽，附表具体数值不可从现有正文恢复。")
r=A.rel("1138_exclusive",[1138],"责任与违约救济",CON,EMP,"protected_party","restricted_party","immunity")
A.detail("1138_only",r,[1138],"责任与救济方式","the only damages payable to the Employer in case the Contractor has failed to meet the Performance Guarantees")
r=A.rel("1140_aggregate_cap",[1140],"责任与违约救济",CON,EMP,"protected_party","restricted_party","immunity")
A.detail("1140_cap",r,[1140],"责任与救济方式","aggregate liability of Delay LDs under Clause 8.7 and Performance LDs of the Contractor be more than 17% of the Contract Price")
A.gap("1140_formula",1140,"missing_slot","迟延违约金与履约违约金合计不得超过合同价 17%；数额槽仅接受固定量，缺少按合同价百分比计算的上限槽。")
r=A.rel("1143_initiate",[1143],"变更",EMP,CON,"power_holder","power_subject","power")
A.detail("1143_means",r,[1143],"变更程序","either by an instruction or by a request for the Contractor to submit a proposal")
A.detail("1143_deadline",r,[1143],"变更程序","at any time prior to issuing the Taking-Over Certificate for the Works or a Section")
r=A.contract_rel("1143_omission",[1143],"变更")
A.detail("1143_exclusion",r,[1143],"变更事项","A Variation shall not comprise the omission of any work which is to be carried out by others")
r=A.rel("1144_execute",[1144],"变更",CON,EMP)
A.detail("1144_execute",r,[1144],"变更程序","execute and be bound by each Variation, unless the Contractor promptly gives notice")
A.detail("1144_exceptions",r,[1144],"变更程序","cannot readily obtain the Goods required for the Variation; reduce the safety or suitability of the Works; adverse impact on the achievement of the Performance Guarantees")
r=A.rel("1144_notice",[1144],"通知与信息提供",CON,EMP)
A.detail("1144_notice",r,[1144],"应通知或提供的信息","notice to the Employer stating (with supporting particulars) that (i) the Contractor cannot readily obtain the Goods required for the Variation, (ii) it will reduce the safety or suitability of the Works, or (iii) it will have an adverse impact on the achievement of the Performance Guarantees")
A.detail("1144_prompt",r,[1144],"通知方式","promptly")
r=A.rel("1144_employer_response",[1144],"变更",EMP,CON)
A.detail("1144_response",r,[1144],"变更程序","Upon receiving this notice, the Employer shall cancel, confirm or vary the instruction")
r=A.rel("1146_value_engineering",[1146],"变更",CON,EMP,"permission_holder","permission_counterparty","permission")
A.detail("1146_proposal",r,[1146],"变更程序","at any time, submit to the Employer a written proposal")
A.detail("1146_benefits",r,[1146],"变更事项","accelerate completion; reduce the cost to the Employer of executing, maintaining or operating the Works; improve the efficiency or value to the Employer of the completed Works; otherwise be of benefit to the Employer")
r=A.contract_rel("1147_cost",[1147],"付款")
A.detail("1147_cost",r,[1147],"付款安排","The proposal shall be prepared at the cost of the Contractor")
r=A.rel("1147_contents",[1147],"通知与信息提供",CON,EMP)
A.detail("1147_contents",r,[1147],"应通知或提供的信息","items listed in Clause 13.3 \\[Variation Procedure\\]")
r=A.rel("1149_response",[1149,1150,1151,1152],"通知与信息提供",CON,EMP)
A.detail("1149_time",r,[1149],"通知方式","in writing as soon as practicable")
A.detail("1149_alternatives",r,[1149],"应通知或提供的信息","either by giving reasons why he cannot comply (if this is the case) or by submitting")
for n,key,txt in [(1150,"design","a description of the proposed design and/or work to be performed and a programme for its execution"),(1151,"programme","proposal for any necessary modifications to the programme according to Clause 8.3 \\[Programme\\] and to the Time for Completion"),(1152,"price","proposal for adjustment to the Contractor Price")]:
    A.detail(f"{n}_{key}",r,[1149,n],"应通知或提供的信息",txt)
r=A.rel("1153_reply",[1153],"通知与信息提供",EMP,CON)
A.detail("1153_reply",r,[1153],"应通知或提供的信息","respond with approval, disapproval or comments")
A.detail("1153_timing",r,[1153],"通知方式","as soon as practicable after receiving such proposal")
r=A.rel("1153_continue",[1153],"工作或服务提供",CON,EMP)
A.detail("1153_continue",r,[1153],"工作或服务内容","shall not delay any work whilst awaiting a response")
r=A.rel("1154_instruction",[1154],"变更",EMP,CON)
A.detail("1154_issue",r,[1154],"变更程序","Each instruction to execute a Variation, with any requirements for the recording of Costs, shall be issued by the Employer to the Contractor")
r=A.rel("1154_ack",[1154],"通知与信息提供",CON,EMP)
A.detail("1154_ack",r,[1154],"应通知或提供的信息","acknowledge receipt")
r=A.rel("1155_determine",[1155,1156],"变更",EMP,CON)
A.detail("1155_price",r,[1155],"变更事项","adjustments to the Contract Price and the Schedule of Payments")
A.detail("1155_process",r,[1155],"变更程序","proceed in accordance with Clause 3.5 \\[Determinations\\] to agree or determine")
A.detail("1155_cost_profit",r,[1155],"变更程序","include Cost Plus Profit as a result of executing such Variation")
A.detail("1156_value_engineering",r,[1155,1156],"变更程序","take account of the Contractor's submissions under Clause 13.2 \\[Value Engineering\\] if applicable")
A.gap("1155_formula",1155,"missing_slot","变更调整须纳入 Cost Plus Profit，但当前词表没有该成本加利润的结构化计算槽。")
r=A.rel("1160_determine",[1160],"变更",EMP,CON,"power_holder","power_subject","power")
A.detail("1160_sums",r,[1160],"变更事项","amount of provisional sums, which is not included in the Contract Price")
r=A.rel("1160_agreement",[1160],"变更",CON,EMP)
A.detail("1160_supplement",r,[1160],"变更程序","The Parties shall enter into a supplementary agreement on the details of the provisional sums within four (4) months from the date on which the Construction Contract is signed by the Parties")
A.gap("1160_joint",1160,"missing_slot","双方共同签署补充协议的共同义务与签约后四个月期限只能以程序文本保留；现有变更单元缺专用期限槽。")
r=A.contract_rel("1163_law_change",[1163],"变更","permission")
A.detail("1163_price",r,[1163],"变更事项","Contract Price may be adjusted to take account of any increase or decrease in Cost resulting from a change in the Laws of the Country")
A.detail("1163_scope",r,[1163],"变更程序","introduction of new Laws and the repeal or modification of existing Laws, or in the judicial or official governmental interpretation of such Laws, made after the Base Date, which affect the Contractor in the performance of obligations under the Contract")
r=A.rel("1164_notice",[1164],"通知与信息提供",CON,EMP)
A.detail("1164_notice",r,[1164],"应通知或提供的信息","delay and/or additional Cost as a result of changes in the Laws or in such interpretations, made after the Base Date")
r=A.rel("1165_time",[1164,1165],"变更",CON,EMP,"power_holder","power_subject","power")
A.detail("1165_extension",r,[1165],"变更事项","an extension of time for any such delay, if completion is or will be delayed, under Sub-Clause 8.4 \\[Extension of Time for Completion\\]")
A.detail("1165_claim",r,[1164],"变更程序","subject to Sub-Clause 20.1 \\[Contractor's Claims\\]")
r=A.rel("1166_cost",[1164,1166],"付款",EMP,CON)
A.detail("1166_pay",r,[1166],"付款安排","payment of any such Cost, which shall be added to the Contract Price")
A.detail("1166_claim",r,[1164],"付款安排","subject to Sub-Clause 20.1 \\[Contractor's Claims\\]")
r=A.rel("1167_determine",[1167],"变更",EMP,CON)
A.detail("1167_process",r,[1167],"变更程序","After receiving this notice, the Employer shall proceed in accordance with Clause 3.5 \\[Determinations\\] to agree or determine these matters")
A.issues += ["1147 将承包商自担提案成本记为付款安排文字，未把雇主虚构为实际收款方；其资金承担关系仍待词表细化。", "1156 是 1155 的续句，已合并入同一变更关系的出处。"]
A.save()

B = Batch("payments_1172_1186", [1172,1173,1174,1175,1176,1179,1180,1181,1182,1183,1184,1185,1186])
r=B.contract_rel("1172_exception",[1172,1173,1174,1175],"付款")
B.detail("1172_exception",r,[1172],"付款安排","Unless otherwise stated in the Construction Contract")
r=B.rel("1173_lump_sum",[1173],"付款",EMP,CON)
B.detail("1173_basis",r,[1173],"付款安排","payment for the Works shall be made on the basis of the lump sum Contract Price")
r=B.contract_rel("1174_inclusive",[1174],"付款")
B.detail("1174_tax",r,[1174],"付款安排","Contract Price is inclusive of all applicable taxes, royalties, duties, charges and fees")
r=B.contract_rel("1175_taxes",[1175],"付款")
B.detail("1175_pay",r,[1175],"付款安排","Contractor shall pay all taxes, royalties, duties, charges and fees required to be paid by him under the Construction Contract")
B.detail("1175_no_adjust",r,[1175],"付款安排","Contract Price shall not be adjusted for any of these costs")
B.gap("1175_tax_recipient",1175,"unmatched_unit","税费实际缴纳对象不是雇主，而合同关系模型现有付款单元只支持两方主体；此记录仅保存承包商承担责任与不调价，不表示雇主是税费收款人。")
r=B.rel("1176_usd",[1176],"付款",EMP,CON)
B.detail("1176_currency",r,[1176],"付款安排","Contract Price shall be paid in accordance with the terms of the Construction Contract in US Dollars")
r=B.rel("1179_security_condition",[1179],"付款",EMP,CON)
B.detail("1179_requirements",r,[1179],"付款安排","subject to the Employer's receipt of the LNTP Advance Payment Security in accordance with Clause 4.2.1 (LNTP Advance Payment Security) and the Performance Security in accordance with Clause 4.2.4 (Performance Security) and the Contractor's corresponding 10% VAT invoice and the original commercial invoice")
r=B.rel("1180_advance",[1180,1181,1182,1183],"付款",EMP,CON)
B.detail("1180_amount",r,[1180],"付款安排","LNTP Advance Payment, equal to 15% of the LNTP Payment")
B.detail("1180_due",r,[1180],"付款安排","within seven (7) Business Days after the later date of receipt of the listed securities")
B.detail("1181_security",r,[1181,1182],"付款安排","receipt of the LNTP Advance Payment Security in accordance with Clause 4.2.1 (LNTP Advance Payment Security) by the Employer")
B.detail("1183_security",r,[1183],"付款安排","receipt of the LNTP Performance Security and the Performance Security in accordance with Clause (Performance Security) by the Employer")
B.gap("1180_formula",1180,"missing_slot","有限开工预付款为有限开工款的 15%，且在两个保函条件较晚满足后七个工作日付款；付款金额和期限槽无法同时结构化表达比例公式与较晚日期。")
B.issues.append("1183 引用 Clause (Performance Security) 缺具体编号；只按草案原文转录，不补造编号。")
r=B.rel("1184_deduction",[1184],"付款",EMP,CON,"power_holder","power_subject","power")
B.detail("1184_rate",r,[1184],"付款安排","deduct 15% from each LNTP Payment Milestone which is completed after the Contractor's receipt of the LNTP Advance Payment")
B.detail("1184_purpose",r,[1184],"付款安排","for the purpose of repayment of the LNTP Advance Payment")
B.gap("1184_deduction_formula",1184,"missing_slot","每一项符合条件的有限开工里程碑款扣减 15%；现有付款安排槽不能结构化表示逐笔扣减比例、适用里程碑及预付款余额联动。")
r=B.rel("1185_continuing_deduction",[1185],"付款",EMP,CON,"power_holder","power_subject","power")
B.detail("1185_balance",r,[1185],"付款安排","whole of the balance then outstanding shall continuously be reduced from the LNTP Payment Milestone Amount")
B.detail("1185_condition",r,[1185],"付款安排","If the LNTP Advance Payment has not been fully repaid prior to the Commencement Date")
r=B.rel("1186_due",[1185,1186],"付款",CON,EMP)
B.detail("1186_balance",r,[1185,1186],"付款安排","If the advance payment has not been repaid prior to termination under Clause 8.1.5 (Termination prior to Commencement Date), Clause 15 \\[Termination by Employer\\], Clause 16 \\[Suspension and Termination by Contractor\\] or Clause 19 \\[Force Majeure\\] (as the case may be), the whole of the balance then outstanding shall immediately become due and payable by the Contractor to the Employer")
B.gap("1186_balance_formula",1186,"missing_slot","终止时未偿还预付款余额立即到期；当前付款金额槽只接受固定数量，不能结构化表达未偿余额及立即到期规则。")
B.save()
