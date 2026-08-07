"""
Notifiers send an alert when the runner finds new jobs. Each notifier
module exposes:

    notify(jobs: list[dict], summary: dict) -> None

so adding email or Slack later is: new module with a notify() function,
one import + call added in collectors/runner.py.
"""
