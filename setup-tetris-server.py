import argparse
import boto3
import dns.resolver
import json
import requests
import sys
import time

# AWS Configuration
HOSTED_ZONE_ID = "ZYTTV7P0U19Z3V"
IAM_POLICY_NAME = "TetrisS3ReadOnlyPolicy"
IAM_ROLE_NAME = "TetrisServerRole"
INSTANCE_PROFILE_NAME = "TetrisInstanceProfile"
INSTANCE_TYPE = "m5.large"
KEY_NAME = "minecraft-key"
REGION = "us-east-1"
SECURITY_GROUP_NAME = "tetris-sg"
TETRIS_PORT = 80

# Domain/DNS Configuration
DOMAIN_NAME = "yourdomain.com"

# Parse Command-Line Arguments
parser = argparse.ArgumentParser(description="Setup a Tetris server on AWS.")
parser.add_argument("--dns", type=str, default="tetris",
                    help="Subdomain to use for the Tetris server (default: tetris.{DOMAIN_NAME})")
parser.add_argument("--test-dns", action="store_true",
                    help="Run only the DNS health check")
args = parser.parse_args()

DNS_NAME = f"{args.dns}.{DOMAIN_NAME}]"

# Initialize AWS Clients
ec2 = boto3.client("ec2", region_name=REGION)
route53 = boto3.client("route53")
iam = boto3.client("iam")

def get_latest_ami():
    """Fetch the latest Ubuntu AMI ID dynamically."""
    print("Fetching latest Ubuntu AMI...")
    amis = ec2.describe_images(
        Owners=["099720109477"],
        Filters=[{"Name": "name", "Values": ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]},
                 {"Name": "state", "Values": ["available"]}]
    )
    latest_ami = sorted(amis["Images"], key=lambda x: x["CreationDate"], reverse=True)[0]["ImageId"]
    print(f"Using latest Ubuntu AMI: {latest_ami}")
    return latest_ami

def ensure_security_group():
    """Ensure the security group exists."""
    try:
        sg = ec2.describe_security_groups(GroupNames=[SECURITY_GROUP_NAME])["SecurityGroups"][0]
        print(f"Using existing security group: {sg['GroupId']}")
        return sg["GroupId"]
    except:
        print(f"Creating security group: {SECURITY_GROUP_NAME}")
        sg = ec2.create_security_group(
            GroupName=SECURITY_GROUP_NAME,
            Description="Tetris Server SG"
        )
        security_group_id = sg["GroupId"]

        ec2.authorize_security_group_ingress(GroupId=security_group_id, IpPermissions=[
            {"IpProtocol": "tcp", "FromPort": 80, "ToPort": 80, "IpRanges": [{"CidrIp": "0.0.0.0/0"}]},
            {"IpProtocol": "tcp", "FromPort": 443, "ToPort": 443, "IpRanges": [{"CidrIp": "0.0.0.0/0"}]}

        ])
        print(f"Security group {SECURITY_GROUP_NAME} configured.")
        return security_group_id

def launch_instance(ami_id, security_group_id):
    """Launch the EC2 instance with user data."""
    print("Launching EC2 instance...")

    user_data_script = f"""#!/bin/bash
set -e
apt update && apt install -y curl git jq nginx unzip wget certbot python3-certbot-nginx

# Clone the Tetris repository
mkdir -p /var/www/html/tetris
git clone https://github.com/davetashner/canvas-tetris.git /var/www/html/tetris

# Configure Nginx to serve Tetris
cat > /etc/nginx/sites-available/tetris <<EOF
server {{
    listen 80;
    server_name {DNS_NAME};

    root /var/www/html/tetris;
    index index.html;

    location / {{
        try_files \\$uri \\$uri/ /index.html;
    }}
}}
EOF

# Enable the Tetris site
cp /etc/nginx/sites-available/tetris /etc/nginx/sites-enabled/tetris
mv /etc/nginx/sites-available/default /etc/nginx/sites-available/default.bak
rm -f /etc/nginx/sites-enabled/default
systemctl restart nginx

# Wait for DNS propagation (ensures Let's Encrypt can verify the domain)
until dig +short {DNS_NAME} | grep -q .; do
    echo "Waiting for DNS propagation..."
    sleep 10
done

# Request SSL certificate from Let's Encrypt
certbot --nginx -n --agree-tos --email admin@{DNS_NAME} -d {DNS_NAME} --redirect

# Enable auto-renewal for SSL certificate
echo "0 0 * * 1 root certbot renew --quiet && systemctl reload nginx" | tee -a /etc/crontab > /dev/null

echo "Tetris is now available at https://{DNS_NAME}"
"""

    instance = ec2.run_instances(
        ImageId=ami_id,
        InstanceType=INSTANCE_TYPE,
        KeyName=KEY_NAME,
        MaxCount=1,
        MinCount=1,
        SecurityGroupIds=[security_group_id],
        TagSpecifications=[{
            "ResourceType": "instance",
            "Tags": [{"Key": "Name", "Value": "TetrisServer"}]
        }],
        UserData=user_data_script 
    )

    instance_id = instance["Instances"][0]["InstanceId"]
    print(f"EC2 Instance launched with ID: {instance_id}")

    print("Waiting for instance to get a public IP...")
    ec2.get_waiter("instance_running").wait(InstanceIds=[instance_id])

    instance_description = ec2.describe_instances(InstanceIds=[instance_id])
    public_ip = instance_description["Reservations"][0]["Instances"][0].get("PublicIpAddress", "N/A")

    print(f"EC2 Instance Public IP: {public_ip}")
    return instance_id, public_ip

def update_route53_dns(public_ip):
    """Update Route 53 DNS record to point to the EC2 instance's public IP."""
    print(f"Updating Route 53 DNS record: {DNS_NAME} -> {public_ip}")

    change_batch = {
        "Comment": "Updating Tetris server DNS record",
        "Changes": [{
            "Action": "UPSERT",
            "ResourceRecordSet": {
                "Name": DNS_NAME,
                "Type": "A",
                "TTL": 300,
                "ResourceRecords": [{"Value": public_ip}]
            }
        }]
    }

    try:
        response = route53.change_resource_record_sets(
            HostedZoneId=HOSTED_ZONE_ID,
            ChangeBatch=change_batch
        )
        print(f"Route 53 DNS updated successfully: {DNS_NAME} -> {public_ip}")
    except Exception as e:
        print(f"Error updating Route 53 DNS: {e}")

def resolve_dns_name(dns_name):
    """Resolve DNS using authoritative servers (like dig) instead of system cache."""
    try:
        resolver = dns.resolver.Resolver()
        resolver.nameservers = ["8.8.8.8", "8.8.4.4"]  # Google DNS (bypasses local cache)
        answers = resolver.resolve(dns_name, "A")  # Query for IPv4 address
        ip_address = answers[0].to_text()
        print(f"✅ DNS resolved: {dns_name} -> {ip_address}")
        return ip_address
    except dns.resolver.NXDOMAIN:
        print(f"❌ DNS name does not exist: {dns_name}")
    except dns.resolver.NoAnswer:
        print(f"⚠️ No DNS answer received for: {dns_name}")
    except dns.resolver.LifetimeTimeout:
        print(f"⏳ DNS query timed out for: {dns_name}")
    return None

def wait_for_dns_health_check():
    """Check if the Tetris server is responding at its DNS name until it is reachable or times out after 5 minutes."""
    url_https = f"https://{DNS_NAME}"
    url_http = f"http://{DNS_NAME}"

    print(f"🔍 Waiting for DNS resolution of {DNS_NAME}...")

    timeout = 300  # 5 minutes
    interval = 5  # Check DNS every 5 seconds
    elapsed_time = 0
    resolved_ip = None

    # Keep checking DNS resolution until successful or timeout
    while elapsed_time < timeout:
        resolved_ip = resolve_dns_name(DNS_NAME)
        if resolved_ip:
            break  # Stop looping when we get an IP

        print(f"⚠️ DNS not resolved yet. Retrying in {interval} seconds...")
        time.sleep(interval)
        elapsed_time += interval

    if not resolved_ip:
        print(f"❌ Timeout: DNS did not resolve within {timeout//60} minutes.")
        return

    # Now check for HTTP/HTTPS availability
    print("\n⏳ Waiting 30 seconds for Nginx startup and Let's Encrypt...")
    for remaining in range(30, 0, -1):
        sys.stdout.write(f"\r⏳ {remaining} seconds remaining... ")
        sys.stdout.flush()
        time.sleep(1)
    print("\n✅ Done! Continuing...")

    elapsed_time = 0
    response_http = None
    while elapsed_time < timeout:
        try:
            # First, check HTTP (faster and avoids SSL issues)
            response_http = requests.get(url_http, timeout=5, allow_redirects=True)
            if response_http.status_code in [200, 301, 302]:
                print(f"✅ HTTP available: {DNS_NAME} (Status: {response_http.status_code})")
                if response_http.status_code == 301:
                    print(f"🔄 Redirecting to HTTPS...")

            # Check HTTPS with SSL verification first
            try:
                response_https = requests.get(url_https, timeout=5, verify=True, allow_redirects=True)
            except requests.exceptions.SSLError:
                print(f"⚠️ SSL verification failed, retrying with unverified HTTPS...")
                response_https = requests.get(url_https, timeout=5, verify=False, allow_redirects=True)

            if response_https.status_code in [200, 301, 302]:
                print(f"✅ Success: {DNS_NAME} is reachable over HTTPS!")
                return
            
            print(f"⚠️ Unexpected Response {response_https.status_code}: Retrying in {interval} seconds...")

        except requests.exceptions.ConnectionError:
            if response_http and response_http.status_code in [200, 301, 302]:
                print(f"⚠️ HTTPS is not available yet, but HTTP is working. Retrying HTTPS check in {interval} seconds...")
            else:
                print(f"❌ {DNS_NAME} is not reachable yet. Retrying in {interval} seconds...")

        except Exception as e:
            print(f"⚠️ Unexpected Error: {e}")

        time.sleep(interval)
        elapsed_time += interval

    print(f"⚠️ Timeout: {DNS_NAME} did not become reachable within {timeout//60} minutes.")

# Capture the start time at the beginning of execution
start_time = time.time()

def main():
    """Main setup function."""
    ami_id = get_latest_ami()
    security_group_id = ensure_security_group()

    print("Starting EC2 instance...")
    instance_id, public_ip = launch_instance(ami_id, security_group_id)

    print(f"Mapping {DNS_NAME} to {public_ip} in Route 53...")
    update_route53_dns(public_ip)
    
    print(f"Waiting for {DNS_NAME} to be reachable...")
    wait_for_dns_health_check()


    print(f"Tetris server running at: {DNS_NAME}")
    print(f"Instance ID: {instance_id}")
    print(f"Public IP Address: {public_ip}")

    return instance_id, public_ip

if __name__ == "__main__":
    if args.test_dns:
        print(f"🔍 Testing DNS health check for {DNS_NAME}...")
        wait_for_dns_health_check()
    else:
        # Start time should only be recorded when main() runs
        start_time = time.time()
        instance_id, public_ip = main()

        # Calculate total elapsed time and display
        elapsed_time = time.time() - start_time
        print(f"\n⏱️ Total elapsed time: {elapsed_time:.2f} seconds")