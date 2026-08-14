# ForgeGuard Nexus Web Console

This console intentionally uses dependency-free ES modules so the competition demo can be reproduced from a clean machine without an npm registry. It is served by the FastAPI application at `/` and calls the typed `/api/v1` endpoints.

The interface implements the complete reference workflow: scenario injection, agent trace, evidence review, maintenance-option approval, work-order creation, and post-maintenance verification.
