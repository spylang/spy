title: Environment Variables
---

SPy defines and respects the following environment variables

## SPY_SHOW_MAGIC_FRAMES

Un-hides some of SPy's internal mechanisms in Python tracebacks. Intended for internal development use.

SPy's internals use a "magic dispatch" pattern in many areas to implement walking AST of trees. Which very useful, it adds two frames to the (internal) Python stack for each "magic" dispatch. These frames are hidden from tracebacks by default. They can be restored by setting `export SPY_SHOW_MAGIC_FRAMES=1`.
