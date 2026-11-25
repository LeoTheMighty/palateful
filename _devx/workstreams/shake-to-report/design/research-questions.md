# Research questions — Shake To Report

<!-- Before drafting. Factual, code-answerable, no intent ("which
     approach?" is design, not research). Answered blind in research.md.
     Add on re-entry; never renumber. -->

1. Which widget sits above every route of the app, and what can it reach
   (root navigator, lifecycle, a scaffold messenger)?
2. How does the client know whether the user is an admin, when is that
   value set or reset, and what is it before it is set?
3. How is the feedback sheet opened today, what context does it send, and
   when is the offline queue flushed?
4. What does the server accept in a feedback's context?
5. Is there an existing server-to-client flag mechanism, how often does
   the client read it, and what manages the server value in production?
6. Which navigators exist, and can an observer see each one's routes?
7. How does a widget tell that a text input has focus?
8. What does the motion plugin need per platform: versions, toolchain,
   Info.plist keys, permission prompts, web behavior, missing sensors?
9. What are the plugin's platform channel names and event payloads?
10. What does a snackbar do under screen readers?
11. Does iOS's Shake to Undo reach Flutter text fields?
12. Where is the dev-request form, how is it entered, and how does it
    close?
13. Can the real app root be pumped in a widget test, and what does that
    take?
