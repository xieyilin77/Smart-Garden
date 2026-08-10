#!/usr/bin/env python3
"""
Smart Garden Manager - Automatic .env Generator

Supports:
  - Offline mode (local development)
  - Online mode with API Gateway
  - Online mode with AWS IoT Core
  - CloudFormation outputs parsing
  - Automatic certificate discovery
  - Interactive configuration wizard
  - AWS CLI validation
  - Better error handling
  - Support for multiple environments (dev, prod, test)
  - Export to different formats (env, json, yaml)
"""

import os
import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, List, Tuple, Any
import argparse

# ============================================
# CONFIGURATION
# ============================================

STACK_NAME = "smart-garden"
DEFAULT_REGION = "us-west-2"
PROJECT_ROOT = Path(__file__).parent.parent.absolute()

# Color codes for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'
    GRAY = '\033[90m'

def print_color(text: str, color: str = Colors.RESET):
    """Print colored text to terminal"""
    print(f"{color}{text}{Colors.RESET}")

# ============================================
# AWS CLI VALIDATION
# ============================================

def validate_aws_cli() -> bool:
    """
    Validate that AWS CLI is installed and configured
    
    Returns:
        True if AWS CLI is properly configured, False otherwise
    """
    try:
        # Check if AWS CLI is installed
        result = subprocess.run(
            ["aws", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode != 0:
            print_color("[ERROR] AWS CLI not installed!", Colors.RED)
            print("   Please install AWS CLI:")
            print("   https://aws.amazon.com/cli/")
            return False
        
        print_color("[OK] AWS CLI installed", Colors.GREEN)
        
        # Check if AWS is configured
        result = subprocess.run(
            ["aws", "sts", "get-caller-identity"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            print_color("[ERROR] AWS not configured!", Colors.RED)
            print("   Please configure AWS CLI:")
            print("   aws configure")
            return False
        
        # Parse account info
        try:
            identity = json.loads(result.stdout)
            account_id = identity.get('Account', 'unknown')
            arn = identity.get('Arn', 'unknown')
            print_color(f"[OK] AWS configured (Account: {account_id})", Colors.GREEN)
            print(f"   ARN: {arn}")
        except json.JSONDecodeError:
            print_color("[OK] AWS configured", Colors.GREEN)
        
        return True
        
    except subprocess.TimeoutExpired:
        print_color("[ERROR] AWS CLI timeout - check your connection", Colors.RED)
        return False
    except FileNotFoundError:
        print_color("[ERROR] AWS CLI not found in PATH", Colors.RED)
        print("   Please install AWS CLI:")
        print("   https://aws.amazon.com/cli/")
        return False
    except Exception as e:
        print_color(f"[ERROR] Error validating AWS CLI: {e}", Colors.RED)
        return False

# ============================================
# AWS CLI FUNCTIONS
# ============================================

def get_cloudformation_outputs(stack_name: str = STACK_NAME) -> Dict[str, str]:
    """
    Fetch CloudFormation stack outputs using AWS CLI
    
    Args:
        stack_name: Name of the CloudFormation stack
        
    Returns:
        Dictionary of output keys and values
    """
    try:
        result = subprocess.run(
            [
                "aws", "cloudformation", "describe-stacks",
                "--stack-name", stack_name,
                "--query", "Stacks[0].Outputs",
                "--output", "json"
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=10
        )
        
        if not result.stdout or result.stdout.strip() == "null":
            print_color(f"[WARNING] No outputs found for stack '{stack_name}'", Colors.YELLOW)
            return {}
            
        outputs = json.loads(result.stdout)
        
        # Convert to dictionary
        output_dict = {}
        for output in outputs:
            output_dict[output['OutputKey']] = output['OutputValue']
        return output_dict
        
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.strip() if e.stderr else 'Unknown error'
        if "does not exist" in error_msg:
            print_color(f"[WARNING] CloudFormation stack '{stack_name}' not found", Colors.YELLOW)
            print("   Tip: Deploy the stack first using: .\\scripts\\deploy.ps1")
        else:
            print_color(f"[WARNING] Error fetching CloudFormation outputs: {error_msg}", Colors.YELLOW)
        return {}
    except (json.JSONDecodeError, subprocess.TimeoutExpired) as e:
        print_color(f"[WARNING] Could not parse CloudFormation outputs: {e}", Colors.YELLOW)
        return {}
    except FileNotFoundError:
        print_color("[WARNING] AWS CLI not found", Colors.YELLOW)
        return {}

def get_iot_endpoint() -> Optional[str]:
    """
    Fetch AWS IoT Core endpoint using AWS CLI
    
    Returns:
        IoT endpoint address or None if not found
    """
    try:
        result = subprocess.run(
            [
                "aws", "iot", "describe-endpoint",
                "--endpoint-type", "iot:Data-ATS",
                "--query", "endpointAddress",
                "--output", "text"
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=10
        )
        endpoint = result.stdout.strip()
        if endpoint and endpoint != "None":
            return endpoint
        return None
    except subprocess.CalledProcessError:
        return None
    except Exception:
        return None

def get_account_id() -> Optional[str]:
    """
    Fetch AWS Account ID using AWS CLI
    
    Returns:
        AWS Account ID or None if not found
    """
    try:
        result = subprocess.run(
            ["aws", "sts", "get-caller-identity", "--query", "Account", "--output", "text"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10
        )
        account = result.stdout.strip()
        return account if account and account != "None" else None
    except Exception:
        return None

def get_region() -> str:
    """
    Fetch AWS region from AWS CLI configuration
    
    Returns:
        AWS region name or default region
    """
    try:
        result = subprocess.run(
            ["aws", "configure", "get", "region"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5
        )
        region = result.stdout.strip()
        return region if region else DEFAULT_REGION
    except Exception:
        return DEFAULT_REGION

def get_available_profiles() -> List[str]:
    """
    Get list of available AWS profiles
    
    Returns:
        List of profile names
    """
    try:
        result = subprocess.run(
            ["aws", "configure", "list-profiles"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5
        )
        profiles = [p.strip() for p in result.stdout.split('\n') if p.strip()]
        return profiles
    except Exception:
        return []

# ============================================
# CERTIFICATE DISCOVERY
# ============================================

def find_certificates(base_path: Path) -> Dict[str, str]:
    """
    Automatically find certificate files in common locations
    
    Args:
        base_path: Base project path to search from
        
    Returns:
        Dictionary with 'cert', 'key', 'ca' paths
    """
    # Common certificate filename patterns
    cert_patterns = [
        "*.pem.crt",
        "*-certificate.pem.crt",
        "device-certificate.pem.crt",
        "certificate.pem.crt",
        "*.crt"
    ]
    
    key_patterns = [
        "*.pem.key",
        "*-private.pem.key",
        "device-private-key.pem.key",
        "private.pem.key",
        "*.key"
    ]
    
    ca_patterns = [
        "root-CA.crt",
        "AmazonRootCA1.pem",
        "AmazonRootCA*.pem",
        "*.pem"
    ]
    
    # Common certificate directories
    cert_dirs = [
        base_path / "certs",
        base_path / "src" / "simulator" / "certs",
        base_path / "src" / "certs",
        base_path / "certificates",
        base_path / "src" / "simulator" / "certificates"
    ]
    
    found = {
        "cert": None,
        "key": None,
        "ca": None,
        "dir": None
    }
    
    for cert_dir in cert_dirs:
        if not cert_dir.exists():
            continue
        
        print_color(f"   Searching in: {cert_dir}", Colors.GRAY)
        
        # Search for certificate
        if not found["cert"]:
            for pattern in cert_patterns:
                matches = list(cert_dir.glob(pattern))
                if matches:
                    # Use the most recent file
                    found["cert"] = str(max(matches, key=lambda p: p.stat().st_mtime))
                    found["dir"] = str(cert_dir)
                    print_color(f"      Found certificate: {Path(found['cert']).name}", Colors.GRAY)
                    break
        
        # Search for private key
        if not found["key"]:
            for pattern in key_patterns:
                matches = list(cert_dir.glob(pattern))
                if matches:
                    found["key"] = str(max(matches, key=lambda p: p.stat().st_mtime))
                    print_color(f"      Found private key: {Path(found['key']).name}", Colors.GRAY)
                    break
        
        # Search for root CA
        if not found["ca"]:
            for pattern in ca_patterns:
                matches = list(cert_dir.glob(pattern))
                if matches:
                    found["ca"] = str(max(matches, key=lambda p: p.stat().st_mtime))
                    print_color(f"      Found root CA: {Path(found['ca']).name}", Colors.GRAY)
                    break
        
        # Exit if all found
        if all(found.values()):
            break
    
    return found

# ============================================
# ENV FILE GENERATION
# ============================================

def generate_env(
    mode: str = "interactive",
    use_aws: bool = True,
    use_api_gateway: bool = True,
    use_iot_core: bool = True,
    environment: str = "dev"
) -> Dict[str, str]:
    """
    Generate environment variables for .env file
    
    Args:
        mode: "interactive", "auto", "offline"
        use_aws: Use AWS CloudFormation outputs
        use_api_gateway: Configure API Gateway
        use_iot_core: Configure AWS IoT Core
        environment: Environment name (dev, prod, test)
        
    Returns:
        Dictionary of environment variables
    """
    
    # Initialize configuration
    env_vars = {
        "ENVIRONMENT": environment,
        "ENVIRONMENT_NAME": environment.upper(),
    }
    
    # ============================================
    # 1. AWS Configuration
    # ============================================
    region = get_region()
    account_id = get_account_id()
    
    if use_aws and account_id:
        print_color("[AWS] Configured", Colors.CYAN)
        print(f"   Account: {account_id}")
        print(f"   Region: {region}")
        
        env_vars["AWS_REGION"] = region
        env_vars["AWS_ACCOUNT_ID"] = account_id
        
        # Fetch CloudFormation outputs
        cf_outputs = get_cloudformation_outputs(STACK_NAME)
        
        if cf_outputs:
            print_color(f"[CloudFormation] Loaded {len(cf_outputs)} outputs", Colors.GREEN)
            
            # IoT Core configuration
            if use_iot_core:
                iot_endpoint = cf_outputs.get("IoTEndpoint") or get_iot_endpoint()
                if iot_endpoint:
                    env_vars["AWS_IOT_ENDPOINT"] = iot_endpoint
                    env_vars["IOT_THING_NAME"] = cf_outputs.get("IoTThingName", "smart-garden-sensor")
                    print_color(f"   IoT Endpoint: {iot_endpoint}", Colors.GRAY)
            
            # API Gateway configuration
            if use_api_gateway:
                api_url = cf_outputs.get("APIGatewayURL")
                if api_url:
                    env_vars["API_URL"] = api_url
                    print_color(f"   API Gateway: {api_url}", Colors.GRAY)
            
            # DynamoDB configuration
            latest_table = cf_outputs.get("LatestTableName")
            history_table = cf_outputs.get("HistoryTableName")
            if latest_table:
                env_vars["LATEST_TABLE"] = latest_table
            if history_table:
                env_vars["HISTORY_TABLE"] = history_table
            
            # S3 configuration
            s3_data = cf_outputs.get("S3DataBucket")
            s3_website = cf_outputs.get("S3WebsiteBucket")
            if s3_data:
                env_vars["S3_DATA_BUCKET"] = s3_data
            if s3_website:
                env_vars["S3_WEBSITE_BUCKET"] = s3_website
            
            # SNS configuration
            sns_arn = cf_outputs.get("SNSTopicARN")
            if sns_arn:
                env_vars["SNS_TOPIC_ARN"] = sns_arn
            
            # CloudFront
            cloudfront_url = cf_outputs.get("CloudFrontURL")
            if cloudfront_url:
                env_vars["CLOUDFRONT_URL"] = cloudfront_url
            
        else:
            # Fallback: Manual input in interactive mode
            if mode == "interactive":
                print_color("[WARNING] CloudFormation stack not found. Please enter manually:", Colors.YELLOW)
                
                if use_iot_core:
                    endpoint = input("  IoT Endpoint (e.g., a1b2c3d4e5f6-ats.iot.region.amazonaws.com): ")
                    if endpoint:
                        env_vars["AWS_IOT_ENDPOINT"] = endpoint
                
                if use_api_gateway:
                    api = input("  API Gateway URL (e.g., https://xxx.execute-api.region.amazonaws.com/prod/data): ")
                    if api:
                        env_vars["API_URL"] = api
            
            # Try to get IoT endpoint separately
            if use_iot_core and not env_vars.get("AWS_IOT_ENDPOINT"):
                iot_endpoint = get_iot_endpoint()
                if iot_endpoint:
                    env_vars["AWS_IOT_ENDPOINT"] = iot_endpoint
                    print_color(f"   Auto-discovered IoT Endpoint: {iot_endpoint}", Colors.GRAY)
    
    # ============================================
    # 2. Sensor Configuration
    # ============================================
    env_vars.update({
        "SENSOR_ID": os.getenv("SENSOR_ID", "sensor-001"),
        "SENSOR_LOCATION": os.getenv("SENSOR_LOCATION", "indoor"),
        "SENSOR_INTERVAL": os.getenv("SENSOR_INTERVAL", "5"),
        "AWS_IOT_TOPIC": os.getenv("AWS_IOT_TOPIC", "sensor/data"),
    })
    
    # ============================================
    # 3. Certificate Discovery
    # ============================================
    print_color("\n[Certificates] Searching for certificates...", Colors.CYAN)
    certs = find_certificates(PROJECT_ROOT)
    
    if certs["cert"] and certs["key"] and certs["ca"]:
        print_color("[Certificates] Found certificates:", Colors.GREEN)
        print(f"   Certificate: {Path(certs['cert']).name}")
        print(f"   Private Key: {Path(certs['key']).name}")
        print(f"   Root CA: {Path(certs['ca']).name}")
        print(f"   Directory: {certs['dir']}")
        
        # Use absolute paths for better compatibility
        env_vars["CERT_PATH"] = str(Path(certs["cert"]).absolute())
        env_vars["PRIVATE_KEY_PATH"] = str(Path(certs["key"]).absolute())
        env_vars["ROOT_CA_PATH"] = str(Path(certs["ca"]).absolute())
        env_vars["CERT_DIR"] = str(Path(certs["dir"]).absolute())
    else:
        print_color("[WARNING] Not all certificates found. Using default paths.", Colors.YELLOW)
        if not certs["cert"]:
            print_color("   Missing: Device certificate", Colors.RED)
        if not certs["key"]:
            print_color("   Missing: Private key", Colors.RED)
        if not certs["ca"]:
            print_color("   Missing: Root CA certificate", Colors.RED)
        
        # Use relative paths as fallback
        env_vars.update({
            "CERT_PATH": "./src/simulator/certs/device-certificate.pem.crt",
            "PRIVATE_KEY_PATH": "./src/simulator/certs/device-private-key.pem.key",
            "ROOT_CA_PATH": "./src/simulator/certs/root-CA.crt",
        })
    
    # ============================================
    # 4. Logging & Debug
    # ============================================
    env_vars.update({
        "LOG_LEVEL": os.getenv("LOG_LEVEL", "INFO"),
        "DEBUG": os.getenv("DEBUG", "false").lower(),
        "USE_WEBSOCKET": os.getenv("USE_WEBSOCKET", "false").lower(),
    })
    
    # ============================================
    # 5. Offline Mode
    # ============================================
    if mode == "offline" or not use_aws:
        env_vars["USE_MOCK_DATA"] = "true"
        env_vars["OFFLINE_MODE"] = "true"
        # Local API for offline testing
        env_vars["API_URL"] = env_vars.get("API_URL", "http://localhost:5000/prod/query")
    
    # ============================================
    # 6. Additional Features
    # ============================================
    
    # Add timestamp
    env_vars["ENV_GENERATED_AT"] = datetime.now().isoformat()
    
    # Add project root
    env_vars["PROJECT_ROOT"] = str(PROJECT_ROOT.absolute())
    
    return env_vars

# ============================================
# WRITE ENV FILE
# ============================================

def write_env_file(env_vars: Dict[str, str], path: Path = None, format_type: str = "env") -> Path:
    """
    Write environment variables to file in different formats
    
    Args:
        env_vars: Dictionary of environment variables
        path: Output path (default: PROJECT_ROOT/.env)
        format_type: Output format ("env", "json", "yaml")
        
    Returns:
        Path to the created file
    """
    
    if path is None:
        if format_type == "env":
            path = PROJECT_ROOT / ".env"
        elif format_type == "json":
            path = PROJECT_ROOT / ".env.json"
        elif format_type == "yaml":
            path = PROJECT_ROOT / ".env.yaml"
        else:
            path = PROJECT_ROOT / ".env"
    
    # Determine mode
    mode = "ONLINE" if env_vars.get("AWS_IOT_ENDPOINT") else "OFFLINE"
    
    if format_type == "env":
        # ENV format (default)
        content = """# ============================================
# SMART GARDEN MANAGER - ENVIRONMENT VARIABLES
# ============================================
# Generated: {timestamp}
# Mode: {mode}
# Environment: {environment}
# ============================================

""".format(
    timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    mode=mode,
    environment=env_vars.get("ENVIRONMENT", "dev")
)
        
        # Categorized sections
        categories = {
            "AWS IoT Core": ["AWS_IOT_ENDPOINT", "AWS_IOT_TOPIC", "IOT_THING_NAME", "USE_WEBSOCKET"],
            "API Gateway": ["API_URL"],
            "DynamoDB": ["LATEST_TABLE", "HISTORY_TABLE"],
            "S3": ["S3_DATA_BUCKET", "S3_WEBSITE_BUCKET"],
            "SNS": ["SNS_TOPIC_ARN"],
            "Sensor": ["SENSOR_ID", "SENSOR_LOCATION", "SENSOR_INTERVAL"],
            "Certificates": ["CERT_PATH", "PRIVATE_KEY_PATH", "ROOT_CA_PATH", "CERT_DIR"],
            "Logging": ["LOG_LEVEL", "DEBUG"],
            "Development": ["USE_MOCK_DATA", "OFFLINE_MODE"],
            "System": ["ENVIRONMENT", "AWS_REGION", "AWS_ACCOUNT_ID", "PROJECT_ROOT"]
        }
        
        for category, keys in categories.items():
            # Check if any values exist
            has_values = any(key in env_vars and env_vars[key] for key in keys)
            if not has_values:
                continue
            
            content += f"\n# {category}\n"
            for key in keys:
                value = env_vars.get(key, "")
                if value:
                    content += f"{key}={value}\n"
        
        # Help section
        content += """

# ============================================
# QUICK START GUIDE
# ============================================
# OFFLINE TESTING:
#    python src/simulator/sensor_simulator.py --offline
#
# ONLINE with AWS IoT Core:
#    python src/simulator/sensor_simulator.py --env
#
# ONLINE with WebSocket (Port 443):
#    python src/simulator/sensor_simulator.py --env --websocket
#
# Dashboard with local API:
#    python src/simulator/mock_api.py
#    (Dashboard uses localhost:5000/prod/query)
#
# Deploy to AWS:
#    .\\scripts\\deploy.ps1
# ============================================
"""
        
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
    
    elif format_type == "json":
        # JSON format
        import json
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(env_vars, f, indent=2, default=str)
    
    elif format_type == "yaml":
        # YAML format (requires pyyaml)
        try:
            import yaml
            with open(path, 'w', encoding='utf-8') as f:
                yaml.dump(env_vars, f, default_flow_style=False)
        except ImportError:
            print_color("[WARNING] PyYAML not installed. Install with: pip install pyyaml", Colors.YELLOW)
            # Fallback to env format
            return write_env_file(env_vars, path.with_suffix('.env'), "env")
    
    return path

# ============================================
# INTERACTIVE SETUP
# ============================================

def interactive_setup():
    """Interactive setup wizard"""
    print_color("=" * 60, Colors.CYAN)
    print_color("Smart Garden - .env Setup Wizard", Colors.BOLD)
    print_color("=" * 60, Colors.CYAN)
    print()
    
    # Validate AWS CLI first
    if not validate_aws_cli():
        print_color("\n[ERROR] AWS CLI validation failed!", Colors.RED)
        print("   Please fix the issues above and try again.")
        return
    
    # Show available AWS profiles
    profiles = get_available_profiles()
    if profiles:
        print_color(f"Available AWS profiles: {', '.join(profiles)}", Colors.GRAY)
        print()
    
    # Environment selection
    print("Select environment:")
    print("  1. Development (dev)")
    print("  2. Production (prod)")
    print("  3. Testing (test)")
    print()
    
    env_choice = input("Your choice (1-3): ").strip()
    env_map = {"1": "dev", "2": "prod", "3": "test"}
    environment = env_map.get(env_choice, "dev")
    print_color(f"Environment: {environment}", Colors.CYAN)
    print()
    
    # Mode selection
    print("Select mode:")
    print("  1. Online (AWS IoT Core + API Gateway) - Production")
    print("  2. Online (API Gateway only) - No IoT Core")
    print("  3. Offline (local development) - No AWS")
    print()
    
    choice = input("Your choice (1-3): ").strip()
    
    if choice == "1":
        mode = "online_full"
        use_aws = True
        use_api_gateway = True
        use_iot_core = True
    elif choice == "2":
        mode = "online_api"
        use_aws = True
        use_api_gateway = True
        use_iot_core = False
    elif choice == "3":
        mode = "offline"
        use_aws = False
        use_api_gateway = False
        use_iot_core = False
    else:
        print_color("[ERROR] Invalid choice. Using online mode.", Colors.RED)
        mode = "online_full"
        use_aws = True
        use_api_gateway = True
        use_iot_core = True
    
    print()
    print_color(f"Mode: {mode}", Colors.CYAN)
    print_color(f"Environment: {environment}", Colors.CYAN)
    print()
    
    # Output format selection
    print("Output format:")
    print("  1. .env (default)")
    print("  2. JSON (.env.json)")
    print("  3. YAML (.env.yaml)")
    print()
    
    format_choice = input("Your choice (1-3): ").strip()
    format_map = {"1": "env", "2": "json", "3": "yaml"}
    output_format = format_map.get(format_choice, "env")
    
    # Generate
    env_vars = generate_env(
        mode=mode,
        use_aws=use_aws,
        use_api_gateway=use_api_gateway,
        use_iot_core=use_iot_core,
        environment=environment
    )
    
    # Write .env
    env_path = write_env_file(env_vars, format_type=output_format)
    
    print()
    print_color("=" * 60, Colors.GREEN)
    print_color("[SUCCESS] .env file successfully generated!", Colors.GREEN)
    print_color("=" * 60, Colors.GREEN)
    print_color(f"Path: {env_path}", Colors.CYAN)
    print_color(f"Format: {output_format.upper()}", Colors.CYAN)
    print()
    print_color("Included variables:", Colors.YELLOW)
    
    # Show important variables
    important_keys = ["ENVIRONMENT", "AWS_REGION", "AWS_IOT_ENDPOINT", "API_URL", "SENSOR_ID"]
    for key in important_keys:
        value = env_vars.get(key, "")
        if value:
            print(f"   {key}={value}")
    print()
    
    print_color("Next Steps:", Colors.YELLOW)
    print("   Online Simulator: python src/simulator/sensor_simulator.py --env")
    print("   Offline Simulator: python src/simulator/sensor_simulator.py --offline")
    print("   Dashboard: start src/dashboard/index.html")
    print("   Deploy: .\\scripts\\deploy.ps1")
    print_color("=" * 60, Colors.GREEN)

# ============================================
# EXPORT FUNCTIONS
# ============================================

def export_to_env(env_vars: Dict[str, str], path: Path = None):
    """Export environment variables to shell script format"""
    if path is None:
        path = PROJECT_ROOT / "export_env.sh"
    
    content = "#!/bin/bash\n"
    content += "# Export Smart Garden environment variables\n"
    content += f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    
    for key, value in env_vars.items():
        if value:
            content += f"export {key}=\"{value}\"\n"
    
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    # Make executable on Unix-like systems
    try:
        os.chmod(path, 0o755)
    except Exception:
        pass
    
    return path

# ============================================
# MAIN
# ============================================

def main():
    """Main entry point"""
    
    parser = argparse.ArgumentParser(
        description="Smart Garden - Automatic .env Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode (recommended)
  python generate_env.py --interactive
  
  # Generate for online mode
  python generate_env.py --online
  
  # Generate for offline mode
  python generate_env.py --offline
  
  # Generate for production environment
  python generate_env.py --online --environment prod
  
  # Export as JSON
  python generate_env.py --online --format json
  
  # Validate AWS CLI only
  python generate_env.py --validate
        """
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Generate .env for offline mode (local development)"
    )
    parser.add_argument(
        "--online",
        action="store_true",
        help="Generate .env for online mode (AWS IoT Core + API Gateway)"
    )
    parser.add_argument(
        "--api-only",
        action="store_true",
        help="Generate .env for API Gateway only (no IoT Core)"
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        default=False,
        help="Interactive mode (recommended)"
    )
    parser.add_argument(
        "--environment",
        type=str,
        choices=["dev", "prod", "test"],
        default="dev",
        help="Environment name (dev, prod, test)"
    )
    parser.add_argument(
        "--format",
        type=str,
        choices=["env", "json", "yaml"],
        default="env",
        help="Output format (env, json, yaml)"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output path for .env file"
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate AWS CLI configuration and exit"
    )
    parser.add_argument(
        "--export-shell",
        action="store_true",
        help="Also generate shell script (export_env.sh)"
    )
    
    args = parser.parse_args()
    
    # Validate mode
    if args.validate:
        if validate_aws_cli():
            print_color("\n[OK] AWS CLI validation passed!", Colors.GREEN)
            sys.exit(0)
        else:
            sys.exit(1)
    
    # Interactive mode
    if args.interactive or (not any([args.offline, args.online, args.api_only])):
        interactive_setup()
        return
    
    # Non-interactive mode
    if args.offline:
        mode = "offline"
        use_aws = False
        use_api_gateway = False
        use_iot_core = False
    elif args.api_only:
        mode = "online_api"
        use_aws = True
        use_api_gateway = True
        use_iot_core = False
    else:  # online
        mode = "online_full"
        use_aws = True
        use_api_gateway = True
        use_iot_core = True
    
    print_color(f"Generating .env in mode: {mode}", Colors.CYAN)
    print_color(f"Environment: {args.environment}", Colors.CYAN)
    print()
    
    # Validate AWS CLI if using AWS
    if use_aws:
        if not validate_aws_cli():
            print_color("[ERROR] AWS validation failed. Using offline mode.", Colors.RED)
            use_aws = False
            mode = "offline"
    
    env_vars = generate_env(
        mode=mode,
        use_aws=use_aws,
        use_api_gateway=use_api_gateway,
        use_iot_core=use_iot_core,
        environment=args.environment
    )
    
    output_path = Path(args.output) if args.output else None
    env_path = write_env_file(env_vars, output_path, args.format)
    
    print_color("\n[OK] .env file generated!", Colors.GREEN)
    print_color(f"Path: {env_path}", Colors.CYAN)
    print_color(f"Format: {args.format.upper()}", Colors.CYAN)
    
    # Export shell script if requested
    if args.export_shell:
        shell_path = export_to_env(env_vars)
        print_color(f"Shell script: {shell_path}", Colors.CYAN)
    
    print()
    print_color("Next Steps:", Colors.YELLOW)
    print("   Simulator: python src/simulator/sensor_simulator.py --env")
    print("   Dashboard: start src/dashboard/index.html")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_color("\n\n[WARNING] Cancelled by user", Colors.YELLOW)
        sys.exit(0)
    except Exception as e:
        print_color(f"\n[ERROR] {e}", Colors.RED)
        import traceback
        traceback.print_exc()
        sys.exit(1)