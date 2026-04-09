# Story 12.5: Production Console (ECS Exec)

Status: in-progress

## Story

As a developer,
I want to open an interactive Python console connected to the production database,
so that I can inspect data, run queries, and perform admin operations like setting users as admin.

## Acceptance Criteria

1. `bin/prod-console` script finds the running API task and opens an interactive session
2. ECS Exec is enabled on the API service via `enable_execute_command = true`
3. API task role has SSM Messages permissions for ECS Exec
4. API task role has CloudWatch Logs read permissions for the admin log viewer
5. Session drops into `manage.py` IPython shell with all models and DB session loaded

## Tasks / Subtasks

- [x] Task 1: Enable execute_command on ECS API service (terraform/modules/ecs/main.tf)
- [x] Task 2: Add SSM permissions to API task role (terraform/modules/iam/main.tf)
- [x] Task 3: Add CloudWatch Logs read permissions to API task role
- [x] Task 4: Create bin/prod-console helper script
