# Validation during snapshot creation

CAMARA Validation runs when a release coordinator posts `/create-snapshot` on a Release Issue. It runs against the current branch content **before** any snapshot is created.

## What you see

After you post `/create-snapshot`, the Release Issue receives a bot reply.

- If validation finds errors, the bot reply says the snapshot failed, includes a one-line summary of the validation result (counts of blocking problems, errors, warnings, and hints), and links to the workflow run. The Release Issue stays in **PLANNED**.
- If validation passes, the Release Issue advances to **SNAPSHOT ACTIVE** and a Release PR is opened.

For the layout of the failure reply and other surfaces, see [Where to see validation results](where-to-see-results.md).

## What you do

1. Open the linked workflow summary for the complete list of problems.
2. Fix each problem in a normal pull request to `main` or the applicable maintenance branch — the same place any contributor would fix it. CAMARA Validation also runs on that pull request, so you can confirm the fix there.
3. Merge the fix.
4. Post `/create-snapshot` again on the Release Issue.

## What does not happen

- No snapshot branch is created when validation fails.
- No Release PR is opened.
- You do not fix API definition or test problems by editing the Release Issue. The Release Issue is a comment thread; it is not a place where code lives.

## When a snapshot already exists

If a problem is found after a snapshot was created — for example during review of the Release PR — the recovery path is the same:

1. Fix the source on `main` or the applicable maintenance branch via a normal pull request, and merge it.
2. Post `/discard-snapshot <reason>` on the Release Issue to discard the active snapshot.
3. Post `/create-snapshot` to create a new snapshot.

This loop can run as many times as needed. It is part of the normal release process.

## What to open next

- For what to look at on the Release PR itself: [Validation on a Release PR](release-prs.md).
- For the format of each problem message: [Validation problem messages](problem-messages.md).
- For the full release process flow: [Release process: lifecycle](https://github.com/camaraproject/ReleaseManagement/blob/main/documentation/release-process/lifecycle.md).

## Related

- [Where to see validation results](where-to-see-results.md)
- [Validation on a Release PR](release-prs.md)
- [Validation on pull requests](pull-requests.md)
- [Validation problem messages](problem-messages.md)
- [Validation FAQ](faq.md)
