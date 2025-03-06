# Azlon Project Fix Plan

This document outlines the steps needed to resolve the current issues in the codebase and prepare for a live test run.

## Backend Issues

### E2B Functions Issues

- [x] Fix import for `log` in `e2b_functions.py`
  - Changed from `from restack_ai.utils import log` to standard Python logging
- [x] Correct async/await issues in `e2b_functions.py`:
  - [x] Fix `CommandResult` awaiting in multiple locations (lines 82, 87, 100, 160, 183, 200, 237, 254)
  - [x] Fix `EntryInfo` awaiting issue (line 186)
  - [x] Fix `str` awaiting issue (line 220)
  - [x] Modified methods to convert string returns to bytes when needed

### Functions Module Issues

- [x] Resolve `PreFlightInput` definition issue in `functions.py`
  - Added the missing `PreFlightInput` class definition
- [x] Fix function parameter issues in the validation function (line 224):
  - [x] Changed `feedback` and `nextIteration` parameters to `result`, `suspectedFiles`, and `unsuspectedFiles`

### File Handling Issues

- [x] Fix positional argument issue in `file_handling.py` (line 355)
  - Updated `_collect_input_files` method to accept the `run_folder` parameter
- [x] Fix parameter issue in `test_file_handling.py` with `bucket_name` parameter (line 53)
  - Updated `PreFlightManager` constructor to accept the `bucket_name` parameter

### GitHub Workflow Issues

- [x] Fix "Property command is not allowed" in `.github/workflows/backend-tests.yml` (line 94)
  - Changed `command` to `entrypoint` with the proper format

## Testing Plan

After resolving the issues:

- [ ] Run `start.sh` to expose the backend server to the frontend
- [ ] Run `cd backend && poetry run schedule` to emulate the same process as if the JSON came from the frontend

## Additional Tasks

- [ ] Verify that the server can be run with publicly available IP addresses
- [ ] Perform a final code review to ensure all issues are resolved
- [ ] Document any remaining issues or considerations for future development

## Changes Made

1. Fixed the logging import in `e2b_functions.py` by replacing the custom import with standard Python logging
2. Removed unnecessary `await` calls in `e2b_functions.py` and changed async methods to regular methods
3. Fixed type conversion in `_download_file_from_e2b` to properly handle string to bytes conversion
4. Added the missing `PreFlightInput` class definition in `functions.py`
5. Fixed the ValidateCodeOutput parameters in `functions.py`
6. Updated `_collect_input_files` method signature to accept the run_folder parameter
7. Modified `PreFlightManager` constructor to accept the bucket_name parameter
8. Fixed GitHub workflow by changing MinIO service `command` to `entrypoint`
