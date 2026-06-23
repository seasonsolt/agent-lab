# SQL Injection

Fix `UserSearch.buildFindByEmail(String)`.

Requirements:

- Keep returning a `Query`.
- Put user-controlled email in `Query.parameters`.
- Keep SQL stable when email contains quotes or SQL syntax.
- Do not add dependencies.
