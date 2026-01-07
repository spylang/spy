# Contributing

Thanks for helping improve SPy! Follow these quick steps:

- Fork the repo <https://github.com/spylang/spy>, go to the project repo page and use the Fork button. This will create a copy of the repo, under your username (e.,g. <https://github.com/yourghname/spy>). (For more details on how to fork a repository see this guide <https://help.github.com/articles/fork-a-repo/>.)

- Clone the repo

  ```bash
  git clone git clone git@github.com:your-user-name/spy.git
  cd spy
  ```

- Create and activate a virtualenv

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

- Install dev dependencies, build runtime, and set up pre-commit

  ```bash
  pip install -e .[dev]
  make -C spy/libspy
  ```

- Run the test suite to be sure that everything is working fine

  ```bash
  pytest
  ```

- Install pre-commit

  ```bash
  pip install pre-commit
  pre-commit install
  ```

- Create a branch and commit your changes

  ```bash
  git checkout -b feature/your-change
  # edit code, add tests, run pytest
  git add -A
  git commit -m "Describe your change"
  git push origin feature/your-change
  ```

- Open a Pull Request
  - Keep the PR focused and describe the problem and approach.
  - Ensure tests pass (interp, doppler, C where relevant).