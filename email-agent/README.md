# Email Agent Security Research

Demonstrates indirect prompt injection vulnerabilities in autonomous email agents.

## ⚠️ Educational Purpose Only

## Attack Vectors

1. **Direct Instruction Injection** - Instructions in email body
2. **HTML Comment Injection** - Hidden in HTML emails
3. **Metadata Injection** - Via sender field or subject
4. **Social Engineering** - Legitimate-looking requests
5. **Chain Attacks** - Multi-step exfiltration

## Defenses Implemented

- Content sanitization (HTML stripping)
- Pattern-based injection detection
- Recipient allowlisting
- Rate limiting
- Anomaly detection
- Comprehensive audit logging

## Structure
```
email-agent/
├── create_test_emails.py      # Generate test dataset
├── email_agent.py             # Vulnerable version
├── email_agent_hardened.py    # Hardened version
├── attack*.py                 # Attack demonstrations
├── test_defenses.py           # Defense validation
└── emails/                    # Test email storage
```

## Run
```bash
# Setup
python create_test_emails.py

# Test vulnerable version
python email_agent.py

# Run attacks
python attack1_direct_instruction.py
python attack2_social_engineering.py
python attack3_html_injection.py

# Test defenses
python test_defenses.py
```

## Key Learning

**Indirect injection** is when malicious instructions come from data the agent retrieves, not from user input directly. This is how production agents get compromised.

Defense requires multiple layers - no single technique is sufficient.
