## Project instructions 
Read before starting project. 

## Learning

Track two types of knowledge:
- Domain: what things are (product context, user preferences, APIs, naming conventions, team decisions
- Procedural: how to do thing (deploy steps, test commands, review flows)

Organize knowledge as a hierarchy of .md files:
- knowledge/index.md routes to categories
- Categories hold the details
Progressive disclosure. Read top-down, only load what you need.

Log errors to knowledge/errors.md. Not every error is a mistake:
- Deterministic errors (bad schema, wrong type, missing field) → conclude immediatel
- Infrastructure errors (timeout, rate limit, network) → log, no conclusion until pattern emerge
- Conclusions graduate into the relevant domain or procedural file

Actively manage the knowledge system. This is as important as the current task:
- Review knowledge files at the start of each session
- Merge overlapping categories
- Split files that grow too long
- Remove knowledge that's no longer accurate
- Create new categories when patterns emerge
- When you notice something that should be in claude.md but isn't — a pattern, a preference, a correction — propose the edit. Don't wait to be asked.
Claude reads claude.md at the start of every session. This instruction tells it to build knowledge as it works - what your system looks like, how your product works, what went wrong and why.

The key is confidence. A single timeout teaches nothing. A bad schema teaches immediately. The system needs to know the difference, or every failed network call becomes a "lesson."

Domain and procedural knowledge are separate because they serve different purposes. Mixing them makes both worse.

No database. No dependencies. Structured markdown that gets smarter every session.



