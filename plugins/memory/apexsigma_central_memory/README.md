# ApexSigma central memory

This source-level provider is a fail-closed Hermes extension surface for the
approved Gateway-mediated `hermes.gateway` memory contract. It requires an
explicit endpoint, client identity, credential reference, logical workspace,
operation/resource policy, and server-owned namespace binding. It sends no
storage namespace identifiers and has no direct database, Omega, or MemPalace
connection.

The API remains unbound pending separate ingress and authentication approval.
Gateway/Omega must reconcile the final request/response envelope and enforce
exact-one-client authentication, duplicate-verifier rejection, identity-keyed
policy, and server-derived namespace bindings before any live endpoint is
configured. No client, route, secret, or installed-runtime change is part of
this provider surface.
