# Changelog

## Unreleased

### Changed
- The `global.timeout` configuration now defaults to 300 seconds (valid range: 30-3600 seconds).
- Repositories with uncommitted changes are skipped during sync operations.
- Error messages from git operations now include stderr when available.
