---
name: create-suite
description: 'Use when the Test Plan has already been created and you need to create static Suites inside it to organize test cases by acceptance criterion.'
---

# Create Suites inside the Test Plan

## What to do

1. Use the Test Plan ID created in the previous step.
2. Read all acceptance criteria from the User Story.
3. Create one static Suite for each acceptance criterion via the `ado-remote-mcp` tools.
4. Generate a Suite name that clearly represents the acceptance criterion.
5. Save the Suite ID associated with its acceptance criterion.
6. Confirm all created Suites to the user.

## Required fields for creation

* Test Plan ID: the one obtained in the previous step
* Name: acceptance criterion title or concise functional description
* Suite type: Static suite

## Suite naming rules

* Each Suite name must represent the acceptance criterion it contains.
* Use business language whenever possible.
* The Suite name must be concise and descriptive.
* Do not use generic names such as:

  * Suite 1
  * Suite 2
  * Acceptance Criterion 1
  * Tests
  * Functional Tests
* Do not use the User Story title as the Suite name.
* The Suite name should allow a tester to understand the functionality being tested without reading the User Story.

### Examples

Acceptance Criterion:
"The user can upload PDF documents successfully"

Suite:
"PDF document upload"

Acceptance Criterion:
"The system rejects unsupported file formats"

Suite:
"Unsupported file format validation"

Acceptance Criterion:
"The user can configure hierarchical segmentation levels"

Suite:
"Hierarchical segmentation configuration"

## Suite creation rules

* Create one Suite for every acceptance criterion identified in the User Story.
* Never group multiple acceptance criteria into the same Suite.
* Never omit an acceptance criterion.
* Create Suites sequentially.
* Maintain the relationship between each acceptance criterion and its corresponding Suite.

## Output format

✅ Suites created successfully:

* **[SUITE_NAME]** (ID: [ID])
* **[SUITE_NAME]** (ID: [ID])
* **[SUITE_NAME]** (ID: [ID])

## Rules

* Save every Suite ID because test cases will be created inside the corresponding Suite.
* Each Suite ID must remain associated with its acceptance criterion.
* Test cases generated from an acceptance criterion must be created only within its corresponding Suite.
* If a Suite creation fails, report the exact error.
* Do not continue with the next Suite until the current operation succeeds or the user decides how to proceed.
