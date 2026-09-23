## Note (2026-09-23, operator): re-issue scripts run as desk jobs after a pane restart

After the Herdr restart at ~13:50 the resumed operator pane could no longer read through the live tree's `data`
junction (bash `Permission denied`, PowerShell "path not found"); from that pane `git status` in the live tree showed
all 125 tracked `data/` files as deleted, while the desktop session (C:\desk jobs, where the launcher runs) saw the tree
clean at the same HEAD. `freeze_deployed*.py` and `issue_binding.py` check the live tree, so after any pane restart run
them as `C:\desk` jobs; the launcher is unaffected. (Staged outside the repo: editing this tracked README mid-pilot would
dirty the live tree through the junction and the launcher would refuse. Land after the pilot.)
