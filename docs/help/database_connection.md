# Database Connection

Database connections let the app discover metadata and run safe read-only evidence SQL.

Navigation path: Database Connections -> Add database connection -> Test.

Steps:
1. Open Database Connections.
2. Select the workspace.
3. Select the database engine.
4. Enter connection name, host, port, and database name.
5. Provide a connection string or secret reference.
6. Click Add connection.
7. Click Test.

Warnings:
- Use read-only database credentials when possible.
- Production secrets should be stored as secret references.
- The app validates investigation SQL as read-only before execution.
