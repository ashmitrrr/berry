---
name: Bug report
about: Something in berry isn't working right
title: "[Bug] "
labels: bug
---

**What happened**
A clear description of the bug.

**What you expected**
What you thought should happen instead.

**Steps to reproduce**
1.
2.
3.

**Environment**
- berry version: `berry --version`
- Install method: Homebrew / manual
- macOS version:
- Chip: Apple Silicon / Intel
- Running as: `berry menubar` / `berry watch` / background service (`launchd`)

**Logs / output**
Paste any relevant terminal output. If it's a background-service issue
(reminders not firing, menu bar not launching), include:
```sh
launchctl list | grep berry
```
and the contents of `~/.berry/daemon.log` if it exists.

**Anything else**
e.g. Full Disk Access granted? Clone location (outside iCloud/Documents/Desktop)?
