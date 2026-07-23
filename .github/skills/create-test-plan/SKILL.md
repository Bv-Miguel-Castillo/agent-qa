---
name: create-test-plan
description: 'Use when the user has confirmed the understanding of the user story and a new Test Plan needs to be created in Azure DevOps.'
---

# Create a Test Plan in Azure DevOps

## What to do

1. Propose the Test Plan name:
- The Test Plan name must be exactly the User Story title.
- Use only the value from the User Story `System.Title` field.
- Do not modify the title.
- Do not add prefixes, suffixes, identifiers, or additional text.

Examples:

Correct:
"User registration"

Incorrect:
"HU-12345 - User registration"
"Test Plan - User registration"

Ask the user: "Please confirm this name or provide a different one."

2. Wait for the user's response. Do not create anything until the name has been confirmed.

3. Create the Test Plan in Azure DevOps via the `ado-remote-mcp` tools using the confirmed name.

4. Confirm to the user:

"✅ Test Plan **[NAME]** created successfully. ID: [ID]"

## Required fields for creation

- Name: the name confirmed by the user
- Area Path: the same area path as the user story's project
- Iteration: the sprint associated with the user story

## Rules

- Save the Test Plan ID; it will be needed in the next step.
- If the creation fails, report the exact error and ask
  the user how they would like to proceed.
- Do not continue if you do not have the confirmed name.
