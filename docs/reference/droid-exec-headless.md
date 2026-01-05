# Automated Code Review

> Set up automated pull request reviews using the Factory GitHub App

Set up automated code review for your repository using the Factory GitHub App. Droid will analyze pull requests, identify issues, and post feedback as inline comments.

<div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
  <div style={{ flex: '1', minWidth: '300px' }}>
    <img src="https://mintcdn.com/factory/h-qPBH0CjxqIkqbW/guides/droid-exec/code-review-picture-1.png?fit=max&auto=format&n=h-qPBH0CjxqIkqbW&q=85&s=8e5dc1e73e4f6e81a18f0ca761df9404" alt="Factory Droid bot posting a code review summary with issues found" data-og-width="1442" width="1442" data-og-height="682" height="682" data-path="guides/droid-exec/code-review-picture-1.png" data-optimize="true" data-opv="3" srcset="https://mintcdn.com/factory/h-qPBH0CjxqIkqbW/guides/droid-exec/code-review-picture-1.png?w=280&fit=max&auto=format&n=h-qPBH0CjxqIkqbW&q=85&s=9f606ec2b1b7adc2ab372e117ab47f34 280w, https://mintcdn.com/factory/h-qPBH0CjxqIkqbW/guides/droid-exec/code-review-picture-1.png?w=560&fit=max&auto=format&n=h-qPBH0CjxqIkqbW&q=85&s=a0bf0cc12a333a9c5db2186b2e8d5b82 560w, https://mintcdn.com/factory/h-qPBH0CjxqIkqbW/guides/droid-exec/code-review-picture-1.png?w=840&fit=max&auto=format&n=h-qPBH0CjxqIkqbW&q=85&s=84e35ee18232de966598f83471ecaef1 840w, https://mintcdn.com/factory/h-qPBH0CjxqIkqbW/guides/droid-exec/code-review-picture-1.png?w=1100&fit=max&auto=format&n=h-qPBH0CjxqIkqbW&q=85&s=e2e4652d031fd973b62e5caecbfa0542 1100w, https://mintcdn.com/factory/h-qPBH0CjxqIkqbW/guides/droid-exec/code-review-picture-1.png?w=1650&fit=max&auto=format&n=h-qPBH0CjxqIkqbW&q=85&s=16512a21ab9cb055c9d4f314e3075196 1650w, https://mintcdn.com/factory/h-qPBH0CjxqIkqbW/guides/droid-exec/code-review-picture-1.png?w=2500&fit=max&auto=format&n=h-qPBH0CjxqIkqbW&q=85&s=505e33328b86dd60a95b97342783534c 2500w" />
  </div>

  <div style={{ flex: '1', minWidth: '300px' }}>
    <img src="https://mintcdn.com/factory/h-qPBH0CjxqIkqbW/guides/droid-exec/code-review-picture-2.png?fit=max&auto=format&n=h-qPBH0CjxqIkqbW&q=85&s=c3398857ac81c4dc013dac67ed078c0f" alt="Factory Droid bot posting inline code review comment on specific lines" data-og-width="1430" width="1430" data-og-height="760" height="760" data-path="guides/droid-exec/code-review-picture-2.png" data-optimize="true" data-opv="3" srcset="https://mintcdn.com/factory/h-qPBH0CjxqIkqbW/guides/droid-exec/code-review-picture-2.png?w=280&fit=max&auto=format&n=h-qPBH0CjxqIkqbW&q=85&s=ae3bb57443c05493a60380a4239b0daa 280w, https://mintcdn.com/factory/h-qPBH0CjxqIkqbW/guides/droid-exec/code-review-picture-2.png?w=560&fit=max&auto=format&n=h-qPBH0CjxqIkqbW&q=85&s=05159822841d106763f0b02d432f775a 560w, https://mintcdn.com/factory/h-qPBH0CjxqIkqbW/guides/droid-exec/code-review-picture-2.png?w=840&fit=max&auto=format&n=h-qPBH0CjxqIkqbW&q=85&s=600f50889da1978590d9210aaa0ff83c 840w, https://mintcdn.com/factory/h-qPBH0CjxqIkqbW/guides/droid-exec/code-review-picture-2.png?w=1100&fit=max&auto=format&n=h-qPBH0CjxqIkqbW&q=85&s=cfbd734c4d977063243deda01ba8d0df 1100w, https://mintcdn.com/factory/h-qPBH0CjxqIkqbW/guides/droid-exec/code-review-picture-2.png?w=1650&fit=max&auto=format&n=h-qPBH0CjxqIkqbW&q=85&s=c6c25dc75da9b31cfa37634b774ac446 1650w, https://mintcdn.com/factory/h-qPBH0CjxqIkqbW/guides/droid-exec/code-review-picture-2.png?w=2500&fit=max&auto=format&n=h-qPBH0CjxqIkqbW&q=85&s=77847360b5dee96484c289756744eac0 2500w" />
  </div>
</div>

## Setup

Use the `/install-gh-app` command to install the Factory GitHub App and configure the code review workflow:

```bash  theme={null}
droid
> /install-gh-app
```

The guided flow will:

1. Verify GitHub CLI prerequisites
2. Install the Factory GitHub App on your repository
3. Let you select the **Droid Review** workflow
4. Create a PR with the workflow files

For detailed setup instructions, see the [GitHub App installation guide](/cli/features/install-github-app).

## How it works

Once enabled, the Droid Review workflow:

1. Triggers on pull request events (opened, synchronized, reopened, ready for review)
2. Skips draft PRs to avoid noise during development
3. Fetches the PR diff and existing comments
4. Analyzes code changes for issues
5. Posts inline comments on problematic lines
6. Submits an approval when no issues are found

## What Droid reviews

The automated reviewer focuses on clear bugs and issues:

* Dead/unreachable code
* Broken control flow (missing break, fallthrough bugs)
* Async/await mistakes
* Null/undefined dereferences
* Resource leaks
* SQL/XSS injection vulnerabilities
* Missing error handling
* Off-by-one errors
* Race conditions

It skips stylistic concerns, minor optimizations, and architectural opinions.

## Customizing the workflow

After the workflow is created, you can customize it by editing `.github/workflows/droid-review.yml` in your repository.

### Change the trigger conditions

Modify when reviews run:

```yaml  theme={null}
on:
  pull_request:
    types: [opened, synchronize, reopened, ready_for_review]
    paths:
      - 'src/**'  # Only review changes in src/
      - '!**/*.test.ts'  # Skip test files
```

### Adjust the review focus

Edit the prompt in the workflow to change what Droid looks for. For example, to add framework-specific checks:

```yaml  theme={null}
run: |
  cat > prompt.txt << 'EOF'
  You are an automated code review system...

  Additional checks for this codebase:
  - React hooks rules violations
  - Missing TypeScript types on public APIs
  - Prisma query performance issues
  EOF
```

### Change the model

Use a different model for reviews:

```yaml  theme={null}
droid exec --auto high --model claude-sonnet-4-5-20250929 -f prompt.txt
# Or use a faster model for quicker feedback:
droid exec --auto high --model claude-haiku-4-5-20251001 -f prompt.txt
```

### Skip certain PRs

Add conditions to skip reviews for specific cases:

```yaml  theme={null}
jobs:
  code-review:
    # Skip bot PRs and PRs with [skip-review] in title
    if: |
      github.event.pull_request.draft == false &&
      !contains(github.event.pull_request.user.login, '[bot]') &&
      !contains(github.event.pull_request.title, '[skip-review]')
```

### Limit comment count

Adjust the maximum number of comments in the prompt:

```
Guidelines:
- Submit at most 5 comments total, prioritizing the most critical issues
```

## See also

* [GitHub App installation](/cli/features/install-github-app) - Full setup guide for `/install-gh-app`
* [GitHub Actions examples](/guides/droid-exec/github-actions) - More automation workflows
* [Droid Exec](/cli/commands/exec) - Running Droid in CI/CD environments


---

> To find navigation and other pages in this documentation, fetch the llms.txt file at: https://docs.factory.ai/llms.txt


# Organize Imports

> Automatically organize imports across your entire codebase using Droid Exec

This tutorial demonstrates how to use Droid Exec to refactor import statements across hundreds of files simultaneously. The script intelligently groups, sorts, and optimizes imports while removing unused dependencies and converting module formats.

## How it works

The script:

1. **Finds files**: Searches for all `.js`, `.jsx`, `.ts`, and `.tsx` files
2. **Filters smartly**: Excludes `node_modules`, `.git`, `dist`, and `build` directories
3. **Checks for imports**: Only processes files that contain import statements
4. **Groups imports**: Organizes into external, internal, and relative imports
5. **Sorts alphabetically**: Within each group for consistency
6. **Removes unused**: Eliminates imports that aren't referenced
7. **Modernizes syntax**: Converts `require()` to ES6 `import`
8. **Consolidates duplicates**: Merges multiple imports from the same module

## Get the script

<Accordion title="View full script source">
  ```bash  theme={null}
  #!/bin/bash

  # Simplified Droid Import Refactoring Script
  # A cookbook example of using AI to refactor imports across a codebase
  #
  # Usage: ./droid-refactor-imports.sh [directory]
  # Example: ./droid-refactor-imports.sh src

  set -e

  # Configuration
  CONCURRENCY=${CONCURRENCY:-5}
  DRY_RUN=${DRY_RUN:-false}
  TARGET_DIR="${1:-.}"

  # Colors for output
  GREEN='\033[0;32m'
  YELLOW='\033[1;33m'
  BLUE='\033[0;34m'
  NC='\033[0m'

  # Temp files for tracking
  TEMP_DIR=$(mktemp -d)
  FILES_LIST="$TEMP_DIR/files.txt"
  MODIFIED_COUNT=0
  PROCESSED_COUNT=0

  # Cleanup on exit
  trap "rm -rf $TEMP_DIR" EXIT

  # Function to process a single file
  process_file() {
      local filepath="$1"
      local filename=$(basename "$filepath")

      # Check if file has imports
      if ! grep -qE "^import |^const .* = require\(|^export .* from" "$filepath" 2>/dev/null; then
          return 0
      fi

      echo -e "${BLUE}Processing: $filepath${NC}"

      # The AI prompt for refactoring imports
      local prompt="Refactor the imports in $filepath:

  1. Group imports in this order with blank lines between:
     - External packages (node_modules)
     - Internal/absolute imports (@/ or src/)
     - Relative imports (./ or ../)

  2. Sort alphabetically within each group
  3. Remove unused imports
  4. Convert require() to ES6 imports
  5. Consolidate duplicate imports from same module

  Only modify imports, preserve all other code exactly.
  Return the complete refactored file."

      if [ "$DRY_RUN" = "true" ]; then
          echo -e "${YELLOW}  [DRY RUN] Would refactor imports${NC}"
          return 0
      fi

      # Get original file hash for comparison
      local original_hash=$(md5sum "$filepath" 2>/dev/null | cut -d' ' -f1 || md5 -q "$filepath")

      # Run droid to refactor the file
      if droid exec --auto low "$prompt" 2>/dev/null; then
          # Check if file was modified
          local new_hash=$(md5sum "$filepath" 2>/dev/null | cut -d' ' -f1 || md5 -q "$filepath")
          if [ "$original_hash" != "$new_hash" ]; then
              echo -e "${GREEN}  ✓ Refactored${NC}"
              ((MODIFIED_COUNT++))
          fi
          ((PROCESSED_COUNT++))
      else
          echo "  ✗ Failed to process"
      fi
  }

  # Export function and variables for parallel execution
  export -f process_file
  export DRY_RUN GREEN YELLOW BLUE NC

  # Main execution
  echo -e "${BLUE}=== Droid Import Refactoring ===${NC}"
  echo -e "${BLUE}Directory: $TARGET_DIR${NC}"
  echo -e "${BLUE}Concurrency: $CONCURRENCY${NC}"
  [ "$DRY_RUN" = "true" ] && echo -e "${YELLOW}DRY RUN MODE${NC}"
  echo ""

  # Find JavaScript and TypeScript files
  find "$TARGET_DIR" -type f \
      \( -name "*.js" -o -name "*.jsx" -o -name "*.ts" -o -name "*.tsx" \) \
      ! -path "*/node_modules/*" \
      ! -path "*/.git/*" \
      ! -path "*/dist/*" \
      ! -path "*/build/*" \
      > "$FILES_LIST"

  FILE_COUNT=$(wc -l < "$FILES_LIST" | tr -d ' ')

  if [ "$FILE_COUNT" -eq 0 ]; then
      echo -e "${YELLOW}No JavaScript/TypeScript files found${NC}"
      exit 0
  fi

  echo -e "${BLUE}Found $FILE_COUNT files to check${NC}\n"

  # Process files in parallel
  cat "$FILES_LIST" | xargs -n 1 -P "$CONCURRENCY" -I {} bash -c 'process_file "$@"' _ {}

  # Show summary
  echo -e "\n${BLUE}=== Summary ===${NC}"
  echo -e "${GREEN}Files processed: $PROCESSED_COUNT${NC}"
  [ "$DRY_RUN" = "false" ] && echo -e "${GREEN}Files modified: $MODIFIED_COUNT${NC}"

  if [ "$DRY_RUN" = "false" ] && [ "$MODIFIED_COUNT" -gt 0 ]; then
      echo -e "\n${BLUE}Next steps:${NC}"
      echo "  git diff           # Review changes"
      echo "  git add -A         # Stage changes"
      echo "  git commit -m 'refactor: organize imports'"
  fi
  ```
</Accordion>

## Prerequisites

Before you begin, complete the [Droid Exec installation](/cli/droid-exec/overview#installation).

## Basic usage

### Preview changes (dry run)

<Warning>
  Always start with a dry run to preview changes before modifying files. This helps you understand what transformations will be applied.
</Warning>

The dry run feature is controlled by the `DRY_RUN` environment variable:

```bash  theme={null}
# Preview what would happen (no changes made)
DRY_RUN=true ./droid-refactor-imports.sh src

# Example output:
# === Droid Import Refactoring ===
# Directory: src
# Concurrency: 5
# DRY RUN MODE
#
# Found 25 files to check
#
# Processing: src/components/Button.tsx
#   [DRY RUN] Would refactor imports
# Processing: src/utils/api.ts
#   [DRY RUN] Would refactor imports
```

**How dry run works:**

* When `DRY_RUN=true`: The script finds all files that need processing and shows which files have imports to refactor, but doesn't modify any files
* When `DRY_RUN=false` (default): Actually runs the AI refactoring and modifies the files

This is particularly useful for:

* Testing on a small directory first to understand the changes
* Estimating time/cost before processing a large codebase
* Verifying the script finds the right files before committing to changes

### Apply refactoring

Once you're satisfied with the preview, run the actual refactoring:

```bash  theme={null}
# Actually refactor the imports (default behavior)
./droid-refactor-imports.sh packages/models

# Or explicitly set DRY_RUN=false
DRY_RUN=false ./droid-refactor-imports.sh packages/models

# Adjust concurrency for faster processing
CONCURRENCY=10 ./droid-refactor-imports.sh packages/models
```

Actual execution example:

```
=== Droid Import Refactoring ===
Directory: packages/models
Concurrency: 5

Found 78 files to check

Processing: packages/models/src/organization/test-utils/fixtures.ts
Processing: packages/models/src/organization/agentReadiness/types.ts
Processing: packages/models/src/organization/utils.ts
Processing: packages/models/src/organization/agentReadiness/handlers.ts
Processing: packages/models/jest.config.ts
Processing: packages/models/src/organization/user/defaultRepositories/handlers.ts
Perfect! I've successfully refactored the imports in the file...
## Summary

I've successfully refactored the imports in `packages/models/src/organization/test-utils/fixtures.ts`.
The imports are now properly organized with comments separating external packages from relative imports...
...
```

## Real-world transformations

### Example 1: CommonJS to ES6 Conversion

<Tabs>
  <Tab title="Before">
    ```typescript  theme={null}
    // customers.ts
    const getStripeInstance = require("./instance").getStripeInstance;
    import dayjs from 'dayjs';  // unused import
    import url from 'url';  // unused import
    ```
  </Tab>

  <Tab title="After">
    ```typescript  theme={null}
    // customers.ts
    // Relative imports
    import { getStripeInstance } from './instance';
    ```

    <Note>CommonJS converted to ES6, unused imports removed</Note>
  </Tab>
</Tabs>

### Example 2: Consolidating Duplicate Imports

<Tabs>
  <Tab title="Before">
    ```typescript  theme={null}
    // admin.ts
    const { auth } = require('firebase-admin');
    import { App } from "firebase-admin/app"
    import { Firestore } from 'firebase-admin/firestore';
    import dotenv from 'dotenv';  // unused import
    const { FirebaseProjectName } = require("./enums");
    import {
      getFirestoreInstanceForProject,
      getFirebaseAuthInstanceForProject,
    } from './multi-admin';
    const { initializeFirebaseAdminApp } = require('./multi-admin');
    import {
      getFirestoreInstance as getDefaultFirestoreInstance,
      getFirestoreInstanceForTest as getDefaultFirestoreInstanceForTest,
      getFirebaseAuthInstance as getDefaultFirebaseAuthInstance,
    } from "./multi-admin"
    import express from 'express';  // unused import
    ```
  </Tab>

  <Tab title="After">
    ```typescript  theme={null}
    // admin.ts
    // External packages
    import { auth } from 'firebase-admin';
    import { App } from 'firebase-admin/app';
    import { Firestore } from 'firebase-admin/firestore';

    // Relative imports
    import { FirebaseProjectName } from './enums';
    import {
      getFirestoreInstanceForProject,
      getFirebaseAuthInstanceForProject,
      initializeFirebaseAdminApp,
      getFirestoreInstance as getDefaultFirestoreInstance,
      getFirestoreInstanceForTest as getDefaultFirestoreInstanceForTest,
      getFirebaseAuthInstance as getDefaultFirebaseAuthInstance,
    } from './multi-admin';
    ```

    <Note>Multiple imports from same module consolidated, unused removed, CommonJS converted</Note>
  </Tab>
</Tabs>

## Best practices

<Note>
  Follow these best practices for safe and effective import refactoring.
</Note>

<Steps>
  <Step title="Start with a dry run">
    Always preview changes before modifying files:

    ```bash  theme={null}
    # Preview what would happen without making changes
    DRY_RUN=true ./droid-refactor-imports.sh packages/models
    ```
  </Step>

  <Step title="Test on a small scope first">
    Start with a specific subdirectory before processing entire codebase:

    ```bash  theme={null}
    # Test on a single module first
    ./droid-refactor-imports.sh packages/models/src/utils

    # Then expand to larger directories
    ./droid-refactor-imports.sh packages/models
    ```
  </Step>

  <Step title="Process incrementally">
    For large codebases, process directories separately for easier review:

    ```bash  theme={null}
    # Process each package separately
    ./droid-refactor-imports.sh packages/models
    git add -A && git commit -m "refactor: organize imports in models"

    ./droid-refactor-imports.sh packages/services
    git add -A && git commit -m "refactor: organize imports in services"
    ```
  </Step>
</Steps>


---

> To find navigation and other pages in this documentation, fetch the llms.txt file at: https://docs.factory.ai/llms.txt


# Improve Error Messages

> Automatically improve Error messages across your entire codebase using Droid Exec

This tutorial demonstrates how to use Droid Exec to refactor error messages across hundreds of files simultaneously. The script intelligently finds all ResponseError instantiations and improves their messages to be more descriptive, actionable, and user-friendly.

<Info>
  `ResponseError` is Factory's internal error handling class used to throw HTTP-style errors with specific status codes. These error classes are used throughout the codebase to handle API errors.
</Info>

## How it works

The script:

1. **Finds files**: Searches for all `.ts` and `.tsx` files containing ResponseError classes
2. **Filters smartly**: Excludes `node_modules`, `.git`, `dist`, `build`, and `.next` directories
3. **Identifies errors**: Locates all ResponseError instantiations (400, 401, 403, 404, etc.)
4. **Improves messages**: Makes them more descriptive and actionable
5. **Adds context**: Includes what went wrong and potential fixes
6. **User-friendly language**: Removes technical jargon
7. **Preserves metadata**: Keeps error codes and metadata intact

## Get the script

<Accordion title="View full script source">
  ```bash  theme={null}
  #!/bin/bash

  # Droid Error Message Improvement Script

  # Automatically improves ResponseError messages across the codebase

  #

  # Usage: ./droid-improve-errors.sh [directory]

  # Example: ./droid-improve-errors.sh apps

  set -e

  # Configuration

  CONCURRENCY=${CONCURRENCY:-5}
  DRY_RUN=${DRY_RUN:-false}
  TARGET_DIR="${1:-.}"

  # Colors for output

  GREEN='\033[0;32m'
  YELLOW='\033[1;33m'
  BLUE='\033[0;34m'
  RED='\033[0;31m'
  NC='\033[0m'

  # Temp files for tracking

  TEMP_DIR=$(mktemp -d)
  FILES_LIST="$TEMP_DIR/files.txt"
  ERRORS_FOUND="$TEMP_DIR/errors_found.txt"
  MODIFIED_COUNT=0
  PROCESSED_COUNT=0
  ERRORS_IMPROVED=0

  # Cleanup on exit

  trap "rm -rf $TEMP_DIR" EXIT

  # Function to process a single file

  process_file() {
  local filepath="$1"
      local filename=$(basename "$filepath")

      # Check if file contains ResponseError instantiations
      if ! grep -qE "new ResponseError[0-9]+|throw new ResponseError" "$filepath" 2>/dev/null; then
          return 0
      fi

      # Count error instances for reporting
      local error_count=$(grep -cE "new ResponseError[0-9]+" "$filepath" 2>/dev/null || echo 0)

      echo -e "${BLUE}Processing: $filepath${NC}"
      echo -e "  Found $error_count error instantiation(s)"

      # The AI prompt for improving error messages
      local prompt="Improve the error messages in $filepath:

  Find all ResponseError instantiations (ResponseError400BadRequest, ResponseError401Unauthorized, etc.)
  and improve their error messages following these guidelines:

  1. Make messages more descriptive and actionable
  2. Include context about what went wrong
  3. Suggest potential fixes when appropriate
  4. Use user-friendly language (avoid technical jargon)
  5. Include relevant details without exposing sensitive data

  Examples of improvements:

  - 'Invalid api key format' → 'API key must be a 32-character alphanumeric string starting with \"fac\_\"'
  - 'Organization not found' → 'Organization with ID {orgId} not found. Please verify the organization exists and you have access.'
  - 'Invalid CSRF token' → 'Security validation failed. Please refresh the page and try again.'
  - 'Invalid request parameters' → 'Missing required field \"email\". Please provide a valid email address.'
  - 'User is already a member' → 'This user is already a member of the organization and cannot be invited again.'

  Only modify the error message strings, preserve all other code including metadata parameters.
  Return the complete file with improved error messages."

      if [ "$DRY_RUN" = "true" ]; then
          echo -e "${YELLOW}  [DRY RUN] Would improve $error_count error message(s)${NC}"
          echo "$error_count" >> "$ERRORS_FOUND"
          return 0
      fi

      # Get original file hash for comparison
      local original_hash=$(md5sum "$filepath" 2>/dev/null | cut -d' ' -f1 || md5 -q "$filepath")

      # Run droid to improve error messages
      if droid exec --auto low "$prompt" 2>/dev/null; then
          # Check if file was modified
          local new_hash=$(md5sum "$filepath" 2>/dev/null | cut -d' ' -f1 || md5 -q "$filepath")
          if [ "$original_hash" != "$new_hash" ]; then
              echo -e "${GREEN}  ✓ Improved error messages${NC}"
              ((MODIFIED_COUNT++))
              ((ERRORS_IMPROVED+=error_count))
          else
              echo -e "  No changes needed"
          fi
          ((PROCESSED_COUNT++))
      else
          echo -e "${RED}  ✗ Failed to process${NC}"
      fi

  }

  # Export function and variables for parallel execution

  export -f process_file
  export DRY_RUN GREEN YELLOW BLUE RED NC ERRORS_FOUND

  # Main execution

  echo -e "${BLUE}=== Droid Error Message Improvement ===${NC}"
  echo -e "${BLUE}Directory: $TARGET_DIR${NC}"
  echo -e "${BLUE}Concurrency: $CONCURRENCY${NC}"
  [ "$DRY_RUN" = "true" ] && echo -e "${YELLOW}DRY RUN MODE${NC}"
  echo ""

  # Find TypeScript files containing ResponseError

  find "$TARGET_DIR" -type f \( -name "*.ts" -o -name "*.tsx" \) \
      ! -path "*/node_modules/*" \
      ! -path "*/.git/*" \
      ! -path "*/dist/*" \
      ! -path "*/build/*" \
      ! -path "*/.next/*" \
      ! -path "*/coverage/*" \
      -exec grep -l "ResponseError[0-9]" {} \; 2>/dev/null > "$FILES_LIST" || true

  FILE_COUNT=$(wc -l < "$FILES_LIST" | tr -d ' ')

  if [ "$FILE_COUNT" -eq 0 ]; then
  echo -e "${YELLOW}No files with ResponseError found${NC}"
  exit 0
  fi

  echo -e "${BLUE}Found $FILE_COUNT files with ResponseError classes${NC}\n"

  # Process files in parallel

  cat "$FILES_LIST" | xargs -n 1 -P "$CONCURRENCY" -I {} bash -c 'process_file "$@"' _ {}

  # Calculate total errors found in dry run

  if [ "$DRY_RUN" = "true" ] && [ -f "$ERRORS_FOUND" ]; then
  TOTAL_ERRORS=$(awk '{sum+=$1} END {print sum}' "$ERRORS_FOUND" 2>/dev/null || echo 0)
  fi

  # Show summary

  echo -e "\n${BLUE}=== Summary ===${NC}"
  echo -e "${GREEN}Files scanned: $FILE_COUNT${NC}"
  echo -e "${GREEN}Files processed: $PROCESSED_COUNT${NC}"

  if [ "$DRY_RUN" = "true" ]; then
  [ -n "$TOTAL_ERRORS" ] && echo -e "${YELLOW}Error messages to improve: $TOTAL_ERRORS${NC}"
  else
  echo -e "${GREEN}Files modified: $MODIFIED_COUNT${NC}"
  [ "$ERRORS_IMPROVED" -gt 0 ] && echo -e "${GREEN}Error messages improved: ~$ERRORS_IMPROVED${NC}"
  fi

  if [ "$DRY_RUN" = "false" ] && [ "$MODIFIED_COUNT" -gt 0 ]; then
  echo -e "\n${BLUE}Next steps:${NC}"
  echo " git diff # Review changes"
  echo " npm run typecheck # Verify types"
  echo " npm run test # Run tests"
  echo " git add -A # Stage changes"
  echo " git commit -m 'refactor: improve error messages for better UX'"
  fi

  ```
</Accordion>

## Prerequisites

Before you begin, complete the [Droid Exec installation](/cli/droid-exec/overview#installation).

## Basic usage

### Preview changes (dry run)

<Warning>
  Always start with a dry run to see how many error messages need improvement before modifying files.
</Warning>

The dry run feature shows you exactly which files contain ResponseError instantiations and how many:

```bash  theme={null}
# Preview what would happen (no changes made)
DRY_RUN=true ./droid-improve-errors.sh apps/factory-admin/src/app/api/_utils/middleware.ts

# Example output:
# === Droid Error Message Improvement ===
# Directory: apps/factory-admin/src/app/api/_utils/middleware.ts
# Concurrency: 5
# DRY RUN MODE
#
# Found 1 files with ResponseError classes
#
# Processing: apps/factory-admin/src/app/api/_utils/middleware.ts
#   Found 6 error instantiation(s)
#   [DRY RUN] Would improve 6 error message(s)
#
# === Summary ===
# Files scanned: 1
# Files processed: 0
# Error messages to improve: 6
```

**How dry run works:**

* When `DRY_RUN=true`: Counts all ResponseError instantiations without making changes
* When `DRY_RUN=false` (default): Actually improves the error messages using AI

This helps you:

* Estimate the scope of changes needed
* Test on a small directory first
* Plan your refactoring strategy

### Apply refactoring

Once you're ready, run the actual error message improvement:

```bash  theme={null}
# Actually improve the error messages (default behavior)
./droid-improve-errors.sh apps/factory-admin

# Or explicitly set DRY_RUN=false
DRY_RUN=false ./droid-improve-errors.sh apps/factory-admin

# Adjust concurrency for faster processing
CONCURRENCY=10 ./droid-improve-errors.sh packages
```

Actual execution example:

```bash  theme={null}
% ./scripts/droid-improve-errors.sh apps/factory-admin/src/app/api/_utils/middleware.ts
=== Droid Error Message Improvement ===
Directory: apps/factory-admin/src/app/api/_utils/middleware.ts
Concurrency: 5

Found 1 files with ResponseError classes

Processing: apps/factory-admin/src/app/api/_utils/middleware.ts
  Found 6 error instantiation(s)
## Summary

I've successfully improved all error messages in the `apps/factory-admin/src/app/api/_utils/middleware.ts` file. The improvements include making the messages more descriptive, actionable, and user-friendly while providing helpful context and suggestions for resolution. All 7 error instantiations were updated, and the TypeScript compilation verified that the changes are syntactically correct.
```

## Real-world transformations

### Example 1: Session Authentication

<Tabs>
  <Tab title="Before">
    ```typescript  theme={null}
    // middleware.ts
    if (!sessionCookie?.value) {
      throw new ResponseError401Unauthorized('No session');
    }

    if (!userRecord) {
      throw new ResponseError401Unauthorized('Invalid session');
    }
    ```
  </Tab>

  <Tab title="After">
    ```typescript  theme={null}
    // middleware.ts
    if (!sessionCookie?.value) {
      throw new ResponseError401Unauthorized(
        'Session cookie not found. Please sign in again to access the admin dashboard.'
      );
    }

    if (!userRecord) {
      throw new ResponseError401Unauthorized(
        'Session is invalid or has expired. Please sign in again to continue.'
      );
    }
    ```

    <Note>Clear instructions on what went wrong and how to fix it</Note>
  </Tab>
</Tabs>

### Example 2: Bearer Token Authorization

<Tabs>
  <Tab title="Before">
    ```typescript  theme={null}
    // middleware.ts
    if (!authHeader) {
      throw new ResponseError401Unauthorized('Missing auth header');
    }

    if (authHeader !== `Bearer ${secret}`) {
      throw new ResponseError401Unauthorized('Invalid token');
    }
    ```
  </Tab>

  <Tab title="After">
    ```typescript  theme={null}
    // middleware.ts
    if (!authHeader) {
      throw new ResponseError401Unauthorized(
        'Authorization header is missing. Please include a valid Bearer token in the Authorization header.'
      );
    }

    if (authHeader !== `Bearer ${secret}`) {
      throw new ResponseError401Unauthorized(
        'Invalid or expired authorization token. Please verify your API credentials and ensure the token is properly formatted as "Bearer <token>".'
      );
    }
    ```

    <Note>Specific format requirements and troubleshooting hints added</Note>
  </Tab>
</Tabs>

## Best practices

<Note>
  Follow these best practices for safe and effective error message improvement.
</Note>

<Steps>
  <Step title="Start with a dry run">
    Always preview the scope of changes first:

    ```bash  theme={null}
    # See how many errors need improvement
    DRY_RUN=true ./droid-improve-errors.sh packages
    ```
  </Step>

  <Step title="Process incrementally">
    For large codebases, tackle one module at a time:

    ```bash  theme={null}
    # Process each app separately for easier review
    ./droid-improve-errors.sh apps/factory-admin
    git add -A && git commit -m "refactor(factory-admin): improve error messages"

    ./droid-improve-errors.sh apps/factory-app
    git add -A && git commit -m "refactor(factory-app): improve error messages"
    ```
  </Step>
</Steps>


---

> To find navigation and other pages in this documentation, fetch the llms.txt file at: https://docs.factory.ai/llms.txt

Droid Exec (Headless)
Automated Lint Fixes

Copy page

Automatically fix ESLint violations across your codebase using Droid Exec

This tutorial demonstrates how to use Droid Exec to automatically fix ESLint violations across your codebase. The script identifies files with lint errors and intelligently fixes them while preserving functionality.
This approach works with any ESLint rule - from simple formatting issues to complex architectural patterns.
​
How it works
The script:
Finds violations: Runs ESLint to identify all route.ts files missing middleware
Analyzes context: Determines the appropriate middleware type based on the route path
Adds middleware: Inserts the correct handle*Middleware call as the first statement
Preserves logic: Wraps existing code in the middleware callback
Maintains types: Ensures TypeScript types are correctly preserved
Formats code: Maintains consistent code style
​
Get the script
View full script source

Critical for Success: When customizing this script for your own lint rules, always include concrete before/after examples in the prompt you give to Droid Exec. This dramatically improves accuracy.
Good prompt structure:
Describe the violation to fix
Show a “before” code example with the violation
Show an “after” code example with the fix applied
List any edge cases or patterns to preserve
The more specific your examples, the better Droid will understand and implement the fix pattern.
​
Prerequisites
Before you begin, ensure you have completed the Droid Exec installation
​
Basic usage
​
Preview violations (dry run)
Always start with a dry run to see which files need fixing before making changes.
The dry run shows you which files violate the middleware rule and what type of middleware would be added:
# Preview what would happen (no changes made)
DRY_RUN=true ./droid-fix-route-middleware.sh apps/factory-admin/src/app/api

# Example output:
# === Droid Route Middleware Fix ===
# Directory: apps/factory-admin/src/app/api
# Concurrency: 5
# DRY RUN MODE
#
# Scanning for route middleware violations...
# Found 3 files with middleware violations
#
# Processing: apps/factory-admin/src/app/api/health/route.ts
#   Detected type: public middleware needed
#   [DRY RUN] Would add public middleware
# Processing: apps/factory-admin/src/app/api/orgs/route.ts
#   Detected type: admin middleware needed
#   [DRY RUN] Would add admin middleware
# Processing: apps/factory-admin/src/app/api/cron/batch-friction/poll-and-report/route.ts
#   Detected type: cron middleware needed
#   [DRY RUN] Would add cron middleware
#
# === Summary ===
# Files processed: 0
How dry run works:
When DRY_RUN=true: Identifies violations and shows what middleware type would be added
When DRY_RUN=false (default): Actually fixes the violations by adding middleware
This helps you:
Understand which routes are missing middleware
Verify the correct middleware type will be used
Estimate the scope of changes
​
Apply fixes
Once ready, run the actual fix:
# Fix all violations in a directory
./droid-fix-route-middleware.sh apps/factory-admin/src/app/api

# Example output:
# === Droid Route Middleware Fix ===
# Directory: apps/factory-admin/src/app/api
# Concurrency: 5
#
# Scanning for route middleware violations...
# Found 3 files with middleware violations
#
# Processing: apps/factory-admin/src/app/api/health/route.ts
#   Detected type: public middleware needed
# Processing: apps/factory-admin/src/app/api/cron/batch-friction/poll-and-report/route.ts
#   Detected type: cron middleware needed
# Processing: apps/factory-admin/src/app/api/orgs/route.ts
#   Detected type: admin middleware needed
# ✓ Fixed middleware violations
# ✓ Fixed middleware violations
# ✓ Fixed middleware violations
​
Real-world transformations
​
Example 1: Simple GET Handler
Before
After
Missing middleware - no authentication check!
// apps/factory-app/src/app/api/sessions/route.ts
import { NextRequest, NextResponse } from 'next/server';
import { getFirestoreInstance } from '@factory/services/firebase/admin';

export async function GET(req: NextRequest) {
  const searchParams = req.nextUrl.searchParams;
  const userId = searchParams.get('userId');

  ...

  return NextResponse.json({
    sessions: sessions.docs.map(doc => doc.data())
  });
}
​
Example 2: Cron Job Handler
Before
After
Cron job without authorization - anyone could trigger it!
// apps/factory-admin/src/app/api/cron/batch-friction/poll-and-report/route.ts
export async function GET(request: NextRequest) {

  logInfo('[poll-report] Starting poll and report workflow');

  const results = {
    polledBatches: 0,
    processedBatches: 0,
    failedBatches: [],
    reportGenerated: false,
    reportError: null,
  };

  // ... rest of the cron job logic ...

  return NextResponse.json({
    success,
    message,
    summary: {
      processedBatches: results.processedBatches,
      failedBatches: results.failedBatches.length,
      reportGenerated: results.reportGenerated,
    },
  });
}
​
Best practices
Follow these best practices for safe and effective middleware addition.
1
Start with dry run

Preview changes before applying:
# See what would be fixed without making changes
DRY_RUN=true ./droid-fix-route-middleware.sh apps
2
Process by app

Fix one application at a time for easier review:
# Fix factory-app routes
./droid-fix-route-middleware.sh apps/factory-app
npm run typecheck -- --filter=factory-app
git add -A && git commit -m "fix(factory-app): add required middleware to API routes"

# Fix factory-admin routes
./droid-fix-route-middleware.sh apps/factory-admin
npm run typecheck -- --filter=factory-admin
git add -A && git commit -m "fix(factory-admin): add required middleware to API routes"

# Automated Documentation

> Automatically update documentation when code changes using CI/CD workflows

This cookbook demonstrates how to use Droid Exec in GitHub Actions to automatically update documentation when code is merged to main. The workflow analyzes code changes, discovers relevant documentation, updates it, and creates a pull request for human review.

## How it works

End-to-end automated workflow:

1. **Trigger**: Code merged to main branch
2. **Explore**: Droid exec explores codebase structure (project type, tech stack)
3. **Analyze**: Identifies changed files and their purpose
4. **Discover**: Searches docs/ directory for relevant documentation
5. **Update**: Updates affected documentation sections
6. **Commit**: Workflow creates commit
7. **PR**: Bot opens pull request for team review

## Prerequisites

To get started, you'll need:

* Droid installed
* A Factory API key
* GitHub repository with Actions enabled
* `FACTORY_API_KEY` in repository secrets (Settings → Secrets → Actions)
* Existing documentation directory

<Note>
  See the Droid Exec setup [here](/cli/droid-exec/overview#installation).
</Note>

## Complete GitHub Actions workflow

<Info>
  This workflow will create pull requests automatically. Review the generated PRs carefully before merging to ensure accuracy.
</Info>

Create `.github/workflows/update-docs.yml`:

```yaml  theme={null}
name: Auto-Update Documentation

on:
  push:
    branches: [main]
    paths:
      - 'src/**/*.ts'
      - 'src/**/*.tsx'
      - 'src/**/*.js'
      - 'src/**/*.py'

jobs:
  update-docs:
    runs-on: ubuntu-latest
    permissions:
      contents: write
      pull-requests: write

    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
          token: ${{ secrets.GITHUB_TOKEN }}

      - name: Setup droid CLI
        run: |
          curl -fsSL https://app.factory.ai/cli | sh
          echo "$HOME/.local/bin" >> $GITHUB_PATH

      - name: Get changed files
        id: changes
        run: |
          git diff --name-only HEAD^ HEAD > changed_files.txt
          echo "Files changed in last commit:"
          cat changed_files.txt

      - name: Update documentation
        env:
          FACTORY_API_KEY: ${{ secrets.FACTORY_API_KEY }}
        run: |
          droid exec --auto low "
          The following source files were just merged to main:
          $(cat changed_files.txt)

          Your task is to update the documentation to match these code changes.

          First, explore the codebase to understand context:
          1. Examine package.json, README, and main entry points
          2. Identify key directories and their purposes
          3. Note the tech stack (languages, frameworks, tools)
          4. Classify the project type:
             - **Library/SDK**: Exports functions/classes, has API docs, used as dependency
             - **Application**: Has routes/pages, domain models, user features
             - **Framework/Protocol**: Defines specs, client/server implementations
             - **Monorepo**: Multiple packages/apps in one repository

          Then, understand what changed:
          1. Read each changed file carefully
          2. Identify if changes are: API updates, new features, bug fixes, refactors
          3. Note breaking changes or new configuration options

          Next, find and update relevant documentation:
          1. Search the docs/ directory for files that reference:
             - The changed filenames or paths
             - Functions, classes, or APIs that were modified
             - Features or concepts affected by the changes
          2. Update the found documentation:
             - Update function signatures if they changed
             - Update code examples to match new APIs
             - Update configuration docs if options changed
             - Update explanations if behavior changed
             - Add notes about breaking changes if needed
          3. Preserve the existing doc structure and writing style
          4. Only modify sections that are actually affected

          DO NOT commit or push changes.

          Finally, create doc-update-summary.md with:
          - List of documentation files that were updated
          - Summary of changes made to each file
          - Any sections that may need human review or clarification
          "

      - name: Commit documentation updates
        run: |
          if [ -n "$(git status --porcelain)" ]; then
            git config user.name "github-actions[bot]"
            git config user.email "github-actions[bot]@users.noreply.github.com"
            git add -A
            git commit -m "docs: automated documentation updates"
          else
            echo "No documentation changes needed"
            exit 0
          fi

      - name: Create Pull Request
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          BRANCH="docs/auto-update-$(date +%Y%m%d-%H%M%S)"
          git checkout -b $BRANCH
          git push origin $BRANCH

          # Get summary or use default message
          SUMMARY=$(cat doc-update-summary.md 2>/dev/null || echo "Documentation updated to reflect recent code changes.")

          gh pr create \
            --title "📚 Automated documentation updates" \
            --body "## Automated Documentation Updates

$SUMMARY

### Review Checklist
- [ ] Documentation accurately reflects code changes
- [ ] Code examples are correct and runnable
- [ ] No unintended changes to other sections
- [ ] Formatting and style are consistent

---
This PR was automatically generated after code was merged to main." \
            --label "documentation,automated"
```

**Key workflow features:**

* Uses `--auto low` for file modifications only (following cookbook patterns)
* Explicit instruction: "DO NOT commit or push" (separation of concerns)
* Workflow handles git operations in separate step
* Droid autonomously explores codebase and discovers relevant docs (no mapping file needed)

## Best practices

<Steps>
  <Step title="Scope triggers carefully">
    Only trigger on meaningful code changes:

    ```yaml  theme={null}
    paths:
      - 'src/**'
      - '!src/**/*.test.ts'
      - '!src/**/*.spec.ts'
    ```
  </Step>

  <Step title="Use --auto low for safety">
    Following cookbook patterns:

    ```bash  theme={null}
    droid exec --auto low "..." # File changes only
    # Workflow handles git operations separately
    ```
  </Step>

  <Step title="Trust autonomous discovery">
    Let droid explore and find relevant docs rather than maintaining manual mappings:

    ```bash  theme={null}
    "Search the docs/ directory for files that reference the changed code"
    ```
  </Step>

  <Step title="Always generate summaries">
    Help reviewers understand changes:

    ```bash  theme={null}
    "Create doc-update-summary.md explaining what was updated and why"
    ```
  </Step>

  <Step title="Consider rate limits">
    For high-frequency repos, use scheduled batch updates:

    ```yaml  theme={null}
    schedule:
      - cron: '0 9 * * 1'  # Weekly on Monday
    ```
  </Step>
</Steps>

## Variations

### Weekly comprehensive review

For repositories with frequent changes, batch updates into a weekly review:

```yaml  theme={null}
on:
  schedule:
    - cron: '0 9 * * 1'  # Monday 9 AM
  workflow_dispatch:  # Allow manual trigger
```

### Multiple documentation directories

If your docs are spread across multiple locations:

```bash  theme={null}
droid exec --auto low "
Search docs/, guides/, and README.md for documentation to update
based on these code changes: $(cat changed_files.txt)
"
```

### Language-specific targeting

Focus on specific file types:

```yaml  theme={null}
on:
  push:
    branches: [main]
    paths:
      - 'src/**/*.ts'
      - 'src/**/*.tsx'
      # TypeScript changes only
```

## Troubleshooting

<Accordion title="No PR created even though code changed">
  Droid may have determined no docs needed updates. Check the workflow logs or add more specific search instructions in the prompt. You can also check if `doc-update-summary.md` was created to see what droid analyzed.
</Accordion>

<Accordion title="Wrong sections get updated">
  Improve the exploration prompt to be more specific about what to look for. Consider adding explicit instructions about which doc sections should or shouldn't be modified.
</Accordion>

<Accordion title="Droid can't find relevant docs">
  Make the search instructions more explicit by pointing Droid Exec at specific directories, filenames, or keywords. Providing a short list of likely docs can dramatically improve accuracy.
</Accordion>

<Accordion title="Workflow times out">
  For large repositories, consider:

  * Increasing the timeout in the workflow
  * Processing documentation updates in batches
  * Using scheduled updates instead of triggering on every merge
</Accordion>

## See also

* [Droid Exec Overview](/cli/droid-exec/overview) - Autonomy levels and capabilities
* [GitHub Actions Cookbook](/guides/droid-exec/github-actions) - More workflow examples
* [Documentation Sync Hooks](/guides/hooks/documentation-sync) - Preventive approach


---

> To find navigation and other pages in this documentation, fetch the llms.txt file at: https://docs.factory.ai/llms.txt

# GitHub Actions

> Ready-to-use GitHub Actions workflows with droid exec.

# GitHub Actions

**Prerequisites:** Add `FACTORY_API_KEY` to repository secrets (Settings → Secrets → Actions)

## Example 1: Automated PR Review and Fix

Automatically reviews PRs, fixes issues, and posts detailed feedback.

<Info>
  For a simpler setup, use the [`/install-gh-app`](/cli/features/install-github-app) command which configures the Factory GitHub App with guided steps.
</Info>

```yaml  theme={null}
name: PR Assistant
on:
  pull_request:
    types: [opened, synchronize]

jobs:
  review-and-fix:
    runs-on: ubuntu-latest
    permissions:
      contents: write
      pull-requests: write

    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
          token: ${{ secrets.GITHUB_TOKEN }}

      - name: Setup droid CLI
        run: |
          curl -fsSL https://app.factory.ai/cli | sh
          echo "$HOME/.local/bin" >> $GITHUB_PATH

      - name: Analyze and fix code
        env:
          FACTORY_API_KEY: ${{ secrets.FACTORY_API_KEY }}
        run: |
          # Get the diff
          git diff origin/${{ github.base_ref }}...HEAD > pr_changes.diff

          # Review and fix issues (pipe diff to stdin)
          cat pr_changes.diff | droid exec --auto low "
          Review this PR diff and:
          1. Fix any obvious bugs, typos, or linting errors
          2. Add missing error handling
          3. Improve code comments where unclear
          4. DO NOT commit or push changes
          "

          # Generate review report (needs --auto to write files)
          droid exec --auto low "Analyze the changes again and write a detailed review to review.md with:
          - Summary of automated fixes made
          - Remaining issues that need human attention
          - Security or performance concerns
          - Test coverage recommendations"

      - name: Commit fixes if any
        run: |
          if [ -n "$(git status --porcelain)" ]; then
            git config user.name "github-actions[bot]"
            git config user.email "github-actions[bot]@users.noreply.github.com"
            git add -A
            git commit -m "fix: automated improvements for PR #${{ github.event.pull_request.number }}

            Co-authored-by: factory-droid[bot] <138933559+factory-droid[bot]@users.noreply.github.com>"
            git push
          fi

      - name: Post review comment
        if: always()
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            let review = '## 🤖 Automated Review\n\n';

            if (fs.existsSync('review.md')) {
              review += fs.readFileSync('review.md', 'utf8');
            } else {
              review += 'Review completed successfully.';
            }

            await github.rest.issues.createComment({
              owner: context.repo.owner,
              repo: context.repo.repo,
              issue_number: context.issue.number,
              body: review
            });
```

## Example 2: Daily Documentation and Test Updates

Keeps documentation and tests in sync with code changes automatically.

```yaml  theme={null}
name: Daily Maintenance
on:
  schedule:
    - cron: '0 3 * * *'  # 3 AM UTC daily
  workflow_dispatch:  # Allow manual trigger

jobs:
  update-docs-and-tests:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Setup droid CLI
        run: |
          curl -fsSL https://app.factory.ai/cli | sh
          echo "$HOME/.local/bin" >> $GITHUB_PATH

      - name: Update documentation
        env:
          FACTORY_API_KEY: ${{ secrets.FACTORY_API_KEY }}
        run: |
          droid exec --auto low "
          Review all code files modified in the last 7 days and:
          1. Update any outdated JSDoc/docstring comments
          2. Update README.md if new features were added
          3. Add missing documentation for public APIs
          4. Update examples to match current implementation
          Write a summary of changes to docs-updates.md
          "

      - name: Generate missing tests
        env:
          FACTORY_API_KEY: ${{ secrets.FACTORY_API_KEY }}
        run: |
          droid exec --auto low "
          Find functions and components without test coverage and:
          1. Generate unit tests for utility functions
          2. Create basic test cases for React components
          3. Add edge case tests for error handling
          4. Follow existing test patterns in the codebase
          Write a summary to test-updates.md
          "

      - name: Create PR if changes exist
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          # Note: gh CLI is pre-installed on GitHub-hosted runners
          if [ -n "$(git status --porcelain)" ]; then
            BRANCH="auto-updates-$(date +%Y%m%d)"
            git config user.name "github-actions[bot]"
            git config user.email "github-actions[bot]@users.noreply.github.com"

            git checkout -b $BRANCH
            git add -A
            git commit -m "chore: automated documentation and test updates

            Co-authored-by: factory-droid[bot] <138933559+factory-droid[bot]@users.noreply.github.com>"
            git push origin $BRANCH

            # Combine summaries for PR body
            PR_BODY="## Automated Updates\n\n"
            [ -f docs-updates.md ] && PR_BODY="${PR_BODY}### Documentation\n$(cat docs-updates.md)\n\n"
            [ -f test-updates.md ] && PR_BODY="${PR_BODY}### Tests\n$(cat test-updates.md)\n\n"

            gh pr create \
              --title "🤖 Daily automated updates" \
              --body "$PR_BODY" \
              --label "automated,documentation,tests"
          fi
```

## Example 3: Security and Dependency Scanner

Scans for vulnerabilities and outdated dependencies on a schedule.

```yaml  theme={null}
name: Security Scanner
on:
  schedule:
    - cron: '0 9 * * 1'  # Mondays at 9 AM UTC
  workflow_dispatch:

jobs:
  security-scan:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Setup droid CLI
        run: |
          curl -fsSL https://app.factory.ai/cli | sh
          echo "$HOME/.local/bin" >> $GITHUB_PATH

      - name: Security audit
        env:
          FACTORY_API_KEY: ${{ secrets.FACTORY_API_KEY }}
        run: |
          droid exec --auto medium "
          Perform a comprehensive security audit:
          1. Check package.json for known vulnerabilities
          2. Update vulnerable dependencies to safe versions
          3. Scan code for hardcoded secrets or API keys
          4. Review authentication and authorization patterns
          5. Check for SQL injection or XSS vulnerabilities
          6. Generate security-report.md with all findings and fixes
          "

      - name: Create issue if vulnerabilities found
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          # Note: gh CLI is pre-installed on GitHub-hosted runners
          if [ -f security-report.md ] && grep -q "vulnerability\|security\|risk" security-report.md; then
            gh issue create \
              --title "🔒 Security audit findings - $(date +%Y-%m-%d)" \
              --body-file security-report.md \
              --label "security,high-priority" \
              --assignee "${{ github.repository_owner }}"
          fi

      - name: Create PR for fixes
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          # Note: gh CLI is pre-installed on GitHub-hosted runners
          if [ -n "$(git status --porcelain)" ]; then
            git config user.name "github-actions[bot]"
            git config user.email "github-actions[bot]@users.noreply.github.com"

            git checkout -b security-fixes-$(date +%Y%m%d)
            git add -A
            git commit -m "fix: security updates and dependency patches

            Co-authored-by: factory-droid[bot] <138933559+factory-droid[bot]@users.noreply.github.com>"
            git push origin HEAD

            gh pr create \
              --title "🔒 Security fixes" \
              --body-file security-report.md \
              --label "security,dependencies" \
              --assignee "${{ github.repository_owner }}"
          fi
```


---

> To find navigation and other pages in this documentation, fetch the llms.txt file at: https://docs.factory.ai/llms.txt
