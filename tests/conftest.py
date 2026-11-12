from pydantic_ai import models

# No test may call a real model; the LLM is replaced by a fake in each test that needs one.
models.ALLOW_MODEL_REQUESTS = False
