# Privacy and publication scope

Only an explicit allowlist of synthetic benchmark results, reports, portable profiles, and the focused benchmark harness is published.

Excluded: user names, home/workspace paths, machine names, hardware serials/UUIDs, personal emails, API keys, auth files, application sessions, private chats, attachments/screenshots, full process lists, complete system logs, model weights, runtime binaries, and unrelated project files.

Windows absolute paths in retained JSON/errors are replaced with placeholders. Some synthetic fixture basenames and public model/repository identifiers remain because they identify the experiment. Localhost endpoint examples are generic. Commit attribution uses a generic documentation identity rather than an account's local Git name/email.

Raw data contains synthetic prompts, generated code, and a basic security-review response. These are evidence rather than executable recommendations. File hashes refer to public model artifacts. Hardware is described only at the model/specification level needed to interpret performance.

The original local files were not modified by sanitization. The repository's documentation commit is the intended publication boundary; no unrelated workspace files or account configuration are staged.
