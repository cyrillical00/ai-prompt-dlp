import sqlite3
import json
import random
from datetime import datetime, timezone, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "dlp_logs.db"
SCHEMA_PATH = Path(__file__).parent.parent / "db" / "schema.sql"


def _ts(days_ago: float, hour: int = 9, minute: int = 0) -> str:
    base = datetime.now(timezone.utc) - timedelta(days=days_ago)
    t = base.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return t.isoformat()


# ---------------------------------------------------------------------------
# Pre-classified submissions
# Each entry: (timestamp, risk_tier, matched_patterns, redacted_preview,
#              original_length, encoding_detected, passed_to_llm, llm_response_id, reason_blocked)
# ---------------------------------------------------------------------------

SUBMISSIONS = [
    # --- 2 BLOCKED ---
    {
        "timestamp": _ts(27, 10, 12),
        "risk_tier": "BLOCKED",
        "matched_patterns": [{"name": "aws_access_key", "category": "CREDENTIAL", "tier": "BLOCKED", "encoding": None}],
        "redacted_preview": "Can you review this deployment script? Access key [REDACTED:CREDENTIAL] should work for S3.",
        "original_length": 312,
        "encoding_detected": None,
        "passed_to_llm": 0,
        "llm_response_id": None,
        "reason_blocked": "Detected: aws_access_key",
    },
    {
        "timestamp": _ts(14, 15, 44),
        "risk_tier": "BLOCKED",
        "matched_patterns": [
            {"name": "ssn_formatted", "category": "PII", "tier": "BLOCKED", "encoding": None},
            {"name": "email", "category": "PII", "tier": "LOW", "encoding": None},
        ],
        "redacted_preview": "Update the HRIS record for Marcus Webb. SSN: ***-**-8847. Contact: m***@***.com. Start date 2019-03-11.",
        "original_length": 198,
        "encoding_detected": None,
        "passed_to_llm": 0,
        "llm_response_id": None,
        "reason_blocked": "Detected: ssn_formatted",
    },
    # --- 3 MEDIUM (single DOB, no escalation) ---
    {
        "timestamp": _ts(17, 13, 0),
        "risk_tier": "MEDIUM",
        "matched_patterns": [{"name": "date_of_birth", "category": "PII", "tier": "MEDIUM", "encoding": None}],
        "redacted_preview": "Please update the employee file. DOB is **/**/****. Everything else is current.",
        "original_length": 88,
        "encoding_detected": None,
        "passed_to_llm": 0,
        "llm_response_id": None,
        "reason_blocked": None,
    },
    {
        "timestamp": _ts(12, 11, 30),
        "risk_tier": "MEDIUM",
        "matched_patterns": [{"name": "date_of_birth", "category": "PII", "tier": "MEDIUM", "encoding": None}],
        "redacted_preview": "Background check form: candidate DOB is **/**/****. Please confirm HR has the signed release.",
        "original_length": 105,
        "encoding_detected": None,
        "passed_to_llm": 0,
        "llm_response_id": None,
        "reason_blocked": None,
    },
    {
        "timestamp": _ts(6, 10, 15),
        "risk_tier": "MEDIUM",
        "matched_patterns": [{"name": "date_of_birth_iso", "category": "PII", "tier": "MEDIUM", "encoding": None}],
        "redacted_preview": "Onboarding checklist for new hire. Date of birth (ISO): **/**/****. Provide to payroll.",
        "original_length": 91,
        "encoding_detected": None,
        "passed_to_llm": 0,
        "llm_response_id": None,
        "reason_blocked": None,
    },
    # --- 1 BLOCKED with base64 encoding ---
    {
        "timestamp": _ts(19, 9, 45),
        "risk_tier": "BLOCKED",
        "matched_patterns": [{"name": "aws_access_key", "category": "CREDENTIAL", "tier": "BLOCKED", "encoding": "base64"}],
        "redacted_preview": "Config payload for the deploy job: [REDACTED:ENCODED_CREDENTIAL]",
        "original_length": 142,
        "encoding_detected": "base64",
        "passed_to_llm": 0,
        "llm_response_id": None,
        "reason_blocked": "Detected: aws_access_key (base64-encoded)",
    },
    # --- 2 multi-category LOW (email + phone) ---
    {
        "timestamp": _ts(22, 16, 0),
        "risk_tier": "LOW",
        "matched_patterns": [
            {"name": "email", "category": "PII", "tier": "LOW", "encoding": None},
            {"name": "us_phone", "category": "PII", "tier": "LOW", "encoding": None},
        ],
        "redacted_preview": "Please reach out to the vendor at v***@***.com or call ***-***-4821 to confirm the renewal.",
        "original_length": 112,
        "encoding_detected": None,
        "passed_to_llm": 1,
        "llm_response_id": "demo-llm-035",
        "reason_blocked": None,
    },
    {
        "timestamp": _ts(4, 14, 45),
        "risk_tier": "LOW",
        "matched_patterns": [
            {"name": "email", "category": "PII", "tier": "LOW", "encoding": None},
            {"name": "us_phone", "category": "PII", "tier": "LOW", "encoding": None},
        ],
        "redacted_preview": "New contractor contact: j***@***.com, mobile ***-***-7733. Please add to the org chart.",
        "original_length": 99,
        "encoding_detected": None,
        "passed_to_llm": 0,
        "llm_response_id": None,
        "reason_blocked": None,
    },
    # --- 2 HIGH ---
    {
        "timestamp": _ts(21, 11, 5),
        "risk_tier": "HIGH",
        "matched_patterns": [{"name": "business_term:project_titan", "category": "BUSINESS", "tier": "HIGH", "encoding": None}],
        "redacted_preview": "What is the current timeline for [REDACTED:BUSINESS] and when are we planning the public announcement?",
        "original_length": 156,
        "encoding_detected": None,
        "passed_to_llm": 1,
        "llm_response_id": "demo-llm-001",
        "reason_blocked": None,
    },
    {
        "timestamp": _ts(8, 14, 22),
        "risk_tier": "HIGH",
        "matched_patterns": [
            {"name": "date_of_birth", "category": "PII", "tier": "MEDIUM", "encoding": None},
            {"name": "date_of_birth", "category": "PII", "tier": "MEDIUM", "encoding": None},
        ],
        "redacted_preview": "I need to merge records for two employees. First DOB: **/**/****. Second DOB: **/**/****. Same department.",
        "original_length": 174,
        "encoding_detected": None,
        "passed_to_llm": 0,
        "llm_response_id": None,
        "reason_blocked": None,
    },
    # --- 46 LOW ---
    {"timestamp": _ts(29, 9, 0),   "risk_tier": "LOW", "matched_patterns": [], "redacted_preview": "Write a Python function that reads a CSV file and returns the top 10 rows sorted by a given column.", "original_length": 102, "encoding_detected": None, "passed_to_llm": 1, "llm_response_id": "demo-llm-002", "reason_blocked": None},
    {"timestamp": _ts(29, 10, 30), "risk_tier": "LOW", "matched_patterns": [], "redacted_preview": "What is the difference between OAuth 2.0 and SAML for enterprise SSO deployments?", "original_length": 83, "encoding_detected": None, "passed_to_llm": 1, "llm_response_id": "demo-llm-003", "reason_blocked": None},
    {"timestamp": _ts(29, 13, 15), "risk_tier": "LOW", "matched_patterns": [], "redacted_preview": "Summarize the key differences between zero-trust and perimeter-based network security models.", "original_length": 95, "encoding_detected": None, "passed_to_llm": 0, "llm_response_id": None, "reason_blocked": None},
    {"timestamp": _ts(28, 8, 45),  "risk_tier": "LOW", "matched_patterns": [], "redacted_preview": "Draft a runbook for responding to an S3 bucket misconfiguration alert from our CSPM tool.", "original_length": 91, "encoding_detected": None, "passed_to_llm": 1, "llm_response_id": "demo-llm-004", "reason_blocked": None},
    {"timestamp": _ts(28, 11, 0),  "risk_tier": "LOW", "matched_patterns": [], "redacted_preview": "How do I configure conditional access policies in Okta to enforce MFA for admin roles?", "original_length": 88, "encoding_detected": None, "passed_to_llm": 1, "llm_response_id": "demo-llm-005", "reason_blocked": None},
    {"timestamp": _ts(28, 14, 30), "risk_tier": "LOW", "matched_patterns": [], "redacted_preview": "Explain the SCIM protocol and how it enables automated user provisioning between identity providers.", "original_length": 99, "encoding_detected": None, "passed_to_llm": 0, "llm_response_id": None, "reason_blocked": None},
    {"timestamp": _ts(27, 9, 20),  "risk_tier": "LOW", "matched_patterns": [], "redacted_preview": "What are the best practices for rotating API keys in a microservices architecture?", "original_length": 82, "encoding_detected": None, "passed_to_llm": 1, "llm_response_id": "demo-llm-006", "reason_blocked": None},
    {"timestamp": _ts(27, 14, 0),  "risk_tier": "LOW", "matched_patterns": [], "redacted_preview": "Write a SQL query to find all users who have not logged in within the last 90 days.", "original_length": 84, "encoding_detected": None, "passed_to_llm": 0, "llm_response_id": None, "reason_blocked": None},
    {"timestamp": _ts(26, 9, 30),  "risk_tier": "LOW", "matched_patterns": [], "redacted_preview": "Draft a Slack message announcing the Q3 security awareness training enrollment period.", "original_length": 87, "encoding_detected": None, "passed_to_llm": 1, "llm_response_id": "demo-llm-007", "reason_blocked": None},
    {"timestamp": _ts(26, 11, 45), "risk_tier": "LOW", "matched_patterns": [], "redacted_preview": "How do I set up a GitHub Actions workflow to run pytest on every pull request?", "original_length": 78, "encoding_detected": None, "passed_to_llm": 0, "llm_response_id": None, "reason_blocked": None},
    {"timestamp": _ts(26, 15, 0),  "risk_tier": "LOW", "matched_patterns": [], "redacted_preview": "Explain how Jamf Pro handles MDM enrollment for corporate-owned macOS devices.", "original_length": 77, "encoding_detected": None, "passed_to_llm": 1, "llm_response_id": "demo-llm-008", "reason_blocked": None},
    {"timestamp": _ts(25, 9, 0),   "risk_tier": "LOW", "matched_patterns": [], "redacted_preview": "What logging should we enable in AWS CloudTrail for a SOC 2 Type II audit?", "original_length": 76, "encoding_detected": None, "passed_to_llm": 0, "llm_response_id": None, "reason_blocked": None},
    {"timestamp": _ts(25, 10, 30), "risk_tier": "LOW", "matched_patterns": [], "redacted_preview": "Draft a post-incident review template for a P1 outage affecting customer-facing APIs.", "original_length": 86, "encoding_detected": None, "passed_to_llm": 1, "llm_response_id": "demo-llm-009", "reason_blocked": None},
    {"timestamp": _ts(25, 13, 0),  "risk_tier": "LOW", "matched_patterns": [], "redacted_preview": "How do I configure Terraform to manage IAM roles with least-privilege policies?", "original_length": 80, "encoding_detected": None, "passed_to_llm": 0, "llm_response_id": None, "reason_blocked": None},
    {"timestamp": _ts(24, 8, 30),  "risk_tier": "LOW", "matched_patterns": [], "redacted_preview": "Write a bash script that checks whether required ports are open on a list of hosts.", "original_length": 83, "encoding_detected": None, "passed_to_llm": 1, "llm_response_id": "demo-llm-010", "reason_blocked": None},
    {"timestamp": _ts(24, 11, 0),  "risk_tier": "LOW", "matched_patterns": [], "redacted_preview": "What is the recommended approach for secret rotation in Kubernetes using Vault or AWS Secrets Manager?", "original_length": 103, "encoding_detected": None, "passed_to_llm": 0, "llm_response_id": None, "reason_blocked": None},
    {"timestamp": _ts(24, 14, 15), "risk_tier": "LOW", "matched_patterns": [], "redacted_preview": "Summarize NIST SP 800-63B password guidance for an internal policy document.", "original_length": 74, "encoding_detected": None, "passed_to_llm": 1, "llm_response_id": "demo-llm-011", "reason_blocked": None},
    {"timestamp": _ts(23, 9, 45),  "risk_tier": "LOW", "matched_patterns": [], "redacted_preview": "How do I interpret a Qualys vulnerability scan report and prioritize remediation?", "original_length": 82, "encoding_detected": None, "passed_to_llm": 0, "llm_response_id": None, "reason_blocked": None},
    {"timestamp": _ts(23, 11, 30), "risk_tier": "LOW", "matched_patterns": [], "redacted_preview": "Draft a vendor security questionnaire covering data handling, encryption, and breach notification.", "original_length": 98, "encoding_detected": None, "passed_to_llm": 1, "llm_response_id": "demo-llm-012", "reason_blocked": None},
    {"timestamp": _ts(23, 14, 0),  "risk_tier": "LOW", "matched_patterns": [], "redacted_preview": "Write a Python decorator that logs function call duration to a structured JSON log.", "original_length": 83, "encoding_detected": None, "passed_to_llm": 0, "llm_response_id": None, "reason_blocked": None},
    {"timestamp": _ts(22, 9, 0),   "risk_tier": "LOW", "matched_patterns": [], "redacted_preview": "What are the key controls required for PCI DSS 4.0 compliance for a SaaS payments platform?", "original_length": 93, "encoding_detected": None, "passed_to_llm": 1, "llm_response_id": "demo-llm-013", "reason_blocked": None},
    {"timestamp": _ts(22, 10, 45), "risk_tier": "LOW", "matched_patterns": [], "redacted_preview": "How do I implement role-based access control in a FastAPI application using JWT claims?", "original_length": 88, "encoding_detected": None, "passed_to_llm": 0, "llm_response_id": None, "reason_blocked": None},
    {"timestamp": _ts(22, 13, 30), "risk_tier": "LOW", "matched_patterns": [], "redacted_preview": "Explain the difference between symmetric and asymmetric encryption with production use cases.", "original_length": 94, "encoding_detected": None, "passed_to_llm": 1, "llm_response_id": "demo-llm-014", "reason_blocked": None},
    {"timestamp": _ts(21, 9, 30),  "risk_tier": "LOW", "matched_patterns": [], "redacted_preview": "Draft an acceptable use policy for AI tools in an enterprise environment.", "original_length": 73, "encoding_detected": None, "passed_to_llm": 0, "llm_response_id": None, "reason_blocked": None},
    {"timestamp": _ts(21, 12, 0),  "risk_tier": "LOW", "matched_patterns": [], "redacted_preview": "How should we structure a tabletop exercise for a ransomware scenario?", "original_length": 71, "encoding_detected": None, "passed_to_llm": 1, "llm_response_id": "demo-llm-015", "reason_blocked": None},
    {"timestamp": _ts(20, 9, 0),   "risk_tier": "LOW", "matched_patterns": [], "redacted_preview": "Write a GitHub Actions workflow that builds a Docker image and pushes it to ECR on merge to main.", "original_length": 98, "encoding_detected": None, "passed_to_llm": 0, "llm_response_id": None, "reason_blocked": None},
    {"timestamp": _ts(20, 11, 15), "risk_tier": "LOW", "matched_patterns": [], "redacted_preview": "Summarize the MITRE ATT&CK techniques most commonly used in supply chain attacks.", "original_length": 82, "encoding_detected": None, "passed_to_llm": 1, "llm_response_id": "demo-llm-016", "reason_blocked": None},
    {"timestamp": _ts(20, 14, 0),  "risk_tier": "LOW", "matched_patterns": [], "redacted_preview": "How do I configure network segmentation between engineering and finance VLANs on Cisco gear?", "original_length": 93, "encoding_detected": None, "passed_to_llm": 0, "llm_response_id": None, "reason_blocked": None},
    {"timestamp": _ts(19, 9, 30),  "risk_tier": "LOW", "matched_patterns": [], "redacted_preview": "Draft a data classification policy with four tiers: public, internal, confidential, and restricted.", "original_length": 101, "encoding_detected": None, "passed_to_llm": 1, "llm_response_id": "demo-llm-017", "reason_blocked": None},
    {"timestamp": _ts(19, 11, 0),  "risk_tier": "LOW", "matched_patterns": [], "redacted_preview": "How should we handle a third-party vendor requesting read access to our production database?", "original_length": 92, "encoding_detected": None, "passed_to_llm": 0, "llm_response_id": None, "reason_blocked": None},
    {"timestamp": _ts(18, 9, 0),   "risk_tier": "LOW", "matched_patterns": [], "redacted_preview": "What are the tradeoffs between agent-based and agentless endpoint detection solutions?", "original_length": 87, "encoding_detected": None, "passed_to_llm": 1, "llm_response_id": "demo-llm-018", "reason_blocked": None},
    {"timestamp": _ts(18, 13, 30), "risk_tier": "LOW", "matched_patterns": [], "redacted_preview": "Explain how certificate pinning works and when it is appropriate to use it in mobile apps.", "original_length": 92, "encoding_detected": None, "passed_to_llm": 0, "llm_response_id": None, "reason_blocked": None},
    {"timestamp": _ts(17, 9, 0),   "risk_tier": "LOW", "matched_patterns": [], "redacted_preview": "Write a Jira ticket template for a high-severity security vulnerability disclosure.", "original_length": 82, "encoding_detected": None, "passed_to_llm": 1, "llm_response_id": "demo-llm-019", "reason_blocked": None},
    {"timestamp": _ts(17, 11, 30), "risk_tier": "LOW", "matched_patterns": [], "redacted_preview": "How do I set retention policies for CloudWatch Logs across all accounts in an AWS Organization?", "original_length": 96, "encoding_detected": None, "passed_to_llm": 0, "llm_response_id": None, "reason_blocked": None},
    {"timestamp": _ts(16, 9, 15),  "risk_tier": "LOW", "matched_patterns": [], "redacted_preview": "Draft an email to engineering explaining why we are enforcing signed commits starting next sprint.", "original_length": 99, "encoding_detected": None, "passed_to_llm": 1, "llm_response_id": "demo-llm-020", "reason_blocked": None},
    {"timestamp": _ts(16, 12, 0),  "risk_tier": "LOW", "matched_patterns": [], "redacted_preview": "What controls should be in place before granting a new SaaS tool access to Google Workspace?", "original_length": 93, "encoding_detected": None, "passed_to_llm": 0, "llm_response_id": None, "reason_blocked": None},
    {"timestamp": _ts(15, 9, 0),   "risk_tier": "LOW", "matched_patterns": [], "redacted_preview": "How do I configure Okta Workflows to auto-deprovision users when they are marked inactive in Workday?", "original_length": 103, "encoding_detected": None, "passed_to_llm": 1, "llm_response_id": "demo-llm-021", "reason_blocked": None},
    {"timestamp": _ts(15, 14, 0),  "risk_tier": "LOW", "matched_patterns": [], "redacted_preview": "What is the right cadence for access reviews in a 300-person company with no dedicated IAM team?", "original_length": 97, "encoding_detected": None, "passed_to_llm": 0, "llm_response_id": None, "reason_blocked": None},
    {"timestamp": _ts(13, 9, 30),  "risk_tier": "LOW", "matched_patterns": [], "redacted_preview": "Write a Python script to pull all open GitHub issues labeled security and export to CSV.", "original_length": 87, "encoding_detected": None, "passed_to_llm": 1, "llm_response_id": "demo-llm-022", "reason_blocked": None},
    {"timestamp": _ts(13, 11, 0),  "risk_tier": "LOW", "matched_patterns": [], "redacted_preview": "How do I scope a penetration test RFP for an application that handles healthcare data?", "original_length": 88, "encoding_detected": None, "passed_to_llm": 0, "llm_response_id": None, "reason_blocked": None},
    {"timestamp": _ts(12, 9, 0),   "risk_tier": "LOW", "matched_patterns": [], "redacted_preview": "Draft a change management process for infrastructure changes in a SOC 2 environment.", "original_length": 86, "encoding_detected": None, "passed_to_llm": 1, "llm_response_id": "demo-llm-023", "reason_blocked": None},
    {"timestamp": _ts(12, 13, 30), "risk_tier": "LOW", "matched_patterns": [], "redacted_preview": "Explain TLS 1.3 improvements over TLS 1.2 for a non-technical audience.", "original_length": 72, "encoding_detected": None, "passed_to_llm": 0, "llm_response_id": None, "reason_blocked": None},
    {"timestamp": _ts(11, 9, 0),   "risk_tier": "LOW", "matched_patterns": [], "redacted_preview": "How should we handle an employee offboarding when they have admin access to 40+ SaaS tools?", "original_length": 92, "encoding_detected": None, "passed_to_llm": 1, "llm_response_id": "demo-llm-024", "reason_blocked": None},
    {"timestamp": _ts(11, 11, 45), "risk_tier": "LOW", "matched_patterns": [], "redacted_preview": "What is the difference between a SIEM and a SOAR platform, and when do you need both?", "original_length": 87, "encoding_detected": None, "passed_to_llm": 0, "llm_response_id": None, "reason_blocked": None},
    {"timestamp": _ts(10, 9, 30),  "risk_tier": "LOW", "matched_patterns": [], "redacted_preview": "Write a Terraform module for deploying an ECS Fargate service with a private load balancer.", "original_length": 91, "encoding_detected": None, "passed_to_llm": 1, "llm_response_id": "demo-llm-025", "reason_blocked": None},
    {"timestamp": _ts(10, 12, 0),  "risk_tier": "LOW", "matched_patterns": [], "redacted_preview": "How do I implement DMARC enforcement for a domain that sends email through three different providers?", "original_length": 102, "encoding_detected": None, "passed_to_llm": 0, "llm_response_id": None, "reason_blocked": None},
    {"timestamp": _ts(9, 9, 0),    "risk_tier": "LOW", "matched_patterns": [], "redacted_preview": "Draft a security section for an enterprise software RFP covering encryption and audit logging.", "original_length": 94, "encoding_detected": None, "passed_to_llm": 1, "llm_response_id": "demo-llm-026", "reason_blocked": None},
    {"timestamp": _ts(9, 13, 0),   "risk_tier": "LOW", "matched_patterns": [], "redacted_preview": "What are the main attack vectors against Kubernetes clusters exposed to the internet?", "original_length": 86, "encoding_detected": None, "passed_to_llm": 0, "llm_response_id": None, "reason_blocked": None},
    {"timestamp": _ts(7, 9, 15),   "risk_tier": "LOW", "matched_patterns": [], "redacted_preview": "How do you structure an IT security team at a 500-person Series B startup?", "original_length": 75, "encoding_detected": None, "passed_to_llm": 1, "llm_response_id": "demo-llm-027", "reason_blocked": None},
    {"timestamp": _ts(7, 11, 30),  "risk_tier": "LOW", "matched_patterns": [], "redacted_preview": "Write a brief for leadership on why we need a bug bounty program and what it costs.", "original_length": 84, "encoding_detected": None, "passed_to_llm": 0, "llm_response_id": None, "reason_blocked": None},
    {"timestamp": _ts(6, 9, 0),    "risk_tier": "LOW", "matched_patterns": [], "redacted_preview": "Explain how passkeys work and whether we should prioritize them over TOTP for our auth flow.", "original_length": 93, "encoding_detected": None, "passed_to_llm": 1, "llm_response_id": "demo-llm-028", "reason_blocked": None},
    {"timestamp": _ts(6, 14, 0),   "risk_tier": "LOW", "matched_patterns": [], "redacted_preview": "What are the top five security risks when migrating from on-prem Active Directory to Entra ID?", "original_length": 96, "encoding_detected": None, "passed_to_llm": 0, "llm_response_id": None, "reason_blocked": None},
    {"timestamp": _ts(5, 9, 30),   "risk_tier": "LOW", "matched_patterns": [], "redacted_preview": "Draft an internal FAQ explaining why we are rolling out hardware security keys for all engineers.", "original_length": 98, "encoding_detected": None, "passed_to_llm": 1, "llm_response_id": "demo-llm-029", "reason_blocked": None},
    {"timestamp": _ts(5, 12, 15),  "risk_tier": "LOW", "matched_patterns": [], "redacted_preview": "How do I set up Wiz to alert on publicly exposed S3 buckets and EC2 instances with no security group?", "original_length": 103, "encoding_detected": None, "passed_to_llm": 0, "llm_response_id": None, "reason_blocked": None},
    {"timestamp": _ts(4, 9, 0),    "risk_tier": "LOW", "matched_patterns": [], "redacted_preview": "What is a good framework for evaluating AI vendor security posture before procurement?", "original_length": 87, "encoding_detected": None, "passed_to_llm": 1, "llm_response_id": "demo-llm-030", "reason_blocked": None},
    {"timestamp": _ts(4, 11, 30),  "risk_tier": "LOW", "matched_patterns": [], "redacted_preview": "Write a Python function that validates whether an uploaded file is a safe image type.", "original_length": 83, "encoding_detected": None, "passed_to_llm": 0, "llm_response_id": None, "reason_blocked": None},
    {"timestamp": _ts(3, 9, 0),    "risk_tier": "LOW", "matched_patterns": [], "redacted_preview": "How do I write an effective security incident communication for external customers?", "original_length": 84, "encoding_detected": None, "passed_to_llm": 1, "llm_response_id": "demo-llm-031", "reason_blocked": None},
    {"timestamp": _ts(3, 13, 0),   "risk_tier": "LOW", "matched_patterns": [], "redacted_preview": "Explain the shared responsibility model for AWS and what the customer is always responsible for.", "original_length": 97, "encoding_detected": None, "passed_to_llm": 0, "llm_response_id": None, "reason_blocked": None},
    {"timestamp": _ts(2, 9, 30),   "risk_tier": "LOW", "matched_patterns": [], "redacted_preview": "What are the most important metrics to track in a security operations dashboard?", "original_length": 81, "encoding_detected": None, "passed_to_llm": 1, "llm_response_id": "demo-llm-032", "reason_blocked": None},
    {"timestamp": _ts(2, 14, 0),   "risk_tier": "LOW", "matched_patterns": [], "redacted_preview": "Draft a one-pager on why we are adopting SSPM and what gaps it closes versus our existing tooling.", "original_length": 99, "encoding_detected": None, "passed_to_llm": 0, "llm_response_id": None, "reason_blocked": None},
    {"timestamp": _ts(1, 9, 0),    "risk_tier": "LOW", "matched_patterns": [], "redacted_preview": "How should we handle a developer who accidentally committed secrets to a public GitHub repo?", "original_length": 92, "encoding_detected": None, "passed_to_llm": 1, "llm_response_id": "demo-llm-033", "reason_blocked": None},
    {"timestamp": _ts(1, 11, 30),  "risk_tier": "LOW", "matched_patterns": [], "redacted_preview": "Write a Confluence page explaining our incident severity levels and response SLAs.", "original_length": 84, "encoding_detected": None, "passed_to_llm": 0, "llm_response_id": None, "reason_blocked": None},
    {"timestamp": _ts(0.5, 10, 0), "risk_tier": "LOW", "matched_patterns": [], "redacted_preview": "What is the best way to structure a quarterly security review for a board that is not technical?", "original_length": 98, "encoding_detected": None, "passed_to_llm": 1, "llm_response_id": "demo-llm-034", "reason_blocked": None},
]


def _db_is_empty() -> bool:
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.execute("SELECT COUNT(*) FROM submissions")
        return cur.fetchone()[0] == 0
    except Exception:
        return True
    finally:
        conn.close()


def seed_if_empty():
    if not _db_is_empty():
        return

    conn = sqlite3.connect(DB_PATH)
    for row in SUBMISSIONS:
        cur = conn.execute(
            """
            INSERT INTO submissions
                (timestamp, risk_tier, matched_patterns, redacted_preview,
                 original_length, encoding_detected, passed_to_llm,
                 llm_response_id, reason_blocked, is_seed)
            VALUES (?,?,?,?,?,?,?,?,?,1)
            """,
            (
                row["timestamp"],
                row["risk_tier"],
                json.dumps(row["matched_patterns"]),
                row["redacted_preview"],
                row["original_length"],
                row["encoding_detected"],
                row["passed_to_llm"],
                row["llm_response_id"],
                row["reason_blocked"],
            ),
        )
        submission_id = cur.lastrowid
        for m in row["matched_patterns"]:
            conn.execute(
                """
                INSERT INTO pattern_hits (submission_id, category, pattern_name, tier)
                VALUES (?,?,?,?)
                """,
                (submission_id, m["category"], m["name"], m["tier"]),
            )
    conn.commit()
    conn.close()
