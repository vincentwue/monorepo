# permissions

Shared utilities for FastAPI services to integrate with Ory Keto / Kratos.

Install locally via [uv](https://docs.astral.sh/uv/):

```bash
uv pip install -e packages/python/permissions
```

Then import helpers in your FastAPI apps:

```python
from permissions import require_user_permission, permissions_router
```
