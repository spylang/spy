---
title: Explanation
---

# Explanation

These pages discuss how and why SPy is designed the way it is. They are meant
to be read to build understanding, not to look up a precise fact (for that, see
the [Reference](../reference/python_builtins.md)).

  - [The compilation pipeline](compilation-pipeline.md): the phases that turn a
    `.spy` file into output, and how WebAssembly is used by both the
    interpreter and the compiler.
  - [Low-level memory model](low-level-memory.md): the unsafe core on which
    SPy's high-level features are built.
  - [llwasm, the low-level WASM layer](llwasm.md) (AI-generated): how SPy loads
    and runs WebAssembly modules.

For the motivations and the language design, see the blog posts and talks
listed on the [home page](../index.md#learn-more-about-the-ideas-behind-spy).
