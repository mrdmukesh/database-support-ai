SET XACT_ABORT ON;

IF DB_NAME() <> N'EvalDemoPayrollV2'
    THROW 51140, 'Create refused: unexpected database identity', 1;

BEGIN TRANSACTION;

IF SCHEMA_ID(N'eval') IS NULL EXEC(N'CREATE SCHEMA eval');
IF SCHEMA_ID(N'fault') IS NULL EXEC(N'CREATE SCHEMA fault');

CREATE TABLE eval.evaluation_marker (
    MarkerId INT NOT NULL PRIMARY KEY,
    DomainName NVARCHAR(64) NOT NULL,
    DatabaseName NVARCHAR(128) NOT NULL,
    IsSynthetic BIT NOT NULL,
    FixtureVersion INT NOT NULL
);

CREATE TABLE dbo.Department (
    DepartmentId INT IDENTITY(1,1) PRIMARY KEY,
    DepartmentCode NVARCHAR(30) NOT NULL UNIQUE,
    DepartmentName NVARCHAR(100) NOT NULL
);

CREATE TABLE dbo.Employee (
    EmployeeId INT IDENTITY(1,1) PRIMARY KEY,
    EmployeeNumber NVARCHAR(40) NOT NULL UNIQUE,
    EmployeeName NVARCHAR(120) NOT NULL,
    DateOfBirth DATE NULL,
    DepartmentId INT NULL,
    EmploymentStatus NVARCHAR(30) NOT NULL,
    BusinessKey NVARCHAR(80) NOT NULL UNIQUE,
    Status NVARCHAR(30) NOT NULL,
    CorrelationId NVARCHAR(80) NOT NULL,
    CONSTRAINT FK_Employee_Department
        FOREIGN KEY (DepartmentId) REFERENCES dbo.Department(DepartmentId)
);

CREATE TABLE dbo.PayrollRun (
    PayrollRunId INT IDENTITY(1,1) PRIMARY KEY,
    PeriodStart DATE NOT NULL,
    PeriodEnd DATE NOT NULL,
    BusinessKey NVARCHAR(80) NOT NULL UNIQUE,
    Status NVARCHAR(30) NOT NULL,
    CorrelationId NVARCHAR(80) NOT NULL
);

CREATE TABLE dbo.PayrollItem (
    PayrollItemId INT IDENTITY(1,1) PRIMARY KEY,
    PayrollRunId INT NOT NULL,
    EmployeeId INT NOT NULL,
    GrossPay DECIMAL(18,2) NULL,
    NetPay DECIMAL(18,2) NULL,
    ErrorCode NVARCHAR(50) NULL,
    BusinessKey NVARCHAR(80) NOT NULL UNIQUE,
    Status NVARCHAR(30) NOT NULL,
    CorrelationId NVARCHAR(80) NOT NULL,
    CONSTRAINT FK_PayrollItem_Run
        FOREIGN KEY (PayrollRunId) REFERENCES dbo.PayrollRun(PayrollRunId),
    CONSTRAINT FK_PayrollItem_Employee
        FOREIGN KEY (EmployeeId) REFERENCES dbo.Employee(EmployeeId)
);

CREATE TABLE dbo.PayrollException (
    PayrollExceptionId INT IDENTITY(1,1) PRIMARY KEY,
    EntityBusinessKey NVARCHAR(80) NOT NULL,
    ExceptionType NVARCHAR(80) NOT NULL,
    RootCause NVARCHAR(500) NULL,
    BusinessKey NVARCHAR(80) NOT NULL UNIQUE,
    Status NVARCHAR(30) NOT NULL,
    CorrelationId NVARCHAR(80) NOT NULL
);

CREATE TABLE fault.DeniedEvidence (
    DeniedEvidenceId INT IDENTITY(1,1) PRIMARY KEY,
    BusinessKey NVARCHAR(80) NOT NULL,
    DiagnosticValue NVARCHAR(200) NULL
);

CREATE INDEX IX_Employee_BusinessKey ON dbo.Employee(BusinessKey);
CREATE INDEX IX_PayrollItem_EmployeeId ON dbo.PayrollItem(EmployeeId);
CREATE INDEX IX_PayrollException_EntityBusinessKey
    ON dbo.PayrollException(EntityBusinessKey);

COMMIT;
GO

CREATE OR ALTER VIEW dbo.vw_ActiveEmployee
AS
SELECT EmployeeId, EmployeeNumber, EmployeeName, DateOfBirth, DepartmentId,
       EmploymentStatus, BusinessKey, Status, CorrelationId
FROM dbo.Employee
WHERE EmploymentStatus = N'Active';
GO

CREATE OR ALTER PROCEDURE dbo.usp_GetEmployeeAge
    @EmployeeId INT
AS
BEGIN
    SET NOCOUNT ON;
    SELECT
        EmployeeId,
        EmployeeNumber,
        EmployeeName,
        DateOfBirth,
        CASE
            WHEN DateOfBirth IS NULL THEN NULL
            ELSE DATEDIFF(YEAR, DateOfBirth, CAST(SYSUTCDATETIME() AS DATE))
                 - CASE
                     WHEN DATEADD(
                         YEAR,
                         DATEDIFF(YEAR, DateOfBirth, CAST(SYSUTCDATETIME() AS DATE)),
                         DateOfBirth
                     ) > CAST(SYSUTCDATETIME() AS DATE)
                     THEN 1 ELSE 0
                   END
        END AS Age
    FROM dbo.Employee
    WHERE EmployeeId = @EmployeeId;
END;
GO
