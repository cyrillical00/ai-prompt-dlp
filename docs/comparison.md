# DLP Tool Comparison

| Dimension | This PoC | Presidio (Microsoft) | AWS Comprehend | Nightfall | Portal 26 |
|-----------|----------|---------------------|----------------|-----------|-----------|
| Deployment model | Streamlit Cloud / self-hosted | Self-hosted (Python lib) | Managed API | SaaS API | SaaS proxy |
| Detection approach | Regex + Luhn + keyword + base64 decode | NLP entities + regex recognizers | ML NER (managed) | ML + regex | ML + proxy inspection |
| Audit surface | SQLite log, CSV export | Pluggable (no built-in) | CloudWatch | Dashboard | Dashboard + SIEM |
| Stack position | Governance brain (pre-LLM filter) | Library (embed anywhere) | API (embed anywhere) | API gateway or SDK | Network proxy |
| Credential detection | BLOCKED tier, 12+ patterns | Partial (no base64 decode) | Limited | Strong | Strong |
| Base64 obfuscation | Yes, one level | No | No | Some | Yes (proxy-level) |
| Luhn validation | Yes | Yes (via recognizer) | No | Yes | Yes |
| Business term config | YAML, session-editable | Custom recognizer code | Entity lists | Policies | Policy builder |
| LLM passthrough | Built-in (gated, annotated) | No | No | No | Yes (proxy) |
| Operational complexity | Near-zero | Medium (self-host, tune) | Low (managed) | Low (SaaS) | High (proxy infra) |
| Cost model | Free (Streamlit Cloud) | Free (self-hosted) | Per character | Per API call | Enterprise license |
| Strengths | Full audit trail, credential-first, base64 | Extensible NLP, open source | Managed, scalable | Easy SaaS integration | Full proxy, DLP + policy |
| Gaps | Semantic detection, multilingual, >base64 obfuscation | No built-in audit, no LLM integration | No credential patterns, no audit | Vendor dependency | Proxy complexity, not classif layer |

## Positioning note

This PoC is the classification layer, not a replacement for a proxy product. At a16z the right production stack is Portal 26 (or equivalent) as the ingress proxy with this classification logic as the policy engine behind it. Presidio is the closest open-source analogue; the PoC demonstrates the governance-layer reasoning that would feed a Presidio or Portal 26 policy decision.
