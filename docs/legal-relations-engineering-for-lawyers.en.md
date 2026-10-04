# An Engineering Approach to Representing Legal Relationships (Lawyers' Edition)

[中文](legal-relations-engineering-for-lawyers.md) | [General edition](legal-relations-engineering.en.md)

## 1. Reliability in Using AI for Contract Work

When AI is used for contract work, a correct result in a single instance does not establish that the same method can be used reliably on an ongoing basis. Whether its work can be relied upon still depends on the accuracy and completeness of the contractual content on which it rests, and on whether the interpretation of that content has an identifiable basis. Continued use therefore requires ways to review conclusions, identify omissions, and correct errors.

This requirement is directly related to the randomness involved in AI generation. An analysis of a payment arrangement, for example, may refer to the amount and deadline while failing to consider a prerequisite in another clause. Even if the account is clearly expressed, the contractual basis for its conclusion remains incomplete. Having correctly addressed similar questions before does not exclude an omission or misinterpretation in the present analysis.

Providing appendices, explaining the background, and specifying the task can help reduce errors. Providing material, however, does not establish that its provisions have been understood accurately; stating a requirement does not establish that the result satisfies it. In the payment example, the analysis must still be checked against the source to confirm that the prerequisite and its effect on performance of the obligation have been fully considered.

Contractual content established through review should also remain available for subsequent work. Without clear records of the source provisions, the grounds for interpretation, and the history of corrections, existing analysis becomes difficult to review and use when responsibility changes hands or the material is used for another purpose. Preserving these matters together allows later work to proceed from the understanding already reached, while remaining open to correction.

cogengine-legal records contractual content by legal relationship, preserving the parties' positions, their specific rights and obligations, the applicable conditions, and related provisions together with the supporting text. Different tasks can use the same records for their respective analyses. Corrections address particular entries, retaining both the earlier entries and the grounds for correction.

The project currently deals with a single contract and its constituent documents, recording what their text stipulates. These records still involve interpretation and judgment; their accuracy and completeness must be tested. The basic questions used to analyze legal relationships provide a starting point for deciding what should be recorded.

## 2. Different Contracts Raise Common Questions About Legal Relationships

Contracts can express their terms in many different ways. A payment arrangement may state that “the buyer shall pay the price” or that “the seller is entitled to require the buyer to pay the price.” Its precise meaning still depends on context, but the reader will ask the same questions: who must pay, to whom, how much, when, and subject to what prerequisites?

These questions are relatively stable; the answers depend on the particular contract. One payment provision may specify a fixed amount, another a calculation by percentage. One may require payment when due, another only after acceptance. A basic task of legal analysis is to identify these distinctions and their effect on the parties' positions and conduct.

This allows an arrangement to be recorded in its constituent parts: the parties involved, what each undertakes or is entitled to, how the terms are determined, and the conditions, limitations, and exceptions that apply. Provisions allowing a party to make a choice, conferring a right to terminate, or prohibiting particular conduct likewise require a clear account of the parties' positions and the arrangement's content.

**The questions used to identify a relationship and the method of recording it can be shared; the answers in each contract still require individual reading and judgment.** A common method allows different people to approach the work in a comparable order and pass their results to others for continued use. This is the starting point for an engineering approach.

For this project, that approach means making the method explicit: specifying what must be recorded, how the entries relate to one another, and what evidence is needed to check them, so that people and tools can divide the work accordingly. Where interpretation is required, the judgment and its grounds must also be preserved for later review.

## 3. Recording Each Arrangement in Full

Consider this short illustrative provision:

> The total contract price is 1,000,000 yuan. The buyer shall pay the seller 20% of the total contract price within 30 days after successful acceptance.

A complete account of the arrangement must address at least the following:

| Question to establish | Answer in this example |
|---|---|
| Which parties are involved? | The two parties designated in the contract as buyer and seller. |
| What is each party's position in this arrangement? | The buyer bears the payment obligation; the seller receives payment. |
| How is the amount determined? | It is 20% of the total contract price, which is specified as 1,000,000 yuan. |
| How is the payment deadline determined? | Payment is due within 30 days after successful acceptance. |
| What supports these findings? | The relevant source provisions concerning the parties, total price, payment, and acceptance. |

What must be preserved extends beyond the conclusion “pay 200,000 yuan.” The percentage used to determine the amount and the acceptance from which the deadline runs are themselves part of the agreement. A later reader should be able to see how the amount and deadline were determined and locate the relevant provisions.

The designation “buyer” is also insufficient on its own. In the payment arrangement, the buyer bears an obligation; in a delivery arrangement, the buyer may receive performance. The record must therefore distinguish a party's identity in the transaction from its position in each particular arrangement.

On this basis, a contract can be organized into numerous connected entries. Each describes a particular arrangement, retaining its amounts, deadlines, conditions, and exceptions. Instalment payments can be recorded separately by instalment; amounts can retain their calculation methods; complex conditions can set out their constituent parts and how they apply together. Where the text prohibits a transfer, the prohibited conduct must be recorded. Every restriction expressed in the text should be preserved.

Completeness depends on whether the entries, taken together, express the contract's content. Labelling a clause “payment” or “liability for breach” classifies it; the record must also explain what that clause actually provides.

## 4. Preserving Connections Between Separately Recorded Provisions

A contract rarely states every element of an arrangement in a single sentence. In the example, the total price may appear in a price schedule, acceptance criteria in a technical appendix, and an exception to payment in another chapter. A lawyer connects these provisions when reading the contract. Those connections also need to form part of the resulting record.

The project records recurring matters in a common place and allows the relevant arrangements to refer to them. The total contract price, for example, has a clear entry to which each instalment can refer as its basis of calculation. Where several provisions use successful acceptance as the point from which time runs, the record should show that they refer to the same acceptance. Acceptance of different batches must be distinguished where the text requires it.

A reader examining the payment arrangement can then follow those references to the price and acceptance provisions on which it depends. What is recorded here is how the contract uses successful acceptance. Establishing whether acceptance has actually occurred requires separate material concerning performance.

Arrangements involving several parties also require their connections to be preserved. The project records the relationships actually established by the text between the relevant pairs of parties. Suppose A and B share an obligation to pay C a total of 1,000,000 yuan. Separate entries for the relationships between A and C and between B and C must still make clear that both concern the same total. They must retain the respective burdens and the effect of performance on the other relationship as provided in the contract. The combined meaning must remain faithful to the agreement; recording the relationships separately must not turn the total into 2,000,000 yuan.

Provisions applying to the contract as a whole, such as its constituent documents, definitions, and conditions for taking effect, must also be preserved separately so that particular arrangements can refer to them. The original order of chapters and clauses is retained, allowing the full context to be consulted at any time.

The project therefore organizes information by specific legal relationships while also preserving the provisions on which those relationships jointly depend. Separate entries make individual matters easier to find; the connections between them preserve a coherent reading of the whole contract.

## 5. Turning Professional Experience into Shared Recording Conventions

In recording a payment provision, one person may describe a payment prerequisite and the starting point for its deadline together, while another records them separately. Either approach may give a clear account. When the work of many people needs to be consulted together, however, differences in presentation increase the effort required to find and check information. Shared use therefore calls for common conventions about categories and the matters to be recorded.

These conventions can be developed from actual contracts and professional experience. Payment arrangements, for example, usually require attention to the amount, calculation basis, deadline, and prerequisites. Liability provisions may require separate treatment of scope, limiting conditions, and caps. The project collects these categories, the matters to be recorded, and instructions for completing the entries in what it calls a “vocabulary.”

This vocabulary can be understood as an agreed outline for organizing the work. It tells the person or tool preparing the record where an item belongs and how to express it clearly enough. The actual content still comes from the contract. If the contract specifies no deadline, the availability of a heading for “deadline” does not authorize anyone to supply one for the parties.

Professional knowledge can thus accumulate in two forms. An individual contract contributes its particular provisions; experience gained across contracts helps improve the common categories and recording methods. Those methods require professional review and must be tested in use to establish whether they can adequately express the arrangements encountered.

Where the available categories or recording methods cannot accommodate a provision, the representable content should be retained and the limitation documented with its textual basis, so that the method can later be revised. Each contract also preserves the conventions used to prepare its records. Subsequent changes to the common conventions therefore leave the basis of earlier work available for interpretation.

This allows the shared method to develop while preserving the differences between individual contracts.

## 6. Records That Others Can Check and Use

For a record to be usable by another professional, that person must be able to identify the basis of each entry. The project therefore requires every item to be connected to the specific clauses and wording that support it, while retaining the full text and original documents.

Where the text expressly states a payment percentage, the corresponding source is identified. Where the presentation of an amount or date has been converted, its original form and the basis of conversion are retained. Where several provisions support an inference, the premises and the person or tool making the judgment must be identified. A later reader can then distinguish what the contract expressly states from the work undertaken to represent it.

Review proceeds in both directions.

A clause-by-clause reading of the contract checks whether every provision has been represented, including incidental obligations, exceptions, and limitations within long passages. An item-by-item reading of the records checks whether each has support in the text, whether its scope has been extended, or whether a condition has been misunderstood.

Locating a relevant quotation establishes that the evidence is available; it remains necessary to determine whether the quotation supports the entry. Similarly, the existence of a record for a clause does not establish that other arrangements in the same clause have been captured. Different recording methods should be assessed as a whole, according to whether they jointly express the same complete meaning.

An absent entry also requires its reason to be established. An express blank in the source, missing material, a limitation of the recording method, and an omission during preparation each present a different issue. The absence of a record is insufficient, by itself, to establish that the contract contains no provision on the matter.

Errors must be capable of correction while preserving the earlier content and its supporting evidence. The work can then improve over time while retaining an account of how the contract was previously understood.

## 7. A Method That Can Be Applied Repeatedly

The basic requirements for an engineering approach are now apparent: common questions for analysis, requirements for a complete record, connections between provisions, and means of checking evidence and correcting errors. These requirements allow the work to be divided and tools to be used where appropriate.

The project uses AI to assist with reading and preparing records. A long contract is first read in sections, its overall arrangements brought together, and its parties and recurring matters identified consistently before individual clauses are examined in detail. Reading tasks responsible for different parts of the contract can then share the same background. Each clause is assigned in full to a single task, so that its principal provisions, incidental obligations, conditions, and exceptions are considered together.

AI must submit its results according to the common recording conventions and include their supporting evidence. Software performs checks that can be governed by explicit rules: whether the organized clauses preserve the full text, whether quotations actually appear in the clauses cited, whether references to parties or other entries can be resolved, and whether amounts and dates are recorded in the required form. Errors in entries or references are returned for correction; results that meet the requirements are then saved through a common process.

This division allows interpretation and routine checking to improve separately. AI undertakes the substantial reading and initial preparation; software consistently applies explicit checks; and professionals approve the shared method, resolve matters requiring a decision, and assess accuracy and completeness against actual contracts. Passing the software checks establishes compliance with those rules. The quality of the interpretation still requires review in both directions as described above.

The original documents, full text, recording conventions, entries, supporting evidence, and correction history are ultimately preserved together in an electronic file that can be handed over as a whole. Agreed ways of recording parties, arrangement categories, and particular terms allow software to find and bring together relevant content. A user can start with a party to find the arrangements involving it, examine all the conditions attached to an obligation, or follow the evidence back to the source text.

The project's goal is for users to obtain the full content of the contract's provisions from these records and return to the original text for verification whenever needed.

Subsequent work can build on that material. Contract review can add review criteria, performance management can add facts about actual performance, and dispute analysis can bring in further evidence and legal grounds. Questions such as whether a clause is valid or an obligation has been performed remain matters for that subsequent work.

The engineering approach to legal relationships takes the form of a method through which professional work can accumulate. A careful reading produces a complete record; shared conventions, connections between entries, and textual evidence make the record open to review and continuing correction. Tools can participate in this work, and others can proceed from what has already been established.

Contractual relationships provide the current scope for applying the method. Its capacity to represent complex arrangements must continue to be tested against real contracts. Extension to other legal relationships would also require reconsidering the sources of material and the questions to be established. The project seeks to develop the ability to represent legal relationships accurately and keep the resulting work available for continuing use.

## 8. Planned Extensions

The current release provides methods and tools for accurately recording contractual provisions, preserving their supporting evidence, and making them available for subsequent work. Once the provisions and their connections have been clearly recorded, further legal work can proceed on that basis. The near-term plans are contract review, followed by contract revision and clause drafting. A longer-term direction is contract management founded on this complete account of the contract's provisions.

### Contract Review

Reviewing a contract first requires establishing what the parties have agreed. The specific rights and obligations, their conditions, limitations and exceptions, and the effect of other clauses all bear on the review conclusions. A clear record of these matters and their textual basis is a prerequisite for evaluating the provisions.

The arrangements can then be assessed in light of the client's requirements and the applicable review criteria. Reviewing payment terms, for example, requires considering the amount, deadline, and prerequisites together. A complete record helps bring these matters within the review. The resulting comments can identify the provisions concerned and their original wording, facilitating verification and further action.

### Contract Revision and Clause Drafting

After establishing the existing provisions and providing review comments, it is often necessary to adjust the arrangements to reflect the parties' requirements or to add new provisions. Revision and drafting both require clarity about what should be retained, what should change, and what rights and obligations the parties ultimately wish to establish.

Whether the task involves adjusting payment conditions, changing the scope of liability, or introducing an obligation, the parties' requirements must be expressed in specific clauses. Understanding the existing provisions and their effects on one another helps identify the matters affected by a revision. A clear record of the proposed arrangements can guide drafting and the subsequent review of the wording. The work already undertaken to understand the contract can therefore continue to support the expression of the parties' intended arrangements and the assessment of whether the revised clauses reflect those intentions.

### Contract Management Based on Structured Contracts

The longer-term plan is to keep established and fully recorded contractual provisions available to the relevant people after signature, and to build a contract management system on that basis.

After a contract is signed, its provisions remain an important basis for organizing performance, asserting rights, and addressing disagreements. Beyond basic information such as price, subject matter, and signing date, management requires knowing what each party must do, which conditions govern performance, which deadlines apply, and how one arrangement affects other provisions. Preserving a complete account of these matters and their textual basis allows them to be consulted and relied upon in subsequent work, with facts about actual performance brought in to support management.

These three directions extend the project's purpose: to keep professional work based on an accurate understanding of a contract available for continuing use. Review draws on that work to evaluate provisions; revision and drafting use it to formulate or adjust them; and contract management continues to use them during performance. The recording methods and tools currently provided preserve a foundation that can be checked, handed over, and carried forward into that subsequent work.
