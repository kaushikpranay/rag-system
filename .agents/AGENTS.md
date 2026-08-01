# Workspace Testing Guidelines & Rules

## Integration & Infrastructure Testing Policy
- **No Mocking of Core Services**: Never use `unittest.mock` or `MagicMock` to stub database calls (PostgreSQL/pgvector, DynamoDB), S3, Bedrock, SQS, or Groq LLM invocations in test files.
- **Tunnel-Detection Wrapper Pattern**: Real infrastructure calls must rely on the existing tunnel-detection wrapper pattern (`TUNNEL_LOCAL_PORT` on `127.0.0.1:15432` or reachable `RDS_HOST:RDS_PORT`).
- **Fail Loudly on Unreachable Infra**: If an infrastructure service or SSH tunnel is down during test execution, tests must raise a clear `RuntimeError` describing the missing host:port or gracefully skip via `pytest.skip()` where appropriate. Do not fall back to silent local defaults (e.g. `localhost:5432`).
