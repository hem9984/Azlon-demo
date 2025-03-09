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

- [x] Run tests for all components (31 tests now passing, 5 skipped due to BAML issues)
- [x] Fix linting issues and formatting with Black and isort
- [ ] Run `make start-server` to build and start Docker containers with Tailscale and expose the backend server to the frontend
- [ ] Run `poetry run schedule` to emulate the same process as if the JSON came from the frontend

## Additional Tasks

- [ ] Verify that the server can be run with publicly available IP addresses
- [ ] Perform a final code review to ensure all issues are resolved
- [ ] Document any remaining issues or considerations for future development

## New Feature Implementation Plan

### 1. Workflow Result API Integration ✅

**Objective**: Create a `/workflow_result/{user_id}/{workflow_id}` endpoint that consolidates the functionality of the backward-compatible endpoints (`output_dirs`, `output_files`, `output_file`) but uses MinIO S3 storage.

**Implementation Steps**:
1. ✅ Add a new endpoint in `main.py` that handles requests with user_id and workflow_id parameters
2. ✅ Create helper functions in `file_server.py` to retrieve workflow files from MinIO
3. ✅ Structure the response to match the existing API format for frontend compatibility
4. ✅ Maintain backward compatibility with local file-based storage for testing

### 2. Zip File Download Functionality ✅

**Objective**: Implement an endpoint that allows users to download all files from a specific workflow as a zip file.

**Implementation Steps**:
1. ✅ Add a new endpoint `/workflow_zip/{user_id}/{workflow_id}` in `main.py`
2. ✅ Create a function in `file_server.py` to retrieve all files for a workflow from MinIO
3. ✅ Use in-memory zip file creation to avoid temporary file storage on the server
4. ✅ Send the zip file as a downloadable response with appropriate headers
5. ✅ Include proper error handling for missing files or empty workflows

### 3. File Upload with Zip Handling ✅

**Objective**: Create an endpoint that accepts file uploads, handles zip files, and makes them available at the beginning of workflows (equivalent to the local input directory).

**Implementation Steps**:
1. ✅ Add a new endpoint `/upload_input/{user_id}` in `main.py` that accepts file uploads
2. ✅ Implement zip file detection and extraction logic
3. ✅ Store extracted files in MinIO under the appropriate input prefix
4. ✅ Extend the `has_input_files` function in `file_handling.py` to correctly check for these uploaded files
5. ✅ Update the E2B functions to access these files from MinIO instead of local storage

### Integration Considerations

1. Storage structure in MinIO will follow the pattern:
   - `azlon-files/user-{user_id}/{workflow_id}/{filename}` - For workflow outputs
   - `azlon-files/input/{user_id}/{filename}` - For uploaded input files

2. Backward compatibility will be maintained by checking both local paths and MinIO storage

3. Error handling will gracefully degrade to local file operations if MinIO is unavailable

## Changes Made

1. Fixed the logging import in `e2b_functions.py` by replacing the custom import with standard Python logging
2. Removed unnecessary `await` calls in `e2b_functions.py` and changed async methods to regular methods
3. Fixed type conversion in `_download_file_from_e2b` to properly handle string to bytes conversion
4. Added the missing `PreFlightInput` class definition in `functions.py`
5. Fixed the ValidateCodeOutput parameters in `functions.py`
6. Updated `_collect_input_files` method signature to accept the run_folder parameter
7. Modified `PreFlightManager` constructor to accept the bucket_name parameter
8. Fixed GitHub workflow by changing MinIO service `command` to `entrypoint`
