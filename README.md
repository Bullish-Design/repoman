# repoman

GitHub repository manager. Configure GitHub accounts and associated repositories via config file + NixOS.

## Configuration

The configuration file supports a global section plus one or more GitHub accounts. The `global.timeout`
value controls the timeout (in seconds) for git operations. It defaults to **300 seconds** and must be
between **30** and **3600** seconds.

```yaml
global:
  base_dir: ~/code
  max_concurrent: 5
  timeout: 300

accounts:
  - name: your-github-username
    repos:
      - repo1
      - repo2
      - name: repo3
        local_dir: ~/custom/location

  - name: organization-name
    base_dir: ~/work
    repos:
      - project1
      - project2
```

## Tests

Integration tests are marked with `integration`.

- Run only integration tests: `pytest -m integration`
- Skip integration tests: `pytest -m "not integration"`
