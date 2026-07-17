SET XACT_ABORT ON;
BEGIN TRANSACTION;
UPDATE eval.[accounts] SET BusinessKey=N'ACC-3103',Status=N'Exception',Details=N'EVAL-BANKING-003',CorrelationId=N'EVAL-BANKING-003' WHERE BusinessKey=N'BANKING-002';
IF @@ROWCOUNT <> 1 THROW 51020, 'Expected baseline entity row missing', 1;
INSERT eval.exceptions(BusinessKey,Status,Details,CorrelationId) VALUES (N'EVAL-BANKING-003',N'Open',N'Synthetic pilot defect for ACC-3103',N'EVAL-BANKING-003');
COMMIT;
GO
