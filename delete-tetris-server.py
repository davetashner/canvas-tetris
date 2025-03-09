import boto3
import argparse
import time

# AWS Configuration
REGION = "us-east-1"
SECURITY_GROUP_NAME = "tetris-sg"
HOSTED_ZONE_ID = "Z2ONH2Z46JHXWL"  # Route 53 hosted zone

# Domain Configuration
DOMAIN_NAME = "davetashner.com"

# Parse Command-Line Arguments
parser = argparse.ArgumentParser(description="Delete Tetris server resources from AWS.")
parser.add_argument("--dns", type=str, default="tetris",
                    help="Subdomain of the Tetris server to delete (default: tetris.yourdomain.com)")
args = parser.parse_args()
DNS_NAME = f"{args.dns}.{DOMAIN_NAME}"

# Initialize AWS Clients
ec2 = boto3.client("ec2", region_name=REGION)
iam = boto3.client("iam")
route53 = boto3.client("route53")

def find_instance():
    """Find the Tetris EC2 instance by tag."""
    print("Searching for the Tetris server instance...")
    instances = ec2.describe_instances(Filters=[{"Name": "tag:Name", "Values": ["TetrisServer"]}])

    for reservation in instances["Reservations"]:
        for instance in reservation["Instances"]:
            if instance["State"]["Name"] not in ["terminated", "shutting-down"]:
                print(f"Found Tetris server: {instance['InstanceId']}")
                return instance

    print("No active Tetris server instance found.")
    return None

def terminate_instance(instance_id):
    """Terminate the EC2 instance and wait for it to shut down."""
    print(f"Terminating EC2 instance: {instance_id}...")
    ec2.terminate_instances(InstanceIds=[instance_id])
    ec2.get_waiter("instance_terminated").wait(InstanceIds=[instance_id])
    print("Instance terminated.")

def delete_security_group():
    """Delete the security group after waiting for dependencies to be released."""
    try:
        print(f"Waiting for security group '{SECURITY_GROUP_NAME}' to be deletable...")
        time.sleep(10)  # Allow AWS time to release dependencies
        print(f"Deleting security group: {SECURITY_GROUP_NAME}...")
        sg = ec2.describe_security_groups(GroupNames=[SECURITY_GROUP_NAME])["SecurityGroups"][0]
        ec2.delete_security_group(GroupId=sg["GroupId"])
        print("Security group deleted.")
    except Exception as e:
        print(f"Security group not found or already deleted: {e}")

def remove_route53_dns():
    """Remove the Route 53 DNS record."""
    print(f"Removing Route 53 DNS record: {DNS_NAME}...")

    try:
        response = route53.list_resource_record_sets(HostedZoneId=HOSTED_ZONE_ID)
        record_to_delete = next((record for record in response["ResourceRecordSets"]
                                 if record["Name"] == f"{DNS_NAME}." and record["Type"] == "A"), None)

        if not record_to_delete:
            print(f"DNS record {DNS_NAME} not found, skipping deletion.")
            return

        delete_batch = {
            "Comment": "Deleting Tetris Server DNS record",
            "Changes": [{
                "Action": "DELETE",
                "ResourceRecordSet": record_to_delete
            }]
        }

        route53.change_resource_record_sets(HostedZoneId=HOSTED_ZONE_ID, ChangeBatch=delete_batch)
        print(f"Successfully deleted DNS record {DNS_NAME}")

    except Exception as e:
        print(f"Error deleting DNS record: {e}")

def main():
    """Main cleanup function."""
    instance = find_instance()

    if instance:
        instance_id = instance["InstanceId"]

        # Terminate the EC2 instance
        terminate_instance(instance_id)

    # Remove all other AWS resources
    delete_security_group()
    remove_route53_dns()

    print("Cleanup complete!")

if __name__ == "__main__":
    main()