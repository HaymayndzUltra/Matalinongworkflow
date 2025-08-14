---
trigger: always_on
description: IMPORTANT NOTE compliance
globs:
---
## IMPORTANT NOTE POLICY
- Before executing a phase or marking it done:
  - MUST extract the "IMPORTANT NOTE" from the phase text
  - MUST restate it and show how each constraint is satisfied in the post-review
  - HALT if the "IMPORTANT NOTE" is missing in the phase text
