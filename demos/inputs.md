# Demo Inputs

Seven scripted prompts for the interview demo flow.

---

## 1. Benign summary request

**Input:**
```
Can you summarize the Q3 earnings report for stakeholders? I need a concise bullet point
overview of revenue, margin, and guidance.
```

**Expected tier:** LOW
**Expected categories:** none
**Narrative:** Baseline happy path. Shows the system passes clean prompts with no friction,
logs the submission, and makes the LLM passthrough button available.

---

## 2. Email + phone (low-risk PII)

**Input:**
```
Please draft a follow-up email to sarah.mitchell@acmecorp.com. She can also be reached
at 312-555-8821 if the email bounces.
```

**Expected tier:** LOW
**Expected categories:** PII (email, phone)
**Narrative:** Two PII signals at LOW tier. Demonstrates that low-risk content is still
logged but not blocked. Good moment to show the dashboard picking up the row.

---

## 3. SSN + DOB + email (escalation fires)

**Input:**
```
Employee onboarding for Marcus Webb. SSN: 532-10-8847. Date of birth: 03/22/1988.
Primary contact: m.webb@acmecorp.com. Please update the HRIS record.
```

**Expected tier:** HIGH (E1 escalation: 2+ MEDIUM matches)
**Expected categories:** PII
**Narrative:** SSN is BLOCKED-tier on its own, so this actually hits BLOCKED. If you want
to demo E1 cleanly, use two DOB values instead of an SSN. Swap to:
```
DOB for record A is 03/22/1988. DOB for record B is 11/05/1976. Please merge the files.
```
That gives two MEDIUM hits and triggers E1 -> HIGH with no BLOCKED override.

---

## 4. Raw AWS access key

**Input:**
```
Here is the key for the staging environment: AKIAIOSFODNN7EXAMPLE
Please use it to pull the S3 bucket contents.
```

**Expected tier:** BLOCKED
**Expected categories:** CREDENTIAL
**Narrative:** Core governance short-circuit. LLM button renders disabled with a tooltip
explaining the reason. Nothing leaves the classifier.

---

## 5. Base64-encoded AWS key

**Input:**
```
Encoded config for the CI pipeline:
eyJhd3NfYWNjZXNzX2tleSI6ICJBS0lBSU9TRk9ETk43RVhBTVBMRSIsICJyZWdpb24iOiAidXMtZWFzdC0xIn0=
```

**Expected tier:** BLOCKED + encoding_detected: base64
**Expected categories:** CREDENTIAL
**Narrative:** Obfuscation detection. The analyzer decodes the base64 block, finds the AWS
key in the decoded text, and flags it. The DB row gets encoding_detected = "base64".
This is the strongest technical signal for the interview.

---

## 6. Dashboard walkthrough

*No input prompt. Navigate to the Dashboard page after running demos 1-5.*

**Narrative beats:**
- KPI row shows total submissions, BLOCKED count, % passed to LLM, top pattern with count (e.g., "aws_access_key (3x)").
- Bar chart shows BLOCKED, HIGH, MEDIUM, and LOW tiers from seed data plus live demos.
- Top patterns chart shows aws_access_key at the top.
- Use the tier filter multiselect to show only BLOCKED rows -- point out the reason_blocked column in the data.
- SEED rows are labeled "SEED | TIER" in the Tier column so live vs. pre-loaded rows are visually distinct.
- Download CSV and open it -- point to the reason_blocked and encoding_detected columns for the BLOCKED base64 row.
- Classification is synchronous and returns in under 50ms for typical prompts; no loading delay visible to the audience.

---

## 7. Settings toggle + re-run demo 3

**Steps:**
1. Go to Settings. Disable the PII category.
2. Return to Analyzer. Re-run the two-DOB input from demo 3.
3. Show that the tier drops to LOW because PII detection is off.
4. Re-enable PII. Run again. Tier returns to HIGH.

**Narrative:** Runtime configurability without restart. Demonstrates that policy changes
take effect immediately within the session, which is the core ask for a governance tool.

---

## Performance note

Classification runs synchronously in the same process as the Streamlit app.
Measured on 30 labeled fixtures and a 50,000-character benign input: all complete
under 2 seconds; typical prompts return in under 50ms. Quote this number confidently
if asked about production readiness -- and note that stateless horizontal workers
would eliminate any latency floor entirely.

## Seed data note

On first load (or after clearing logs), the app seeds 75 pre-classified submissions
to give the dashboard something to show. Seeded rows are labeled "SEED | TIER" in
the dashboard table. All live submissions you create during the demo appear without
the SEED prefix, making it easy to distinguish your demo runs from the pre-loaded data.
