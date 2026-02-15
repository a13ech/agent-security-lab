import anthropic
import os
import json
import glob
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

# Email agent tools
tools = [
    {
        "name": "list_emails",
        "description": "Lists all emails in the inbox with basic info (sender, subject, date)",
        "input_schema": {
            "type": "object",
            "properties": {
                "folder": {
                    "type": "string",
                    "description": "Folder to list (default: inbox)",
                    "enum": ["inbox", "sent", "archive"]
                }
            }
        }
    },
    {
        "name": "read_email",
        "description": "Reads the full content of a specific email",
        "input_schema": {
            "type": "object",
            "properties": {
                "email_id": {
                    "type": "string",
                    "description": "ID of the email to read"
                }
            },
            "required": ["email_id"]
        }
    },
    {
        "name": "categorize_email",
        "description": "Categorizes an email (important, work, personal, spam, newsletter)",
        "input_schema": {
            "type": "object",
            "properties": {
                "email_id": {
                    "type": "string",
                    "description": "ID of the email"
                },
                "category": {
                    "type": "string",
                    "description": "Category to assign",
                    "enum": ["important", "work", "personal", "spam", "newsletter"]
                }
            },
            "required": ["email_id", "category"]
        }
    },
    {
        "name": "send_email",
        "description": "Sends an email",
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {
                    "type": "string",
                    "description": "Recipient email address"
                },
                "subject": {
                    "type": "string",
                    "description": "Email subject"
                },
                "body": {
                    "type": "string",
                    "description": "Email body content"
                }
            },
            "required": ["to", "subject", "body"]
        }
    },
    {
        "name": "archive_email",
        "description": "Moves an email to archive folder",
        "input_schema": {
            "type": "object",
            "properties": {
                "email_id": {
                    "type": "string",
                    "description": "ID of email to archive"
                }
            },
            "required": ["email_id"]
        }
    }
]

# Tool implementations - VULNERABLE VERSION
def list_emails(folder="inbox"):
    """List emails in a folder"""
    try:
        pattern = f"emails/{folder}/*.json"
        email_files = glob.glob(pattern)
        
        emails = []
        for filepath in email_files:
            with open(filepath, 'r') as f:
                email = json.load(f)
                emails.append({
                    "id": email["id"],
                    "sender": email["sender"],
                    "subject": email["subject"],
                    "date": email["date"],
                    "category": email.get("category", "uncategorized")
                })
        
        emails.sort(key=lambda x: x["date"], reverse=True)
        return {"emails": emails, "count": len(emails)}
    except Exception as e:
        return {"error": str(e)}

def read_email(email_id):
    """Read full email content - VULNERABLE: Returns raw content"""
    try:
        filepath = f"emails/inbox/{email_id}.json"
        
        if not os.path.exists(filepath):
            # Try archive
            filepath = f"emails/archive/{email_id}.json"
        
        if not os.path.exists(filepath):
            return {"error": f"Email {email_id} not found"}
        
        with open(filepath, 'r') as f:
            email = json.load(f)
        
        # Mark as read
        email["read"] = True
        with open(filepath, 'w') as f:
            json.dump(email, f, indent=2)
        
        # VULNERABILITY: Returns everything including HTML and special chars
        return {
            "id": email["id"],
            "sender": email["sender"],
            "subject": email["subject"],
            "body": email["body"],
            "html_body": email.get("html_body"),
            "date": email["date"]
        }
    except Exception as e:
        return {"error": str(e)}

def categorize_email(email_id, category):
    """Categorize an email"""
    try:
        filepath = f"emails/inbox/{email_id}.json"
        
        if not os.path.exists(filepath):
            return {"error": f"Email {email_id} not found"}
        
        with open(filepath, 'r') as f:
            email = json.load(f)
        
        email["category"] = category
        
        with open(filepath, 'w') as f:
            json.dump(email, f, indent=2)
        
        return {"success": True, "email_id": email_id, "category": category}
    except Exception as e:
        return {"error": str(e)}

def send_email(to, subject, body):
    """Send an email - VULNERABLE: No validation"""
    try:
        # Create sent email record
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
        
        # VULNERABILITY: No validation on recipient or content
        print(f"\n EMAIL SENT!")
        print(f"   To: {to}")
        print(f"   Subject: {subject}")
        print(f"   Body: {body[:100]}...")
        
        return {
            "success": True,
            "email_id": email_id,
            "message": f"Email sent to {to}"
        }
    except Exception as e:
        return {"error": str(e)}

def archive_email(email_id):
    """Archive an email"""
    try:
        src = f"emails/inbox/{email_id}.json"
        dst = f"emails/archive/{email_id}.json"
        
        if not os.path.exists(src):
            return {"error": f"Email {email_id} not found in inbox"}
        
        # Move file
        os.rename(src, dst)
        
        return {"success": True, "message": f"Archived {email_id}"}
    except Exception as e:
        return {"error": str(e)}

# Map tool names to functions
tool_functions = {
    "list_emails": list_emails,
    "read_email": read_email,
    "categorize_email": categorize_email,
    "send_email": send_email,
    "archive_email": archive_email
}

def run_email_agent(user_message, verbose=True):
    """Run the email agent"""
    if verbose:
        print(f"\n{'='*70}")
        print(f"USER REQUEST: {user_message}")
        print(f"{'='*70}\n")
    
    messages = [{"role": "user", "content": user_message}]
    
    iteration = 0
    max_iterations = 10  # Prevent infinite loops
    
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
                    print(f"\n🔧 TOOL: {tool_name}")
                    print(f"   Input: {json.dumps(tool_input, indent=2)}")
                
                # Execute tool
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
            # Get final response
            final_text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    final_text += block.text
            
            if verbose:
                print(f"\n ASSISTANT RESPONSE:")
                print(final_text)
                print()
            
            return final_text
    
    return "Max iterations reached"

if __name__ == "__main__":
    # Test normal usage
    run_email_agent("Can you show me my emails and categorize the important ones?")
