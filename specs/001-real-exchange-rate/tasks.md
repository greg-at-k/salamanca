# Tasks

Check items only when the corresponding work has been completed and verified.

- [x] Draft the economic specification and acceptance criteria.
- [x] Verify live keyless IMF downloads for UK, U.S., and Euro area FX.
- [x] Verify country metadata and identify the Euro area HICP key.
- [x] Write the implementation plan and document data-contract decisions.
- [x] Save reproducible live-response fixtures and probe evidence.
- [x] Implement validated IMF requests and parsing.
- [x] Implement calendar alignment, RER, normalization, and CSV export.
- [x] Implement the Streamlit interface and all three Plotly chart modes.
- [x] Run calculation, parsing, transport, and Streamlit interaction tests with Python 3.12.
- [x] Save one independently reproduced live-data RER calculation and CSV.
- [x] Update README with use, deployment, methodology, and validation instructions.
- [x] Review implementation against the specification and record results.
- [x] Publish the public GitHub repository: https://github.com/greg-at-k/salamanca (main).
- [ ] Deploy with Streamlit Python 3.12. Requires dashboard access; no browser surface is available in this session.
- [ ] Verify the deployed application and add its public URLs to submission evidence.
- [ ] User performs final manual verification and retains prompt/model/date evidence.

## Follow-up: euro report and selection workflow

- [x] Check Euro area/U.S. with live IMF data; actual G163 downloads work in this environment.
- [x] Remove three-letter regions, including misleading Europe (EUR), and clarify the G163 label.
- [x] Specify and implement a 30-year maximum automatic window plus shorter/full-history presets.
- [x] Replace long month lists with custom year/month inputs.
- [x] Batch selection changes behind Load comparison; keep explicit data refresh separate.
- [x] Run 29 regression checks and verify the full revised Euro area/U.S. flow with live data.
- [ ] Verify the exact failure in the user's deployed app if it persists; deployment URL/error has not been provided.
