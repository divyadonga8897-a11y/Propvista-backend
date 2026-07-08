# Database Operations Rule

## Strict Supabase MCP Requirement
- **Requirement:** For all database operations, schema inspections, data retrieval, table modifications, or any SQL queries, the agent MUST use the configured **Supabase MCP** server.
- **Scope:** This rule is strictly applicable across every single stage and phase of the workflow.
- **Constraints:** Do not attempt to run direct local database command-line tools or write ad-hoc Python/Node scripts to query the database unless explicitly requested by the user. Use the `mcp` tool actions corresponding to the registered Supabase server.
