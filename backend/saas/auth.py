"""Resolve a request's tenant from its credential."""

import hashlib
from typing import Literal

from fastapi import HTTPException, Request

from backend.shared.config import Credential, ServerSettings


class Authenticator:
    def __init__(self, settings: ServerSettings):
        self.credentials = {item.token_sha256: item for item in settings.credentials}

    def require(self, request: Request, role: Literal["operator", "collector"]) -> Credential:
        headers = request.headers.getlist("authorization")
        parts = headers[0].split() if len(headers) == 1 else []
        if len(parts) != 2 or parts[0].lower() != "bearer" or len(parts[1]) > 512:
            raise HTTPException(401, "Bearer credential required", headers={"WWW-Authenticate": "Bearer"})
        credential = self.credentials.get(hashlib.sha256(parts[1].encode()).hexdigest())
        if credential is None:
            raise HTTPException(401, "Invalid credential", headers={"WWW-Authenticate": "Bearer"})
        tenants = request.headers.getlist("x-tenant-id")
        if credential.role != role or tenants not in ([], [credential.tenant_id]):
            raise HTTPException(403, "Credential scope mismatch")
        return credential
