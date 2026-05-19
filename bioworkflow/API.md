# API Documentation

Complete REST API documentation for the Bioinformatics Workflow Platform.

Base URL: `https://your-domain.com`

All endpoints return JSON responses.

## Authentication

The API uses session-based authentication. After logging in, the session cookie is used for subsequent requests.

### Register

Create a new user account.

**Endpoint:** `POST /auth/register`

**Request Body:**
```json
{
  "username": "string",
  "email": "string",
  "password": "string",
  "confirm_password": "string"
}
```

**Response (201 Created):**
```json
{
  "message": "Registration successful",
  "user": {
    "id": 1,
    "username": "testuser",
    "email": "test@example.com"
  }
}
```

**Response (400 Bad Request):**
```json
{
  "error": "Validation failed",
  "errors": {
    "username": ["Username already taken. Please choose a different one."]
  }
}
```

### Login

Authenticate and create a session.

**Endpoint:** `POST /auth/login`

**Request Body:**
```json
{
  "username": "string",
  "password": "string",
  "remember_me": boolean
}
```

**Response (200 OK):**
```json
{
  "message": "Login successful",
  "user": {
    "id": 1,
    "username": "testuser",
    "email": "test@example.com",
    "last_login": "2024-01-15T10:30:00"
  }
}
```

**Response (401 Unauthorized):**
```json
{
  "error": "Invalid username or password"
}
```

### Logout

End the current session.

**Endpoint:** `POST /auth/logout`

**Response (200 OK):**
```json
{
  "message": "Logout successful"
}
```

### Get Current User

Get information about the authenticated user.

**Endpoint:** `GET /auth/me`

**Response (200 OK):**
```json
{
  "user": {
    "id": 1,
    "username": "testuser",
    "email": "test@example.com",
    "created_at": "2024-01-01T00:00:00",
    "last_login": "2024-01-15T10:30:00"
  }
}
```

---

## Projects

### List Projects

Get all projects for the authenticated user.

**Endpoint:** `GET /projects/`

**Query Parameters:**
- `sort`: Sort by `created` or `updated` (default: `created`)
- `order`: `asc` or `desc` (default: `desc`)

**Response (200 OK):**
```json
{
  "projects": [
    {
      "id": 1,
      "name": "Cancer Genomics Study",
      "description": "Analysis of tumor samples",
      "created_at": "2024-01-01T00:00:00",
      "updated_at": "2024-01-15T10:00:00",
      "experiment_count": 5
    }
  ]
}
```

### Create Project

Create a new project.

**Endpoint:** `POST /projects/`

**Request Body:**
```json
{
  "name": "string",
  "description": "string"
}
```

**Response (201 Created):**
```json
{
  "message": "Project created successfully",
  "project": {
    "id": 1,
    "name": "Cancer Genomics Study",
    "description": "Analysis of tumor samples",
    "created_at": "2024-01-01T00:00:00"
  }
}
```

### Get Project

Get detailed information about a project.

**Endpoint:** `GET /projects/<project_id>`

**Response (200 OK):**
```json
{
  "project": {
    "id": 1,
    "name": "Cancer Genomics Study",
    "description": "Analysis of tumor samples",
    "created_at": "2024-01-01T00:00:00",
    "updated_at": "2024-01-15T10:00:00",
    "experiment_count": 5,
    "status_counts": {
      "completed": 3,
      "running": 1,
      "ready": 1
    },
    "storage": {
      "uploads_mb": 1024.5,
      "intermediate_mb": 512.3,
      "results_mb": 256.1,
      "total_mb": 1792.9
    }
  },
  "experiments": [
    {
      "id": 1,
      "name": "Sample A Analysis",
      "status": "completed",
      "created_at": "2024-01-05T00:00:00",
      "has_expression_file": true,
      "has_vcf_files": true,
      "vcf_file_count": 3
    }
  ]
}
```

### Update Project

Update project details.

**Endpoint:** `PUT /projects/<project_id>`

**Request Body:**
```json
{
  "name": "string",
  "description": "string"
}
```

**Response (200 OK):**
```json
{
  "message": "Project updated successfully",
  "project": {
    "id": 1,
    "name": "Updated Project Name",
    "description": "Updated description",
    "updated_at": "2024-01-15T10:00:00"
  }
}
```

### Delete Project

Delete a project and all its experiments.

**Endpoint:** `DELETE /projects/<project_id>`

**Response (200 OK):**
```json
{
  "message": "Project deleted successfully",
  "project_id": 1
}
```

### Generate Merged Table

Generate a merged contingency table from all completed experiments.

**Endpoint:** `POST /projects/<project_id>/generate_merged_table`

**Response (202 Accepted):**
```json
{
  "message": "Merge task queued",
  "task_id": "abc123-task-id",
  "experiments_to_merge": 5
}
```

**Response (400 Bad Request):**
```json
{
  "error": "No completed experiments to merge"
}
```

### Get Merged Results

List merged result tables for a project.

**Endpoint:** `GET /projects/<project_id>/merged_results`

**Response (200 OK):**
```json
{
  "merged_results": [
    {
      "id": 1,
      "created_at": "2024-01-15T12:00:00",
      "experiment_count": 5,
      "file_size_mb": 12.5
    }
  ]
}
```

### Download Merged Result

Download a merged contingency table.

**Endpoint:** `GET /projects/<project_id>/merged_results/<result_id>/download`

**Response:** File download (CSV)

---

## Experiments

### List Experiments

Get all experiments in a project.

**Endpoint:** `GET /experiments/<project_id>`

**Query Parameters:**
- `status`: Filter by status (optional)

**Response (200 OK):**
```json
{
  "experiments": [
    {
      "id": 1,
      "name": "Sample A Analysis",
      "description": "First tumor sample",
      "status": "completed",
      "created_at": "2024-01-05T00:00:00",
      "updated_at": "2024-01-05T02:30:00",
      "has_expression_file": true,
      "has_vcf_files": true,
      "vcf_file_count": 3,
      "started_at": "2024-01-05T01:00:00",
      "completed_at": "2024-01-05T02:30:00",
      "current_step": 4,
      "has_result": true
    }
  ]
}
```

### Create Experiment

Create a new experiment in a project.

**Endpoint:** `POST /experiments/<project_id>`

**Request Body:**
```json
{
  "name": "string",
  "description": "string"
}
```

**Response (201 Created):**
```json
{
  "message": "Experiment created successfully",
  "experiment": {
    "id": 1,
    "name": "Sample A Analysis",
    "description": "First tumor sample",
    "status": "created",
    "created_at": "2024-01-05T00:00:00"
  }
}
```

### Get Experiment

Get detailed information about an experiment.

**Endpoint:** `GET /experiments/<experiment_id>`

**Response (200 OK):**
```json
{
  "experiment": {
    "id": 1,
    "name": "Sample A Analysis",
    "description": "First tumor sample",
    "project_id": 1,
    "project_name": "Cancer Genomics Study",
    "status": "completed",
    "created_at": "2024-01-05T00:00:00",
    "updated_at": "2024-01-05T02:30:00",
    "has_expression_file": true,
    "expression_filename": "expression_data.csv",
    "has_vcf_files": true,
    "vcf_file_count": 3,
    "started_at": "2024-01-05T01:00:00",
    "completed_at": "2024-01-05T02:30:00",
    "duration_seconds": 5400,
    "current_step": 4,
    "celery_task_id": "abc123-task-id",
    "error_message": null,
    "has_result": true,
    "can_run": false
  }
}
```

### Upload Expression File

Upload gene expression file for an experiment.

**Endpoint:** `POST /experiments/<experiment_id>/upload_expression`

**Content-Type:** `multipart/form-data`

**Form Data:**
- `expression_file`: File upload

**Response (200 OK):**
```json
{
  "message": "Expression file uploaded successfully",
  "file": {
    "filename": "expression_data.csv",
    "size_bytes": 1048576
  },
  "experiment": {
    "id": 1,
    "status": "uploading",
    "can_run": false
  }
}
```

**Response (400 Bad Request):**
```json
{
  "error": "File type not allowed. Allowed types: {'.csv', '.tsv', '.txt', '.tab'}"
}
```

### Upload VCF Files

Upload VCF files for an experiment.

**Endpoint:** `POST /experiments/<experiment_id>/upload_vcf`

**Content-Type:** `multipart/form-data`

**Form Data:**
- `vcf_files`: Multiple file uploads

**Response (200 OK):**
```json
{
  "message": "3 VCF files uploaded successfully",
  "files": [
    {
      "filename": "sample1.vcf",
      "size_bytes": 524288
    },
    {
      "filename": "sample2.vcf.gz",
      "size_bytes": 262144
    },
    {
      "filename": "sample3.vcf",
      "size_bytes": 458752
    }
  ],
  "experiment": {
    "id": 1,
    "status": "ready",
    "vcf_file_count": 3,
    "can_run": true
  }
}
```

### Run Experiment

Execute the bioinformatics pipeline.

**Endpoint:** `POST /experiments/<experiment_id>/run`

**Response (202 Accepted):**
```json
{
  "message": "Pipeline execution queued",
  "task_id": "abc123-task-id",
  "experiment": {
    "id": 1,
    "status": "queued"
  }
}
```

**Response (400 Bad Request):**
```json
{
  "error": "Experiment cannot be executed",
  "reason": "Check that all files are uploaded and experiment is not already running",
  "status": "created",
  "has_expression_file": false,
  "has_vcf_files": true
}
```

### Get Experiment Status

Get current execution status.

**Endpoint:** `GET /experiments/<experiment_id>/status`

**Response (200 OK):**
```json
{
  "experiment_id": 1,
  "status": "running",
  "current_step": 2,
  "total_steps": 4,
  "created_at": "2024-01-05T00:00:00",
  "updated_at": "2024-01-05T01:15:00",
  "started_at": "2024-01-05T01:00:00",
  "task_id": "abc123-task-id"
}
```

**Response (if completed):**
```json
{
  "experiment_id": 1,
  "status": "completed",
  "current_step": 4,
  "total_steps": 4,
  "created_at": "2024-01-05T00:00:00",
  "updated_at": "2024-01-05T02:30:00",
  "started_at": "2024-01-05T01:00:00",
  "completed_at": "2024-01-05T02:30:00",
  "duration_seconds": 5400,
  "task_id": "abc123-task-id"
}
```

**Response (if failed):**
```json
{
  "experiment_id": 1,
  "status": "failed",
  "current_step": 2,
  "total_steps": 4,
  "created_at": "2024-01-05T00:00:00",
  "updated_at": "2024-01-05T01:45:00",
  "started_at": "2024-01-05T01:00:00",
  "completed_at": "2024-01-05T01:45:00",
  "duration_seconds": 2700,
  "error_message": "VEP script failed: Invalid VCF format",
  "task_id": "abc123-task-id"
}
```

### Download Result

Download the final contingency table.

**Endpoint:** `GET /experiments/<experiment_id>/download`

**Response:** File download (CSV)

**Response (404 Not Found):**
```json
{
  "error": "No result available",
  "status": "running"
}
```

### Delete Experiment

Delete an experiment and its files.

**Endpoint:** `DELETE /experiments/<experiment_id>`

**Response (200 OK):**
```json
{
  "message": "Experiment deleted successfully",
  "experiment_id": 1
}
```

---

## Status Codes

The API uses standard HTTP status codes:

- `200 OK`: Request successful
- `201 Created`: Resource created successfully
- `202 Accepted`: Request accepted for processing (async)
- `400 Bad Request`: Invalid request data
- `401 Unauthorized`: Authentication required
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Resource not found
- `413 Payload Too Large`: File too large
- `500 Internal Server Error`: Server error

---

## Error Response Format

All errors follow this format:

```json
{
  "error": "Error type",
  "message": "Detailed error message"
}
```

Validation errors include field-specific errors:

```json
{
  "error": "Validation failed",
  "errors": {
    "field_name": ["Error message 1", "Error message 2"]
  }
}
```

---

## Rate Limiting

Currently, no rate limiting is implemented. Consider adding rate limiting in production using Flask-Limiter or similar.

---

## Example Workflows

### Complete Experiment Workflow

```bash
# 1. Register and login
curl -X POST https://your-domain.com/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"researcher","email":"researcher@lab.edu","password":"SecurePass123!","confirm_password":"SecurePass123!"}'

curl -X POST https://your-domain.com/auth/login \
  -H "Content-Type: application/json" \
  -c cookies.txt \
  -d '{"username":"researcher","password":"SecurePass123!"}'

# 2. Create project
curl -X POST https://your-domain.com/projects/ \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{"name":"Tumor Analysis","description":"Patient cohort study"}'
# Response includes project_id: 1

# 3. Create experiment
curl -X POST https://your-domain.com/experiments/1 \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{"name":"Sample A","description":"First patient sample"}'
# Response includes experiment_id: 1

# 4. Upload expression file
curl -X POST https://your-domain.com/experiments/1/upload_expression \
  -b cookies.txt \
  -F "expression_file=@/path/to/expression_data.csv"

# 5. Upload VCF files
curl -X POST https://your-domain.com/experiments/1/upload_vcf \
  -b cookies.txt \
  -F "vcf_files=@/path/to/sample1.vcf" \
  -F "vcf_files=@/path/to/sample2.vcf" \
  -F "vcf_files=@/path/to/sample3.vcf"

# 6. Run pipeline
curl -X POST https://your-domain.com/experiments/1/run \
  -b cookies.txt
# Response includes task_id

# 7. Poll for status
while true; do
  curl -X GET https://your-domain.com/experiments/1/status -b cookies.txt
  sleep 30
done

# 8. Download result when completed
curl -X GET https://your-domain.com/experiments/1/download \
  -b cookies.txt \
  -O -J

# 9. Generate project-wide merged table
curl -X POST https://your-domain.com/projects/1/generate_merged_table \
  -b cookies.txt

# 10. Download merged table
curl -X GET https://your-domain.com/projects/1/merged_results/1/download \
  -b cookies.txt \
  -O -J
```

---

## WebSocket Support (Future Enhancement)

For real-time pipeline progress updates, consider adding WebSocket support using Flask-SocketIO.

---

## API Versioning (Future Enhancement)

When making breaking changes, consider implementing API versioning:
- URL-based: `/api/v1/projects/`, `/api/v2/projects/`
- Header-based: `Accept: application/vnd.bioworkflow.v1+json`
