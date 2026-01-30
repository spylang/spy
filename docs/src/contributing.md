## SPy Source

For guidelines on setting up your machine to build and contribute to SPy, see [CONTRIBUTING.md](https://github.com/spylang/spy/blob/main/CONTRIBUTING.md)

## Documentation

/// note | Cloning the Repo
The first two steps below (forking and cloning the repo) are the same as for the steps for contributing to SPy's source code. You do not need a separate fork and clone for documentation.
///

To set up your machine to contribute to the SPy documentation, first Fork the repo <https://github.com/spylang/spy>, go to the project repo page and use the Fork button. This will create a copy of the repo, under your username (e.,g. <https://github.com/yourghname/spy>). (For more details on how to fork a repository see this guide <https://help.github.com/articles/fork-a-repo/>.)

Next, clone the repo to your machine:

  ```bash
  git clone git clone git@github.com:your-user-name/spy.git
  cd spy
  ```

Create a virtual environment for your project, and install both the SPy dependencies and the docs-specific dependencies. Any package installer and virtual environment will work; here are a couple of options:

=== "pip"
    ```bash
    python -m venv .venv
    source ./.venv/bin/activate # or similar for your flavor of shell
    python -m pip install .[docs]
    ```
=== "uv"
    ```bash
    uv sync --group docs
    ```

Build a copy of the docs locally, and start a live server to view the current state of the docs:

=== "pip"
    ```bash
    # with the virtual environment active
    mike deploy mylocalcopy
    mike serve
    # open http://localhost:8000/mylocalcopy in a browser
    ```
=== "uv"
    ```bash
    uv run mike reploy mylocalcopy
    uv run mike serve
    # open http://localhost:8000/mylocalcopy in a browser
    ```

/// tip |"Updating Docs
Some changes - like adding or moving files, or changes to configuration in `mkdocs.yml`, will not be visible immediately in the server preview. To see them, stop the server (ctl/cmd + c), rerun the build command, and restart the live server using the commands above.
///

Create a new git branch to make changes on:

  ```bash
  git checkout -b feature/your-change
  ```

At this point, you're ready to start writing and editing your contributions!

/// note | Documentation Tools
SPy uses [mkdocs](https://www.mkdocs.org/) as its documentation builder with the [material for mkdocs theme](https://squidfunk.github.io/mkdocs-material/), and [mike](https://github.com/jimporter/mike) to manage docs versioning. See their pages for additional information on formatting and options.
///

Once you're happy with your changes, add them to your git branch and push them to GitHub

```bash
  git add -A
  git commit -m "Describe your change"
  git push origin feature/your-change
```

Finally, open a Pull Request on the [SPy GitHub page](https://github.com/spylang/spy).
