"""ClinicalQueryMessage Update

Revision ID: 8d34c7147b00
Revises: 8c34c7147b99
Create Date: 2025-09-10 10:03:56.922889

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8d34c7147b00'
down_revision: Union[str, None] = '8c34c7147b99'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Update PlaceholderText values
    op.execute("""
        DECLARE @Query1Id INT, @Query2Id INT, @Query3Id INT, @Query4Id INT, @Query5Id INT,@Query6Id INT, @Query7Id INT;

        INSERT INTO PredefinedQuery (CategoryId, TemplateText, DatasetType, TablesInvolved, QueryType, Status) VALUES
        (7, 'For <subject>, what were the concomitant medications <categories> and <indications> 30 days prior to and during the study?', 'SDTM', 'CM,DM', 'prior_during', 1);
        SET @Query1Id = SCOPE_IDENTITY();
        INSERT INTO PredefinedQuery (CategoryId, TemplateText, DatasetType, TablesInvolved, QueryType, Status) VALUES
        (7, 'For <subject>, what were the concomitant medications <categories> and <indications> during the <AE> on <YYYY-MM-DD> To <YYYY-MM-DD>?', 'SDTM', 'CM, AE', 'during', 1);
        SET @Query2Id = SCOPE_IDENTITY();
        INSERT INTO PredefinedQuery (CategoryId, TemplateText, DatasetType, TablesInvolved, QueryType, Status) VALUES
        (7, 'For <subject>, what were the concomitant medications <categories> and <indications> with in <+/- dd> day(s) of <AE> at <YYYY-MM-DD>?', 'SDTM', 'CM,AE', 'within_days', 1);
        SET @Query3Id = SCOPE_IDENTITY();

        INSERT INTO PredefinedQuery (CategoryId, TemplateText, DatasetType, TablesInvolved, QueryType, Status) VALUES
        (8, 'For <subject>, what procedures <categories> and <indications> were performed during the study?', 'SDTM', 'PR,DM', 'study', 1);
        SET @Query4Id = SCOPE_IDENTITY();
        INSERT INTO PredefinedQuery (CategoryId, TemplateText, DatasetType, TablesInvolved, QueryType, Status) VALUES
        (8, 'For <subject>, what procedures  <categories> and <indications> were performed prior to the first dose of study treatment?', 'SDTM', 'PR', 'prior_first', 1);
        SET @Query5Id = SCOPE_IDENTITY();
        INSERT INTO PredefinedQuery (CategoryId, TemplateText, DatasetType, TablesInvolved, QueryType, Status) VALUES
        (8, 'For <subject>, what procedures <categories> and <indications> were performed during the <AE> on <YYYY-MM-DD> To <YYYY-MM-DD>?', 'SDTM', 'PR,AE', 'during', 1);
        SET @Query6Id = SCOPE_IDENTITY();
        INSERT INTO PredefinedQuery (CategoryId, TemplateText, DatasetType, TablesInvolved, QueryType, Status) VALUES
        (8, 'For <subject>, what procedures  <categories> and <indications> were performed with in <+/- dd> day(s) of <AE> at <YYYY-MM-DD>?', 'SDTM', 'PR,AE', 'within_days', 1); 
        SET @Query7Id = SCOPE_IDENTITY();

        INSERT INTO QueryPlaceholder (QueryId, PlaceholderText, InputType, SourceTable, SourceColumn, CategoryFilter) VALUES
        (@Query1Id, '<subject>', 'single-select', 'CM', 'USUBJID', NULL),
        (@Query1Id, '<categories>', 'multi-select', 'CM', 'CMCAT', NULL),
        (@Query1Id, '<indications>', 'multi-select', 'CM', 'CMINDC', NULL),

        (@Query2Id, '<subject>', 'single-select', 'CM', 'USUBJID', NULL),    
        (@Query2Id, '<categories>', 'multi-select', 'CM', 'CMCAT', NULL),
        (@Query2Id, '<indications>', 'multi-select', 'CM', 'CMINDC', NULL),
        (@Query2Id, '<AE>', 'single-select', 'AE', 'AEDECOD', NULL),
        (@Query2Id, '<YYYY-MM-DD>', 'single-select', 'AE', 'AESTDTC', NULL),
        (@Query2Id, '<YYYY-MM-DD>', 'auto-select', 'AE', 'AEENDTC', NULL),

        (@Query3Id, '<subject>', 'single-select', 'CM', 'USUBJID', NULL),
        (@Query3Id, '<categories>', 'multi-select', 'CM', 'CMCAT', NULL),
        (@Query3Id, '<indications>', 'multi-select', 'CM', 'CMINDC', NULL),
        (@Query3Id, '<+/- dd>', 'text-field', 'NULL', 'NULL', NULL),
        (@Query3Id, '<AE>', 'single-select', 'AE', 'AEDECOD', NULL),
        (@Query3Id, '<YYYY-MM-DD>', 'single-select', 'AE', 'AESTDTC', NULL);

        INSERT INTO QueryPlaceholder (QueryId, PlaceholderText, InputType, SourceTable, SourceColumn, CategoryFilter) VALUES
        (@Query4Id, '<subject>', 'single-select', 'PR', 'USUBJID', NULL),
        (@Query4Id, '<categories>', 'multi-select', 'PR', 'PRCAT', NULL),
        (@Query4Id, '<indications>', 'multi-select', 'PR', 'PRINDC', NULL), 

        (@Query5Id, '<subject>', 'single-select', 'PR', 'USUBJID', NULL),
        (@Query5Id, '<categories>', 'multi-select', 'PR', 'PRCAT', NULL),
        (@Query5Id, '<indications>', 'multi-select', 'PR', 'PRINDC', NULL), 

        (@Query6Id, '<subject>', 'single-select', 'PR', 'USUBJID', NULL),    
        (@Query6Id, '<categories>', 'multi-select', 'PR', 'PRCAT', NULL),
        (@Query6Id, '<indications>', 'multi-select', 'PR', 'PRINDC', NULL),
        (@Query6Id, '<AE>', 'single-select', 'AE', 'AEDECOD', NULL),
        (@Query6Id, '<YYYY-MM-DD>', 'single-select', 'AE', 'AESTDTC', NULL),
        (@Query6Id, '<YYYY-MM-DD>', 'auto-select', 'AE', 'AEENDTC', NULL),

        (@Query7Id, '<subject>', 'single-select', 'PR', 'USUBJID', NULL),
        (@Query7Id, '<categories>', 'multi-select', 'PR', 'PRCAT', NULL),
        (@Query7Id, '<indications>', 'multi-select', 'PR', 'PRINDC', NULL),
        (@Query7Id, '<+/- dd>', 'text-field', 'NULL', 'NULL', NULL),
        (@Query7Id, '<AE>', 'single-select', 'AE', 'AEDECOD', NULL),
        (@Query7Id, '<YYYY-MM-DD>', 'single-select', 'AE', 'AESTDTC', NULL);

        """)
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("""
            DELETE FROM QueryPlaceholder 
            WHERE QueryId IN (
                SELECT Id FROM PredefinedQuery 
                WHERE CategoryId IN (7, 8) 
                AND QueryType IN ('prior_during', 'during', 'within_days', 'study', 'prior_first')
            );
            
            DELETE FROM PredefinedQuery 
            WHERE CategoryId IN (7, 8) 
            AND QueryType IN ('prior_during', 'during', 'within_days', 'study', 'prior_first');
        """)
    # ### end Alembic commands ###
