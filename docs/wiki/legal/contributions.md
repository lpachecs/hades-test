The primary use of the LDF package is, and will continue to be, the creation of automated test cases across Lawo product lines. Any changes to the package must be considered within this context and must not come at the detriment to existing QA use cases.

Pull requests for additional functionality are welcomed and encouraged but will be considered in this context. Where possible, we will try to avoid impacting existing test cases in the automated test library.

# Issues + Change Requests
Bug reports and requests for changes in functionality should be communicated via the Gitea repository [Issues Page](https://ccp-tea.lawo.de/quality-assurance/lawo-device-factory/issues).

# Pull Requests
- Pull requests for bug fixes should have a corresponding ticket on the [Issues Page](https://ccp-tea.lawo.de/quality-assurance/lawo-device-factory/issues) that demonstrates the issue with examples.
- Pull requests for functionality changes should provide significant value before being considered for merging to minimise QA distraction time fielding PRs with minimal gain.
- Pull requests should be raised from a branch off `main` in the QA organisation to ensure pipeline checks are executed.
- The LDF codebase is checked for linting, typing and formatting as part of the CI/CD pipeline and any changes to the code must pass these tests in order to be accepted into the `main` branch.