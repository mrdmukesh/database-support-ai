SET XACT_ABORT ON;
BEGIN TRANSACTION;
UPDATE eval.[tax_filings] SET BusinessKey=N'TAX-2026-07',Status=N'Exception',Details=N'EVAL-PAYROLL-005',CorrelationId=N'EVAL-PAYROLL-005' WHERE BusinessKey=N'PAYROLL-012';
IF @@ROWCOUNT <> 1 THROW 51020, 'Expected baseline entity row missing', 1;
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EVAL-PAYROLL-005',N'Open',N'Synthetic pilot defect for TAX-2026-07',N'EVAL-PAYROLL-005');
COMMIT;
GO
