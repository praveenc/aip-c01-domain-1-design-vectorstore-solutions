#!/usr/bin/env python3
"""
Generate synthetic legal documents for the Legal Research RAG demo.

Produces 30 documents across 3 categories:
  - Case Briefs (10): summaries of legal cases with holdings and reasoning
  - Contract Templates (10): standard clauses for SaaS, NDA, and service agreements
  - Regulatory Memos (10): internal guidance on compliance topics (GDPR, SOX, HIPAA)

Output: synth_data/output/ directory with .txt files and a manifest.json

No external dependencies — uses only Python standard library.
"""

import hashlib
import json
import random
from pathlib import Path

# Seed for reproducibility
random.seed(42)

SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = SCRIPT_DIR / "output"


# ─── Document Templates ─────────────────────────────────────────────────────

CASE_BRIEF_AUTHORS = [
    "Sarah Chen, Senior Associate",
    "Michael Torres, Partner",
    "Priya Patel, Associate",
    "James O'Brien, Of Counsel",
    "Lisa Nakamura, Senior Associate",
]

CONTRACT_AUTHORS = [
    "David Kim, Corporate Counsel",
    "Rachel Green, Contract Specialist",
    "Ahmed Hassan, Senior Associate",
    "Emily Watson, Partner",
    "Carlos Rivera, Associate",
]

MEMO_AUTHORS = [
    "Dr. Anna Schmidt, Compliance Director",
    "Robert Chang, Regulatory Counsel",
    "Maria Gonzalez, Privacy Officer",
    "Thomas Wright, Risk Manager",
    "Jennifer Liu, Senior Compliance Analyst",
]

CASE_BRIEFS = [
    {
        "title": "TechCorp v. DataFlow Inc. — Breach of SaaS Agreement",
        "court": "U.S. District Court, Northern District of California",
        "date": "2025-06-15",
        "docket": "Case No. 3:24-cv-01234",
        "topic": "breach_of_contract",
        "body": (
            "CASE BRIEF\n\n"
            "Caption: TechCorp International LLC v. DataFlow Inc.\n"
            "Court: U.S. District Court, Northern District of California\n"
            "Docket: Case No. 3:24-cv-01234\n"
            "Date: June 15, 2025\n\n"
            "FACTS:\n"
            "TechCorp entered into a three-year SaaS subscription agreement with DataFlow for "
            "enterprise data analytics services. The agreement specified 99.9% uptime SLA with "
            "service credits for downtime exceeding the threshold. Over a six-month period, "
            "DataFlow's platform experienced 47 hours of unplanned downtime, resulting in an "
            "effective uptime of 98.9%. TechCorp claimed material breach and sought termination "
            "plus damages of $2.3 million in lost productivity.\n\n"
            "ISSUE:\n"
            "Whether repeated SLA violations constituting a cumulative 1% uptime shortfall over "
            "six months amounts to a material breach justifying contract termination, or whether "
            "the contractual service credit remedy is the exclusive remedy.\n\n"
            "HOLDING:\n"
            "The court held that the SLA service credit provision was not an exclusive remedy. "
            "The pattern of repeated failures demonstrated a fundamental inability to perform "
            "the core obligation of the agreement. The court applied the Restatement (Second) of "
            "Contracts Section 241 factors and found that TechCorp was deprived of the substantial "
            "benefit it reasonably expected.\n\n"
            "REASONING:\n"
            "The court distinguished between isolated service disruptions (which the SLA credit "
            "mechanism was designed to address) and a persistent pattern of non-performance. "
            "Key factors included: (1) the cumulative nature of the failures, (2) DataFlow's "
            "failure to implement remedial measures after the first three incidents, (3) the "
            "impact on TechCorp's downstream customer commitments, and (4) the absence of an "
            "explicit exclusivity clause for the SLA credit remedy.\n\n"
            "SIGNIFICANCE:\n"
            "This case establishes that SLA credit provisions in SaaS agreements do not "
            "automatically constitute exclusive remedies unless explicitly stated. Vendors should "
            "include clear exclusive remedy language if they intend SLA credits to be the sole "
            "recourse for service failures. Customers should negotiate for termination rights "
            "triggered by cumulative SLA failures over defined periods."
        ),
    },
    {
        "title": "GlobalBank NA v. SecureVault Systems — Data Breach Liability",
        "court": "Supreme Court of New York, Commercial Division",
        "date": "2025-03-22",
        "docket": "Index No. 651234/2024",
        "topic": "data_breach",
        "body": (
            "CASE BRIEF\n\n"
            "Caption: GlobalBank NA v. SecureVault Systems Corp.\n"
            "Court: Supreme Court of New York, Commercial Division\n"
            "Docket: Index No. 651234/2024\n"
            "Date: March 22, 2025\n\n"
            "FACTS:\n"
            "GlobalBank contracted SecureVault to provide cloud-based document management for "
            "sensitive financial records. SecureVault's system suffered a data breach exposing "
            "records of 150,000 bank customers. Investigation revealed SecureVault had not "
            "implemented encryption at rest despite contractual requirements, and had delayed "
            "patching a known vulnerability (CVE-2024-3094) for 90 days.\n\n"
            "ISSUE:\n"
            "Whether a cloud service provider's failure to implement contractually required "
            "security controls constitutes gross negligence sufficient to pierce a limitation "
            "of liability clause capping damages at 12 months of fees.\n\n"
            "HOLDING:\n"
            "The court held that SecureVault's conduct constituted gross negligence. The "
            "limitation of liability clause was unenforceable as applied to the data breach "
            "damages because New York law does not permit contractual limitation of liability "
            "for gross negligence.\n\n"
            "REASONING:\n"
            "The court found two independent bases for gross negligence: (1) the deliberate "
            "failure to implement encryption at rest, which was an explicit contractual "
            "obligation and an industry-standard security control, and (2) the 90-day delay "
            "in patching a critical vulnerability with a CVSS score of 10.0. The court noted "
            "that SecureVault's internal communications showed awareness of both deficiencies "
            "and a conscious decision to defer remediation to reduce costs.\n\n"
            "SIGNIFICANCE:\n"
            "This decision reinforces that limitation of liability clauses in technology "
            "contracts do not protect vendors from consequences of gross negligence. Cloud "
            "service providers must implement all contractually specified security controls "
            "and maintain timely patch management. The case also highlights the importance of "
            "carve-outs in LoL clauses for data breach, IP infringement, and confidentiality "
            "violations."
        ),
    },
    {
        "title": "Meridian Health v. PharmaCo — Force Majeure in Supply Chain",
        "court": "U.S. Court of Appeals, Seventh Circuit",
        "date": "2025-09-10",
        "docket": "No. 24-2567",
        "topic": "force_majeure",
        "body": (
            "CASE BRIEF\n\n"
            "Caption: Meridian Health Systems v. PharmaCo Distribution LLC\n"
            "Court: U.S. Court of Appeals, Seventh Circuit\n"
            "Docket: No. 24-2567\n"
            "Date: September 10, 2025\n\n"
            "FACTS:\n"
            "PharmaCo failed to deliver critical pharmaceutical supplies to Meridian Health "
            "for three consecutive months, citing supply chain disruptions caused by a major "
            "port closure and semiconductor shortage affecting cold-chain logistics equipment. "
            "The supply agreement contained a force majeure clause listing 'natural disasters, "
            "war, government actions, and epidemics' but did not explicitly mention supply chain "
            "disruptions or port closures.\n\n"
            "ISSUE:\n"
            "Whether supply chain disruptions caused by port closures and component shortages "
            "fall within a force majeure clause that does not explicitly enumerate such events, "
            "and whether the non-performing party took reasonable steps to mitigate.\n\n"
            "HOLDING:\n"
            "The Seventh Circuit held that the force majeure clause did not excuse PharmaCo's "
            "non-performance. The clause was narrowly drafted and did not include catch-all "
            "language. Furthermore, PharmaCo failed to demonstrate that it took commercially "
            "reasonable steps to secure alternative supply routes.\n\n"
            "REASONING:\n"
            "The court applied the principle of ejusdem generis, finding that the enumerated "
            "events (natural disasters, war, government actions, epidemics) all involve "
            "extraordinary, unforeseeable circumstances beyond human control. Supply chain "
            "disruptions, while severe, are foreseeable business risks that sophisticated "
            "commercial parties should plan for. The court also noted that PharmaCo had not "
            "activated its business continuity plan or attempted to source from alternative "
            "suppliers, undermining its claim of impossibility.\n\n"
            "SIGNIFICANCE:\n"
            "This case narrows the application of force majeure in commercial supply agreements. "
            "Parties should: (1) draft force majeure clauses with explicit catch-all language "
            "if broad coverage is intended, (2) include supply chain disruptions as a named "
            "event if relevant, (3) document mitigation efforts contemporaneously, and "
            "(4) maintain active business continuity plans."
        ),
    },
    {
        "title": "InnovateTech v. CloudScale — IP Ownership in Custom Development",
        "court": "U.S. District Court, District of Delaware",
        "date": "2025-01-18",
        "docket": "Case No. 1:24-cv-00789",
        "topic": "intellectual_property",
        "body": (
            "CASE BRIEF\n\n"
            "Caption: InnovateTech Solutions v. CloudScale Platforms Inc.\n"
            "Court: U.S. District Court, District of Delaware\n"
            "Docket: Case No. 1:24-cv-00789\n"
            "Date: January 18, 2025\n\n"
            "FACTS:\n"
            "InnovateTech engaged CloudScale to develop a custom machine learning pipeline "
            "integrated with CloudScale's existing platform. The statement of work specified "
            "that 'all custom code developed specifically for Client shall be owned by Client.' "
            "CloudScale incorporated portions of its proprietary framework into the custom "
            "deliverables without disclosure. When InnovateTech attempted to migrate to a "
            "competitor's platform, CloudScale asserted IP rights over the integrated code.\n\n"
            "ISSUE:\n"
            "Whether a vendor's pre-existing proprietary code incorporated into custom "
            "deliverables without disclosure becomes subject to the client's IP ownership "
            "clause, and whether the vendor's failure to disclose constitutes breach.\n\n"
            "HOLDING:\n"
            "The court held that CloudScale's pre-existing IP remained its property, but "
            "CloudScale breached its duty of good faith by failing to disclose the incorporation "
            "of proprietary components. InnovateTech was entitled to a perpetual, irrevocable "
            "license to the incorporated proprietary code and damages for the cost of migration.\n\n"
            "REASONING:\n"
            "The court applied the work-for-hire doctrine and found that the IP ownership clause "
            "applied only to code 'developed specifically for Client,' not to pre-existing "
            "frameworks. However, CloudScale's failure to disclose the dependency created an "
            "implied license and breached the covenant of good faith and fair dealing. The court "
            "noted that sophisticated technology vendors have a duty to clearly delineate "
            "pre-existing IP from custom deliverables.\n\n"
            "SIGNIFICANCE:\n"
            "Technology development agreements should include: (1) clear definitions of "
            "'pre-existing IP' vs 'custom deliverables,' (2) mandatory disclosure requirements "
            "for any proprietary components incorporated into deliverables, (3) automatic license "
            "grants for incorporated pre-existing IP, and (4) escrow provisions for source code "
            "of critical dependencies."
        ),
    },
    {
        "title": "RetailMax v. AI Solutions Corp — Algorithmic Bias Liability",
        "court": "U.S. District Court, Southern District of New York",
        "date": "2025-11-05",
        "docket": "Case No. 1:25-cv-04567",
        "topic": "ai_liability",
        "body": (
            "CASE BRIEF\n\n"
            "Caption: RetailMax Inc. v. AI Solutions Corp.\n"
            "Court: U.S. District Court, Southern District of New York\n"
            "Docket: Case No. 1:25-cv-04567\n"
            "Date: November 5, 2025\n\n"
            "FACTS:\n"
            "RetailMax deployed AI Solutions' credit scoring model for customer financing "
            "decisions. An audit revealed the model exhibited disparate impact against protected "
            "classes, resulting in denial rates 2.3x higher for minority applicants. RetailMax "
            "faced regulatory enforcement action and consumer class action lawsuits. RetailMax "
            "sued AI Solutions for breach of warranty and indemnification.\n\n"
            "ISSUE:\n"
            "Whether an AI vendor's warranty that its model 'complies with applicable laws' "
            "encompasses compliance with fair lending regulations, and whether the vendor bears "
            "liability for algorithmic bias in a model deployed by the customer.\n\n"
            "HOLDING:\n"
            "The court held that the compliance warranty was broad enough to encompass fair "
            "lending requirements. AI Solutions bore partial liability for the biased model, "
            "but RetailMax's failure to conduct independent bias testing before deployment "
            "constituted contributory negligence reducing the damages award by 40%.\n\n"
            "REASONING:\n"
            "The court found that: (1) the compliance warranty was not limited to technical "
            "specifications and reasonably encompassed regulatory compliance, (2) AI Solutions "
            "had superior knowledge of the model's training data and methodology, (3) however, "
            "RetailMax as the deployer had an independent duty to validate the model for its "
            "specific use case under ECOA and Regulation B. The court established a shared "
            "responsibility framework for AI deployment.\n\n"
            "SIGNIFICANCE:\n"
            "This case establishes a dual-responsibility framework for AI model deployment: "
            "vendors must ensure models are designed to minimize bias, while deployers must "
            "conduct independent validation for their specific use case. AI procurement "
            "contracts should include: (1) specific bias testing warranties, (2) model card "
            "and training data documentation requirements, (3) ongoing monitoring obligations, "
            "and (4) clear allocation of regulatory liability."
        ),
    },
    {
        "title": "GreenEnergy Co. v. StateGrid — Regulatory Taking of Renewable Credits",
        "court": "U.S. Court of Federal Claims",
        "date": "2025-07-28",
        "docket": "No. 24-1890C",
        "topic": "regulatory_compliance",
        "body": (
            "CASE BRIEF\n\n"
            "Caption: GreenEnergy Co. v. United States (StateGrid as Intervenor)\n"
            "Court: U.S. Court of Federal Claims\n"
            "Docket: No. 24-1890C\n"
            "Date: July 28, 2025\n\n"
            "FACTS:\n"
            "GreenEnergy invested $45 million in solar generation facilities based on existing "
            "renewable energy credit (REC) pricing. A subsequent regulatory change retroactively "
            "reduced REC values by 60%, rendering GreenEnergy's investment economically unviable. "
            "GreenEnergy claimed the regulatory change constituted a taking under the Fifth "
            "Amendment.\n\n"
            "ISSUE:\n"
            "Whether a retroactive reduction in renewable energy credit values constitutes a "
            "regulatory taking requiring just compensation under the Fifth Amendment.\n\n"
            "HOLDING:\n"
            "The court held that the retroactive application of the reduced REC values to "
            "existing facilities constituted a regulatory taking. However, prospective "
            "application to new facilities was within the government's regulatory authority.\n\n"
            "REASONING:\n"
            "Applying the Penn Central factors, the court found: (1) the economic impact was "
            "severe — a 60% reduction in expected revenue made the investment non-viable, "
            "(2) GreenEnergy had reasonable investment-backed expectations based on the existing "
            "regulatory framework, and (3) the retroactive character of the regulation was "
            "particularly significant. The court distinguished between prospective regulatory "
            "changes (permissible) and retroactive changes that destroy vested economic rights.\n\n"
            "SIGNIFICANCE:\n"
            "Energy companies should: (1) document reliance on existing regulatory frameworks "
            "in investment decisions, (2) include regulatory change provisions in financing "
            "agreements, (3) monitor proposed regulatory changes and participate in comment "
            "periods, and (4) consider regulatory risk insurance for large capital investments."
        ),
    },
    {
        "title": "MedDevice Inc. v. HealthTech — Product Liability for AI Diagnostics",
        "court": "Superior Court of California, County of Santa Clara",
        "date": "2025-04-12",
        "docket": "Case No. 24CV123456",
        "topic": "product_liability",
        "body": (
            "CASE BRIEF\n\n"
            "Caption: MedDevice Inc. v. HealthTech AI Systems\n"
            "Court: Superior Court of California, County of Santa Clara\n"
            "Docket: Case No. 24CV123456\n"
            "Date: April 12, 2025\n\n"
            "FACTS:\n"
            "HealthTech developed an AI-powered diagnostic imaging system marketed as capable "
            "of detecting early-stage tumors with 99.2% accuracy. MedDevice integrated the "
            "system into its radiology workflow. The system failed to detect tumors in 23 "
            "patients over a six-month period, resulting in delayed treatment. Investigation "
            "revealed the training data was predominantly from one demographic group, reducing "
            "accuracy for underrepresented populations.\n\n"
            "ISSUE:\n"
            "Whether an AI diagnostic tool constitutes a 'product' subject to strict liability "
            "under California product liability law, and whether the vendor's accuracy claims "
            "create an express warranty.\n\n"
            "HOLDING:\n"
            "The court held that the AI diagnostic system was a product subject to strict "
            "liability. The 99.2% accuracy claim constituted an express warranty, and the "
            "system's failure to perform as warranted across diverse patient populations "
            "rendered it defective.\n\n"
            "REASONING:\n"
            "The court rejected HealthTech's argument that AI software is a 'service' rather "
            "than a 'product.' The system was a standardized, commercially distributed tool "
            "integrated into a physical workflow — meeting the Restatement (Third) of Torts "
            "definition. The accuracy claim in marketing materials and technical documentation "
            "created an express warranty under UCC Section 2-313. The demographic bias in "
            "training data constituted a design defect.\n\n"
            "SIGNIFICANCE:\n"
            "AI medical device vendors must: (1) ensure training data represents the intended "
            "patient population, (2) qualify accuracy claims with demographic breakdowns, "
            "(3) implement post-market surveillance for performance degradation, and "
            "(4) maintain clear documentation of model limitations and intended use populations."
        ),
    },
    {
        "title": "FinServ Partners v. BlockChain Solutions — Smart Contract Dispute",
        "court": "U.S. District Court, Southern District of Florida",
        "date": "2025-08-19",
        "docket": "Case No. 0:25-cv-60123",
        "topic": "smart_contracts",
        "body": (
            "CASE BRIEF\n\n"
            "Caption: FinServ Partners LLC v. BlockChain Solutions Inc.\n"
            "Court: U.S. District Court, Southern District of Florida\n"
            "Docket: Case No. 0:25-cv-60123\n"
            "Date: August 19, 2025\n\n"
            "FACTS:\n"
            "FinServ engaged BlockChain Solutions to implement automated escrow using smart "
            "contracts on Ethereum. A coding error in the smart contract caused premature "
            "release of $8.5 million in escrow funds before delivery conditions were met. "
            "BlockChain Solutions argued that the smart contract code was the definitive "
            "agreement and the code executed as written.\n\n"
            "ISSUE:\n"
            "Whether a smart contract's automated execution controls over the parties' written "
            "agreement when the code deviates from the documented business requirements, and "
            "whether the developer bears liability for coding errors.\n\n"
            "HOLDING:\n"
            "The court held that the written agreement controlled over the smart contract code. "
            "The smart contract was an implementation tool, not a superseding agreement. "
            "BlockChain Solutions was liable for the coding error as a breach of its development "
            "obligations.\n\n"
            "REASONING:\n"
            "The court found that: (1) the parties' intent was documented in the written "
            "agreement and statement of work, (2) the smart contract was intended to automate "
            "the agreed-upon terms, not to create new terms, (3) the 'code is law' argument "
            "was rejected as inconsistent with established contract law principles, and "
            "(4) BlockChain Solutions had a professional duty to implement code that accurately "
            "reflected the agreed business logic.\n\n"
            "SIGNIFICANCE:\n"
            "Smart contract implementations should: (1) include explicit provisions stating "
            "that the written agreement controls in case of discrepancy, (2) require formal "
            "code audits before deployment, (3) implement pause/emergency stop mechanisms, "
            "and (4) maintain comprehensive test documentation mapping code behavior to "
            "business requirements."
        ),
    },
    {
        "title": "DataPrivacy Alliance v. SocialMedia Corp — CCPA Enforcement",
        "court": "California Court of Appeal, First District",
        "date": "2025-02-28",
        "docket": "No. A165432",
        "topic": "data_privacy",
        "body": (
            "CASE BRIEF\n\n"
            "Caption: DataPrivacy Alliance v. SocialMedia Corp.\n"
            "Court: California Court of Appeal, First District\n"
            "Docket: No. A165432\n"
            "Date: February 28, 2025\n\n"
            "FACTS:\n"
            "SocialMedia Corp collected user behavioral data through third-party tracking pixels "
            "embedded in partner websites. Users who opted out of data sale on SocialMedia's "
            "platform continued to have their data collected through these pixels. The "
            "DataPrivacy Alliance brought a representative action under CCPA Section 1798.150.\n\n"
            "ISSUE:\n"
            "Whether third-party tracking pixel data collection constitutes a 'sale' of personal "
            "information under CCPA when the consumer has exercised their opt-out right on the "
            "collecting entity's platform.\n\n"
            "HOLDING:\n"
            "The court held that the tracking pixel data collection constituted a 'sale' under "
            "CCPA's broad definition, and SocialMedia Corp's opt-out mechanism was inadequate "
            "because it did not extend to third-party collection channels.\n\n"
            "REASONING:\n"
            "CCPA defines 'sale' as making personal information available to a third party for "
            "monetary or other valuable consideration. The tracking pixels transmitted user "
            "behavioral data to SocialMedia Corp's servers, which was then used for targeted "
            "advertising — constituting valuable consideration. The opt-out mechanism's failure "
            "to cover third-party channels violated the spirit and letter of CCPA Section "
            "1798.120(a), which requires businesses to respect opt-out requests across all "
            "collection methods.\n\n"
            "SIGNIFICANCE:\n"
            "Companies must ensure opt-out mechanisms cover ALL data collection channels, "
            "including third-party integrations. Privacy compliance programs should: "
            "(1) inventory all data collection touchpoints including third-party pixels and "
            "SDKs, (2) implement centralized consent management that propagates to all channels, "
            "(3) conduct regular audits of third-party data sharing, and (4) maintain "
            "documentation of opt-out implementation across all collection methods."
        ),
    },
    {
        "title": "WorkForce Inc. v. TalentAI — Employment Discrimination via AI Screening",
        "court": "U.S. District Court, Eastern District of Virginia",
        "date": "2025-05-30",
        "docket": "Case No. 1:25-cv-00234",
        "topic": "employment_law",
        "body": (
            "CASE BRIEF\n\n"
            "Caption: WorkForce Inc. v. TalentAI Systems Corp.\n"
            "Court: U.S. District Court, Eastern District of Virginia\n"
            "Docket: Case No. 1:25-cv-00234\n"
            "Date: May 30, 2025\n\n"
            "FACTS:\n"
            "WorkForce used TalentAI's resume screening system to filter job applicants. An "
            "EEOC investigation revealed the system systematically ranked candidates from "
            "certain universities lower, correlating with race and socioeconomic status. "
            "TalentAI's model used 'university prestige scores' as a feature, which served "
            "as a proxy for protected characteristics.\n\n"
            "ISSUE:\n"
            "Whether an employer using a third-party AI screening tool bears liability under "
            "Title VII for disparate impact caused by the tool's algorithmic bias, and whether "
            "the AI vendor shares liability.\n\n"
            "HOLDING:\n"
            "The court held that WorkForce bore primary liability as the employer making hiring "
            "decisions, regardless of the AI tool's role. TalentAI bore secondary liability "
            "as an 'employment agency' under Title VII Section 703(b) because it participated "
            "in the selection process.\n\n"
            "REASONING:\n"
            "Under Griggs v. Duke Power Co., facially neutral practices that produce disparate "
            "impact violate Title VII unless justified by business necessity. The university "
            "prestige score was facially neutral but produced discriminatory outcomes. WorkForce "
            "could not delegate its Title VII obligations to a vendor. TalentAI qualified as an "
            "employment agency because it 'procured' employees for WorkForce by filtering and "
            "ranking candidates.\n\n"
            "SIGNIFICANCE:\n"
            "Employers using AI hiring tools must: (1) conduct adverse impact analyses before "
            "deployment, (2) validate that model features do not serve as proxies for protected "
            "characteristics, (3) maintain human oversight of AI-generated rankings, and "
            "(4) include indemnification and bias audit provisions in vendor contracts. AI "
            "vendors should proactively test for disparate impact and provide bias audit reports."
        ),
    },
]

CONTRACT_TEMPLATES = [
    {
        "title": "Master SaaS Subscription Agreement — Standard Terms",
        "doc_type": "saas_agreement",
        "date": "2025-01-01",
        "body": (
            "MASTER SAAS SUBSCRIPTION AGREEMENT\n\n"
            "This Master SaaS Subscription Agreement ('Agreement') is entered into as of the "
            "Effective Date set forth in the applicable Order Form.\n\n"
            "1. DEFINITIONS\n\n"
            "1.1 'Service' means the cloud-based software application described in the Order Form.\n"
            "1.2 'Subscription Term' means the period specified in the Order Form during which "
            "Customer may access the Service.\n"
            "1.3 'Customer Data' means all data submitted by Customer to the Service.\n"
            "1.4 'SLA' means the Service Level Agreement attached as Exhibit A.\n\n"
            "2. SERVICE ACCESS AND USE\n\n"
            "2.1 Grant of Access. Subject to the terms of this Agreement, Provider grants Customer "
            "a non-exclusive, non-transferable right to access and use the Service during the "
            "Subscription Term for Customer's internal business purposes.\n\n"
            "2.2 Usage Limits. Customer's use is limited to the number of authorized users, "
            "storage capacity, and API call volumes specified in the Order Form.\n\n"
            "2.3 Acceptable Use. Customer shall not: (a) sublicense or resell the Service, "
            "(b) reverse engineer or decompile the Service, (c) use the Service to develop a "
            "competing product, or (d) transmit malicious code through the Service.\n\n"
            "3. SERVICE LEVELS AND SUPPORT\n\n"
            "3.1 Uptime Commitment. Provider shall maintain Service availability of 99.9% "
            "measured monthly, excluding scheduled maintenance windows.\n\n"
            "3.2 Service Credits. If Provider fails to meet the uptime commitment, Customer "
            "shall receive service credits as specified in the SLA. Service credits are "
            "Customer's sole and exclusive remedy for downtime, except in cases of gross "
            "negligence or willful misconduct by Provider.\n\n"
            "3.3 Support. Provider shall provide technical support during business hours "
            "(8 AM - 8 PM ET, Monday through Friday) with response times as specified in the SLA.\n\n"
            "4. DATA PROTECTION\n\n"
            "4.1 Customer Data Ownership. Customer retains all rights in Customer Data. Provider "
            "acquires no rights in Customer Data except as necessary to provide the Service.\n\n"
            "4.2 Security. Provider shall implement and maintain administrative, physical, and "
            "technical safeguards consistent with industry standards (SOC 2 Type II, ISO 27001) "
            "to protect Customer Data.\n\n"
            "4.3 Data Processing Agreement. The parties shall execute a Data Processing Agreement "
            "substantially in the form attached as Exhibit B, incorporating Standard Contractual "
            "Clauses where applicable.\n\n"
            "5. INDEMNIFICATION\n\n"
            "5.1 Provider Indemnification. Provider shall indemnify Customer against third-party "
            "claims alleging that the Service infringes intellectual property rights, provided "
            "Customer gives prompt notice and cooperates in the defense.\n\n"
            "5.2 Customer Indemnification. Customer shall indemnify Provider against claims "
            "arising from Customer's use of the Service in violation of this Agreement or "
            "applicable law.\n\n"
            "6. LIMITATION OF LIABILITY\n\n"
            "6.1 Cap. Each party's total aggregate liability under this Agreement shall not "
            "exceed the fees paid or payable in the 12 months preceding the claim.\n\n"
            "6.2 Exclusions from Cap. The liability cap does not apply to: (a) indemnification "
            "obligations, (b) breach of confidentiality, (c) willful misconduct or gross "
            "negligence, or (d) Provider's data breach obligations.\n\n"
            "6.3 Consequential Damages Waiver. Neither party shall be liable for indirect, "
            "incidental, special, or consequential damages, except for breaches of "
            "confidentiality or data protection obligations."
        ),
    },
    {
        "title": "Mutual Non-Disclosure Agreement — Bilateral",
        "doc_type": "nda",
        "date": "2025-02-15",
        "body": (
            "MUTUAL NON-DISCLOSURE AGREEMENT\n\n"
            "This Mutual Non-Disclosure Agreement ('NDA') is entered into between the parties "
            "identified in the signature block below ('Disclosing Party' and 'Receiving Party,' "
            "each a 'Party' and collectively the 'Parties').\n\n"
            "1. DEFINITION OF CONFIDENTIAL INFORMATION\n\n"
            "1.1 'Confidential Information' means any non-public information disclosed by either "
            "Party, whether orally, in writing, or electronically, that is designated as "
            "confidential or that a reasonable person would understand to be confidential given "
            "the nature of the information and circumstances of disclosure.\n\n"
            "1.2 Confidential Information includes but is not limited to: trade secrets, business "
            "plans, financial data, customer lists, technical specifications, source code, "
            "algorithms, product roadmaps, and personnel information.\n\n"
            "1.3 Exclusions. Confidential Information does not include information that: "
            "(a) is or becomes publicly available without breach of this NDA, (b) was known to "
            "the Receiving Party prior to disclosure, (c) is independently developed without "
            "use of Confidential Information, or (d) is rightfully received from a third party "
            "without restriction.\n\n"
            "2. OBLIGATIONS\n\n"
            "2.1 The Receiving Party shall: (a) use Confidential Information solely for the "
            "Purpose defined below, (b) protect Confidential Information with at least the same "
            "degree of care used for its own confidential information (but no less than "
            "reasonable care), and (c) limit disclosure to employees and contractors with a "
            "need to know who are bound by confidentiality obligations at least as protective.\n\n"
            "2.2 Purpose. The Parties are exchanging Confidential Information solely to evaluate "
            "a potential business relationship ('Purpose').\n\n"
            "3. TERM AND TERMINATION\n\n"
            "3.1 This NDA is effective for two (2) years from the Effective Date.\n"
            "3.2 Confidentiality obligations survive termination for three (3) years, except "
            "for trade secrets which are protected indefinitely.\n"
            "3.3 Upon termination, each Party shall return or destroy Confidential Information "
            "and certify destruction in writing within thirty (30) days.\n\n"
            "4. COMPELLED DISCLOSURE\n\n"
            "4.1 If compelled by law to disclose Confidential Information, the Receiving Party "
            "shall: (a) provide prompt written notice to the Disclosing Party, (b) cooperate "
            "with efforts to obtain protective order, and (c) disclose only the minimum "
            "information required."
        ),
    },
    {
        "title": "Professional Services Agreement — Technology Consulting",
        "doc_type": "services_agreement",
        "date": "2025-03-10",
        "body": (
            "PROFESSIONAL SERVICES AGREEMENT\n\n"
            "This Professional Services Agreement ('Agreement') governs the provision of "
            "technology consulting services.\n\n"
            "1. SCOPE OF SERVICES\n\n"
            "1.1 Provider shall perform the services described in each Statement of Work ('SOW') "
            "executed by the Parties. Each SOW shall specify: deliverables, timeline, acceptance "
            "criteria, fees, and assigned personnel.\n\n"
            "1.2 Change Orders. Changes to an SOW require written agreement. Provider shall "
            "submit a Change Order specifying the impact on timeline, fees, and deliverables.\n\n"
            "2. INTELLECTUAL PROPERTY\n\n"
            "2.1 Work Product. All deliverables created specifically for Client under an SOW "
            "('Work Product') shall be owned by Client upon full payment.\n\n"
            "2.2 Pre-Existing IP. Provider retains ownership of all pre-existing intellectual "
            "property. If Provider incorporates Pre-Existing IP into Work Product, Provider "
            "grants Client a perpetual, non-exclusive, royalty-free license to use such "
            "Pre-Existing IP solely as embedded in the Work Product.\n\n"
            "2.3 Disclosure Obligation. Provider shall identify all Pre-Existing IP incorporated "
            "into Work Product in writing before delivery. Failure to disclose grants Client "
            "a broader license as reasonably necessary for Client's intended use.\n\n"
            "3. WARRANTIES\n\n"
            "3.1 Provider warrants that: (a) services will be performed in a professional and "
            "workmanlike manner consistent with industry standards, (b) deliverables will "
            "conform to the specifications in the applicable SOW for thirty (30) days after "
            "acceptance, and (c) Provider has the right to grant the licenses described herein.\n\n"
            "3.2 Warranty Remedy. Provider shall re-perform non-conforming services at no "
            "additional cost. If re-performance fails, Client may terminate the affected SOW "
            "and receive a refund of fees paid for the non-conforming services.\n\n"
            "4. LIMITATION OF LIABILITY\n\n"
            "4.1 Each party's liability is limited to the fees paid under the applicable SOW "
            "in the twelve (12) months preceding the claim.\n\n"
            "4.2 Neither party shall be liable for lost profits, lost data, or consequential "
            "damages, except for breaches of Section 2 (IP) or confidentiality obligations."
        ),
    },
    {
        "title": "Data Processing Agreement — GDPR Compliant",
        "doc_type": "dpa",
        "date": "2025-04-01",
        "body": (
            "DATA PROCESSING AGREEMENT\n\n"
            "This Data Processing Agreement ('DPA') supplements the Master Agreement between "
            "Controller and Processor.\n\n"
            "1. DEFINITIONS\n\n"
            "1.1 'Personal Data' means any information relating to an identified or identifiable "
            "natural person as defined in GDPR Article 4(1).\n"
            "1.2 'Processing' means any operation performed on Personal Data as defined in "
            "GDPR Article 4(2).\n"
            "1.3 'Sub-processor' means any third party engaged by Processor to process Personal "
            "Data on behalf of Controller.\n\n"
            "2. PROCESSING INSTRUCTIONS\n\n"
            "2.1 Processor shall process Personal Data only on documented instructions from "
            "Controller, including transfers to third countries, unless required by EU or Member "
            "State law.\n\n"
            "2.2 The subject matter, duration, nature, and purpose of processing, types of "
            "Personal Data, and categories of data subjects are described in Annex 1.\n\n"
            "3. SECURITY MEASURES\n\n"
            "3.1 Processor shall implement appropriate technical and organizational measures "
            "as described in GDPR Article 32, including: (a) encryption of Personal Data in "
            "transit and at rest, (b) access controls and authentication, (c) regular security "
            "testing, and (d) incident response procedures.\n\n"
            "3.2 Processor shall maintain SOC 2 Type II certification and make audit reports "
            "available to Controller upon request.\n\n"
            "4. SUB-PROCESSING\n\n"
            "4.1 Processor shall not engage Sub-processors without prior written authorization "
            "from Controller. Processor shall maintain a current list of Sub-processors.\n\n"
            "4.2 Processor shall impose data protection obligations on Sub-processors that are "
            "no less protective than those in this DPA.\n\n"
            "5. DATA SUBJECT RIGHTS\n\n"
            "5.1 Processor shall assist Controller in responding to data subject requests "
            "exercising rights under GDPR Chapter III (access, rectification, erasure, "
            "portability, restriction, objection).\n\n"
            "6. BREACH NOTIFICATION\n\n"
            "6.1 Processor shall notify Controller of any Personal Data breach without undue "
            "delay and no later than 48 hours after becoming aware of the breach.\n\n"
            "6.2 Notification shall include: nature of the breach, categories and approximate "
            "number of data subjects affected, likely consequences, and measures taken or "
            "proposed to address the breach."
        ),
    },
    {
        "title": "Software License Agreement — Enterprise On-Premise",
        "doc_type": "license_agreement",
        "date": "2025-05-20",
        "body": (
            "SOFTWARE LICENSE AGREEMENT\n\n"
            "This Software License Agreement ('Agreement') governs the licensing of the "
            "software product identified in the Order Form.\n\n"
            "1. LICENSE GRANT\n\n"
            "1.1 Subject to the terms of this Agreement, Licensor grants Licensee a "
            "non-exclusive, non-transferable, perpetual license to install and use the Software "
            "on Licensee's premises for Licensee's internal business purposes.\n\n"
            "1.2 The license is limited to the number of users, instances, and locations "
            "specified in the Order Form.\n\n"
            "2. RESTRICTIONS\n\n"
            "2.1 Licensee shall not: (a) copy the Software except for reasonable backup "
            "purposes, (b) modify, adapt, or create derivative works, (c) reverse engineer, "
            "decompile, or disassemble the Software, (d) sublicense, rent, or lease the "
            "Software, or (e) remove proprietary notices.\n\n"
            "3. MAINTENANCE AND SUPPORT\n\n"
            "3.1 During the Maintenance Term, Licensor shall provide: (a) bug fixes and "
            "security patches, (b) minor version updates, (c) technical support via email "
            "and phone during business hours.\n\n"
            "3.2 Major version upgrades are available at additional cost as specified in the "
            "then-current price list.\n\n"
            "4. WARRANTIES\n\n"
            "4.1 Licensor warrants that the Software will substantially conform to the "
            "documentation for ninety (90) days from delivery ('Warranty Period').\n\n"
            "4.2 Licensor's sole obligation for breach of warranty is to repair or replace "
            "the non-conforming Software. If repair or replacement is not commercially "
            "reasonable, Licensor shall refund the license fee.\n\n"
            "5. INTELLECTUAL PROPERTY\n\n"
            "5.1 Licensor retains all intellectual property rights in the Software. This "
            "Agreement does not transfer ownership of the Software to Licensee.\n\n"
            "5.2 Licensor shall indemnify Licensee against third-party claims that the "
            "Software infringes valid intellectual property rights."
        ),
    },
    {
        "title": "Cloud Infrastructure Services Agreement",
        "doc_type": "cloud_services",
        "date": "2025-06-15",
        "body": (
            "CLOUD INFRASTRUCTURE SERVICES AGREEMENT\n\n"
            "This Agreement governs the provision of cloud infrastructure services.\n\n"
            "1. SERVICE DESCRIPTION\n\n"
            "1.1 Provider shall make available cloud computing resources including compute "
            "instances, storage, networking, and managed services as specified in the Order Form.\n\n"
            "1.2 Service Regions. Services are available in the regions specified in the Order "
            "Form. Data residency requirements shall be documented in the DPA.\n\n"
            "2. SERVICE LEVELS\n\n"
            "2.1 Availability. Provider commits to 99.99% monthly availability for production "
            "workloads across multiple availability zones.\n\n"
            "2.2 Performance. Provider shall meet the latency and throughput benchmarks "
            "specified in Exhibit A for each service tier.\n\n"
            "2.3 Disaster Recovery. Provider shall maintain disaster recovery capabilities "
            "with RPO of 1 hour and RTO of 4 hours for Tier 1 services.\n\n"
            "3. SECURITY AND COMPLIANCE\n\n"
            "3.1 Provider maintains: SOC 2 Type II, ISO 27001, ISO 27017, ISO 27018, "
            "PCI DSS Level 1, HIPAA eligibility, and FedRAMP authorization.\n\n"
            "3.2 Shared Responsibility. Security responsibilities are allocated per the "
            "shared responsibility model documented in Exhibit B.\n\n"
            "4. DATA GOVERNANCE\n\n"
            "4.1 Customer Data remains Customer's property. Provider processes Customer Data "
            "solely to provide the Services.\n\n"
            "4.2 Data Portability. Upon termination, Provider shall make Customer Data "
            "available for export in standard formats for sixty (60) days.\n\n"
            "4.3 Data Deletion. After the export period, Provider shall securely delete "
            "Customer Data and certify deletion in writing."
        ),
    },
    {
        "title": "Vendor Risk Assessment Questionnaire — Standard",
        "doc_type": "risk_assessment",
        "date": "2025-07-01",
        "body": (
            "VENDOR RISK ASSESSMENT QUESTIONNAIRE\n\n"
            "This questionnaire must be completed by all vendors processing confidential "
            "or regulated data.\n\n"
            "SECTION 1: ORGANIZATIONAL SECURITY\n\n"
            "1.1 Does your organization maintain a formal information security program? "
            "Describe the framework (ISO 27001, NIST CSF, SOC 2, etc.).\n\n"
            "1.2 Do you have a dedicated Chief Information Security Officer (CISO) or "
            "equivalent role? Provide reporting structure.\n\n"
            "1.3 Describe your security awareness training program. How frequently is "
            "training conducted? Is it mandatory for all employees?\n\n"
            "SECTION 2: ACCESS CONTROLS\n\n"
            "2.1 Describe your access control model (RBAC, ABAC, etc.).\n"
            "2.2 How do you manage privileged access? Do you use PAM solutions?\n"
            "2.3 Describe your authentication mechanisms. Do you require MFA for all access?\n"
            "2.4 How frequently do you review access permissions?\n\n"
            "SECTION 3: DATA PROTECTION\n\n"
            "3.1 Describe encryption standards for data at rest and in transit.\n"
            "3.2 How do you manage encryption keys? Do you use HSMs?\n"
            "3.3 Describe your data classification scheme.\n"
            "3.4 How do you handle data retention and secure deletion?\n\n"
            "SECTION 4: INCIDENT RESPONSE\n\n"
            "4.1 Describe your incident response plan. How frequently is it tested?\n"
            "4.2 What is your breach notification timeline?\n"
            "4.3 Do you carry cyber insurance? Provide coverage details.\n\n"
            "SECTION 5: BUSINESS CONTINUITY\n\n"
            "5.1 Describe your business continuity and disaster recovery plans.\n"
            "5.2 What are your RPO and RTO targets?\n"
            "5.3 How frequently do you test DR procedures?\n\n"
            "SECTION 6: COMPLIANCE\n\n"
            "6.1 List all compliance certifications and audit reports available.\n"
            "6.2 Describe your approach to regulatory compliance (GDPR, CCPA, HIPAA, SOX).\n"
            "6.3 Have you experienced any regulatory enforcement actions in the past 3 years?"
        ),
    },
    {
        "title": "Indemnification Clause Library — Technology Agreements",
        "doc_type": "clause_library",
        "date": "2025-08-01",
        "body": (
            "INDEMNIFICATION CLAUSE LIBRARY\n\n"
            "Standard indemnification clauses for use in technology agreements. Select and "
            "customize based on deal specifics.\n\n"
            "CLAUSE A: STANDARD MUTUAL INDEMNIFICATION\n\n"
            "Each party ('Indemnifying Party') shall defend, indemnify, and hold harmless the "
            "other party ('Indemnified Party') from and against any third-party claims, damages, "
            "losses, and expenses (including reasonable attorneys' fees) arising from: "
            "(a) the Indemnifying Party's breach of this Agreement, (b) the Indemnifying Party's "
            "negligence or willful misconduct, or (c) the Indemnifying Party's violation of "
            "applicable law.\n\n"
            "CLAUSE B: IP INDEMNIFICATION (VENDOR)\n\n"
            "Vendor shall defend, indemnify, and hold harmless Customer from any third-party "
            "claim that the Service or Deliverables infringe any valid patent, copyright, or "
            "trade secret ('IP Claim'). Vendor's obligations are conditioned on: (i) prompt "
            "written notice, (ii) sole control of the defense, and (iii) Customer's reasonable "
            "cooperation. If an IP Claim is made or reasonably anticipated, Vendor may at its "
            "option: (a) obtain the right to continue using the infringing material, "
            "(b) replace or modify the material to be non-infringing, or (c) if neither (a) nor "
            "(b) is commercially reasonable, terminate the affected service and refund prepaid "
            "fees for the unused portion.\n\n"
            "CLAUSE C: DATA BREACH INDEMNIFICATION\n\n"
            "Provider shall indemnify Customer for all costs and damages arising from a data "
            "breach caused by Provider's failure to comply with its security obligations under "
            "this Agreement, including: (a) notification costs, (b) credit monitoring services, "
            "(c) regulatory fines and penalties, (d) forensic investigation costs, and "
            "(e) reasonable attorneys' fees. This indemnification obligation is not subject to "
            "the general limitation of liability.\n\n"
            "CLAUSE D: AI/ML MODEL INDEMNIFICATION\n\n"
            "Vendor shall indemnify Customer against claims arising from: (a) algorithmic bias "
            "in the Model that results in discriminatory outcomes in violation of applicable law, "
            "(b) the Model's use of training data that infringes third-party rights, or "
            "(c) the Model producing outputs that violate applicable regulations. Vendor's "
            "obligation is limited to claims arising from the Model as delivered, not from "
            "Customer's modifications or use outside the documented intended purpose."
        ),
    },
    {
        "title": "Service Level Agreement — Enterprise SaaS",
        "doc_type": "sla",
        "date": "2025-09-01",
        "body": (
            "SERVICE LEVEL AGREEMENT\n\n"
            "This SLA is incorporated into and forms part of the Master Agreement.\n\n"
            "1. AVAILABILITY\n\n"
            "1.1 Monthly Uptime Percentage. Provider shall maintain a Monthly Uptime Percentage "
            "of at least 99.9% for the Service.\n\n"
            "1.2 Calculation. Monthly Uptime Percentage = ((Total Minutes in Month - Downtime "
            "Minutes) / Total Minutes in Month) x 100.\n\n"
            "1.3 Exclusions. Downtime does not include: (a) scheduled maintenance (with 72 hours "
            "notice), (b) force majeure events, (c) Customer's internet connectivity issues, "
            "(d) Customer's misuse of the Service.\n\n"
            "2. SERVICE CREDITS\n\n"
            "2.1 Credit Schedule:\n"
            "  - 99.0% to 99.9%: 10% credit of monthly fee\n"
            "  - 95.0% to 99.0%: 25% credit of monthly fee\n"
            "  - Below 95.0%: 50% credit of monthly fee\n\n"
            "2.2 Credit Request. Customer must request credits within 30 days of the incident.\n\n"
            "2.3 Maximum Credits. Total credits in any month shall not exceed 50% of monthly fee.\n\n"
            "3. SUPPORT TIERS\n\n"
            "3.1 Severity 1 (Critical): Service is down or major functionality is unavailable. "
            "Response: 15 minutes. Resolution target: 4 hours.\n\n"
            "3.2 Severity 2 (High): Significant functionality is impaired. Response: 1 hour. "
            "Resolution target: 8 hours.\n\n"
            "3.3 Severity 3 (Medium): Minor functionality issue with workaround available. "
            "Response: 4 hours. Resolution target: 2 business days.\n\n"
            "3.4 Severity 4 (Low): General inquiry or enhancement request. Response: 1 business "
            "day. Resolution target: best effort.\n\n"
            "4. PERFORMANCE METRICS\n\n"
            "4.1 API Response Time: P95 latency shall not exceed 200ms for standard API calls.\n"
            "4.2 Throughput: Service shall support the transaction volumes specified in the "
            "Order Form without degradation.\n"
            "4.3 Data Durability: 99.999999999% (11 nines) for stored data."
        ),
    },
    {
        "title": "Acceptable Use Policy — Cloud Platform",
        "doc_type": "aup",
        "date": "2025-10-01",
        "body": (
            "ACCEPTABLE USE POLICY\n\n"
            "This Acceptable Use Policy ('AUP') governs Customer's use of the Platform.\n\n"
            "1. PERMITTED USE\n\n"
            "1.1 Customer may use the Platform for lawful business purposes consistent with "
            "the Master Agreement and applicable Order Forms.\n\n"
            "2. PROHIBITED ACTIVITIES\n\n"
            "2.1 Customer shall not use the Platform to:\n"
            "(a) Violate any applicable law, regulation, or third-party rights\n"
            "(b) Transmit malware, viruses, or other malicious code\n"
            "(c) Conduct unauthorized vulnerability scanning or penetration testing\n"
            "(d) Send unsolicited bulk communications (spam)\n"
            "(e) Mine cryptocurrency without prior written approval\n"
            "(f) Store or process data subject to ITAR or EAR without appropriate authorization\n"
            "(g) Engage in activities that could damage, disable, or impair the Platform\n"
            "(h) Attempt to gain unauthorized access to other customers' resources\n\n"
            "3. RESOURCE LIMITS\n\n"
            "3.1 Customer shall not exceed the resource quotas specified in the Order Form "
            "without prior approval.\n\n"
            "3.2 Provider reserves the right to throttle or suspend access if Customer's usage "
            "materially exceeds agreed limits or threatens Platform stability.\n\n"
            "4. CONTENT RESPONSIBILITY\n\n"
            "4.1 Customer is solely responsible for all content stored on or transmitted through "
            "the Platform.\n\n"
            "4.2 Customer shall implement appropriate content moderation for user-generated "
            "content hosted on the Platform.\n\n"
            "5. ENFORCEMENT\n\n"
            "5.1 Provider may investigate suspected violations and take remedial action including "
            "suspension or termination of access.\n\n"
            "5.2 Provider shall provide reasonable notice before enforcement action except in "
            "cases of imminent harm or legal requirement."
        ),
    },
]

REGULATORY_MEMOS = [
    {
        "title": "GDPR Compliance Framework — Data Processing Operations",
        "regulation": "GDPR",
        "date": "2025-01-15",
        "body": (
            "INTERNAL MEMORANDUM — CONFIDENTIAL\n\n"
            "TO: All Practice Groups\n"
            "FROM: Compliance Department\n"
            "RE: GDPR Compliance Framework for Client Data Processing\n"
            "DATE: January 15, 2025\n\n"
            "PURPOSE:\n"
            "This memo establishes the firm's compliance framework for processing personal data "
            "of EU data subjects under the General Data Protection Regulation (GDPR).\n\n"
            "1. LAWFUL BASIS FOR PROCESSING\n\n"
            "All processing of EU personal data must have a documented lawful basis under "
            "Article 6(1). For our operations, the primary bases are:\n"
            "- Legitimate interest (Article 6(1)(f)): Legal research and case preparation\n"
            "- Contractual necessity (Article 6(1)(b)): Client engagement and service delivery\n"
            "- Legal obligation (Article 6(1)(c)): Regulatory reporting and compliance\n\n"
            "A Legitimate Interest Assessment (LIA) must be completed before relying on "
            "legitimate interest. Templates are available on the compliance portal.\n\n"
            "2. DATA SUBJECT RIGHTS\n\n"
            "We must respond to data subject requests within 30 days. The compliance team "
            "coordinates responses. Key rights include: access (Art. 15), rectification (Art. 16), "
            "erasure (Art. 17), restriction (Art. 18), portability (Art. 20), and objection (Art. 21).\n\n"
            "3. CROSS-BORDER TRANSFERS\n\n"
            "Following the Schrems II decision, transfers to non-adequate countries require "
            "Standard Contractual Clauses (SCCs) plus a Transfer Impact Assessment (TIA). "
            "The EU-US Data Privacy Framework is available for certified US recipients.\n\n"
            "4. DATA PROTECTION IMPACT ASSESSMENTS\n\n"
            "A DPIA is required for: (a) large-scale processing of special category data, "
            "(b) systematic monitoring of public areas, (c) automated decision-making with "
            "legal effects, and (d) new technology deployments processing personal data.\n\n"
            "5. BREACH NOTIFICATION\n\n"
            "Personal data breaches must be reported to the DPO within 4 hours of discovery. "
            "The DPO will assess whether notification to the supervisory authority (within 72 "
            "hours) and/or data subjects is required under Articles 33 and 34."
        ),
    },
    {
        "title": "SOX Compliance — IT General Controls for Legal Tech Systems",
        "regulation": "SOX",
        "date": "2025-02-20",
        "body": (
            "INTERNAL MEMORANDUM — CONFIDENTIAL\n\n"
            "TO: IT Department, Finance Department\n"
            "FROM: Risk Management\n"
            "RE: SOX Compliance Requirements for Legal Technology Systems\n"
            "DATE: February 20, 2025\n\n"
            "PURPOSE:\n"
            "This memo outlines IT General Controls (ITGCs) required for SOX compliance "
            "across the firm's legal technology systems that impact financial reporting.\n\n"
            "1. IN-SCOPE SYSTEMS\n\n"
            "The following systems are in scope for SOX ITGCs:\n"
            "- Billing and time tracking system (iManage)\n"
            "- Trust account management system\n"
            "- Client matter management system\n"
            "- Document management system (NetDocuments)\n"
            "- Financial reporting and GL system\n\n"
            "2. ACCESS CONTROL REQUIREMENTS\n\n"
            "2.1 User access reviews must be performed quarterly for all in-scope systems.\n"
            "2.2 Privileged access must be reviewed monthly.\n"
            "2.3 Segregation of duties must be enforced — no single individual should have "
            "both data entry and approval authority.\n"
            "2.4 Terminated employee access must be revoked within 24 hours.\n\n"
            "3. CHANGE MANAGEMENT\n\n"
            "3.1 All changes to in-scope systems must follow the formal change management "
            "process: request → review → approve → test → deploy → verify.\n"
            "3.2 Emergency changes require post-implementation review within 5 business days.\n"
            "3.3 Change logs must be retained for 7 years.\n\n"
            "4. BACKUP AND RECOVERY\n\n"
            "4.1 Daily backups for all in-scope systems.\n"
            "4.2 Quarterly backup restoration tests.\n"
            "4.3 Off-site backup storage with encryption.\n\n"
            "5. AUDIT TRAIL\n\n"
            "5.1 All in-scope systems must maintain comprehensive audit logs.\n"
            "5.2 Logs must capture: user identity, timestamp, action performed, and data affected.\n"
            "5.3 Audit logs must be tamper-evident and retained for 7 years."
        ),
    },
    {
        "title": "HIPAA Compliance — Handling Protected Health Information",
        "regulation": "HIPAA",
        "date": "2025-03-25",
        "body": (
            "INTERNAL MEMORANDUM — CONFIDENTIAL\n\n"
            "TO: Healthcare Practice Group, Litigation Department\n"
            "FROM: Compliance Department\n"
            "RE: HIPAA Compliance Requirements for PHI in Legal Matters\n"
            "DATE: March 25, 2025\n\n"
            "PURPOSE:\n"
            "This memo provides guidance on handling Protected Health Information (PHI) received "
            "in connection with healthcare litigation and regulatory matters.\n\n"
            "1. WHEN HIPAA APPLIES TO LAW FIRMS\n\n"
            "Law firms are generally not covered entities under HIPAA. However, we may be "
            "business associates when we: (a) receive PHI from covered entity clients, "
            "(b) perform functions involving PHI on behalf of covered entities, or "
            "(c) provide legal services that require access to PHI.\n\n"
            "2. BUSINESS ASSOCIATE AGREEMENTS\n\n"
            "Before receiving PHI, ensure a Business Associate Agreement (BAA) is in place. "
            "The BAA must specify: permitted uses, safeguard requirements, breach notification "
            "obligations, and return/destruction requirements.\n\n"
            "3. MINIMUM NECESSARY STANDARD\n\n"
            "Request and use only the minimum PHI necessary for the legal matter. De-identify "
            "PHI when possible using Safe Harbor (remove 18 identifiers) or Expert Determination "
            "methods.\n\n"
            "4. SECURITY REQUIREMENTS\n\n"
            "4.1 PHI must be stored in encrypted systems (AES-256 at rest, TLS 1.2+ in transit).\n"
            "4.2 Access to PHI must be limited to authorized personnel on the matter.\n"
            "4.3 PHI must not be stored on personal devices or unencrypted removable media.\n"
            "4.4 Physical PHI documents must be stored in locked cabinets with access logs.\n\n"
            "5. BREACH RESPONSE\n\n"
            "Any suspected PHI breach must be reported to the Privacy Officer within 2 hours. "
            "HIPAA requires notification to the covered entity, which then notifies HHS and "
            "affected individuals. Breaches affecting 500+ individuals require media notification."
        ),
    },
    {
        "title": "AI Governance Framework — Responsible AI Deployment",
        "regulation": "AI_GOVERNANCE",
        "date": "2025-04-10",
        "body": (
            "INTERNAL MEMORANDUM — CONFIDENTIAL\n\n"
            "TO: All Practice Groups, IT Department\n"
            "FROM: Innovation Committee\n"
            "RE: AI Governance Framework for Legal AI Tools\n"
            "DATE: April 10, 2025\n\n"
            "PURPOSE:\n"
            "This memo establishes governance requirements for the firm's use of AI tools in "
            "legal practice, including large language models, document review systems, and "
            "predictive analytics.\n\n"
            "1. APPROVED AI TOOLS\n\n"
            "Only AI tools approved by the Innovation Committee may be used for client work. "
            "Currently approved tools: (a) firm-deployed LLM instance (Azure OpenAI), "
            "(b) Relativity AI for document review, (c) Kira Systems for contract analysis, "
            "(d) internal legal research assistant (Bedrock-powered).\n\n"
            "2. PROHIBITED USES\n\n"
            "AI tools must NOT be used to: (a) make final legal judgments without attorney "
            "review, (b) generate court filings without human verification, (c) process client "
            "data through non-approved external AI services, (d) replace required human "
            "supervision in regulated activities.\n\n"
            "3. QUALITY ASSURANCE\n\n"
            "3.1 All AI-generated content must be reviewed by a qualified attorney before use.\n"
            "3.2 AI-assisted research must be verified against primary sources.\n"
            "3.3 AI-generated contract language must be reviewed for jurisdiction-specific "
            "requirements.\n\n"
            "4. CLIENT DISCLOSURE\n\n"
            "4.1 Clients must be informed when AI tools are used in their matters.\n"
            "4.2 Engagement letters should include AI usage disclosure language.\n"
            "4.3 Billing entries should distinguish AI-assisted work from traditional work.\n\n"
            "5. DATA HANDLING\n\n"
            "5.1 Client data must not be used to train AI models without explicit consent.\n"
            "5.2 AI tool outputs containing client information must be treated as confidential.\n"
            "5.3 AI interaction logs must be retained as part of the matter file.\n\n"
            "6. RISK ASSESSMENT\n\n"
            "Before deploying a new AI tool, complete the AI Risk Assessment form covering: "
            "accuracy validation, bias testing, data privacy impact, ethical considerations, "
            "and professional responsibility implications."
        ),
    },
    {
        "title": "CCPA/CPRA Compliance — California Privacy Rights",
        "regulation": "CCPA",
        "date": "2025-05-15",
        "body": (
            "INTERNAL MEMORANDUM — CONFIDENTIAL\n\n"
            "TO: All Practice Groups\n"
            "FROM: Privacy Office\n"
            "RE: CCPA/CPRA Compliance Requirements\n"
            "DATE: May 15, 2025\n\n"
            "PURPOSE:\n"
            "This memo outlines compliance requirements under the California Consumer Privacy "
            "Act (CCPA) as amended by the California Privacy Rights Act (CPRA).\n\n"
            "1. APPLICABILITY\n\n"
            "CCPA applies to businesses that: (a) have annual gross revenue exceeding $25 million, "
            "(b) buy, sell, or share personal information of 100,000+ consumers, or "
            "(c) derive 50%+ of revenue from selling/sharing personal information.\n\n"
            "2. CONSUMER RIGHTS\n\n"
            "California consumers have the right to: (a) know what personal information is "
            "collected, (b) delete personal information, (c) opt out of sale/sharing, "
            "(d) correct inaccurate information, (e) limit use of sensitive personal information, "
            "and (f) non-discrimination for exercising rights.\n\n"
            "3. SENSITIVE PERSONAL INFORMATION\n\n"
            "CPRA adds protections for sensitive PI including: SSN, financial account numbers, "
            "precise geolocation, racial/ethnic origin, religious beliefs, union membership, "
            "biometric data, health information, and sexual orientation.\n\n"
            "4. SERVICE PROVIDER REQUIREMENTS\n\n"
            "When acting as a service provider, we must: (a) process PI only as specified in "
            "the service agreement, (b) not sell or share PI received, (c) assist businesses "
            "in responding to consumer requests, and (d) implement reasonable security measures.\n\n"
            "5. PRIVACY NOTICE REQUIREMENTS\n\n"
            "Our privacy notice must disclose: categories of PI collected, purposes of collection, "
            "categories of third parties with whom PI is shared, consumer rights and how to "
            "exercise them, and retention periods for each category of PI."
        ),
    },
    {
        "title": "Anti-Money Laundering — Client Due Diligence Procedures",
        "regulation": "AML",
        "date": "2025-06-20",
        "body": (
            "INTERNAL MEMORANDUM — CONFIDENTIAL\n\n"
            "TO: All Partners, Client Intake Department\n"
            "FROM: General Counsel\n"
            "RE: Enhanced AML/KYC Due Diligence Procedures\n"
            "DATE: June 20, 2025\n\n"
            "PURPOSE:\n"
            "This memo updates the firm's Anti-Money Laundering (AML) and Know Your Client "
            "(KYC) procedures in response to the Corporate Transparency Act and updated "
            "FinCEN guidance.\n\n"
            "1. CLIENT IDENTIFICATION\n\n"
            "All new client engagements require: (a) government-issued photo ID for individuals, "
            "(b) articles of incorporation and beneficial ownership information for entities, "
            "(c) verification of identity through independent sources, and (d) screening against "
            "OFAC SDN list and other sanctions databases.\n\n"
            "2. BENEFICIAL OWNERSHIP\n\n"
            "Under the Corporate Transparency Act, we must identify all beneficial owners "
            "(25%+ ownership or substantial control) of entity clients. Beneficial ownership "
            "information must be updated annually.\n\n"
            "3. ENHANCED DUE DILIGENCE\n\n"
            "Enhanced procedures apply to: (a) politically exposed persons (PEPs), "
            "(b) clients from high-risk jurisdictions (FATF grey/black list), (c) complex "
            "corporate structures with multiple layers, (d) transactions involving virtual "
            "assets or cryptocurrency, and (e) matters involving unusually large cash transactions.\n\n"
            "4. SUSPICIOUS ACTIVITY REPORTING\n\n"
            "While law firms are not currently required to file SARs, attorneys must report "
            "suspected money laundering to the General Counsel. The attorney-client privilege "
            "does not protect communications made in furtherance of a crime or fraud.\n\n"
            "5. RECORD RETENTION\n\n"
            "All CDD/KYC documentation must be retained for at least 5 years after the "
            "termination of the client relationship."
        ),
    },
    {
        "title": "Export Controls — Technology Transfer Compliance",
        "regulation": "EXPORT_CONTROLS",
        "date": "2025-07-25",
        "body": (
            "INTERNAL MEMORANDUM — CONFIDENTIAL\n\n"
            "TO: Technology Practice Group, International Trade Group\n"
            "FROM: Trade Compliance Office\n"
            "RE: Export Control Compliance for Technology Clients\n"
            "DATE: July 25, 2025\n\n"
            "PURPOSE:\n"
            "This memo provides guidance on export control compliance when advising technology "
            "clients on international transactions.\n\n"
            "1. REGULATORY FRAMEWORK\n\n"
            "Key regulations include: (a) Export Administration Regulations (EAR) administered "
            "by BIS, (b) International Traffic in Arms Regulations (ITAR) administered by DDTC, "
            "(c) OFAC sanctions programs, and (d) EU Dual-Use Regulation.\n\n"
            "2. CLASSIFICATION\n\n"
            "All technology must be classified before export: (a) determine if the item is on "
            "the Commerce Control List (CCL) or US Munitions List (USML), (b) identify the "
            "Export Control Classification Number (ECCN), (c) determine if a license is required "
            "based on destination, end-user, and end-use.\n\n"
            "3. DEEMED EXPORTS\n\n"
            "Release of controlled technology to foreign nationals in the US constitutes a "
            "'deemed export' requiring the same analysis as a physical export. This applies to: "
            "technical data, source code, and technology shared with foreign national employees "
            "or contractors.\n\n"
            "4. CLOUD COMPUTING CONSIDERATIONS\n\n"
            "Storing controlled data in cloud environments raises export control issues: "
            "(a) data center locations may constitute exports, (b) foreign national access to "
            "cloud-hosted data may be deemed exports, (c) encryption does not automatically "
            "exempt data from export controls.\n\n"
            "5. COMPLIANCE PROGRAM ELEMENTS\n\n"
            "Advise clients to implement: (a) written export compliance procedures, "
            "(b) regular training for employees handling controlled items, (c) screening of "
            "all parties against restricted party lists, (d) record keeping for 5 years, and "
            "(e) regular internal audits."
        ),
    },
    {
        "title": "ESG Reporting — SEC Climate Disclosure Requirements",
        "regulation": "ESG",
        "date": "2025-08-30",
        "body": (
            "INTERNAL MEMORANDUM — CONFIDENTIAL\n\n"
            "TO: Securities Practice Group, Corporate Governance Group\n"
            "FROM: ESG Advisory Team\n"
            "RE: SEC Climate-Related Disclosure Requirements\n"
            "DATE: August 30, 2025\n\n"
            "PURPOSE:\n"
            "This memo summarizes the SEC's climate-related disclosure requirements and their "
            "implications for our public company clients.\n\n"
            "1. DISCLOSURE REQUIREMENTS\n\n"
            "Registrants must disclose: (a) climate-related risks that have materially impacted "
            "or are reasonably likely to impact business strategy, (b) governance processes for "
            "managing climate risks, (c) risk management processes for identifying and assessing "
            "climate risks, and (d) targets and goals related to climate risk management.\n\n"
            "2. GREENHOUSE GAS EMISSIONS\n\n"
            "Large accelerated filers must disclose: (a) Scope 1 (direct) emissions, "
            "(b) Scope 2 (indirect from purchased energy) emissions, with attestation by an "
            "independent provider. Scope 3 (value chain) emissions disclosure is currently "
            "not required but may be added in future rulemaking.\n\n"
            "3. FINANCIAL STATEMENT IMPACTS\n\n"
            "Companies must disclose in financial statement footnotes: (a) costs and losses "
            "from severe weather events exceeding 1% of pre-tax income, (b) costs of carbon "
            "offsets and renewable energy credits, and (c) material impacts of transition "
            "activities on financial estimates.\n\n"
            "4. SAFE HARBOR\n\n"
            "Forward-looking climate disclosures are protected by a safe harbor provision, "
            "provided they are accompanied by meaningful cautionary statements and are not "
            "made with actual knowledge of falsity.\n\n"
            "5. TIMELINE\n\n"
            "Large accelerated filers: FY beginning 2025. Accelerated filers: FY beginning "
            "2026. Smaller reporting companies: FY beginning 2027."
        ),
    },
    {
        "title": "Cybersecurity Incident Response — Legal Obligations",
        "regulation": "CYBERSECURITY",
        "date": "2025-09-15",
        "body": (
            "INTERNAL MEMORANDUM — CONFIDENTIAL\n\n"
            "TO: All Practice Groups, IT Security\n"
            "FROM: Incident Response Team\n"
            "RE: Legal Obligations in Cybersecurity Incident Response\n"
            "DATE: September 15, 2025\n\n"
            "PURPOSE:\n"
            "This memo outlines the legal obligations triggered by cybersecurity incidents "
            "and the firm's response procedures.\n\n"
            "1. NOTIFICATION OBLIGATIONS\n\n"
            "Multiple overlapping notification requirements may apply:\n"
            "- State breach notification laws (all 50 states + DC, PR, VI)\n"
            "- GDPR Article 33/34 (72-hour supervisory authority notification)\n"
            "- HIPAA (60-day notification to HHS and individuals)\n"
            "- SEC (material cybersecurity incidents within 4 business days on Form 8-K)\n"
            "- NYDFS (72-hour notification for covered entities)\n"
            "- PCI DSS (notification to card brands and acquiring banks)\n\n"
            "2. PRIVILEGE CONSIDERATIONS\n\n"
            "2.1 Engage outside counsel to direct the forensic investigation to establish "
            "attorney-client privilege over findings.\n"
            "2.2 Label all investigation communications as 'Privileged and Confidential — "
            "Attorney Work Product.'\n"
            "2.3 Maintain separate privileged and non-privileged investigation tracks.\n"
            "2.4 Be aware that some courts have found privilege does not apply to forensic "
            "reports prepared in the ordinary course of business.\n\n"
            "3. REGULATORY ENGAGEMENT\n\n"
            "3.1 Coordinate with regulators proactively — cooperation is a mitigating factor.\n"
            "3.2 Document all regulatory communications.\n"
            "3.3 Preserve all evidence — implement litigation hold immediately.\n\n"
            "4. INSURANCE\n\n"
            "4.1 Notify cyber insurance carrier within 24 hours.\n"
            "4.2 Comply with policy requirements for panel counsel and forensic vendors.\n"
            "4.3 Document all costs for potential coverage claims.\n\n"
            "5. CLASS ACTION PREPARATION\n\n"
            "Assume a class action will follow any significant breach. Preserve all documents "
            "related to security practices, prior incidents, and remediation efforts."
        ),
    },
    {
        "title": "Sanctions Compliance — OFAC Requirements for International Transactions",
        "regulation": "SANCTIONS",
        "date": "2025-10-20",
        "body": (
            "INTERNAL MEMORANDUM — CONFIDENTIAL\n\n"
            "TO: International Practice Group, Banking & Finance Group\n"
            "FROM: Sanctions Compliance Officer\n"
            "RE: OFAC Sanctions Compliance for International Transactions\n"
            "DATE: October 20, 2025\n\n"
            "PURPOSE:\n"
            "This memo provides updated guidance on OFAC sanctions compliance for attorneys "
            "advising on international transactions.\n\n"
            "1. SANCTIONS PROGRAMS\n\n"
            "Key programs include: (a) country-based sanctions (Cuba, Iran, North Korea, Syria, "
            "Crimea region), (b) list-based sanctions (SDN List, Sectoral Sanctions), "
            "(c) secondary sanctions targeting non-US persons, and (d) sector-specific "
            "restrictions (Russian energy, Chinese military companies).\n\n"
            "2. SCREENING REQUIREMENTS\n\n"
            "All parties to international transactions must be screened against: (a) OFAC SDN "
            "List, (b) OFAC Consolidated Sanctions List, (c) EU Consolidated List, "
            "(d) UN Security Council Consolidated List, and (e) relevant national sanctions "
            "lists. Screening must be performed at engagement and periodically during the matter.\n\n"
            "3. GENERAL LICENSES\n\n"
            "Certain activities are authorized under general licenses without specific OFAC "
            "approval. Key general licenses include: (a) legal services (GL for legal "
            "representation), (b) humanitarian transactions, (c) personal communications, "
            "and (d) certain informational materials.\n\n"
            "4. SPECIFIC LICENSE APPLICATIONS\n\n"
            "When a general license is not available, a specific license may be requested from "
            "OFAC. Applications should include: (a) detailed description of proposed activity, "
            "(b) all parties involved, (c) justification for the license, and (d) proposed "
            "compliance measures.\n\n"
            "5. PENALTIES\n\n"
            "OFAC violations can result in: (a) civil penalties up to $330,947 per violation "
            "(adjusted annually), (b) criminal penalties up to $1 million and 20 years "
            "imprisonment, and (c) reputational damage. Voluntary self-disclosure is a "
            "significant mitigating factor."
        ),
    },
]


# ─── Document Generation ────────────────────────────────────────────────────


def generate_documents():
    """Generate all synthetic legal documents and write to output directory."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    manifest = []
    doc_counter = 0

    # Generate case briefs
    for i, brief in enumerate(CASE_BRIEFS):
        doc_counter += 1
        filename = f"case_brief_{i + 1:02d}.txt"
        filepath = OUTPUT_DIR / filename
        author = CASE_BRIEF_AUTHORS[i % len(CASE_BRIEF_AUTHORS)]

        filepath.write_text(brief["body"])

        content_hash = hashlib.md5(brief["body"].encode(), usedforsecurity=False).hexdigest()
        manifest.append(
            {
                "document_id": f"DOC-{doc_counter:04d}",
                "filename": filename,
                "title": brief["title"],
                "document_type": "case_brief",
                "topic": brief["topic"],
                "author": author,
                "court": brief.get("court", ""),
                "docket": brief.get("docket", ""),
                "date": brief["date"],
                "word_count": len(brief["body"].split()),
                "checksum": content_hash,
            }
        )

    # Generate contract templates
    for i, contract in enumerate(CONTRACT_TEMPLATES):
        doc_counter += 1
        filename = f"contract_{i + 1:02d}.txt"
        filepath = OUTPUT_DIR / filename
        author = CONTRACT_AUTHORS[i % len(CONTRACT_AUTHORS)]

        filepath.write_text(contract["body"])

        content_hash = hashlib.md5(contract["body"].encode(), usedforsecurity=False).hexdigest()
        manifest.append(
            {
                "document_id": f"DOC-{doc_counter:04d}",
                "filename": filename,
                "title": contract["title"],
                "document_type": "contract_template",
                "topic": contract["doc_type"],
                "author": author,
                "court": "",
                "docket": "",
                "date": contract["date"],
                "word_count": len(contract["body"].split()),
                "checksum": content_hash,
            }
        )

    # Generate regulatory memos
    for i, memo in enumerate(REGULATORY_MEMOS):
        doc_counter += 1
        filename = f"memo_{i + 1:02d}.txt"
        filepath = OUTPUT_DIR / filename
        author = MEMO_AUTHORS[i % len(MEMO_AUTHORS)]

        filepath.write_text(memo["body"])

        content_hash = hashlib.md5(memo["body"].encode(), usedforsecurity=False).hexdigest()
        manifest.append(
            {
                "document_id": f"DOC-{doc_counter:04d}",
                "filename": filename,
                "title": memo["title"],
                "document_type": "regulatory_memo",
                "topic": memo["regulation"],
                "author": author,
                "court": "",
                "docket": "",
                "date": memo["date"],
                "word_count": len(memo["body"].split()),
                "checksum": content_hash,
            }
        )

    # Write manifest
    manifest_path = OUTPUT_DIR / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))

    # Print summary
    type_counts: dict[str, int] = {}
    total_words = 0
    for doc in manifest:
        doc_type = doc["document_type"]
        type_counts[doc_type] = type_counts.get(doc_type, 0) + 1
        total_words += doc["word_count"]

    print(f"\n{'=' * 60}")
    print("  Legal Document Generation Complete")
    print(f"{'=' * 60}")
    print(f"  Total documents: {len(manifest)}")
    print(f"  Total words:     {total_words:,}")
    print(f"  Output dir:      {OUTPUT_DIR}")
    print()
    for doc_type, count in sorted(type_counts.items()):
        print(f"    {doc_type:25s} {count:3d} documents")
    print(f"\n  Manifest: {manifest_path}")
    print(f"{'=' * 60}\n")

    return manifest


if __name__ == "__main__":
    generate_documents()
