# Decision Log

## Decision: Use In Progress → Done as cycle time
Reason:
For the MVP, Done is treated as the point where work is completed. Closed is excluded because it may mean admin closure, duplicate, cancelled, or no longer required depending on the workflow.

## Decision: Exclude Closed for MVP
Reason:
Closed can mean different things across Jira workflows. It may mean completed work, but it may also mean cancelled, duplicate, no longer required, or admin closure. To avoid noisy data, the MVP only uses tickets that reached Done.

## Decision: Auto-discover story points field
Reason:
The story points field in Jira is typically a custom field (e.g. customfield_10016) and its ID varies across Jira instances. Querying /rest/api/3/field and searching by name avoids hardcoding a field ID that may not exist on this instance.

## Decision: Extract full changelog in Phase 1
Reason:
The changelog contains status transition timestamps needed to calculate cycle time in Phase 2. Extracting it now avoids re-fetching all issues later.

## Decision: Store raw description as-is (ADF format)
Reason:
Jira Cloud returns descriptions in Atlassian Document Format (ADF), a JSON structure. Phase 1 stores it raw; Phase 2 will convert it to plain text during cleaning.

## Decision: Compare same issue types only
Reason:
Stories, Tasks, Bugs, and Sub-tasks represent different types of work. Mixing them may produce misleading estimates.

## Decision: Skip Epics for MVP
Reason:
Epics are containers for child work items and should not be compared directly with Stories or Tasks. Epic estimation can be added later by rolling up child ticket estimates.

## Decision: Use Git/GitHub for version tracking instead of GitHub API
Reason:
Normal version control only requires Git commands. GitHub API is unnecessary unless the app later needs to programmatically interact with GitHub issues, pull requests, or repository data.

## Decision: Keep .env out of Git
Reason:
.env contains secrets such as Jira API tokens and OpenAI API keys. Only .env.example should be committed.

## Decision: Use time-based train/test split (Phase 2)
Reason:
In real usage, future tickets are estimated using older historical tickets, so the test set should contain newer completed tickets.

## Decision: Use combined_text for semantic search (Phase 3)
Reason:
Important Jira context is spread across summary, description, component, labels, epic, and parent fields. Combining these fields gives the embedding model better context for finding similar tickets.
