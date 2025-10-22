"""add DomainFullName

Revision ID: b3f42d98f1a1
Revises: a2d19a00762a
Create Date: 2025-08-18 14:23:40.424559

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text

# revision identifiers, used by Alembic.
revision: str = 'b3f42d98f1a1'
down_revision: Union[str, None] = 'a2d19a00762a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Map: DomainName -> DomainFullName
DOMAIN_FULLNAME_MAP = {
    "adae": "ADaM Adverse Events",
    "adcm": "ADaM Concomitant Medications",
    "adcv": "ADaM Cardiovascular Assessments",
    "adda": "ADaM Drug Accountability",
    "addv": "ADaM Deviations",
    "adecog": "ADaM Cognitive Assessments",
    "adef1": "ADaM Efficacy Dataset 1",
    "adef2": "ADaM Efficacy Dataset 2",
    "adeff": "ADaM Efficacy",
    "adeg": "ADaM ECG",
    "adex": "ADaM Exposure",
    "adexsum": "ADaM Exposure Summary",
    "adho": "ADaM Holter Monitoring",
    "adie": "ADaM Inclusion/Exclusion",
    "adis": "ADaM Immunogenicity",
    "adlb": "ADaM Laboratory Tests",
    "admh": "ADaM Medical History",
    "adoe": "ADaM Ophthalmology Exams",
    "adpc": "ADaM Pharmacokinetics (Concentration)",
    "adpe": "ADaM Pharmacokinetics (Events)",
    "adpf": "ADaM Pharmacokinetics (Parameters)",
    "adpr": "ADaM Procedures",
    "adqs": "ADaM Questionnaires",
    "adrs": "ADaM Response",
    "adsl": "ADaM Subject Level",
    "adss": "ADaM Safety Summary",
    "adtr": "ADaM Tumor Response",
    "adtte": "ADaM Time-to-Event",
    "adtte1": "ADaM Time-to-Event 1",
    "adtte2": "ADaM Time-to-Event 2",
    "advs": "ADaM Vital Signs",
    "ae": "Adverse Events",
    "ce": "Clinical Events",
    "cm": "Concomitant Medications",
    "co": "Comments",
    "cv": "Cardiovascular Assessments",
    "da": "Drug Accountability",
    "dd": "Death Details",
    "dm": "Demographics",
    "ds": "Disposition",
    "dv": "Protocol Deviations",
    "ec": "Exposure as Collected",
    "eg": "ECG",
    "ex": "Exposure",
    "fa": "Findings About",
    "ho": "Holter Monitoring",
    "ie": "Inclusion/Exclusion Criteria Not Met",
    "is": "Immunogenicity Specimen Assessments",
    "lb": "Laboratory Tests",
    "mb": "Microbiology Specimen Assessments",
    "mh": "Medical History",
    "mi": "Microscopic Findings",
    "nv": "Nervous System Findings",
    "oe": "Ophthalmic Examinations",
    "pc": "Pharmacokinetics Concentrations",
    "pd": "Pharmacokinetics Parameters",
    "pe": "Physical Examination",
    "pf": "Pharmacokinetics Derived Parameters",
    "pr": "Procedures",
    "qs": "Questionnaires",
    "relrec": "Related Records",
    "rp": "Protocol Deviations Resolution",
    "rs": "Disease Response",
    "sc": "Subject Characteristics",
    "se": "Exposure as Collected (Supplemental)",
    "ss": "Subject Summary",
    "su": "Substance Use",
    "suppae": "Supplemental Adverse Events",
    "suppce": "Supplemental Clinical Events",
    "suppcm": "Supplemental Concomitant Medications",
    "suppcv": "Supplemental Cardiovascular Assessments",
    "suppda": "Supplemental Drug Accountability",
    "suppdd": "Supplemental Death Details",
    "suppdm": "Supplemental Demographics",
    "suppds": "Supplemental Disposition",
    "suppdv": "Supplemental Protocol Deviations",
    "suppec": "Supplemental Exposure Collected",
    "suppeg": "Supplemental ECG",
    "suppex": "Supplemental Exposure",
    "suppfa": "Supplemental Findings About",
    "suppho": "Supplemental Holter Monitoring",
    "suppie": "Supplemental Inclusion/Exclusion",
    "suppis": "Supplemental Immunogenicity",
    "supplb": "Supplemental Lab Tests",
    "suppmb": "Supplemental Microbiology",
    "suppmh": "Supplemental Medical History",
    "suppmi": "Supplemental Microscopic Findings",
    "suppnv": "Supplemental Nervous System Findings",
    "suppoe": "Supplemental Ophthalmology Exams",
    "supppc": "Supplemental PK Concentrations",
    "supppd": "Supplemental PK Parameters",
    "supppe": "Supplemental Physical Exams",
    "supppf": "Supplemental PK Derived Parameters",
    "supppr": "Supplemental Procedures",
    "supprs": "Supplemental Disease Response",
    "suppss": "Supplemental Subject Summary",
    "suppsv": "Supplemental Subject Visits",
    "supptr": "Supplemental Tumor Response",
    "supptu": "Supplemental Tumor Assessments",
    "suppve": "Supplemental Ophthalmology Visual Exams",
    "suppvs": "Supplemental Vital Signs",
    "suppzi": "Supplemental Custom Domain (ZI)",
    "sv": "Subject Visits",
    "ta": "Trial Arms",
    "te": "Trial Elements",
    "ti": "Trial Inclusion/Exclusion",
    "tr": "Tumor Results",
    "ts": "Trial Summary",
    "tu": "Tumor Identification",
    "tv": "Trial Visits",
    "ve": "Ophthalmology Visual Exams",
    "vs": "Vital Signs",
    "xv": "ECG Holter Derived",
    "zi": "Custom Domain (User-Defined)"
}

def upgrade() -> None:
    """Upgrade schema."""
    for domain, fullname in DOMAIN_FULLNAME_MAP.items():
        op.execute(
            text("""
                UPDATE DomainClassification
                SET DomainFullName = :fullname
                WHERE DomainName = :domain
            """).bindparams(domain=domain, fullname=fullname)
        )


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    conn = op.get_bind()   # get the active connection
    for domain in DOMAIN_FULLNAME_MAP.keys():
        conn.execute(
            text("""
                UPDATE DomainClassification
                SET DomainFullName = NULL
                WHERE DomainName = :domain
            """),
            {"domain": domain}
        )
