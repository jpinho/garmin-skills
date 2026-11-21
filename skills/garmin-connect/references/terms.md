# What Garmin's terms say about this use

Read on 21 November 2026. Terms change: read them again before relying on this page.

## Which terms apply

A personal API key is covered by two texts:

- **Garmin's Terms of Use** (effective 1 April 2026): https://www.garmin.com/en-US/legal/terms-of-use/
- **The "Garmin Connect Personal API Supplemental Terms"**, which the user accepts when creating the key in Garmin Connect (Settings → Personal API key). They say that where the two conflict, the Supplemental Terms "control with respect to your use of the API".

The wording below was read from the public text file that the key page loads, last modified on 3 November 2026. The same text is shown in the dialog when a key is created.

The **Garmin Connect Developer Program Agreement** is a different contract. It binds organisations that build apps for other people. Its rules on passing Garmin data on to third parties, and on a published statement about AI processing, belong to that programme and not to a personal key.

## The Supplemental Terms

**Personal use of the key:**

> "Any API key issued to you is personal to you and may be used only by you in connection with applications, services, or tools that you develop or operate for your own use. You may not sell, transfer, sublicense, distribute, disclose, or otherwise share your API key with any third party. You are responsible for maintaining the confidentiality and security of your API key and for all activity that occurs using your API key."

**Rate limits:**

> "Garmin may establish and enforce limits on the number, frequency, or volume of API requests that may be made using the API. These limits may be modified by Garmin at any time. If you exceed applicable rate limits, Garmin may throttle, delay, reject, suspend, or otherwise restrict API requests without notice."

**Violations:**

> "Violation of these Supplemental Terms may result in suspension or termination of your access to the API and revocation of your API key."

## Garmin's own description of the API

From the Personal API FAQ (https://developer.garmin.com/gc-developer-program/personal/personal-faq/):

> "The Personal API is intended for individual Garmin users who want programmatic access to their own data. It is not intended for commercial applications serving multiple end users."

## The Terms of Use on automated access

The Terms of Use list as a violation:

> "Using any process, whether automated or manual, that accesses, copies, or scrapes content from the Site through any means not purposely made available through the Site"

The Personal API is a means Garmin makes available for exactly this. Logging in to Garmin Connect with a password from a script is not: this skill does not do it, and should not be changed to.

## What is not said

Neither text mentions AI models, agents or assistants. That is silence, not written permission. Garmin can change the terms, the limits or the API at any time.

## What this means for an agent

- **One person, their own data.** The key belongs to the person whose data it reads. Never use one person's key to serve someone else, and never build a shared service on it.
- **The key is never shared.** It stays in an environment variable or a key file that only its owner controls. It never goes into a chat, a repository, a URL, a log or another service.
- **The data goes where the agent runs.** What the agent reads is sent to the model it runs on. It is the user's own data and their choice; say so if they ask.
- **Back off when told.** Honour HTTP 429 and its `retryInSeconds`. Prefer range endpoints over one call per day.
- **Read-only, official route only.** No password login, no scraping of Garmin Connect, no unofficial endpoints.
