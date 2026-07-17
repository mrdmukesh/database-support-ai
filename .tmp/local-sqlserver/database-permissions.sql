USE [EvalPayroll];
GO
IF USER_ID('evaladmin') IS NULL CREATE USER [evaladmin] FOR LOGIN [evaladmin];
GO
ALTER ROLE db_owner ADD MEMBER [evaladmin];
GO
IF USER_ID('evalreader') IS NULL CREATE USER [evalreader] FOR LOGIN [evalreader];
GO
ALTER ROLE db_datareader ADD MEMBER [evalreader];
GO
USE [EvalClinic];
GO
IF USER_ID('evaladmin') IS NULL CREATE USER [evaladmin] FOR LOGIN [evaladmin];
GO
ALTER ROLE db_owner ADD MEMBER [evaladmin];
GO
IF USER_ID('evalreader') IS NULL CREATE USER [evalreader] FOR LOGIN [evalreader];
GO
ALTER ROLE db_datareader ADD MEMBER [evalreader];
GO
USE [EvalOrders];
GO
IF USER_ID('evaladmin') IS NULL CREATE USER [evaladmin] FOR LOGIN [evaladmin];
GO
ALTER ROLE db_owner ADD MEMBER [evaladmin];
GO
IF USER_ID('evalreader') IS NULL CREATE USER [evalreader] FOR LOGIN [evalreader];
GO
ALTER ROLE db_datareader ADD MEMBER [evalreader];
GO
USE [EvalBanking];
GO
IF USER_ID('evaladmin') IS NULL CREATE USER [evaladmin] FOR LOGIN [evaladmin];
GO
ALTER ROLE db_owner ADD MEMBER [evaladmin];
GO
IF USER_ID('evalreader') IS NULL CREATE USER [evalreader] FOR LOGIN [evalreader];
GO
ALTER ROLE db_datareader ADD MEMBER [evalreader];
GO
USE [EvalShipping];
GO
IF USER_ID('evaladmin') IS NULL CREATE USER [evaladmin] FOR LOGIN [evaladmin];
GO
ALTER ROLE db_owner ADD MEMBER [evaladmin];
GO
IF USER_ID('evalreader') IS NULL CREATE USER [evalreader] FOR LOGIN [evalreader];
GO
ALTER ROLE db_datareader ADD MEMBER [evalreader];
GO