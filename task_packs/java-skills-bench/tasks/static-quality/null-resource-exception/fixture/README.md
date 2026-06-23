# Null Resource Exception

Fix `ResourceLoader.loadFirstLine(Path)`.

Requirements:

- Return `Optional.empty()` for missing files.
- Return `Optional.empty()` for empty files.
- Trim non-empty first lines.
- Close file resources.
- Keep the method signature unchanged.
