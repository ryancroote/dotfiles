---
name: eli5
description: Makes agent responses concise, simple, and approachable when a topic is overly technical or confusing. Use when explaining complex concepts, summarizing technical work, reporting implementation results, or when the user requests plain language, simplicity, brevity, or an ELI5 explanation.
---

# ELI5

Make the response easy to understand without losing the information the user needs.

## Guidelines

1. Lead with the answer, outcome, or next action.
2. Use plain language and short sentences.
3. Prefer a few focused bullets over long paragraphs.
4. Remove unnecessary jargon, repetition, background, and implementation detail.
5. When a technical term is necessary, define it briefly in everyday language.
6. Keep commands, paths, error messages, safety warnings, and important caveats exact.
7. Give deeper technical detail only when the user asks for it or needs it to make a decision.
8. Follow the user's requested format and level of detail when they explicitly specify one.

## Response Shape

Use this structure when it fits:

1. One-sentence answer or result.
2. Up to five short bullets with essential details.
3. One clear next step, if needed.

Do not add a summary that repeats the response.

## Examples

### Technical status

Instead of:

> The deployment subsystem now performs content-addressed comparisons before initiating mutation operations, after which it serializes rollback metadata to the transaction journal.

Write:

> Deployment is now safer: it checks what changed and saves everything needed to undo the update.

### Technical explanation

Instead of:

> DNS resolution maps a human-readable fully qualified domain name to an IP address through a hierarchy of recursive and authoritative nameservers.

Write:

> DNS is the internet's address book. It turns a name like `example.com` into the numeric address computers use.

### Important detail

Do not simplify away required information:

> Run `./dotfiles restore --recover`. This restores the interrupted deployment; files changed afterward may need `--force` and will be saved in a rescue backup.
