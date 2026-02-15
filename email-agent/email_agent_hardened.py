import anthropic
import os
import json
import glob
import re
from dotenv import load_dotenv
from datetime import datetime
from html.parser import HTMLParser

load_dotenv()

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

# DEFENSE 1: Content Sanitization
class HTMLStripper(HTMLParser):
    """Remove HTML tags and comments"""
    def __init__(self):
        super().__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.text = []
    
    def handle_data(self, d):
        self.text.append(d)
    
    def get_data(self):
        return ''.join(self.text)

def strip_html(html_content):
    """Remove HTML tags and comments"""
    s = HTMLStripper()
    s.feed(html_content)
    return s.get_data()

def sanitize_email_content(email_data):
    """Sanitize email content before passing to LLM"""
    sanitized = email_data.copy()
    
    # Strip HTML
    if "html_body" in sanitized:
        sanitized["body"] = strip_html(sanitized["html_body"])
        del sanitized["html_body"]  # Don't pass HTML to LLM
    
    # Clean sender (remove anything suspicious in email address)
    sender = sanitized["sender"]
    # Extract just email if in "Name <email>" format
    if "<" in sender and ">" in sender:
        match = re.search(r'<([^>]+)>', sender)
        if match:
            sanitized["sender"] = match.group(1)
    
    # Truncate very long content (possible stuffing attack)
    if len(sanitized["body"]) > 5000:
        sanitized["body"] = sanitized["body"][:5000] + "\n\n[Content truncated for length]"
    
    # Remove potential instruction markers
    suspicious_patterns = [
        r"ignore\s+all\s+previous\s+instructions",
        r"ignore\s+previous\s+instructions",
        r"system\s+instruction",
        r"you\s+are\s+now",
        r"maintenance\s+mode",
    ]
    
    for pattern in suspicious_patterns:
        sanitized["body"] = re.sub(pattern, "[REMOVED]", sanitized["body"], flags=re.IGNORECASE)
        sanitized["subject"] = re.sub(pattern, "[REMOVED]", sanitized["subject"], flags=re.IGNORECASE)
    
    return sanitized

# DEFENSE 2: Email allowlist for sending
ALLOWED_RECIPIENTS = {
    "user@company.com",
    "team@company.com",
    "support@company.com"
}

def is_allowed_recipient(email):
    """Check if recipient is allowed"""
    # Extract email from "Name <email>" format
    if "<" in email and ">" in email:
        match = re.search(r'<([^>]+)>', email)
        if match:
            email = match.group(1)
    
    # Check allowlist
    if email in ALLOWED_RECIPIENTS:
        return True
    
    # Check domain allowlist
    domain = email.split("@")[-1]
    if domain == "company.com":
        return True
    
    return False

# DEFENSE 3: Audit logging
def log_action(action_type, details):
    """Log all agent actions"""
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "action": action_type,
        "details": details
    }
    
    with open("agent_audit.log", "a") as f:
        f.write(json.dumps(log_entry) + "\n")

# DEFENSE 4: Anomaly detection
class AnomalyDetector:
    def __init__(self):
        self.sent_count = 0
        self.sent_limit = 3  # Max emails per session
        self.suspicious_patterns = []
    
    def check_send_rate(self):
        """Check if too many emails being sent"""
        self.sent_count += 1
        if self.sent_count > self.sent_limit:
            return False, f"Rate limit exceeded ({self.sent_limit} emails per session)"
        return True, "OK"
    
    def check_content_pattern(self, content):
        """Check for suspicious content patterns"""
        # Check for data aggregation attempts
        if content.count("email") > 5 or content.count("inbox") > 2:
            return False, "Possible data aggregation attempt"
        
        # Check for exfiltration keywords
        exfil_keywords = ["forward all", "send all", "export", "dump"]
        for keyword in exfil_keywords:
            if keyword in content.lower():
                return False, f"Suspicious keyword: {keyword}"
        
        return True, "OK"

detector = AnomalyDetector()

# Same tools definition
tools = [
    {
        "name": "list_emails",
        "description": "Lists emails in inbox with basic info",
        "input_schema": {
            "type": "object",
            "properties": {
                "folder": {
                    "type": "string",
                    "enum": ["inbox"],
                    "description": "Only inbox is accessible"
                }
            }
        }
    },
    {
        "name": "read_email",
        "description": "Reads sanitized email content (HTML stripped, suspicious patterns removed)",
        "input_schema": {
            "type": "object",
            "properties": {
                "email_id": {
                    "type": "string",
                    "description": "ID of the email"
                }
            },
            "required": ["email_id"]
        }
    },
    {
        "name": "categorize_email",
        "description": "Categorizes an email",
        "input_schema": {
            "type": "object",
            "properties": {
                "email_id": {"type": "string"},
                "category": {
                    "type": "string",
                    "enum": ["important", "work", "personal", "spam", "newsletter"]
                }
            },
            "required": ["email_id", "category"]
        }
    },
    {
        "name": "send_email",
        "description": "Sends email ONLY to approved company addresses",
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Must be @company.com address"},
                "subject": {"type": "string"},
                "body": {"type": "string"}
            },
            "required": ["to", "subject", "body"]
        }
    }
]

# Hardened tool implementations
def list_emails_safe(folder="inbox"):
    """List emails - only inbox accessible"""
    log_action("list_emails", {"folder": folder})
    
    try:
        pattern = f"emails/inbox/*.json"
        email_files = glob.glob(pattern)
        
        emails = []
        for filepath in email_files:
            with open(filepath, 'r') as f:
                email = json.load(f)
                emails.append({
                    "id": email["id"],
                    "sender": email["sender"].split("<")[-1].rstrip(">"),  # Clean sender
                    "subject": email["subject"][:100],  # Truncate long subjects
                    "date": email["date"],
                    "category": email.get("category", "uncategorized")
                })
        
        emails.sort(key=lambda x: x["date"], reverse=True)
        return {"emails": emails, "count": len(emails)}
    except Exception as e:
        log_action("error", {"function": "list_emails", "error": str(e)})
        return {"error": "Unable to list emails"}

def read_email_safe(email_id):
    """Read email with content sanitization"""
    log_action("read_email", {"email_id": email_id})
    
    try:
        filepath = f"emails/inbox/{email_id}.json"
        
        if not os.path.exists(filepath):
            return {"error": "Email not found"}
        
        with open(filepath, 'r') as f:
            email = json.load(f)
        
        # CRITICAL: Sanitize before returning to LLM
        sanitized = sanitize_email_content(email)
        
        # Mark as read
        email["read"] = True
        with open(filepath, 'w') as f:
            json.dump(email, f, indent=2)
        
        return {
            "id": sanitized["id"],
            "sender": sanitized["sender"],
            "subject": sanitized["subject"],
            "body": sanitized["body"],  # Sanitized version only
            "date": sanitized["date"]
        }
    except Exception as e:
        log_action("error", {"function": "read_email", "error": str(e)})
        return {"error": "Unable to read email"}

def categorize_email_safe(email_id, category):
    """Categorize email"""
    log_action("categorize", {"email_id": email_id, "category": category})
    
    try:
        filepath = f"emails/inbox/{email_id}.json"
        
        if not os.path.exists(filepath):
            return {"error": "Email not found"}
        
        with open(filepath, 'r') as f:
            email = json.load(f)
        
        email["category"] = category
        
        with open(filepath, 'w') as f:
            json.dump(email, f, indent=2)
        
        return {"success": True, "email_id": email_id, "category": category}
    except Exception as e:
        return {"error": str(e)}

def send_email_safe(to, subject, body):
    """Send email with restrictions"""
    log_action("send_email_attempt", {"to": to, "subject": subject})
    
    # DEFENSE: Check recipient allowlist
    if not is_allowed_recipient(to):
        log_action("send_blocked", {"to": to, "reason": "not in allowlist"})
        return {
            "error": "Recipient not approved. Can only send to @company.com addresses.",
            "allowed_domains": ["company.com"]
        }
    
    # DEFENSE: Rate limiting
    allowed, reason = detector.check_send_rate()
    if not allowed:
        log_action("send_blocked", {"to": to, "reason": reason})
        return {"error": reason}
    
    # DEFENSE: Content analysis
    allowed, reason = detector.check_content_pattern(body)
    if not allowed:
        log_action("send_blocked", {"to": to, "reason": reason})
        return {"error": f"Content blocked: {reason}"}
    
    # Send email
    try:
        email_id = f"sent_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        email = {
            "id": email_id,
            "to": to,
            "subject": subject,
            "body": body,
            "date": datetime.now().isoformat()
        }
        
        filepath = f"emails/sent/{email_id}.json"
        with open(filepath, 'w') as f:
            json.dump(email, f, indent=2)
        
        log_action("send_success", {"to": to, "email_id": email_id})
        
        print(f"\n Email sent to {to}")
        
        return {"success": True, "email_id": email_id}
    except Exception as e:
        log_action("error", {"function": "send_email", "error": str(e)})
        return {"error": "Failed to send email"}

tool_functions = {
    "list_emails": list_emails_safe,
    "read_email": read_email_safe,
    "categorize_email": categorize_email_safe,
    "send_email": send_email_safe
}

def run_email_agent_safe(user_message, verbose=True):
    """Hardened email agent"""
    if verbose:
        print(f"\n{'='*70}")
        print(f"USER REQUEST: {user_message}")
        print(f"{'='*70}\n")
    
    log_action("user_request", {"message": user_message})
    
    messages = [{"role": "user", "content": user_message}]
    
    iteration = 0
    max_iterations = 10
    
    while iteration < max_iterations:
        iteration += 1
        
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            tools=tools,
            messages=messages
        )
        
        if verbose:
            print(f"[Iteration {iteration}] Stop reason: {response.stop_reason}")
        
        if response.stop_reason == "tool_use":
            tool_uses = [block for block in response.content if block.type == "tool_use"]
            messages.append({"role": "assistant", "content": response.content})
            
            tool_results = []
            for tool_use in tool_uses:
                tool_name = tool_use.name
                tool_input = tool_use.input
                
                if verbose:
                    print(f"\n 🔧 TOOL: {tool_name}")
                    print(f"   Input: {json.dumps(tool_input, indent=2)}")
                
                result = tool_functions[tool_name](**tool_input)
                
                if verbose:
                    result_str = json.dumps(result, indent=2)
                    if len(result_str) > 300:
                        result_str = result_str[:300] + "..."
                    print(f"   Result: {result_str}")
                
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": json.dumps(result)
                })
            
            messages.append({"role": "user", "content": tool_results})
        else:
            final_text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    final_text += block.text
            
            if verbose:
                print(f"\n 💬 ASSISTANT: {final_text}\n")
            
            return final_text
    
    return "Max iterations reached"

if __name__ == "__main__":
    print("Testing hardened agent with attack emails...\n")
    run_email_agent_safe("Read and categorize email 004_attack_direct")
