"""ClinicalQueryMessage Update aedoe

Revision ID: 9d34c7147b01
Revises: 8d34c7147b00
Create Date: 2025-09-10 10:03:56.922889

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9d34c7147b01'
down_revision: Union[str, None] = '8d34c7147b00'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Update PlaceholderText values
    # Adverse Events
    op.execute("""
            
            DECLARE @Module1Id INT, @Module2Id INT, @Module3Id INT, @Module4Id INT;
            INSERT INTO QueryModule (Name, Status) VALUES
            ('Adverse Events', 1);
            SET @Module1Id = SCOPE_IDENTITY();
            INSERT INTO QueryModule (Name, Status) VALUES
            ('Vital Signs', 1);
            SET @Module2Id = SCOPE_IDENTITY();
            INSERT INTO QueryModule (Name, Status) VALUES
            ('Disposition and Outcome', 1);
            SET @Module3Id = SCOPE_IDENTITY();
            INSERT INTO QueryModule (Name, Status) VALUES
            ('Dosing and Exposure', 1);
            SET @Module4Id = SCOPE_IDENTITY();
            
            DECLARE @QueryCategory1Id INT, @QueryCategory2Id INT, @QueryCategory3Id INT, @QueryCategory4Id INT;
            INSERT INTO QueryCategory (ModuleId, Name, LBCAT, Status) VALUES
            (@Module1Id, 'Adverse Events', '', 1);
            SET @QueryCategory1Id = SCOPE_IDENTITY();
            INSERT INTO QueryCategory (ModuleId, Name, LBCAT, Status) VALUES
            (@Module2Id, 'Vital Signs', '', 1);
            SET @QueryCategory2Id = SCOPE_IDENTITY();
            INSERT INTO QueryCategory (ModuleId, Name, LBCAT, Status) VALUES
            (@Module3Id, 'Disposition and Outcome', '', 1);
            SET @QueryCategory3Id = SCOPE_IDENTITY();
            INSERT INTO QueryCategory (ModuleId, Name, LBCAT, Status) VALUES
            (@Module4Id, 'Dosing and Exposure', '', 1);
            SET @QueryCategory4Id = SCOPE_IDENTITY();
            
        
            DECLARE @Query1Id INT, @Query2Id INT, @Query3Id INT, @Query4Id INT, @Query5Id INT,@Query6Id INT, @Query7Id INT;

            INSERT INTO PredefinedQuery (CategoryId, TemplateText, DatasetType, TablesInvolved, QueryType, Status) VALUES
            (@QueryCategory1Id, 'For <subject>, what were the other AEs during the <AE> at <YYYY-MM-DD> To <YYYY-MM-DD>?', 'SDTM', 'AE', 'during', 1);
            SET @Query1Id = SCOPE_IDENTITY();
            
            INSERT INTO PredefinedQuery (CategoryId, TemplateText, DatasetType, TablesInvolved, QueryType, Status) VALUES
            (@QueryCategory1Id, 'For <subject>, what were the other AEs most proximal prior to the <AE> at <YYYY-MM-DD>?', 'SDTM', 'AE', 'prior', 1);
            SET @Query2Id = SCOPE_IDENTITY();
            
            INSERT INTO PredefinedQuery (CategoryId, TemplateText, DatasetType, TablesInvolved, QueryType, Status) VALUES
            (@QueryCategory1Id, 'For <subject>, what were the other AEs most proximal to the start of the <AE> at <YYYY-MM-DD>?', 'SDTM', 'AE', 'at_time', 1);
            SET @Query3Id = SCOPE_IDENTITY();
            
            INSERT INTO PredefinedQuery (CategoryId, TemplateText, DatasetType, TablesInvolved, QueryType, Status) VALUES
            (@QueryCategory1Id, 'For <subject>, what AEs occurred within <+/- dd> day(s) of the <AE> at <YYYY-MM-DD>?', 'SDTM', 'AE', 'within_days', 1);
            SET @Query4Id = SCOPE_IDENTITY();
            
        
            INSERT INTO QueryPlaceholder (QueryId, PlaceholderText, InputType, SourceTable, SourceColumn, CategoryFilter) VALUES
            (@Query1Id, '<subject>', 'single-select', 'AE', 'USUBJID', NULL),
            (@Query1Id, '<AE>', 'single-select', 'AE', 'AEDECOD', NULL),
            (@Query1Id, '<YYYY-MM-DD>', 'single-select', 'AE', 'AESTDTC', NULL),
            (@Query1Id, '<YYYY-MM-DD>', 'auto-select', 'AE', 'AEENDTC', NULL),

            (@Query2Id, '<subject>', 'single-select', 'AE', 'USUBJID', NULL),  
            (@Query2Id, '<AE>', 'single-select', 'AE', 'AEDECOD', NULL),
            (@Query2Id, '<YYYY-MM-DD>', 'single-select', 'AE', 'AESTDTC', NULL),
            
            (@Query3Id, '<subject>', 'single-select', 'AE', 'USUBJID', NULL),  
            (@Query3Id, '<AE>', 'single-select', 'AE', 'AEDECOD', NULL),
            (@Query3Id, '<YYYY-MM-DD>', 'single-select', 'AE', 'AESTDTC', NULL),

            (@Query4Id, '<subject>', 'single-select', 'AE', 'USUBJID', NULL),
            (@Query4Id, '<AE>', 'single-select', 'AE', 'AEDECOD', NULL),
            (@Query4Id, '<+/- dd>', 'text-field', 'NULL', 'NULL', NULL),
            (@Query4Id, '<YYYY-MM-DD>', 'single-select', 'AE', 'AESTDTC', NULL);

            """)
    # Vital Signs
    op.execute("""
            DECLARE @VSCategoryId INT = (SELECT TOP 1 Id FROM QueryCategory WHERE Name = 'Vital Signs');

            DECLARE @Query1Id INT, @Query2Id INT, @Query3Id INT, @Query4Id INT;

            INSERT INTO PredefinedQuery (CategoryId, TemplateText, DatasetType, TablesInvolved, QueryType, Status)
            VALUES (@VSCategoryId,
                    'For <subject>, what were the vital signs <vital signs values> most proximal to the start of the <AE> at <YYYY-MM-DD>?',
                    'SDTM',
                    'VS,AE',
                    'at_time',
                    1);
            SET @Query1Id = SCOPE_IDENTITY();

            INSERT INTO QueryPlaceholder (QueryId, PlaceholderText, InputType, SourceTable, SourceColumn, CategoryFilter)
            VALUES
            (@Query1Id, '<subject>', 'single-select', 'VS', 'USUBJID', NULL),
            (@Query1Id, '<vital signs values>', 'multi-select', 'VS', 'VSTEST', NULL),
            (@Query1Id, '<AE>', 'single-select', 'AE', 'AEDECOD', NULL),
            (@Query1Id, '<YYYY-MM-DD>', 'single-select', 'AE', 'AESTDTC', NULL);

            INSERT INTO PredefinedQuery (CategoryId, TemplateText, DatasetType, TablesInvolved, QueryType, Status)
            VALUES (@VSCategoryId,
                    'For <subject>, what were the vital signs <vital signs values> during the <AE> at <YYYY-MM-DD> To <YYYY-MM-DD>?',
                    'SDTM',
                    'VS,AE',
                    'during',
                    1);
            SET @Query2Id = SCOPE_IDENTITY();

            INSERT INTO QueryPlaceholder (QueryId, PlaceholderText, InputType, SourceTable, SourceColumn, CategoryFilter)
            VALUES
            (@Query2Id, '<subject>', 'single-select', 'VS', 'USUBJID', NULL),
            (@Query2Id, '<vital signs values>', 'multi-select', 'VS', 'VSTEST', NULL),
            (@Query2Id, '<AE>', 'single-select', 'AE', 'AEDECOD', NULL),
            (@Query2Id, '<YYYY-MM-DD>', 'single-select', 'AE', 'AESTDTC', NULL),
            (@Query2Id, '<YYYY-MM-DD>', 'auto-select', 'AE', 'AEENDTC', NULL);


            INSERT INTO PredefinedQuery (CategoryId, TemplateText, DatasetType, TablesInvolved, QueryType, Status)
            VALUES (@VSCategoryId,
                    'For <subject>, what were the vital signs <vital signs values> most proximal prior to the <AE> at <YYYY-MM-DD>?',
                    'SDTM',
                    'VS,AE',
                    'prior',
                    1);
            SET @Query3Id = SCOPE_IDENTITY();

            INSERT INTO QueryPlaceholder (QueryId, PlaceholderText, InputType, SourceTable, SourceColumn, CategoryFilter)
            VALUES
            (@Query3Id, '<subject>', 'single-select', 'VS', 'USUBJID', NULL),
            (@Query3Id, '<vital signs values>', 'multi-select', 'VS', 'VSTEST', NULL),
            (@Query3Id, '<AE>', 'single-select', 'AE', 'AEDECOD', NULL),
            (@Query3Id, '<YYYY-MM-DD>', 'single-select', 'AE', 'AESTDTC', NULL);


            INSERT INTO PredefinedQuery (CategoryId, TemplateText, DatasetType, TablesInvolved, QueryType, Status)
            VALUES (@VSCategoryId,
                    'For <subject>, what were the vital signs <vital signs values> within <+/- dd> day(s) of the <AE> at <YYYY-MM-DD>?',
                    'SDTM',
                    'VS,AE',
                    'within_days',
                    1);
            SET @Query4Id = SCOPE_IDENTITY();

            INSERT INTO QueryPlaceholder (QueryId, PlaceholderText, InputType, SourceTable, SourceColumn, CategoryFilter)
            VALUES
            (@Query4Id, '<subject>', 'single-select', 'VS', 'USUBJID', NULL),
            (@Query4Id, '<vital signs values>', 'multi-select', 'VS', 'VSTEST', NULL),
            (@Query4Id, '<AE>', 'single-select', 'AE', 'AEDECOD', NULL),
            (@Query4Id, '<+/- dd>', 'text-field', NULL, NULL, NULL),
            (@Query4Id, '<YYYY-MM-DD>', 'single-select', 'AE', 'AESTDTC', NULL);

    """)
    op.execute("""
            DECLARE @DSCategoryId INT = (SELECT TOP 1 Id FROM QueryCategory WHERE Name = 'Disposition and Outcome');

            DECLARE @Query5Id INT, @Query6Id INT;


            INSERT INTO PredefinedQuery (CategoryId, TemplateText, DatasetType, TablesInvolved, QueryType, Status)
            VALUES (@DSCategoryId,
                    'For <subject> what is the reason and date for treatment discontinuation?',
                    'SDTM',
                    'DS',
                    'treatment_discontinuation',
                    1);
            SET @Query5Id = SCOPE_IDENTITY();


            INSERT INTO PredefinedQuery (CategoryId, TemplateText, DatasetType, TablesInvolved, QueryType, Status)
            VALUES (@DSCategoryId,
                    'For <subject> what is the reason and date for study discontinuation?',
                    'SDTM',
                    'DS',
                    'study_discontinuation',
                    1);
            SET @Query6Id = SCOPE_IDENTITY();


            INSERT INTO QueryPlaceholder (QueryId, PlaceholderText, InputType, SourceTable, SourceColumn, CategoryFilter)
            VALUES
            (@Query5Id, '<subject>', 'single-select', 'DS', 'USUBJID', NULL);


            INSERT INTO QueryPlaceholder (QueryId, PlaceholderText, InputType, SourceTable, SourceColumn, CategoryFilter)
            VALUES
            (@Query6Id, '<subject>', 'single-select', 'DS', 'USUBJID', NULL);
    """)
    op.execute("""
            DECLARE @EXCategoryId INT = (SELECT TOP 1 Id FROM QueryCategory WHERE Name = 'Dosing and Exposure');

            DECLARE @Query1Id INT, @Query2Id INT, @Query3Id INT;

            INSERT INTO PredefinedQuery (CategoryId, TemplateText, DatasetType, TablesInvolved, QueryType, Status)
            VALUES (@EXCategoryId,
                    'For <subject>, when was the subject’s first and last dose of study drug administered?',
                    'SDTM',
                    'EX',
                    'summary',
                    1);
            SET @Query1Id = SCOPE_IDENTITY();

            INSERT INTO QueryPlaceholder (QueryId, PlaceholderText, InputType, SourceTable, SourceColumn, CategoryFilter)
            VALUES
            (@Query1Id, '<subject>', 'single-select', 'EX', 'USUBJID', NULL);


            INSERT INTO PredefinedQuery (CategoryId, TemplateText, DatasetType, TablesInvolved, QueryType, Status)
            VALUES (@EXCategoryId,
                    'For <subject>, was the study drug dose modified? If so, what were the dates and reasons?',
                    'SDTM',
                    'EX',
                    'modification',
                    1);
            SET @Query2Id = SCOPE_IDENTITY();

            INSERT INTO QueryPlaceholder (QueryId, PlaceholderText, InputType, SourceTable, SourceColumn, CategoryFilter)
            VALUES
            (@Query2Id, '<subject>', 'single-select', 'EX', 'USUBJID', NULL);


            INSERT INTO PredefinedQuery (CategoryId, TemplateText, DatasetType, TablesInvolved, QueryType, Status)
            VALUES (@EXCategoryId,
                    'For <subject>, was the study drug dose interrupted? If so, what were the dates and reasons?',
                    'SDTM',
                    'EX',
                    'interruption',
                    1);
            SET @Query3Id = SCOPE_IDENTITY();

            INSERT INTO QueryPlaceholder (QueryId, PlaceholderText, InputType, SourceTable, SourceColumn, CategoryFilter)
            VALUES
            (@Query3Id, '<subject>', 'single-select', 'EX', 'USUBJID', NULL);

    """)


    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # Delete QueryPlaceholder records for all new modules
    op.execute("""
        DELETE FROM QueryPlaceholder 
        WHERE QueryId IN (
            SELECT pq.Id FROM PredefinedQuery pq
            INNER JOIN QueryCategory qc ON pq.CategoryId = qc.Id
            INNER JOIN QueryModule qm ON qc.ModuleId = qm.Id
            WHERE qm.Name IN ('Adverse Events', 'Vital Signs', 'Disposition and Outcome', 'Dosing and Exposure')
        );
    """)
    
    # Delete PredefinedQuery records for all new modules
    op.execute("""
        DELETE FROM PredefinedQuery 
        WHERE CategoryId IN (
            SELECT qc.Id FROM QueryCategory qc
            INNER JOIN QueryModule qm ON qc.ModuleId = qm.Id
            WHERE qm.Name IN ('Adverse Events', 'Vital Signs', 'Disposition and Outcome', 'Dosing and Exposure')
        );
    """)
    
    # Delete QueryCategory records for all new modules
    op.execute("""
        DELETE FROM QueryCategory 
        WHERE ModuleId IN (
            SELECT Id FROM QueryModule 
            WHERE Name IN ('Adverse Events', 'Vital Signs', 'Disposition and Outcome', 'Dosing and Exposure')
        );
    """)
    
    # Delete QueryModule records
    op.execute("""
        DELETE FROM QueryModule 
        WHERE Name IN ('Adverse Events', 'Vital Signs', 'Disposition and Outcome', 'Dosing and Exposure');
    """)
    # ### end Alembic commands ###
